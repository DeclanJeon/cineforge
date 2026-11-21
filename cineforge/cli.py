"""CineForge CLI — 요구사항 입력 → 대화형 선택 → 콘셉트 → 기획안 → SSOT → 에셋 → 검수 → 인계, 진행 상태 표시."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from cineforge import __version__
from cineforge.data_loader import data_path, load
from cineforge.pipeline import Project
from cineforge.progress import render
from cineforge.providers.router import MODES, build_router
from cineforge.selection import interactive, merge, new_selection, parse_set_flags, summarize, load_json
from cineforge.intake import analyze
from cineforge.ssot import SSOT_TYPES, impact
from cineforge.taxonomy import Taxonomy


def _print_table(rows: list[tuple[str, str, str]]) -> None:
    for axis, value, source in rows:
        print(f"  {axis:<22} {value:<40} [{source}]")


def cmd_taxonomy(args: argparse.Namespace) -> int:
    tax = Taxonomy()
    if args.export:
        target = Path(args.export)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(data_path("taxonomy.yaml"), target)
        if args.with_rules:
            shutil.copyfile(data_path("rules.yaml"), target.with_name("concept-rules.yaml"))
        print(f"내보냄: {target}")
        return 0
    if args.json:
        print(json.dumps(tax.raw, ensure_ascii=False, indent=2))
        return 0
    axes = [args.axis] if args.axis else tax.order()
    for axis_id in axes:
        axis = tax.axis(axis_id)
        print(f"\n■ {axis['ko']} ({axis_id}) — select={axis.get('select')}{' 필수' if axis.get('required') else ''}")
        for g in axis["groups"]:
            print(f"  [{g['ko']}] " + ", ".join(f"{i.ko}({i.id})" for i in tax.items(axis_id, g["id"])))
    print(f"\n총 {len(tax.axes)}개 축, {tax.total_items()}개 항목 · 프리셋 {len(tax.presets)}개")
    return 0


def _build_selection(args: argparse.Namespace, tax: Taxonomy, request: str, router: Any, detected: dict[str, Any], constraints: list[str]) -> dict[str, Any]:
    sel = merge(new_selection(), detected, "request")
    sel["constraints"] = list(constraints)
    if args.preset:
        preset = tax.presets.get(args.preset)
        if not preset:
            raise SystemExit(f"프리셋 없음: {args.preset} (가능: {', '.join(tax.presets)})")
        sel = merge(sel, preset["selection"], "preset")
    if args.input_json:
        sel = merge(sel, load_json(args.input_json), "user")
    if args.set:
        sel = merge(sel, parse_set_flags(args.set, tax), "user")
    if not args.non_interactive and sys.stdin.isatty():
        sel = interactive(sel, request, router, tax, confirm_detected=args.confirm_all)
    return sel


def cmd_new(args: argparse.Namespace) -> int:
    tax = Taxonomy()
    request = args.request or ""
    if not request and not args.non_interactive and sys.stdin.isatty():
        request = input("만들고 싶은 영상을 자유롭게 적어 주세요: ").strip()
    if not request:
        print("요구사항(request)이 필요합니다.", file=sys.stderr)
        return 2
    inputs = {k: getattr(args, k) for k in ("script", "scenario", "reference", "lead_character", "voice") if getattr(args, k, None)}
    if args.nonstop and not args.confirm_all:
        args.non_interactive = True
    if args.with_dialogue:
        inputs["with_dialogue"] = True
    if args.no_speech:
        inputs["no_speech"] = True
    project = Project.create(Path(args.projects_dir), request, args.provider, args.project_id, inputs=inputs)
    print(f"프로젝트: {project.root}")
    if args.nonstop:
        project.grant(accept_plan=True, accept_preproduction=True, notes=["nonstop"])
    if args.image_limit is not None:
        project.grant(image_limit=args.image_limit)
    project.run(until="S00_intake")
    intake = project.read("intake.json")
    if intake is None:
        print("\n요구사항 분석에 호스트 에이전트 응답이 필요합니다. 응답 파일을 쓴 뒤 `cineforge select` → `cineforge run`으로 이어가세요.")
        print(render(project.progress(), load("pipeline.yaml")))
        return 0
    print("\n[요구사항 분석 — 9개 판단 요소]")
    for fid, f in intake["factors"].items():
        mark = {"provided": "있음", "partial": "일부", "missing": "없음"}[f["status"]]
        print(f"  {f['ko']:<24} {mark:<4} → {'' if f['status'] == 'provided' else f['if_missing']}")
    sel = _build_selection(args, tax, request, project.router, intake["detected_selection"], intake["constraints"])
    if args.lead_character:
        sel["free_text"]["lead_character"] = args.lead_character
    errors = project.save_selection(sel)
    pending = [e.split(":")[0] for e in errors if "필수 선택" in e]
    real = [e for e in errors if "필수 선택" not in e]
    if pending:
        print("남은 필수 항목 → AI 추천으로 채움: " + ", ".join(pending))
    if real:
        print("선택 오류: " + "; ".join(real), file=sys.stderr)
        return 1
    grants: dict[str, Any] = {}
    if args.auto_accept_plan:
        grants["accept_plan"] = True
    if args.nonstop:
        grants.update(accept_plan=True, accept_preproduction=True)
    if grants:
        auth = project.grant(**grants)
        if args.nonstop:
            auth["notes"] = sorted(set(auth.get("notes", [])) | {"nonstop"})
            project.write("authority.json", auth, "authority")
    print("\n[선택 요약]")
    _print_table(summarize(sel, tax))
    return _run_and_report(project, args.until)


def _run_and_report(project: Project, until: str | None) -> int:
    from cineforge.progress import share
    from cineforge.ui import panel, supports_color

    prog = project.run(until=until, echo=print)
    share(project.root)
    print()
    print(panel(prog, load("pipeline.yaml"), color=supports_color()))
    concept = project.read("concept.json")
    if concept:
        c, e = concept["concept"], concept["evaluation"]
        print(f"\n조합된 제작 콘셉트: {c['title_line']} — {c['subtitle']}")
        if c.get("chain"):
            print(f"  {c['chain']} | 감정: {c['emotion_arc']}")
        print(f"  평가: {e['total']}점 ({e['verdict']}) " + " ".join(f"{k}={v}" for k, v in e["scores"].items()))
        for cand in concept.get("candidates", []):
            print(f"  대안: {cand['label']} → {cand['evaluation']['total']}점")
        for issue in concept["compatibility"]:
            print(f"  [{issue['severity']}] {issue['rule']} {issue['message']}")
    if (project.root / "plan.md").exists():
        print(f"\n기획안: {project.root / 'plan.md'}")
    return 0


def cmd_select(args: argparse.Namespace) -> int:
    """기존 프로젝트의 선택을 (다시) 진행하고 S01 이후를 재실행 대상으로 만든다."""
    tax = Taxonomy()
    project = Project(Path(args.project))
    intake = project.read("intake.json")
    if intake is None:
        print("intake.json 없음 — 먼저 `cineforge run`으로 요구사항 분석을 끝내세요.", file=sys.stderr)
        return 1
    current = project.read("selection.json")
    if current is None:
        current = merge(new_selection(), intake["detected_selection"], "request")
        current["constraints"] = list(intake.get("constraints", []))
    if args.preset:
        current = merge(current, tax.presets[args.preset]["selection"], "preset")
    if args.input_json:
        current = merge(current, load_json(args.input_json), "user")
    if args.set:
        current = merge(current, parse_set_flags(args.set, tax), "user")
    if not args.non_interactive and sys.stdin.isatty():
        current = interactive(current, intake["request"], project.router, tax, confirm_detected=args.confirm_all)
    errors = project.save_selection(current)
    for e in errors:
        print("선택 오류: " + e)
    project.reset_from("S01_selection")
    _print_table(summarize(current, tax))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if not (Path(args.project) / "project.json").is_file():
        raise FileNotFoundError(f"프로젝트를 찾을 수 없습니다: {args.project}")
    project = Project(Path(args.project), router=build_router(args.provider, io_dir=Path(args.project) / "agent_io") if args.provider else None)
    if args.image_limit is not None:
        project.grant(image_limit=args.image_limit)
    return _run_and_report(project, args.until)


def cmd_setup(args: argparse.Namespace) -> int:
    from getpass import getpass

    from cineforge.sound import KEYS, MCP_SERVERS, SetupError, apply, remove_key, set_key, status

    try:
        if args.set_key:
            set_key(args.set_key, getpass(f"{args.set_key} 키 입력(표시되지 않음): "))
            print(f"{args.set_key} 키를 등록했습니다: {KEYS[args.set_key]}")
            return 0
        if args.remove_key:
            remove_key(args.remove_key)
            print(f"{args.remove_key} 키를 삭제했습니다.")
            return 0
        if args.no_sync and not (args.discover or args.import_mcp):
            pass
        elif not (args.discover or args.import_mcp) and not args.no_sync:
            from cineforge.mcp_discovery import sync

            report = sync()
            print(f"MCP 자동 동기화: 추가 {len(report['added'])}, 갱신 {len(report['updated'])}, "
                  f"제거 {len(report['removed'])}, 충돌 {len(report['conflicts'])} → {report['target']}")
        if args.discover or args.import_mcp:
            from cineforge.mcp_discovery import discover, import_config, matches

            rows = discover()
            if args.import_mcp:
                target = import_config(rows)
                print(json.dumps({"imported": str(target), "providers": sorted(matches(rows))}, ensure_ascii=False))
                return 0
            print(json.dumps({'servers': rows, 'matched': sorted(matches(rows))}, ensure_ascii=False, indent=2))
            return 0
        if args.apply:
            recipes = {}
            for item in getattr(args, "recipe", None) or []:
                name, _, command = item.partition("=")
                recipes[name] = command.split()
            done = apply(args.apply, yes=args.yes, recipes=recipes)
            print("설치 완료: " + ", ".join(done) + f" (host={args.host})")
            return 0
    except SetupError as exc:
        print(f"설정 실패: {exc}", file=sys.stderr)
        return 1
    for row in status():
        host = f"외부설치({row['agent']})" if row['installed_elsewhere'] else ('명령' if row['command_available'] else '없음')
        print(f"{row['server']:<12} {host:<16} "
              f"키 {'등록' if row['key_registered'] else '없음':<3} {row['purpose']}")
    print("설치: cineforge setup --apply suno --recipe 'suno=<설치 명령>' --yes")
    print("키 등록: cineforge setup --set-key <server>  (값은 숨김 입력)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    if not (Path(args.project) / "project.json").is_file():
        raise FileNotFoundError(f"프로젝트를 찾을 수 없습니다: {args.project}")
    project = Project(Path(args.project))
    prog = project.progress()
    from cineforge.progress import share, snapshot
    from cineforge.ui import banner, panel, supports_color

    state = snapshot(args.project)
    share(args.project)
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        color = supports_color()
        print(banner(color=color))
        print()
        print(panel(prog, load("pipeline.yaml"), color=color))
    return 0


def cmd_execute(args: argparse.Namespace) -> int:
    from cineforge.audio_jobs import plan_jobs as audio_plan
    from cineforge.jobs import write_envelope
    from cineforge.video_jobs import plan_jobs as video_plan

    project = Path(args.project)
    jobs = audio_plan(project) if args.stage == "S08_audio" else video_plan(project)
    if args.preview:
        from dataclasses import asdict

        print(json.dumps({'stage': args.stage, 'jobs': [asdict(job) for job in jobs]}, ensure_ascii=False))
        return 0
    quotes = json.loads(Path(args.quotes).read_text(encoding='utf-8')) if args.quotes else None
    path = write_envelope(project, args.stage, jobs, quotes=quotes)
    print(json.dumps({"stage": args.stage, "jobs": len(jobs), "envelope": str(path)}, ensure_ascii=False))
    return 0


def cmd_results(args: argparse.Namespace) -> int:
    from cineforge.jobs import record_results

    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    path = record_results(Path(args.project), args.stage, list(data), runner_meta=args.runner or "")
    if args.stage == "S08_audio":
        from cineforge.audio_jobs import apply_results

        apply_results(Path(args.project), list(data))
    print(json.dumps({"stage": args.stage, "receipt": str(path)}, ensure_ascii=False))
    return 0


def cmd_edit(args: argparse.Namespace) -> int:
    from cineforge.edit_plan import build, validate

    project = Path(args.project)
    plan = build(project)
    issues = validate(project, plan)
    if issues:
        raise ValueError("; ".join(issues))
    target = project / "edit/edit_plan.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cuts": len(plan["cuts"]), "audio": len(plan["audio"]),
                      "subtitles": len(plan["subtitles"]), "plan": str(target)}, ensure_ascii=False))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    from cineforge.assembly import render

    project = Path(args.project)
    plan = json.loads((project / "edit/edit_plan.json").read_text(encoding="utf-8"))
    size = tuple(int(part) for part in args.size.lower().split("x")) if args.size else None
    if size is not None and len(size) != 2:
        raise ValueError("--size는 WxH 형식입니다")
    target = render(project, plan, output=args.output, size=size)
    print(json.dumps({"render": str(target)}, ensure_ascii=False))
    return 0


def cmd_qa_final(args: argparse.Namespace) -> int:
    from cineforge.final_qa import inspect

    project = Path(args.project)
    report = inspect(project, project / args.video)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"최종 검수: {report['status']}")
    return 0 if report["status"] == "pass" else 1


def cmd_deliver(args: argparse.Namespace) -> int:
    from cineforge.delivery import DeliveryError, deliver

    try:
        bundle = deliver(Path(args.project))
    except DeliveryError as exc:
        print(f"납품 차단: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(bundle, ensure_ascii=False, indent=2) if args.json else f"납품: {bundle['video']}")
    return 0


def cmd_mcp_sync(args: argparse.Namespace) -> int:
    from cineforge import mcp_sync

    if args.action == "start":
        result = mcp_sync.start(interval=args.interval)
    elif args.action == "stop":
        result = mcp_sync.stop()
    else:
        result = mcp_sync.status()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") not in ("start_failed", "stop_timeout") else 1


def cmd_route(args: argparse.Namespace) -> int:
    from cineforge.route import evaluate, judge

    if args.eval or args.holdout:
        import json as _json

        if args.holdout:
            from pathlib import Path as _Path

            rows = _json.loads((_Path(__file__).parent / "data/routing_holdout.json").read_text(encoding="utf-8"))["cases"]
            hits = sum(judge(row["request"])["route"] == row["expect"] for row in rows)
            report = {"total": len(rows), "correct": hits, "accuracy": round(hits / len(rows), 3)}
        else:
            report = evaluate()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["accuracy"] >= 0.9 else 1
    result = judge(args.request)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_execution_plan(args: argparse.Namespace) -> int:
    from cineforge.execution_plan import proposal

    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    print(json.dumps(proposal(Project(Path(args.project)), data), ensure_ascii=False, indent=2))
    return 0


def cmd_authorize(args: argparse.Namespace) -> int:
    import time
    from cineforge.execution_plan import approve

    if args.approve_plan is not None:
        if args.providers is not None or args.spend_ceiling is not None:
            raise ValueError("use_provider_and_ceiling_from_execution_plan")
        approval = approve(Project(Path(args.project)), args.approve_plan, args.hours)
        print(json.dumps(approval, ensure_ascii=False, indent=2))
        return 0

    if not sys.stdin.isatty():
        raise PermissionError("승인은 대화형 터미널에서만 가능합니다")
    answer = input(f"실행을 승인하려면 APPROVE 입력 (상한 {args.spend_ceiling or '미지정'}, {args.hours}시간): ")
    if answer.strip() != "APPROVE":
        print("승인 취소", file=sys.stderr)
        return 1
    project = Project(Path(args.project))
    providers = [part.strip() for part in (args.providers or "").split(",") if part.strip()]
    project.grant(execution=True, spend_ceiling=args.spend_ceiling, providers=providers or None,
                  execution_until=int(time.time()) + args.hours * 3600, notes=["authorized-by-user"])
    print(json.dumps(project.authority(), ensure_ascii=False, indent=2))
    return 0


def cmd_qa_playback(args: argparse.Namespace) -> int:
    from cineforge.playback import submit

    report = json.loads(Path(args.file).read_text(encoding="utf-8"))
    path = submit(Path(args.project), report)
    print(json.dumps({"record": str(path), "provenance": "reviewer_reported"}, ensure_ascii=False))
    return 0


def cmd_skills(args: argparse.Namespace) -> int:
    from cineforge.skills import check

    report = check(Path(args.root) if args.root else None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["available"] else 1


def cmd_gate(args: argparse.Namespace) -> int:
    from cineforge.gate import check

    report = check(Path(args.project))
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        print("납품 게이트: " + ("통과" if report.status == "pass" else f"차단 {len(report.blockers)}건"))
        for row in report.blockers:
            print(f"  - {row['kind']} {row['item']}: {row['reason']}")
    return 0 if report.status == "pass" else 1


def cmd_verify(args: argparse.Namespace) -> int:
    from cineforge.gate import check, promote

    project = Path(args.project)
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"프로젝트를 찾을 수 없습니다: {project}")
    ids = [row["item"] for row in check(project).blockers] if args.all else list(args.asset or [])
    if not ids:
        print("검증할 에셋을 지정하세요: --asset ID 또는 --all", file=sys.stderr)
        return 2
    if not args.attest or not str(args.attest).strip():
        print("사람 확인 내용을 --attest에 적어야 합니다", file=sys.stderr)
        return 2
    if not sys.stdin.isatty():
        print("검증 승격은 대화형 터미널에서만 가능합니다", file=sys.stderr)
        return 2
    if input(f"{len(ids)}건을 verified로 승격하려면 VERIFY 입력: ").strip() != "VERIFY":
        print("승격 취소", file=sys.stderr)
        return 1
    count = promote(project, ids, attestation=args.attest, by="user")
    print(f"검증 승격 {count}건 (파일·해시 재확인)")
    return 0


def cmd_accept(args: argparse.Namespace) -> int:
    Project(Path(args.project)).accept(args.gate)
    print(f"승인 기록: {args.gate}")
    return 0


def cmd_grant(args: argparse.Namespace) -> int:
    project = Project(Path(args.project))
    changes: dict[str, Any] = {args.authority: True}
    if args.spend_ceiling:
        changes["spend_ceiling"] = args.spend_ceiling
    project.grant(**changes)
    print(f"권한 기록: {args.authority}{' (한도 ' + args.spend_ceiling + ')' if args.spend_ceiling else ''}")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    Project(Path(args.project)).complete(args.stage, args.evidence or [])
    print(f"완료 기록: {args.stage}")
    return 0


def cmd_impact(args: argparse.Namespace) -> int:
    if args.ssot not in SSOT_TYPES + ["plan"]:
        print(f"ssot는 {SSOT_TYPES + ['plan']} 중 하나", file=sys.stderr)
        return 2
    print("영향 대상: " + ", ".join(impact(args.ssot)))
    if args.apply:
        stages = Project(Path(args.project)).apply_impact(args.ssot)
        print("재실행 대상 단계: " + ", ".join(stages))
    return 0


def cmd_lock(args: argparse.Namespace) -> int:
    Project(Path(args.project)).store.set_lock(args.ssot, not args.unlock)
    print(f"{args.ssot} {'잠금 해제' if args.unlock else '잠금'}")
    return 0


def cmd_providers(args: argparse.Namespace) -> int:
    router = build_router(args.provider or "auto", io_dir=Path.cwd() / "agent_io")
    print(json.dumps(router.describe(), ensure_ascii=False, indent=2))
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    result = analyze(args.request, build_router(args.provider or "mock"), Taxonomy())
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cineforge", description="대화형 AI 콘텐츠 제작 오케스트레이터 (contents-production-skills 연동)")
    p.add_argument("--version", action="version", version=f"cineforge {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    t = sub.add_parser("taxonomy", help="콘셉트 라이브러리 보기/내보내기")
    t.add_argument("--axis")
    t.add_argument("--json", action="store_true")
    t.add_argument("--export", help="taxonomy.yaml을 지정 경로로 복사(스킬 저장소 동기화)")
    t.add_argument("--with-rules", action="store_true", help="rules.yaml도 concept-rules.yaml로 함께 복사")
    t.set_defaults(func=cmd_taxonomy)

    n = sub.add_parser("new", help="새 제작: 요구사항 → 선택 → 논스톱 진행")
    n.add_argument("request", nargs="?", help="만들고 싶은 영상(자유 서술)")
    n.add_argument("--projects-dir", default="./productions")
    n.add_argument("--project-id")
    n.add_argument("--provider", choices=MODES, default="auto")
    n.add_argument("--preset", help="taxonomy.yaml presets의 id")
    n.add_argument("--input-json", help="선택값 JSON 파일(selection.schema.json 형식)")
    n.add_argument("--set", action="append", help="axis=value[,value] (예: --set narrative=결말 선공개형 --set direction.texture=시네마틱)")
    n.add_argument("--non-interactive", action="store_true", help="질문 없이 진행(남은 필수 항목은 AI 추천)")
    n.add_argument("--confirm-all", action="store_true", help="요청문에서 감지된 항목도 다시 묻기")
    n.add_argument("--script", help="대본 파일 경로")
    n.add_argument("--scenario", help="시나리오/시놉시스 파일 경로")
    n.add_argument("--reference", help="레퍼런스 URL 또는 설명")
    n.add_argument("--lead-character", help="주연 캐릭터 이름/파일")
    n.add_argument("--voice", help="목소리 방침")
    speech = n.add_mutually_exclusive_group()
    speech.add_argument("--with-dialogue", action="store_true", help="극영화 대사 사용")
    speech.add_argument("--no-speech", action="store_true", help="대사·음성 없음(효과음·연출만)")
    n.add_argument("--auto-accept-plan", action="store_true", help="기획안 자동 검수 통과 시 사용자 승인으로 간주(사용자가 명시적으로 위임)")
    n.add_argument("--nonstop", action=argparse.BooleanOptionalAction, default=True, help="기본: 자동 기획, --no-nonstop: 수동 검토")
    n.add_argument("--image-limit", type=int, help="Codex Imagen 실행·참조 전송 범위 상한(작품 누적 건수). 비용 승인 아님")
    n.add_argument("--until", help="이 단계까지만 실행(예: S03_plan)")
    n.set_defaults(func=cmd_new)

    se = sub.add_parser("select", help="기존 프로젝트의 콘셉트 선택 (재)진행")
    se.add_argument("project")
    se.add_argument("--preset")
    se.add_argument("--input-json")
    se.add_argument("--set", action="append")
    se.add_argument("--non-interactive", action="store_true")
    se.add_argument("--confirm-all", action="store_true")
    se.set_defaults(func=cmd_select)

    r = sub.add_parser("run", help="중단된 지점부터 이어서 실행")
    r.add_argument("project")
    r.add_argument("--provider", choices=MODES)
    r.add_argument("--until")
    r.add_argument("--image-limit", type=int, help="Codex Imagen 실행 범위 상한(누적 건수). 비용 승인 아님")
    r.set_defaults(func=cmd_run)

    g = sub.add_parser("gate", help="납품 게이트 점검(verified만 통과)")
    g.add_argument("project")
    g.add_argument("--json", action="store_true")
    g.set_defaults(func=cmd_gate)

    ms = sub.add_parser("mcp-sync", help="외부 MCP 설정 백그라운드 동기화")
    ms.add_argument("action", choices=["start", "stop", "status"])
    ms.add_argument("--interval", type=float, default=5.0)
    ms.set_defaults(func=cmd_mcp_sync)

    ro = sub.add_parser("route", help="제작 요청인지 판정")
    ro.add_argument("request", nargs="?")
    ro.add_argument("--eval", action="store_true")
    ro.add_argument("--holdout", action="store_true")
    ro.set_defaults(func=cmd_route)

    ep = sub.add_parser("execution-plan", help="제작 시작 전 공급자·모델·예상 비용 범위 제안")
    ep.add_argument("project")
    ep.add_argument("--file", required=True)
    ep.set_defaults(func=cmd_execution_plan)

    au = sub.add_parser("authorize", help="실행 계획 해시 승인 또는 기존 대화형 승인")
    au.add_argument("project")
    au.add_argument("--approve-plan", metavar="HASH", help="이미 명시적으로 승인받은 실행 계획 기록")
    au.add_argument("--spend-ceiling")
    au.add_argument("--providers")
    au.add_argument("--hours", type=int, default=24)
    au.set_defaults(func=cmd_authorize)

    qp = sub.add_parser("qa-playback", help="사람 재생 검수 기록(납품 해시 고정)")
    qp.add_argument("project")
    qp.add_argument("--file", required=True)
    qp.set_defaults(func=cmd_qa_playback)

    sk = sub.add_parser("skills", help="스킬팩 연결·핀 검사")
    sk.add_argument("--root")
    sk.set_defaults(func=cmd_skills)

    ex = sub.add_parser("execute", help="실행 봉투 생성(S08_audio/S08_video)")
    ex.add_argument("project")
    ex.add_argument("--stage", choices=["S08_audio", "S08_video"], default="S08_audio")
    ex.add_argument("--preview", action="store_true", help="견적용 작업 조회만 수행, 실행 봉투 미작성")
    ex.add_argument("--quotes", help="유료 작업별 검증한 견적 JSON 파일")
    ex.set_defaults(func=cmd_execute)

    rs = sub.add_parser("results", help="실행 결과 영수증 기록")
    rs.add_argument("project")
    rs.add_argument("--stage", choices=["S08_audio", "S08_video"], default="S08_audio")
    rs.add_argument("--file", required=True)
    rs.add_argument("--runner", default="")
    rs.set_defaults(func=cmd_results)

    ed = sub.add_parser("edit", help="편집 계획 생성")
    ed.add_argument("project")
    ed.set_defaults(func=cmd_edit)

    rd = sub.add_parser("render", help="ffmpeg 조립")
    rd.add_argument("project")
    rd.add_argument("--output", default="edit/render.mp4")
    rd.add_argument("--size")
    rd.set_defaults(func=cmd_render)

    qf = sub.add_parser("qa-final", help="최종 검수")
    qf.add_argument("project")
    qf.add_argument("--video", default="edit/render.mp4")
    qf.add_argument("--json", action="store_true")
    qf.set_defaults(func=cmd_qa_final)

    dl = sub.add_parser("deliver", help="납품 번들 생성")
    dl.add_argument("project")
    dl.add_argument("--json", action="store_true")
    dl.set_defaults(func=cmd_deliver)

    v = sub.add_parser("verify", help="에셋·음성·테이크를 verified로 승격")
    v.add_argument("project")
    v.add_argument("--asset", action="append")
    v.add_argument("--all", action="store_true")
    v.add_argument("--attest", help="사람이 확인한 내용(필수)")
    v.set_defaults(func=cmd_verify)

    su = sub.add_parser("setup", help="필요 MCP 서버 확인·설치·키 등록")
    su.add_argument("--apply", nargs="+", metavar="SERVER", help="선택한 MCP 서버 설치 실행")
    su.add_argument("--yes", action="store_true", help="설치 실행 확인(없으면 거부)")
    su.add_argument("--recipe", action="append", metavar="SERVER=CMD", help="서버 설치 명령(반복)")
    su.add_argument("--discover", action="store_true", help="다른 에이전트에 설치된 MCP 읽기")
    su.add_argument("--import-mcp", action="store_true", help="발견한 MCP 항목을 지금 즉시 기록")
    su.add_argument("--no-sync", action="store_true", help="자동 동기화를 끄고 상태만 본다")
    su.add_argument("--host", choices=["codex", "claude", "pi"], default="codex")
    su.add_argument("--set-key", metavar="SERVER", help="키를 숨김 입력으로 등록")
    su.add_argument("--remove-key", metavar="SERVER")
    su.set_defaults(func=cmd_setup)

    s = sub.add_parser("status", help="진행률·작업률·검수 상태")
    s.add_argument("project")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_status)

    a = sub.add_parser("accept", help="게이트 승인(plan | preproduction | final)")
    a.add_argument("project")
    a.add_argument("gate", choices=["plan", "preproduction", "final"])
    a.set_defaults(func=cmd_accept)

    g = sub.add_parser("grant", help="실행 권한 기록(execution | edit | publish)")
    g.add_argument("project")
    g.add_argument("authority", choices=["execution", "edit", "publish"])
    g.add_argument("--spend-ceiling", help="비용 한도(예: 20USD)")
    g.set_defaults(func=cmd_grant)

    c = sub.add_parser("complete", help="외부 단계 완료 기록(증거 파일 필수)")
    c.add_argument("project")
    c.add_argument("stage", choices=["S08_generation", "S09_edit", "S10_qa", "S11_delivery"])
    c.add_argument("--evidence", nargs="+")
    c.set_defaults(func=cmd_complete)

    i = sub.add_parser("impact", help="SSOT 변경 영향 분석(--apply 시 재실행 대상 표시)")
    i.add_argument("project")
    i.add_argument("ssot")
    i.add_argument("--apply", action="store_true")
    i.set_defaults(func=cmd_impact)

    lk = sub.add_parser("lock", help="SSOT 잠금/해제")
    lk.add_argument("project")
    lk.add_argument("ssot", choices=SSOT_TYPES)
    lk.add_argument("--unlock", action="store_true")
    lk.set_defaults(func=cmd_lock)

    pv = sub.add_parser("providers", help="판단·생성 공급자 체인과 사용 가능 여부")
    pv.add_argument("--provider", choices=MODES)
    pv.set_defaults(func=cmd_providers)

    an = sub.add_parser("analyze", help="요구사항 분석만 실행(JSON 출력)")
    an.add_argument("request")
    an.add_argument("--provider", choices=MODES)
    an.set_defaults(func=cmd_analyze)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except (FileExistsError, FileNotFoundError, KeyError, ValueError, PermissionError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
