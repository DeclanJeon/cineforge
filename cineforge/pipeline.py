"""오케스트레이션 상태 기계 — 단계 실행, 게이트, 권한, 인계(handoff), 진행 상태 저장."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from cineforge import __version__, assets, qa
from cineforge.concept import build_concept
from cineforge.data_loader import load
from cineforge.intake import analyze
from cineforge.planner import build_payload, generate_plan
from cineforge.progress import rates
from cineforge.project_skills import LOCK, LOCK_HASH, MODE, binding_hash, initial_binding, lock_text, require_pack
from cineforge.skill_handoff import CRAFT_STAGES, check_handoff_identity, craft_facts, legacy_guidance, pack_fields
from cineforge.skill_pack_manifest import SkillPackError
from cineforge.providers.base import AgentInputRequired, ProviderError
from cineforge.providers.router import ProviderRouter, build_router
from cineforge.render import plan_markdown
from cineforge.schemas import validate
from cineforge.selection import fill_required, merge, new_selection, validate as validate_selection
from cineforge.ssot import SSOT_TYPES, SSOTStore, build_all, impact, now
from cineforge.taxonomy import Taxonomy

EXTERNAL_STAGES = {"S08_generation", "S09_edit", "S10_qa", "S11_delivery"}
IMPACT_TO_STAGE = {"plan": "S03_plan", "story": "S04_story", "concept": "S04_story", "character": "S05_character_world",
                   "world": "S05_character_world", "scene": "S06_storyboard", "camera": "S06_storyboard", "motion": "S06_storyboard",
                   "audio": "S07_assets", "assets/image_prompts": "S07_assets", "assets/video_prompts": "S07_assets",
                   "assets/frames": "S07_assets", "assets/sound_cue_sheet": "S07_assets"}
DEFAULT_AUTHORITY = {"accept_plan": False, "accept_preproduction": False, "execution": False, "edit": False, "publish": False,
                     "image_limit": None, "providers": None, "execution_until": None, "spend_ceiling": None, "granted_by": "user", "granted_at": None, "notes": []}


class InvalidProjectIdError(ValueError):
    """A new project requires a folder-safe project ID."""


from .receipts import atomic_text, pins


class InvalidCutRevisionError(ValueError):
    """A cut revision requires both a scope and a preservation constraint."""


class Project:
    def __init__(self, root: Path, router: ProviderRouter | None = None, tax: Taxonomy | None = None) -> None:
        self.root = Path(root)
        self.tax = tax or Taxonomy()
        self.pipeline = load("pipeline.yaml")
        meta = self.read("project.json") or {}
        self.router = router or build_router(meta.get("provider_mode", "auto"), io_dir=self.root / "agent_io")
        self.store = SSOTStore(self.root)

    # ---------- 파일 I/O ----------
    def read(self, rel: str) -> Any:
        p = self.root / rel
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None

    def write(self, rel: str, data: Any, schema: str | None = None) -> Path:
        if schema:
            errors = validate(data, schema)
            if errors:
                raise ValueError(f"{rel} 스키마 오류: {errors[:5]}")
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2)
        atomic_text(p, text)
        return p

    def log(self, event: str, **fields: Any) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "history.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": now(), "event": event, **fields}, ensure_ascii=False) + "\n")

    # ---------- 생성 ----------
    @classmethod
    def create(cls, parent: Path, request: str, provider_mode: str = "auto", project_id: str | None = None,
               router: ProviderRouter | None = None, inputs: dict[str, Any] | None = None, *,
               cut_revision: tuple[str, str] | None = None) -> "Project":
        if cut_revision is not None:
            scope, preserve = (value.strip() for value in cut_revision)
            if not scope or not preserve:
                raise InvalidCutRevisionError("수정 범위와 보존 조건이 모두 필요합니다.")
            cut_revision = (scope, preserve)
        if not project_id or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", project_id):
            raise InvalidProjectIdError("프로젝트명은 영문 소문자·숫자 단어를 하이픈으로 연결하세요 (예: cineforge-demo).")
        pid = project_id
        root = Path(parent) / pid
        if (root / "project.json").exists():
            raise FileExistsError(f"이미 있는 프로젝트: {root}")
        binding = initial_binding(provider_mode)
        root.mkdir(parents=True, exist_ok=True)
        tax = Taxonomy()
        meta = {"project_id": pid, "created_at": now(), "request": request, "provider_mode": provider_mode,
                "taxonomy_version": tax.version, "cineforge_version": __version__, "inputs": inputs or {}}
        if cut_revision is not None:
            scope, preserve = cut_revision
            meta["cut_revision"] = {"scope": scope, "preserve": preserve}
        meta[MODE] = "bound" if binding is not None else "mock"
        if binding is not None:
            pinned = lock_text(binding)
            atomic_text(root / LOCK, pinned)
            meta[LOCK_HASH] = binding_hash(pinned)
        atomic_text(root / "project.json", json.dumps(meta, ensure_ascii=False, indent=2))
        project = cls(root, router=router or build_router(provider_mode, io_dir=root / "agent_io"), tax=tax)
        project.write("authority.json", dict(DEFAULT_AUTHORITY), "authority")
        project.write("progress.json", project._initial_progress(), "progress")
        project.log("project_created", request=request, provider_mode=provider_mode)
        return project

    @property
    def meta(self) -> dict[str, Any]:
        return self.read("project.json")

    def _initial_progress(self) -> dict[str, Any]:
        stages = {s["id"]: {"status": "pending", "tasks": {t: "pending" for t in s["tasks"]}, "qa": None, "started_at": None,
                            "finished_at": None, "note": None, "provider": None, "evidence": []} for s in self.pipeline["stages"]}
        stages["S12_feedback"]["status"] = "skipped"
        stages["S12_feedback"]["note"] = "성과 피드백(L6)은 로드맵 6단계 — 현재 설계만"
        return {"project_id": self.root.name, "updated_at": now(), "current_stage": self.pipeline["stages"][0]["id"],
                "stages": stages, "task_rate": 0.0, "progress_rate": 0.0}

    # ---------- 진행 상태 ----------
    def progress(self) -> dict[str, Any]:
        return self.read("progress.json")

    def save_progress(self, prog: dict[str, Any]) -> None:
        prog["updated_at"] = now()
        prog["current_stage"] = next((sid for sid, st in prog["stages"].items() if st["status"] not in ("done", "skipped")), None)
        prog["task_rate"], prog["progress_rate"] = rates(prog, self.pipeline)
        self.write("progress.json", prog, "progress")

    def set_stage(self, prog: dict[str, Any], sid: str, status: str, note: str | None = None, tasks_done: list[str] | None = None,
                  qa_report: dict[str, Any] | None = None, provider: str | None = None, evidence: list[str] | None = None) -> None:
        st = prog["stages"][sid]
        if st["started_at"] is None and status != "pending":
            st["started_at"] = now()
        for t in tasks_done or []:
            if t in st["tasks"]:
                st["tasks"][t] = "done"
        if status == "done":
            st["tasks"] = {k: "done" for k in st["tasks"]}
            st["finished_at"] = now()
        st["status"], st["note"] = status, note
        if qa_report is not None:
            st["qa"] = {"status": qa_report["status"], "counts": qa_report["summary"].get("counts")}
        if provider:
            st["provider"] = provider
        if evidence:
            st["evidence"] = evidence
        self.save_progress(prog)
        self.log("stage", stage=sid, status=status, note=note)

    # ---------- 권한 ----------
    def authority(self) -> dict[str, Any]:
        return self.read("authority.json") or dict(DEFAULT_AUTHORITY)

    def grant(self, **changes: Any) -> dict[str, Any]:
        auth = self.authority()
        for key, value in changes.items():
            if key == "image_limit" and (type(value) is not int or value < 0):
                raise ValueError("image-limit must be a nonnegative integer")
            if key == "execution_until" and (type(value) is not int or value <= 0):
                raise ValueError("execution_until must be a unix timestamp")
            if key == "providers" and value is not None and not isinstance(value, list):
                raise ValueError("providers must be a list")
            if key not in DEFAULT_AUTHORITY:
                raise KeyError(key)
            auth[key] = value
        auth["granted_at"] = now()
        auth["granted_by"] = "user"
        self.write("authority.json", auth, "authority")
        self.log("authority_granted", changes=changes)
        return auth

    # ---------- 선택 ----------
    def save_selection(self, sel: dict[str, Any]) -> list[str]:
        errors = validate_selection(sel, self.tax)
        self.write("selection.json", sel)
        return errors

    # ---------- 실행 루프 ----------
    def run(self, until: str | None = None, echo: Callable[[str], None] | None = None) -> dict[str, Any]:
        pack = require_pack(self.root, allow_mock=True)
        echo = echo or (lambda _m: None)
        prog = self.progress()
        runners: dict[str, Callable[[dict[str, Any]], bool]] = {
            "S00_intake": self._s00, "S01_selection": self._s01, "S02_concept": self._s02, "S03_plan": self._s03,
            "G1_plan_review": self._g1, "S04_story": self._s04, "S05_character_world": self._s05, "S06_storyboard": self._s06,
            "S07_assets": self._s07, "G2_preproduction_review": self._g2, "S08_generation": self._external,
            "S09_edit": self._external, "S10_qa": self._external, "G3_user_review": self._g3, "S11_delivery": self._external,
        }
        from .goal_driver import ceiling

        stage_ids = [s["id"] for s in self.pipeline["stages"]]
        cap = ceiling(self.root)
        for stage in self.pipeline["stages"]:
            sid = stage["id"]
            if cap and stage_ids.index(sid) > stage_ids.index(cap):
                break  # goal: later stages are outside the requested deliverable
            if sid in EXTERNAL_STAGES:
                receipt = self.read(f"receipts/{sid}.json")
                status = prog["stages"][sid]["status"]
                if status == "done" or receipt is not None:
                    if not receipt or not receipt.get("outputs"):
                        raise ValueError(f"receipt missing: {sid}")
                    self.complete(sid, list(receipt["outputs"]))
                    prog = self.progress()
                elif status == "waiting_external":
                    path = f"handoffs/{sid}.json"
                    handoff = self.read(path)
                    if pack is not None and handoff is not None:
                        check_handoff_identity(handoff, pack)
                        if handoff["skill_pack"]["root"] != str(pack.root):
                            handoff["skill_pack"]["root"] = str(pack.root)
                            self.write(path, handoff, "handoff")
                    from .execution_plan import read as read_execution_plan

                    # Recover projects that entered scoped S08 before image preparation.
                    scoped = read_execution_plan(self.root) if sid == "S08_generation" else None
                    if (not scoped or 'video_cut' not in scoped['lanes']
                            or self.read('assets/image_outputs.json') is not None):
                        return prog
            if prog["stages"][sid]["status"] in ("done", "skipped"):
                continue
            runner = runners.get(sid)
            if runner is None:
                break
            echo(f"▶ {sid} {stage['ko']}")
            self.set_stage(prog, sid, "running")
            try:
                ok = runner(prog) if runner != self._external else self._external(prog, sid)
            except AgentInputRequired as req:
                self.set_stage(prog, sid, "waiting_agent", f"에이전트 응답 필요: {req.request_path} → {req.response_path}")
                break
            except ProviderError as exc:
                self.set_stage(prog, sid, "failed", f"공급자 오류: {exc}")
                break
            except ValueError as exc:
                self.set_stage(prog, sid, "failed", str(exc))
                break
            prog = self.progress()
            if not ok or prog["stages"][sid]["status"] != "done":
                break
            if until and sid == until:
                break
        self.write("provider_log.json", self.router.log)
        return self.progress()

    # ---------- 단계 구현 ----------
    def _s00(self, prog: dict[str, Any]) -> bool:
        meta = self.meta
        result = analyze(meta["request"], self.router, self.tax, meta.get("inputs"))
        self.write("intake.json", result.to_dict(), "intake")
        missing = result.missing()
        note = f"부족한 요소 {len(missing)}개: {', '.join(missing)} → 선택 단계에서 보완" if missing else "필요 요소 모두 확인"
        self.set_stage(prog, "S00_intake", "done", note, provider=",".join(result.providers_used) or None)
        return True

    def _providers_ready(self, prog: dict[str, Any]) -> bool:
        """Ask once per project which production services to use; a host agent must relay it to the user."""
        from . import provider_choice
        from .providers.host_agent import _HostIO

        meta = self.read("project.json") or {}
        inputs = meta.setdefault("inputs", {})
        if inputs.get("providers"):
            return True
        if getattr(self.router, "agent", False):
            try:
                reply = _HostIO(self.root / "agent_io").exchange("providers_choice", provider_choice.request())
            except AgentInputRequired as req:
                self.set_stage(prog, "S01_selection", "waiting_user",
                               f"사용자 선택 필요(에이전트가 대신 답하지 말 것): {req.request_path} → {req.response_path}")
                return False
            said = reply.get("user_said") if isinstance(reply, dict) else None
            if not isinstance(said, str) or not said.strip():
                self.set_stage(prog, "S01_selection", "blocked", "providers_choice 응답에 user_said(사용자가 실제로 한 말)가 필요합니다")
                return False
            try:
                choices = provider_choice.validate(reply.get("choices"))
            except ValueError as exc:
                self.set_stage(prog, "S01_selection", "blocked", f"providers_choice 응답 오류: {exc}")
                return False
            provider_choice.apply(inputs, choices, "user", said.strip())
        else:
            provider_choice.apply(inputs, {}, "default")
        atomic_text(self.root / "project.json", json.dumps(meta, ensure_ascii=False, indent=2))
        self.log("providers_chosen", providers=inputs["providers"], source=inputs["providers_source"])
        return True

    def _s01(self, prog: dict[str, Any]) -> bool:
        if not self._providers_ready(prog):
            return False
        intake = self.read("intake.json")
        sel = self.read("selection.json")
        if sel is None:
            sel = merge(new_selection(), intake["detected_selection"], "request")
            for layer, source in (self.read("selection_seed.json") or {}).get("layers", []):
                sel = merge(sel, layer, source)
        sel.setdefault("constraints", [])
        sel["constraints"] = sorted(set(sel["constraints"]) | set(intake.get("constraints", [])))
        before = {k for k, v in sel["sources"].items()}
        sel = fill_required(sel, intake["request"], self.router, self.tax)
        errors = self.save_selection(sel)
        if errors:
            self.set_stage(prog, "S01_selection", "blocked", "선택 오류: " + "; ".join(errors))
            return False
        auto = sorted(set(sel["sources"]) - before)
        self.set_stage(prog, "S01_selection", "done", f"AI가 채운 항목: {', '.join(auto)}" if auto else "모든 항목 사용자 확정")
        return True

    def _s02(self, prog: dict[str, Any]) -> bool:
        sel = self.read("selection.json")
        concept = build_concept(sel, self.tax, self.router)
        self.write("concept.json", concept)
        if concept["blocking"]:
            fixes = "; ".join(f"{i['rule']} {i['message']} {i.get('fix') or ''}" for i in concept["blocking"])
            self.set_stage(prog, "S02_concept", "blocked", "적합성 오류(선택 수정 또는 override 필요): " + fixes,
                           qa_report=qa.report("compatibility", self._as_issues(concept["compatibility"])))
            return False
        self.set_stage(prog, "S02_concept", "done", f"평가 {concept['evaluation']['total']}점({concept['evaluation']['verdict']})",
                       qa_report=qa.report("compatibility", self._as_issues(concept["compatibility"])),
                       provider=",".join(concept["evaluation"]["providers"]))
        return True

    @staticmethod
    def _as_issues(compat: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"rule": c["rule"], "severity": "info" if c["overridden"] else c["severity"], "target": None, "message": c["message"]} for c in compat]

    def _labels(self, sel: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for axis in self.tax.order():
            v = sel.get(axis)
            if v in (None, [], {}):
                continue
            if axis == "direction":
                out[axis] = {g: self.tax.get(axis, i, g).ko for g, i in v.items()}
            elif isinstance(v, list):
                out[axis] = self.tax.labels(axis, v)
            else:
                out[axis] = self.tax.get(axis, v).ko
        return out

    def _s03(self, prog: dict[str, Any]) -> bool:
        sel, concept, intake = self.read("selection.json"), self.read("concept.json"), self.read("intake.json")
        rhythm = sel.get("direction", {}).get("edit_rhythm")
        avg = self.tax.get("direction", rhythm, "edit_rhythm").data.get("avg_cut_s") if rhythm else None
        payload = build_payload(sel, concept, intake, self._labels(sel), avg)
        plan, provider = generate_plan(self.router, payload)
        self.write("plan.json", plan, "plan")
        self.write("plan.md", plan_markdown(plan, concept))
        fails = [c for c in plan["preflight_checks"] if c["status"] == "fail"]
        report = qa.report("plan_preflight", [{"rule": c["id"], "severity": "error" if c["status"] == "fail" else ("warn" if c["status"] == "warn" else "info"),
                                                "target": None, "message": f"{c['item']}: {c.get('detail', '')}"} for c in plan["preflight_checks"] if c["status"] != "pass"])
        self.set_stage(prog, "S03_plan", "done", f"{plan['meta']['scene_count']}씬 {plan['meta']['cut_count']}컷 · 사전점검 실패 {len(fails)}건",
                       qa_report=report, provider=provider)
        return True

    def _g1(self, prog: dict[str, Any]) -> bool:
        plan = self.read("plan.json")
        # Re-check the current plan: a stored preflight goes stale when plan.json is edited after S03.
        from .planner import preflight
        fresh = [c for c in plan.get("preflight_checks", []) if isinstance(c, dict) and c.get("id", "").startswith("U")] + preflight(plan)
        if fresh != plan.get("preflight_checks"):
            plan["preflight_checks"] = fresh
            self.write("plan.json", plan, "plan")
        fails = [c for c in plan["preflight_checks"] if c["status"] == "fail"]
        review = qa.report("G1_plan_review", [{"rule": c["id"], "severity": "error", "target": None, "message": c["item"] + ": " + c.get("detail", "")} for c in fails])
        self.write("reviews/plan_review.json", review, "qa_report")
        if fails:
            self.set_stage(prog, "G1_plan_review", "blocked", "기획안 자동 검수 실패 → plan.json 수정 후 `cineforge run`", qa_report=review, tasks_done=["auto_review"])
            return False
        if not self.authority()["accept_plan"]:
            self.set_stage(prog, "G1_plan_review", "waiting_user", "plan.md 검토 후 `cineforge accept <프로젝트> plan`", qa_report=review, tasks_done=["auto_review"])
            return False
        self.set_stage(prog, "G1_plan_review", "done", "자동 검수 통과 + 사용자 승인(사전 위임 포함)", qa_report=review)
        return True

    def _ssot_build(self) -> dict[str, dict[str, Any]]:
        sel, concept, plan = self.read("selection.json"), self.read("concept.json"), self.read("plan.json")
        labels = self._labels(sel)
        return build_all(plan, concept, sel, {"era": labels.get("era"), "world": labels.get("world")})

    def _write_ssots(self, kinds: list[str]) -> list[str]:
        data = self._ssot_build()
        written = []
        for kind in kinds:
            doc, changed = self.store.write(kind, data[kind])
            written.append(f"{kind} v{doc['version']}{'' if changed else ' (변경 없음)'}")
        return written

    def _handoff(self, sid: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        stage = next(s for s in self.pipeline["stages"] if s["id"] == sid)
        pack = require_pack(self.root, allow_mock=sid not in EXTERNAL_STAGES)
        auth_key = stage.get("requires_authority")
        packet = {"stage": sid, "authority_required": auth_key,
                  "authority_granted": bool(self.authority().get(auth_key)) if auth_key else True,
                  "inputs": [str(p.relative_to(self.root)) for p in sorted((self.root / "ssot").glob("*.json"))] + ["plan.json", "selection.json"],
                  "outputs_expected": stage["outputs"], "packet": dict(extra or {}),
                  "completion_command": f"cineforge complete {self.root} {sid} --evidence <파일...>"}
        facts, context = craft_facts(self.meta, self.read("plan.json") or {})
        if pack is not None:
            packet.update(pack_fields(pack, sid, facts))
            packet["packet"].pop("enrich", None)
        elif self.meta.get(MODE) != "mock":
            route = load("legacy_skill_routes.yaml")[sid]
            packet.update(route=route["route"], owner_skills=route["skills"])
            if sid in CRAFT_STAGES:
                packet.update(legacy_guidance(sid, facts))
        else:
            packet.update(route=None, owner_skills=[])
            packet["packet"].pop("enrich", None)
        if sid in CRAFT_STAGES:
            packet.update(context)
            if "cut_revision" in context and sid in EXTERNAL_STAGES:
                packet["inputs"].append("project.json")
        if pack is not None and sid in EXTERNAL_STAGES:
            packet["inputs"].append(LOCK)
        if sid in EXTERNAL_STAGES:
            names = packet["inputs"] + (extra or {}).get("prompts", []) + list((extra or {}).get("images", {}).values())
            for previous in self.pipeline["stages"]:
                if previous["id"] == sid:
                    break
                receipt = self.read(f"receipts/{previous['id']}.json") if previous["id"] in EXTERNAL_STAGES else None
                if receipt:
                    names.extend(receipt["outputs"])
            packet["input_pins"] = pins(self.root, names)
        self.write(f"handoffs/{sid}.json", packet, "handoff")
        return packet

    def _s04(self, prog: dict[str, Any]) -> bool:
        written = self._write_ssots(["concept", "story"])
        self._handoff("S04_story", {"enrich": "developing-video-synopses로 비트·복선을, video-production-assets(03-screenplay)로 대본을 보강해 ssot/story.json에 반영",
                                    "language": "ko"})
        self.write("script.md", self._script_md())
        self.set_stage(prog, "S04_story", "done", ", ".join(written))
        return True

    def _script_md(self) -> str:
        from .audio_design import design as audio_design

        plan = self.read("plan.json")
        selection = self.read("selection.json") or {}
        silent = selection.get("direction", {}).get("sound") == "silent" or "no_speech" in selection.get("constraints", [])
        names = {c["id"]: c["name"] for c in plan["characters"]}
        out = [f"# 대본 — {plan['title']}", ""]
        for s in plan["scenes"]:
            out += [f"## S#{s['no']}. {s['location']} — {s['title']}", ""]
            for c in s["cuts"]:
                out.append(f"- ({c['no']:02d}, {c['duration']:g}s) {c['visual']}")
                if c.get("dialogue"):
                    out.append(f"  - **{names.get(c.get('speaker'), c.get('speaker') or '?')}**: {c['dialogue']}")
                if c.get("sound"):
                    out.append(f"  - 사운드: {c['sound']}")
            design = next(row for row in audio_design(plan, silent=silent) if row.scene_no == s["no"])
            layers = [f"OST({design.ost})" if design.ost else "BGM", design.ambience,
                      *(f"효과음({item})" for item in design.sfx)]
            out.append(f"- 사운드 설계: {' · '.join(layers)}")
            out.append("")
        return "\n".join(out)

    def _s05(self, prog: dict[str, Any]) -> bool:
        written = self._write_ssots(["character", "world"])
        self._handoff("S05_character_world", {"enrich": "designing-video-character-sheets(R03)로 캐릭터 바이블·의상, designing-character-personas(R04)로 페르소나·연기 방향 보강",
                                              "lock_rule": "보강 후 `cineforge lock <프로젝트> character`로 잠금"})
        self.set_stage(prog, "S05_character_world", "done", ", ".join(written))
        return True

    def _s06(self, prog: dict[str, Any]) -> bool:
        written = self._write_ssots(["scene", "camera", "motion"])
        self._handoff("S06_storyboard", {"enrich": "storyboarding-video(R10)로 패널, camera-spatial-design(R18)로 렌즈·동선, animatic-direction(R08)으로 타이밍 검증"})
        self.set_stage(prog, "S06_storyboard", "done", ", ".join(written))
        return True

    def _ssots(self) -> dict[str, dict[str, Any]]:
        return {k: self.store.read(k) for k in SSOT_TYPES}

    def _s07(self, prog: dict[str, Any]) -> bool:
        written = self._write_ssots(["audio"])
        ss = self._ssots()
        sel = self.read("selection.json")
        pid = self.root.name
        aspect = self.tax.get("aspect", sel["aspect"]).ko.split()[0] if sel.get("aspect") else "9:16"
        look = self.read("plan.json")["meta"]["style"]
        silent = sel.get("direction", {}).get("sound") == "silent" or "no_speech" in sel.get("constraints", [])
        runtime = float(self.read("plan.json")["meta"]["runtime_s"])
        self.write("assets/asset_registry.json", assets.registry(pid, ss), "asset_registry")
        self.write("assets/frames.json", assets.frames(pid, ss), "frames")
        self.write("assets/image_prompts.json", assets.image_prompts(pid, ss, aspect, look), "prompts")
        self.write("assets/video_prompts.json", assets.video_prompts(pid, ss, aspect, silent, external_voice=bool((self.read("project.json") or {}).get("inputs", {}).get("external_voice"))), "prompts")
        self.write("assets/sound_cue_sheet.json", assets.sound_cue_sheet(pid, ss, runtime), "sound_cue_sheet")
        from .sound import plan as sound_plan, write_plan
        mood = self.read("plan.json")["production_spec"].get("bgm") or "장면 정서에 맞춘 절제된 긴장"
        era = ss["world"]["data"].get("era") or ""
        write_plan(self.root, sound_plan(ss["audio"]["data"]["cues"], mood=mood, era=era,
                                          external_voice=bool((self.read("project.json") or {}).get("inputs", {}).get("external_voice")),
                                          voice_provider=(self.read("project.json") or {}).get("inputs", {}).get("voice_provider")), selected={})
        self._handoff("S07_assets", {"enrich": "video-production-assets(11-ai-handoff)·ai-camera-control(R19)로 모델별 프롬프트 방언 변환은 실행 직전에"})
        self.set_stage(prog, "S07_assets", "done", ", ".join(written) + " · 에셋/프레임/프롬프트/큐시트 작성")
        return True

    def _g2(self, prog: dict[str, Any]) -> bool:
        ss = self._ssots()
        plan, sel, intake = self.read("plan.json"), self.read("selection.json"), self.read("intake.json")
        img = self.read("assets/image_prompts.json")["prompts"]
        vid = self.read("assets/video_prompts.json")["prompts"]
        issues = qa.continuity(ss, float(plan["meta"]["runtime_s"])) + qa.constraints(ss, img + vid, sel.get("direction", {}).get("sound") == "silent",
                                                                                    "no_speech" in sel.get("constraints", [])) + qa.identity(ss, img) \
            + qa.rights_safety(ss, sel, intake)
        if plan["meta"].get("profile") == "action":
            from .action import validate as action_issues
            issues += action_issues(ss)
        method = self.tax.get("production_method", sel["production_method"]).data.get("ai_difficulty", 1) if sel.get("production_method") else 1
        cost = qa.cost_plan(ss, method)
        review = qa.report("G2_preproduction_review", issues, {"cost_plan": cost, "ssot_versions": self.store.versions()})
        self.write("reviews/preproduction_review.json", review, "qa_report")
        tasks = ["continuity_rules", "constraint_rules", "rights_safety", "cost_estimate"]
        if review["status"] == "fail":
            self.set_stage(prog, "G2_preproduction_review", "blocked", "검수 오류 → reviews/preproduction_review.json 확인 후 수정", tasks_done=tasks, qa_report=review)
            return False
        auth = self.authority()
        from .phase_review import review as phase_review
        try:
            phase_review(self.root, 'pre')
        except ValueError as exc:
            self.set_stage(prog, 'G2_preproduction_review', 'waiting_agent', str(exc))
            return False
        if not (auth["accept_preproduction"] or auth["accept_plan"] and "nonstop" in auth.get("notes", [])):
            self.set_stage(prog, "G2_preproduction_review", "waiting_user", "`cineforge accept <프로젝트> preproduction`", tasks_done=tasks, qa_report=review)
            return False
        self.set_stage(prog, "G2_preproduction_review", "done", f"검수 {review['status']} · 고비용 컷 {cost['high_tier_cuts']}개", qa_report=review)
        return True

    def _external(self, prog: dict[str, Any], sid: str | None = None) -> bool:
        sid = sid or prog["current_stage"]
        try:
            require_pack(self.root)
        except SkillPackError as exc:
            self.set_stage(prog, sid, "blocked", str(exc))
            return False
        stage = next(s for s in self.pipeline["stages"] if s["id"] == sid)
        extra = {"spend_ceiling": self.authority().get("spend_ceiling")}
        if sid == "S08_generation":
            from . import execution_plan
            from .local_motion import has_local_motion

            if has_local_motion(self.read('plan.json') or {}):
                self.set_stage(prog, sid, 'waiting_external', '로컬 모션 → cineforge motion <project> --font <font>')
                return False
            plan = execution_plan.read(self.root)
            if plan is not None:
                try:
                    execution_plan.approved(self.root, plan)
                except ValueError as exc:
                    self.set_stage(prog, sid, "blocked", str(exc))
                    return False
                if 'video_cut' not in plan['lanes']:
                    self.set_stage(prog, sid, "waiting_external", "cineforge execute --stage S08_audio")
                    return False
            extra["cost_plan"] = (self.read("reviews/preproduction_review.json") or {}).get("summary", {}).get("cost_plan")
            extra["prompts"] = ["assets/image_prompts.json", "assets/video_prompts.json", "assets/frames.json"]
            rows = self.read("assets/image_prompts.json")["prompts"]
            extra["image_engine"] = "codex-imagen"
            extra["image_job_count"] = len(rows)
            limit = self.authority().get("image_limit")
            if limit is None and (plan is not None or ("nonstop" in self.authority().get("notes", []) and not self.authority().get("execution"))):
                if plan is None:
                    self._handoff(sid, extra)
                self.set_stage(prog, sid, "blocked", f"이미지 작업 {len(rows)}개 계획. 실행 범위 상한: cineforge run <project> --image-limit N (Codex Imagen 정지 이미지는 유료 견적 대상 아님); 영상 execution 권한은 별도")
                return False
            if limit is not None and len(rows) > limit:
                if plan is None:
                    self._handoff(sid, extra)
                self.set_stage(prog, sid, "blocked", f"이미지 작업 {len(rows)}개 > 승인 상한 {limit}개 — --image-limit {len(rows)} 이상으로 승인해야 합니다")
                return False
            if limit is not None:
                from .image_queue import generate
                supplied = self.read("assets/supplied_images.json") or {}
                images = generate(self.root, rows, limit, supplied=supplied)
                self.write("assets/image_outputs.json", images)
                registry = self.read("assets/asset_registry.json")
                for row in registry["assets"]:
                    if row["asset_id"] in images:
                        row.update(status="available", path=images[row["asset_id"]], sha256=pins(self.root, [images[row["asset_id"]]])[images[row["asset_id"]]])
                self.write("assets/asset_registry.json", registry, "asset_registry")
                extra["images"] = images
            if plan is not None:
                # Never emit the broad legacy handoff for a lane-bound approval.
                self.set_stage(prog, sid, "waiting_external",
                               "실행 계획 범위 확인 → cineforge execute --preview / execute --stage S08_audio 또는 S08_video")
                return False
        packet = self._handoff(sid, extra)
        if stage.get("requires_authority") and not packet["authority_granted"]:
            self.set_stage(prog, sid, "blocked", f"'{stage['requires_authority']}' 권한 필요 → `cineforge grant <프로젝트> {stage['requires_authority']}`"
                           " (사용자 승인·비용 한도). 인계 패킷: handoffs/" + sid + ".json")
            return False
        self.set_stage(prog, sid, "waiting_external", f"호스트 에이전트가 {', '.join(packet['owner_skills'])}로 실행 → 완료 후 `cineforge complete`")
        return False

    def _g3(self, prog: dict[str, Any]) -> bool:
        if not self.read("reviews/user_review.json"):
            self.set_stage(prog, "G3_user_review", "waiting_user", "완성본 확인 후 `cineforge accept <프로젝트> final`")
            return False
        self.set_stage(prog, "G3_user_review", "done", "사용자 최종 승인")
        return True

    # ---------- 외부 완료·승인·영향 ----------
    def complete(self, sid: str, evidence: list[str]) -> None:
        if sid not in EXTERNAL_STAGES:
            raise ValueError(f"{sid}는 외부 완료 대상이 아닙니다")
        pack = require_pack(self.root)
        prog = self.progress()
        state = prog["stages"][sid]["status"]
        packet = self.read(f"handoffs/{sid}.json") or {}
        inputs = packet.get("input_pins")
        existing = self.read(f"receipts/{sid}.json")
        if state not in ("waiting_external", "done") or not evidence or not inputs:
            raise ValueError(f"receipt not eligible: {sid}")
        if not packet.get("authority_granted") or (packet["authority_required"] and not self.authority().get(packet["authority_required"])):
            raise ValueError(f"receipt authority missing: {sid}")
        if pins(self.root, list(inputs)) != inputs:
            raise ValueError(f"receipt inputs changed: {sid}")
        outputs = pins(self.root, evidence)
        receipt = {"stage": sid, "inputs": inputs, "outputs": outputs}
        if pack is not None:
            check_handoff_identity(packet, pack)
            if LOCK not in inputs:
                raise SkillPackError("invalid", f"handoff missing lock evidence: {sid}")
            receipt["skill_pack"] = pack.binding.identity()
        if existing != receipt and (existing is not None or state == "done"):
            raise ValueError(f"receipt mismatch: {sid}")
        if state == "done":
            return
        if existing is None:
            self.write(f"receipts/{sid}.json", receipt)
        self.set_stage(prog, sid, "done", f"검증된 증거 {len(outputs)}개", evidence=list(outputs))

    def accept(self, gate: str) -> None:
        prog = self.progress()
        if gate == "plan":
            self.grant(accept_plan=True)
            if prog["stages"]["G1_plan_review"]["status"] == "waiting_user":
                self.set_stage(prog, "G1_plan_review", "done", "사용자 승인")
        elif gate == "preproduction":
            self.grant(accept_preproduction=True)
            if prog["stages"]["G2_preproduction_review"]["status"] == "waiting_user":
                self.set_stage(prog, "G2_preproduction_review", "done", "사용자 승인")
        elif gate == "final":
            record: dict[str, Any] = {"accepted": True, "at": now()}
            render = self.root / "edit/render.mp4"
            if render.is_file():
                import hashlib
                record["render_sha256"] = hashlib.sha256(render.read_bytes()).hexdigest()
            self.write("reviews/user_review.json", record)
            self.set_stage(prog, "G3_user_review", "done", "사용자 최종 승인")
        else:
            raise ValueError("gate는 plan | preproduction | final")

    def reset_from(self, sid: str) -> None:
        """sid 이후 단계를 pending으로 되돌린다(외부 단계의 증거·권한 기록은 유지)."""
        prog = self.progress()
        order = [x["id"] for x in self.pipeline["stages"]]
        for later in order[order.index(sid):]:
            st = prog["stages"][later]
            if st["status"] == "skipped":
                continue
            st["status"], st["note"] = "pending", None
            st["tasks"] = {k: "pending" for k in st["tasks"]}
            st["qa"] = None
        self.save_progress(prog)
        self.log("reset", from_stage=sid)

    def apply_impact(self, changed: str) -> list[str]:
        affected = impact(changed)
        stages = sorted({IMPACT_TO_STAGE[a] for a in affected + [changed] if a in IMPACT_TO_STAGE},
                        key=lambda s: [x["id"] for x in self.pipeline["stages"]].index(s))
        prog = self.progress()
        order = [x["id"] for x in self.pipeline["stages"]]
        if stages:
            first = order.index(stages[0])
            for sid in order[first:]:
                if sid in stages or sid.startswith("G") or sid in EXTERNAL_STAGES:
                    st = prog["stages"][sid]
                    if st["status"] != "skipped":
                        st["status"] = "stale" if sid in stages else "pending"
                        st["tasks"] = {k: "pending" for k in st["tasks"]}
                        st["note"] = f"'{changed}' 변경 영향" if sid in stages else st["note"]
        self.save_progress(prog)
        self.log("impact_applied", changed=changed, affected=affected, stages=stages)
        return stages
