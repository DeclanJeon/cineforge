"""Deterministic first-hop routing: is this a CineForge production request?

The agent cannot rely on skill-description similarity alone. This command is the
single question a coordinator asks before planning: production or not.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CASES = Path(__file__).with_name('data') / 'routing_cases.json'

PRODUCTION = re.compile(
    r'영상|콘텐츠|드라마|숏폼|숏드라마|릴스|쇼츠|광고|브랜드\s*필름|뮤직비디오|다큐|애니|'
    r'콘티|스토리보드|스토리\s*보드|편집|자막|bgm|ost|효과음|내레이션|더빙|립싱크|'
    r'컷|씬|테이크|렌더|시나리오|대본|캐릭터\s*시트|의상|소품|공간\s*시트|'
    r'video|film|storyboard|reel|shorts|edit', re.IGNORECASE)
TROUBLE = re.compile(r'안\s*(돼|됨|열|나와|재생)|오류|버그|에러|설치|업데이트|와이파이|로그인\s*안|실패|로그|디버그|원인')
NON_PRODUCTION = re.compile(r'코드|함수|서버|api|데이터베이스|번역|요약|이메일|보고서|회의록|질문|설명해|알려줘')
SINGLE_IMAGE = re.compile(r'이미지\s*(한\s*)?장|사진\s*(한\s*)?장|로고|아이콘|썸네일')
EXPLICIT = re.compile(r'영상\s*(만들|제작|기획)|콘텐츠\s*(만들|제작)|드라마\s*(만들|제작)|제작해|만들어줘|편집해')
DIRECT = re.compile(r'만들어\s*줘|제작해|편집해|기획해|렌더|뽑아\s*줘|써\s*줘|구성해')
ADVISORY = re.compile(r'주의할\s*점|방법|어떻게|추천|설명|알려줘|장단점|차이|비교|아이디어|견적|비용|가격|얼마')


def judge(request: str) -> dict[str, object]:
    text = request.strip()
    production = bool(PRODUCTION.search(text))
    trouble = bool(TROUBLE.search(text))
    non_production = bool(NON_PRODUCTION.search(text))
    single_image = bool(SINGLE_IMAGE.search(text)) and not re.search(r'영상|드라마|콘티|스토리보드', text)
    explicit = bool(EXPLICIT.search(text))
    direct = bool(DIRECT.search(text))
    advisory = bool(ADVISORY.search(text))
    if not text:
        return {'route': 'other', 'confidence': 0.0, 'reasons': ['empty'], 'next': None}
    if advisory and not direct:
        return {'route': 'other', 'confidence': 0.85, 'reasons': ['advisory_intent'], 'next': None}
    if trouble and not explicit:
        return {'route': 'other', 'confidence': 0.9, 'reasons': ['troubleshooting'], 'next': None}
    if single_image:
        return {'route': 'other', 'confidence': 0.85, 'reasons': ['single_image'], 'next': 'imagegen'}
    if production and not non_production:
        confidence = 0.95 if explicit else 0.9
        return {'route': 'cineforge', 'confidence': confidence, 'reasons': ['production_cue', 'explicit' if explicit else 'context'],
                'next': 'cineforge new "<요청 원문>" --provider host'}
    if production and non_production:
        confidence = 0.55 if explicit else 0.4
        return {'route': 'cineforge' if explicit else 'other', 'confidence': confidence,
                'reasons': ['mixed_intent'], 'next': 'cineforge new "<요청 원문>" --provider host' if explicit else None}
    return {'route': 'other', 'confidence': 0.8, 'reasons': ['no_production_cue'], 'next': None}


def cases() -> list[dict[str, str]]:
    return json.loads(CASES.read_text(encoding='utf-8'))['cases']


def evaluate() -> dict[str, object]:
    rows = cases()
    correct = 0
    misses = []
    for row in rows:
        result = judge(row['request'])
        if result['route'] == row['expect']:
            correct += 1
        else:
            misses.append({'request': row['request'], 'expect': row['expect'], 'got': result['route']})
    total = len(rows)
    return {'total': total, 'correct': correct, 'accuracy': round(correct / total, 3) if total else 0.0, 'misses': misses}
