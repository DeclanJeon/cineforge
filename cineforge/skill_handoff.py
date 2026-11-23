"""Translate production facts into pack-owned craft guidance (not execution policy)."""
from __future__ import annotations

import re
from typing import Any

from .skill_pack_manifest import SkillPackError
from .skills import InstalledPack

CRAFT_STAGES = {'S06_storyboard', 'S07_assets', 'S08_generation', 'S09_edit', 'S10_qa'}
_REALTIME = re.compile(r'실시간\s*3d|스크롤\s*(?:기반\s*)?모션|three\.js|scroll[- ]driven\s+motion|real[- ]time\s+3d', re.I)
_MOTION = re.compile(r'모션\s*그래픽|키네틱\s*타이포|(?:제품\s*)?ui\s*데모|motion\s+graphics?|kinetic\s+type|ui\s+demo|(?:motion\s+design|code[- ]rendered)\s+showreel', re.I)
_LEGACY_REVISION = {
    'S06_storyboard': '수정 범위·보존 조건을 해당 컷과 인접 편집 경계에 연결한다.',
    'S07_assets': '수정 대상과 보존할 참조 에셋을 구분한다.',
    'S08_generation': '기존 테이크를 먼저 비교하고, 생성 결함 수정은 승인 범위에서만 검토한다.',
    'S09_edit': '대상 구간의 최소 편집·합성·믹싱 변경과 보존할 요소를 기록한다.',
    'S10_qa': '수정 전후 버전과 시간 기준, 실제 재검수 및 미확인 결과를 기록한다. 부분 검사는 전편 검수가 아니다.',
}


def craft_facts(meta: dict[str, Any], plan: dict[str, Any]) -> tuple[set[str], dict[str, Any]]:
    request = meta.get('request', '')
    spec = plan.get('production_spec', {})
    choice = spec.get('motion_recipe') or {}
    realtime = bool(_REALTIME.search(request))
    facts: set[str] = set()
    context = {}
    if realtime or choice.get('recipe') == 'realtime_3d':
        facts.add('realtime_3d')
    if realtime or _MOTION.search(request) or choice:
        facts.add('code_motion')
        for key in ('motion_recipe', 'motion_brief'):
            if spec.get(key):
                context[key] = spec[key]
    if meta.get('cut_revision'):
        facts.add('cut_revision')
        context['cut_revision'] = meta['cut_revision']
    return facts, context


def pack_fields(pack: InstalledPack, sid: str, facts: set[str]) -> dict[str, Any]:
    row = pack.binding.stages[sid]
    fields: dict[str, Any] = {
        'skill_pack': pack.provenance(), 'route': row.route, 'owner_skills': list(row.owners),
        'owner_entrypoints': [f'{owner}/SKILL.md' for owner in row.owners], 'craft_refs': row.references(facts),
    }
    if row.guide:
        fields['guide'] = row.guide
    return fields


def check_handoff_identity(packet: dict[str, Any], pack: InstalledPack) -> None:
    prior = packet.get('skill_pack')
    if not isinstance(prior, dict) or any(prior.get(k) != v for k, v in pack.binding.identity().items()):
        raise SkillPackError('invalid', f'handoff pack does not match the pin: {packet.get("stage")}')


def legacy_guidance(sid: str, facts: set[str]) -> dict[str, Any]:
    """Original in-tree directions for projects created before pack binding."""
    refs = []
    instruction = []
    if 'code_motion' in facts:
        refs.extend(['creative-production/references/motion-pipeline.md',
                     'video-production-assets/references/08b-code-motion-production.md',
                     'video-production-assets/assets/code-motion-brief-template.md'])
        instruction.append('현재 단계 작업 전에 craft_refs와 해당 오너 지침을 읽고 컷 상태·타이밍·실제 출력 검수에 반영. '
                           '참조 연결은 렌더러 선택이나 실행·과금 승인이 아님.')
    if 'realtime_3d' in facts:
        refs.append('open-3d-production/references/realtime-motion-direction.md')
    if 'cut_revision' in facts:
        refs.append('video-production-assets/references/21-generated-video-qa-retry.md')
        instruction.extend(['컷 수정 QA 참조를 읽는다. 인계는 자동 수정·실행·과금 승인이 아니다.', _LEGACY_REVISION[sid]])
    return {'craft_refs': refs, 'craft_instruction': ' '.join(instruction)} if refs else {}
