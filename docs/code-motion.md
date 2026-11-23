# 코드 모션 컷을 납품하기

제작·렌더는 `contents-production-skills`(모션 제출 검사 도입 커밋 `0fafda5` 이상), 작업 범위와 접수·납품은 CineForge가 담당한다. Node/Chrome과 FFmpeg는 스킬팩 렌더에, ffprobe/FFmpeg는 CineForge 미디어 검증 및 조립에 필요하다. CLI는 HTML을 직접 실행하지 않는다.

1. 사전 제작과 컷 ID를 확정한 후 승인 범위를 만든다. 예: `{"lanes":[{"kind":"video_cut","provider":"code-motion","model":"html-seek-v1","max_jobs":1,"cut_ids":["S01C01"]}]}`. `cineforge execution-plan PROJECT --file SCOPE.json`의 해시를 확인하고 기존 `authorize --approve-plan`으로 승인한다. `cut_ids`는 실제 SSOT 컷 ID다. 브리프가 있으면 `route_by_cut`의 코드 컷과 일치해야 한다. 미지정은 전체 코드 컷 호환 모드다. 다른 생성 공급자의 비디오 레인은 같은 범위에 추가하지 않는다.
2. `cineforge execute PROJECT --stage S08_video`로 승인된 작업 봉투를 발행한다. 스킬팩으로 렌더·검수한 결과를 `submit_code_motion.py PROJECT --file RESULTS.json`으로 제출한다. 코드 컷의 파일은 프로젝트 내부에 둔다.
3. `cineforge select-take PROJECT --cut S01C01 --path takes/c01.mp4`로 접수된 파일을 채택한다. 나머지 컷도 기존 테이크를 명시적으로 채택한다. `cineforge edit PROJECT`, `cineforge render PROJECT`로 조립한다.
4. 에셋 검증 및 `qa-final`을 통과해야 한다. 사람이 `edit/render.mp4` 전체를 확인하고 현재 해시·리뷰어·판정·관찰 및 재생 확인을 담은 보고서를 `cineforge qa-playback PROJECT --rendered --file REVIEW.json`으로 기록한다. 필드: `sha256`, `reviewer`, `verdict`(`pass`, `pass_with_notes`, `needs_revision`), `observations`, `watched_entire_video`, `heard_entire_audio`. 검수 후 파일이 달라지거나 통과 판정이 없으면 `deliver`가 차단된다. 재생 검수는 게시 승인이 아니다. `--rendered` 없는 `qa-playback`은 기존처럼 이미 납품된 파일에 대한 기록이다.
