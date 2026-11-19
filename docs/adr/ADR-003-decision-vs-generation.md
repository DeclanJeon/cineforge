# ADR-003 Jev는 판단 전용, 문장 생성은 호스트 AI/별도 모델

- 상황: Jev 1.14는 Choice/Score/Noul/Box 같은 typed 답을 주는 판단 모델이다. 기획안·대본 같은 긴 문장을 쓰는 모델이 아니다.
- 결정: 판단 체인(요소 판정·추천·평가)과 생성 체인(기획안 등)을 분리한다. 생성은 호스트 AI(agent_io) 또는 `CINEFORGE_GEN_MODEL`로 지정한 OpenRouter 모델.
- 결과: Jev가 없어도 호스트 AI가 같은 질문 형식으로 답하므로 동작이 같다.
