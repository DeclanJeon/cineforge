# ADR-001 별도 프로젝트 cineforge, Python CLI + YAML/JSON 데이터

- 상황: 스킬은 지시문이라 상태 기계·진행률·스키마 검증·대화형 선택을 직접 실행할 수 없다.
- 결정: `01_Persnal_Work/cineforge`에 Python 3.10+ CLI(argparse, PyYAML, 선택 jsonschema)를 만든다. 분류·규칙·파이프라인은 YAML, 산출물은 JSON 스키마.
- 결과: 의존성이 적고 호스트 에이전트(Codex/Claude Code)에서 바로 실행 가능. 웹 UI는 범위 밖.
