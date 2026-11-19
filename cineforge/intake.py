"""S00 요구사항 접수·분석 — 9개 판단 요소를 판정하고 요청문에서 콘셉트 단서를 추출한다."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from cineforge.providers.base import Question
from cineforge.providers.router import ProviderRouter
from cineforge.taxonomy import Taxonomy

# 사용자가 지정한 판단 요소(순서 유지)
FACTORS: list[dict[str, Any]] = [
    {"id": "script", "ko": "대본·각본이 있나?", "keywords": ["대본", "각본", "스크립트", "script", "대사:"],
     "fills": "S04_story", "if_missing": "AI가 기획안 확정 후 대본을 작성"},
    {"id": "scenario", "ko": "시나리오(시놉시스)가 있나?", "keywords": ["시나리오", "시놉시스", "줄거리", "synopsis", "로그라인"],
     "fills": "S03_plan", "if_missing": "AI가 시놉시스를 작성"},
    {"id": "reference", "ko": "원하는 레퍼런스가 있나?", "keywords": ["레퍼런스", "참고 영상", "참고영상", "처럼", "같은 느낌", "http://", "https://", "tiktok", "youtube"],
     "fills": "S03_plan", "if_missing": "레퍼런스 없이 콘셉트 라이브러리로 설계"},
    {"id": "plot_concept", "ko": "원하는 플롯이나 컨셉이 있나?", "keywords": ["플롯", "컨셉", "콘셉트", "설정", "이야기", "내용은"],
     "fills": "S01_selection", "if_missing": "장르·소재·관계·세계관 선택 또는 AI 추천"},
    {"id": "lead_character", "ko": "주연으로 쓰일 캐릭터가 있나?", "keywords": ["주인공", "주연", "캐릭터", "한서윤", "서윤"],
     "fills": "S05_character_world", "if_missing": "AI가 주연 캐릭터 바이블을 설계"},
    {"id": "voice", "ko": "목소리(대사·내레이션)는?", "keywords": ["목소리", "보이스", "음성", "내레이션", "더빙", "무음성", "대사 없", "말 없", "무성"],
     "fills": "S01_selection", "if_missing": "사운드 축(무성/대사/내레이션/음악/ASMR) 선택"},
    {"id": "content_concept", "ko": "만들 콘텐츠의 콘셉트는?", "keywords": [], "taxonomy_axes": ["format", "genre"],
     "fills": "S01_selection", "if_missing": "형식·문화권·시대·장르·길이 선택"},
    {"id": "story_development", "ko": "스토리 전개(서사 구조)는?", "keywords": [], "taxonomy_axes": ["narrative"],
     "fills": "S01_selection", "if_missing": "12개 서사 구조 중 선택, 감정 곡선·후킹 선택"},
    {"id": "direction", "ko": "영상의 연출은?", "keywords": ["연출", "카메라", "시네마틱", "질감", "톤"], "taxonomy_axes": ["direction", "production_method"],
     "fills": "S01_selection", "if_missing": "연출 8개 하위 축·제작 방식 선택"},
]

SEOYUN_NAMES = ("한서윤", "서윤")
NO_SPEECH_PATTERNS = ["무음성", "대사 없", "대사없", "말 없", "speech 없", "no speech", "무성"]


@dataclass
class IntakeResult:
    request: str
    factors: dict[str, dict[str, Any]]
    detected: dict[str, Any]
    constraints: list[str]
    inputs: dict[str, Any] = field(default_factory=dict)
    providers_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"request": self.request, "factors": self.factors, "detected_selection": self.detected,
                "constraints": self.constraints, "inputs": self.inputs, "providers_used": self.providers_used}

    def missing(self) -> list[str]:
        return [k for k, v in self.factors.items() if v["status"] == "missing"]


def _aliases(label: str) -> list[str]:
    base = label.replace(" ", "")
    out = [base]
    if base.endswith("형") and len(base) > 3:
        out.append(base[:-1])
    return out


def detect_selection(text: str, tax: Taxonomy) -> dict[str, Any]:
    """요청문에서 콘셉트 라이브러리 라벨을 찾아 축별 후보를 만든다.

    겹치는 위치에서는 더 긴 라벨이 이긴다(예: '숏드라마'가 '드라마'를 가린다).
    같은 위치·같은 길이의 라벨은 서로 다른 축에 동시에 들어갈 수 있다(예: '실사').
    """
    found: dict[str, Any] = {}
    compact = text.replace(" ", "")
    m = re.search(r"(\d{2,3})\s*초", text)
    if m:
        seconds = int(m.group(1))
        match = [i for i in tax.items("duration") if i.data.get("seconds") == seconds]
        if match:
            found["duration"] = match[0].id
        else:
            found["duration_custom_s"] = seconds
    aspect = re.search(r"(9:16|16:9|1:1|4:5)", text)
    if aspect:
        for item in tax.items("aspect"):
            if item.ko.startswith(aspect.group(1)):
                found["aspect"] = item.id
    hits: list[tuple[int, int, str, str | None, Any]] = []  # (start, end, axis, group, item)
    for axis_id in tax.order():
        if axis_id in ("duration", "aspect"):
            continue
        per_group = tax.axis(axis_id).get("select") == "per_group"
        for item in tax.items(axis_id):
            for alias in _aliases(item.ko):
                if len(alias) < 2:
                    continue
                for mm in re.finditer(re.escape(alias), compact):
                    hits.append((mm.start(), mm.end(), axis_id, item.group if per_group else None, item))
    hits.sort(key=lambda h: (-(h[1] - h[0]), h[0]))
    accepted: list[tuple[int, int, str, str | None, Any]] = []
    for h in hits:
        clash = [a for a in accepted if not (h[1] <= a[0] or h[0] >= a[1])]
        if any((a[1] - a[0]) > (h[1] - h[0]) or a[2] == h[2] and a[3] == h[3] for a in clash):
            continue
        accepted.append(h)
    accepted.sort(key=lambda h: h[0])
    for start, _end, axis_id, group, item in accepted:
        axis = tax.axis(axis_id)
        if group is not None:
            found.setdefault("direction", {}).setdefault(group, item.id)
        elif axis.get("select") in ("many", "arc"):
            bucket = found.setdefault(axis_id, [])
            if item.id not in bucket and len(bucket) < int(axis.get("max", 3)):
                bucket.append(item.id)
        else:
            found.setdefault(axis_id, item.id)
    # 장르는 하위 장르에서 역추론
    if "genre" not in found and "subgenre" in found:
        parents: list[str] = []
        groups = {g["id"]: g for g in tax.axis("subgenre")["groups"]}
        for sub in found["subgenre"]:
            parent = groups[tax.get("subgenre", sub).group].get("parent_genre", [None])[0]
            if parent and parent not in parents:
                parents.append(parent)
        if parents:
            found["genre"] = parents[:2]
    if found.get("romance_concept") and "romance" not in found.get("genre", []):
        found["genre"] = (["romance"] + found.get("genre", []))[:2]
    return found


def analyze(request: str, router: ProviderRouter, tax: Taxonomy, inputs: dict[str, Any] | None = None) -> IntakeResult:
    inputs = {k: v for k, v in (inputs or {}).items() if v}
    detected = detect_selection(request, tax)
    questions = [
        Question(f["id"], "noul", f"사용자 요청에 다음이 이미 들어 있는가: {f['ko']}",
                 hints={"keywords": f.get("keywords", [])}) for f in FACTORS if f.get("keywords")
    ]
    answers = router.decide(request, questions, task="intake_factors")
    factors: dict[str, dict[str, Any]] = {}
    for f in FACTORS:
        fid = f["id"]
        status, evidence, source = "missing", None, None
        if fid in inputs:
            status, evidence, source = "provided", f"입력 제공: {fid}", "input"
        elif fid in answers and answers[fid].yes:
            status, evidence, source = "provided", "요청문에서 확인", answers[fid].provider
        axes = f.get("taxonomy_axes")
        if axes and status != "provided":
            hit = [a for a in axes if a in detected]
            if hit:
                status = "provided" if len(hit) == len(axes) else "partial"
                evidence, source = f"요청문에서 축 감지: {', '.join(hit)}", "taxonomy"
        factors[fid] = {"ko": f["ko"], "status": status, "evidence": evidence, "source": source,
                        "fills_stage": f["fills"], "if_missing": f["if_missing"]}
    constraints: list[str] = []
    # 사용자 고정 규칙: 한서윤(AI 페르소나) 영상은 대사 없음 + AI임을 숨기지 않음
    seoyun = any(name in request or name in str(inputs.get("lead_character") or "") for name in SEOYUN_NAMES)
    if seoyun:
        constraints.append("ai_persona_disclosure")
    if any(p in request for p in NO_SPEECH_PATTERNS) or inputs.get("no_speech") or seoyun:
        constraints.append("no_speech")
        detected.setdefault("direction", {}).setdefault("sound", "silent")
        factors["voice"].update(status="provided", evidence="무음성(대사 없음) 제약", source="rule")
    used = sorted({a.provider for a in answers.values()})
    return IntakeResult(request, factors, detected, constraints, inputs, used)
