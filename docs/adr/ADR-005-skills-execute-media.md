# ADR-005 유료 생성·편집은 스킬이 실행, CineForge는 인계·증거만

- 상황: 생성 공급자·모델·가격은 자주 바뀌고, 스킬 패키지에 실행 게이트(실시간 스키마·권리·비용 확인)가 이미 있다.
- 결정: S08–S11은 `handoffs/<단계>.json`을 만들고, 권한이 없으면 blocked. 스킬이 실행한 뒤 `cineforge complete --evidence`로만 완료된다.
- 결과: CineForge는 유료 API 키·호출이 없다. 실행 품질과 공급자 선택은 스킬 책임.
