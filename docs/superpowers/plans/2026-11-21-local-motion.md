# 로컬 모션 제작 큐

범위: `ui_state`와 `kinetic_type`에서 콘티의 구조화된 `motion` 지시를 동일한 로컬 FFmpeg 실행기에 전달한다. 우선 무음 세로 영상. 다른 레시피·임의 자산 다운로드·TTS·권한 추론은 지원하지 않는다. 기존 공급자 경로와 최종 게이트는 변경하지 않는다.

- [x] 컷 계약: UI `headline/option/reply/select_frame/reply_frame`, 타이포 `headline/detail`; ASCII 숫자 프레임과 텍스트 타입 검사. 선택/답장/읽기 순서, 연속 컷 및 타임라인 합계 검증. 실행기 스키마와 호스트 기획 지침을 연결.
- [x] 로컬 렌더 `cineforge motion`: FFmpeg 텍스트 파일로 외부 전달 없이 동일 코드 렌더. 출력 스펙·전체 디코드·입력/출력 해시 검수 영수증. 잘못된 데이터·누락 폰트·비지원 레시피는 오류.
- [x] 납품: 사용자가 검토한 영상 해시를 `cineforge motion --deliver <sha256>`로 명시한 경우에만 사본과 납품 JSON. 변경된 계획·프리뷰는 납품 거부. 테스트 프로젝트에서만 권한 경로 검증, 실제 납품은 사용자 확인 전 보류.
- [x] UI/타이포 테스트, 기존 실제 호스트 기획의 복사본 로컬 프리뷰, 기술 검사/대표 프레임 기록. 커밋·푸시는 밖.

검증: CineForge 133 통과, 2 건너뜀. `~/Documents/Media_Studio/mbti-motion-local-MaWRdk/qa/motion-preview.mp4`: 15초, 450프레임, 무음. 앞선 호스트 콘티를 복사하고 구조화 데이터를 채워 동일 실행기로 제작했다. 시각 샘플에서 선택 전/선택 후/답장 순서를 확인. 새 자유 브리프부터 전체 무인 실행을 검증한 것은 아니다. 실제 프리뷰에 사용자 납품 승인 미기록; 승인/오류 해시/입력 변경은 격리 테스트로 검증.

## 새 브리프 후속 검증
`~/Documents/Media_Studio/motion-e2e-UZY7zJ/{ui,type,control}`. 실제 host 인계로 새 세 브리프를 작성. G2 1회에서 무음과 기본 오디오 큐 충돌, UI 읽기 시간, 대조군 등장인물 누락을 발견하고 수정. 2회에서 수정 확인. UI/타이포는 S08 외부 실행 대신 로컬 모션 렌더로 안내되고 `execute`는 거부. 둘 다 15초(450프레임) 무음 세로 MP4 출력. UI 프레임 155/156/179/180과 타이포 세 카드 확인. 대조군에는 motion recipe를 넣지 않았고 로컬 렌더 거부 확인. 시각 결과물은 사용자 납품 전. 최종 전체 테스트 134 passed, 2 skipped.

## 확장: 순차 단계도
- [x] `diagram_data` 중 무음 9:16 순차 절차(`steps` 2–3개, `reveal_frames`)를 FFmpeg로 렌더. 숫자 데이터나 분기형 차트는 지원하지 않음. 마지막 단계 공개 뒤 최소 30프레임 유지.
- [x] 실제 호스트·G2·CLI로 `~/Documents/Media_Studio/library-steps-motion/qa/motion-preview.mp4` 제작. 450프레임, 전체 디코드 통과. 첫 두 번째 카드의 공개 경계(35→36) 픽셀 차이 및 4개 대표 화면 확인. 납품 승인 미기록.
- [x] 신규 회귀 RED 2개 재현 → 구현 후 통과. CineForge 전체 136 passed, 2 skipped.

## 확장: 형태 변환
- [x] `shape_morph`: 사각형·둥근 사각형·원 사이에서 중심을 고정하고 윤곽을 보간. 결과 문구는 종료 프레임 이후, 최소 1초 유지. 임의 SVG나 로고 변환은 아님.
- [x] 호스트/G2/CLI로 `~/Documents/Media_Studio/rounded-heart-motion/qa/motion-preview.mp4` 출력. 450프레임 전체 디코드 및 프레임 75/200/299/300 대표 화면 확인. 299에는 결과 문구가 없고 300부터 보임. 납품·푸시 미실행.
- [x] 형태 변환 테스트 RED 2개에서 구현 후 GREEN, 전체 138 passed, 2 skipped.
