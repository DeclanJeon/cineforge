# 릴리스 노트 작성 규칙

GitHub 릴리스 본문은 CineForge 랜딩(https://github.com/DeclanJeon/cineforge-landing)의 개발노트 원본이다.
태그를 push하면 `release.yml`이 `docs/release-notes/<버전>.md`를 본문으로 발행하고 랜딩에 동기화 신호를 보낸다.

## 형식

아래 제목을 그대로 쓴다. 한국어 구획을 먼저, 영어 구획을 뒤에 둔다. 해당 내용이 없는 구획은 생략한다.
`## 요약` 또는 `## Summary` 중 하나는 반드시 있어야 한다(없으면 릴리스가 실패한다).

```
## 요약
## 새 기능
## 개선
## 수정
## 호환성
## Summary
## New
## Improved
## Fixed
## Compatibility
```

- 요약은 한두 문장 문단, 나머지는 `- `로 시작하는 목록.
- 인라인 `코드`, **굵게**, [링크](https://...)만 랜딩에 렌더된다. HTML·표·이미지는 쓰지 않는다.

## 내용

- 사용자가 체감하는 변화를 쓴다: 무엇을 새로 할 수 있는지, 무엇이 달라졌는지, 기존 프로젝트에 영향이 있는지.
- 내부 경로, QA 기록, 측정 로그, 토큰·키, 아직 출시하지 않은 내용은 쓰지 않는다. `CHANGELOG.md`는 버전별 요약만 둔다.
- 호환성에는 필요한 스킬팩 버전과 기존 프로젝트 영향을 적는다.

## 발행 절차

1. `pyproject.toml` version과 `cineforge/__init__.py`의 버전을 올리고 `CHANGELOG.md`에 한 줄 요약을 추가한다.
2. `docs/release-notes/<버전>.md`를 위 형식으로 작성한다.
3. 커밋 후 `git tag v<버전> && git push origin v<버전>`.
