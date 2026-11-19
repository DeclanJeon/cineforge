# 03. 콘셉트 분류 체계(Taxonomy)

원본: `cineforge/data/taxonomy.yaml` (v1.0.0). 이 문서는 그 데이터를 그대로 펼친 것이며, 수정은 YAML에서 한다. 스킬 저장소 사본은 `cineforge taxonomy --export ... --with-rules`로 동기화하고 테스트가 바이트 일치를 확인한다.

## 표기

- `select`: one(하나) · many(여러 개, max) · per_group(연출처럼 하위 축마다 하나) · arc(감정 곡선, 순서 있는 2~3개)
- `source: user`는 사용자가 준 목록, `proposed`는 설계 중 보완한 항목이다.
- 최종 12축 분류의 축 번호는 `final_axis`.

## 선택 순서

format → culture_style → era → genre → subgenre → romance_concept → world → story_nature → setting → relationship → narrative → direction → emotion_arc → visual_aesthetic → production_method → hook → duration → aspect

## 콘텐츠 형식 (`format`)

select=one · 필수 · 최종 분류 축 1 · 항목 89개

- **드라마·극영화** [user] · 9개: 숏드라마(`short_drama`); 웹드라마(`web_drama`); 마이크로드라마(`micro_drama`); 단편영화(`short_film`); 시트콤(`sitcom`); 스케치 코미디(`sketch_comedy`); 옴니버스(`omnibus`); 미니시리즈(`miniseries`); 인터랙티브 드라마(`interactive_drama`)
- **영화적 영상** [user] · 7개: 시네마틱 쇼트(`cinematic_short`); 무성영화(`silent_film`); 실험영화(`experimental_film`); 비주얼 포엠(`visual_poem`); 콘셉트 필름(`concept_film`); 무드 필름(`mood_film`); 트레일러형 영화(`trailer_film`)
- **다큐멘터리** [user] · 8개: 숏다큐(`short_doc`); 휴먼다큐(`human_doc`); 관찰다큐(`observational_doc`); 자연다큐(`nature_doc`); 역사다큐(`history_doc`); 범죄다큐(`crime_doc`); 페이크 다큐(`fake_doc`); 모큐멘터리(`mockumentary`)
- **예능·엔터테인먼트** [user] · 8개: 리얼리티쇼(`reality_show`); 버라이어티(`variety`); 몰래카메라(`hidden_camera`); 챌린지(`challenge`); 상황극(`situation_play`); 패러디(`parody`); 리액션(`reaction`); 게임쇼(`game_show`)
- **정보·교육** [user] · 8개: 설명형 영상(`explainer`); 인포테인먼트(`infotainment`); 튜토리얼(`tutorial`); 강의(`lecture`); 지식 숏폼(`knowledge_short`); 팩트체크(`fact_check`); 실험·검증(`experiment`); 비교 분석(`comparison`)
- **광고·브랜디드** [user] · 8개: CF(`cf`); 브랜드 필름(`brand_film`); 제품 광고(`product_ad`); UGC 광고(`ugc_ad`); 바이럴 광고(`viral_ad`); 패션 필름(`fashion_film`); 티저(`teaser`); 캠페인 필름(`campaign_film`)
- **음악·퍼포먼스** [user] · 6개: 뮤직비디오(`music_video`); 리릭비디오(`lyric_video`); 댄스필름(`dance_film`); 퍼포먼스 비디오(`performance_video`); 라이브 세션(`live_session`); 비주얼라이저(`visualizer`)
- **애니메이션** [user] · 7개: 2D 애니메이션(`anim_2d`); 3D 애니메이션(`anim_3d`); 스톱모션(`stop_motion`); 스틱맨(`stickman`); 모션코믹(`motion_comic`); 애니매틱(`animatic`); 컷아웃 애니메이션(`cutout_animation`)
- **일상·라이프스타일** [user] · 7개: 브이로그(`vlog`); 시네마틱 브이로그(`cinematic_vlog`); 여행기(`travelogue`); 일상 기록(`daily_record`); 루틴(`routine`); 감성 에세이(`emotional_essay`); 성장 기록(`growth_record`)
- **인터뷰·토크** [user] · 7개: 인터뷰(`interview`); 토크쇼(`talk_show`); 팟캐스트 영상(`podcast_video`); 거리 인터뷰(`street_interview`); 토론(`debate`); 상담(`counseling`); 1인 독백(`monologue`)
- **실험·몰입형** [user] · 7개: POV 영상(`pov_video`); 1인칭 체험(`first_person`); 파운드 푸티지(`found_footage`); 스크린라이프(`screenlife`); ASMR(`asmr`); 슬로 시네마(`slow_cinema`); 초현실 영상(`surreal_video`)
- **소셜·참여형** [user] · 7개: 밈(`meme`); 숏폼 챌린지(`shortform_challenge`); 댓글 기반 콘텐츠(`comment_based`); 선택형 스토리(`choice_story`); 듀엣(`duet`); 리믹스(`remix`); 인터랙티브 영상(`interactive_video`)

## 국가·문화권 / 드라마 스타일 (`culture_style`)

select=one · 선택 · 최종 분류 축 2 · 항목 22개

- **한국** [user] · 5개: K-드라마(`k_drama`) — 강한 감정선, 인물 관계, 로맨스, 반전; 한국 막장 드라마(`kr_makjang`) — 출생의 비밀, 불륜, 복수, 재벌가 갈등; 한국 일일드라마(`kr_daily`) — 가족 갈등, 생활 밀착형 서사; 한국 주말드라마(`kr_weekend`) — 가족애, 세대 갈등, 결혼; 한국 청춘드라마(`kr_youth`) — 첫사랑, 우정, 성장, 취업
- **일본** [user] · 4개: 일본 트렌디 드라마(`jp_trendy`) — 도시 생활, 연애, 직장인 감성; 일본 순정 드라마(`jp_pure_romance`) — 섬세한 감정, 짝사랑, 잔잔한 로맨스; 일본 학원물(`jp_school`) — 동아리, 학교생활, 청춘; 일본 특촬물(`jp_tokusatsu`) — 변신 히어로, 괴수, 실물 특수효과
- **중국·대만** [user] · 5개: 중국 고장극(`cn_costume`) — 중국 고대 배경의 궁중·시대극; 중국 선협극(`cn_xianxia`) — 신선, 수련, 윤회, 초월적 사랑; 중국 무협극(`cn_wuxia`) — 강호, 문파, 무공, 복수; 중국 현대로맨스(`cn_modern_romance`) — 도시, 계약연애, 재벌 로맨스; 대만 청춘 로맨스(`tw_youth_romance`) — 학창 시절 첫사랑, 추억, 감성
- **미국·유럽** [user] · 4개: 미국 하이틴 드라마(`us_highteen`) — 학교 내 계층, 파티, 연애, 정체성; 미국 시트콤(`us_sitcom`) — 상황 중심 코미디, 재치 있는 대사; 영국 범죄 드라마(`uk_crime`) — 절제된 연기, 수사, 심리전; 북유럽 느와르(`nordic_noir`) — 차가운 색감, 어두운 범죄 미스터리
- **기타 문화권** [user] · 4개: 인도 볼리우드(`bollywood`) — 극적 감정, 음악, 춤, 가족 서사; 튀르키예 멜로드라마(`turkish_melo`) — 가족, 운명적 사랑, 격정적인 감정; 라틴 텔레노벨라(`telenovela`) — 사랑, 배신, 가족 비밀, 극적인 반전; 태국 BL·GL 드라마(`thai_bl_gl`) — 관계 중심 로맨스, 성장, 감정 갈등

## 시대·시대감 (`era`)

select=one · 선택 · 최종 분류 축 3 · 항목 13개

- **역사** [user] · 1개: 조선시대(`joseon`)
- **역사(보강)** [proposed] · 6개: 삼국·고려시대(`three_kingdoms_kr`); 고대 중국(`ancient_china`); 중세 유럽(`medieval_europe`); 19세기·개화기(`c19`); 1970년대(`y1970s`); 1980년대(`y1980s`)
- **근현대** [user] · 4개: 1990년대(`y1990s`); Y2K(`y2k`); 현대(`present`); 근미래(`near_future`)
- **근현대(보강)** [proposed] · 2개: 2010년대(`y2010s`); 먼 미래(`far_future`)

## 핵심 장르 (`genre`)

select=many · 필수 · 최대 2개 · 최종 분류 축 4 · 항목 11개

- **로맨스·감성** [user] · 2개: 로맨스(`romance`); 멜로·감성(`melodrama`)
- **공포·스릴러** [user] · 2개: 공포(`horror`); 스릴러(`thriller`)
- **판타지·SF·액션** [user] · 3개: 판타지(`fantasy`); SF(`sf`); 액션(`action`)
- **코미디·풍자** [user] · 2개: 코미디(`comedy`); 풍자(`satire`)
- **드라마(보강)** [proposed] · 2개: 드라마(`drama`); 미스터리(`mystery`)

## 하위 장르 (`subgenre`)

select=many · 선택 · 최대 3개 · 최종 분류 축 5 · 항목 31개

- **로맨스·감성** [user] · 8개: 첫사랑(`first_love`); 재회(`reunion`); 짝사랑(`crush`); 이별(`breakup`); 가족애(`family_love`); 휴먼드라마(`human_drama`); 성장물(`coming_of_age`); 힐링(`healing`)
- **공포·스릴러** [user] · 8개: 좀비(`zombie`); 심리공포(`psychological_horror`); 미스터리(`mystery`); 서스펜스(`suspense`); 생존(`survival`); 재난(`disaster`); 범죄(`crime`); 추리(`detective`)
- **판타지·SF·액션** [user] · 8개: 무협(`murim`); 선협(`xianxia`); 초능력(`superpower`); 타임루프(`time_loop`); 평행세계(`parallel_world`); 디스토피아(`dystopia`); 괴수(`kaiju`); 사이버펑크(`cyberpunk`)
- **코미디·풍자** [user] · 7개: 블랙코미디(`black_comedy`); 일상 코미디(`everyday_comedy`); 로맨틱 코미디(`romcom`); 부조리극(`absurdist`); 사회풍자(`social_satire`); 패러디(`parody`); 슬랩스틱(`slapstick`)

## 로맨스 콘셉트 (`romance_concept`)

select=one · 선택 · 최종 분류 축 5 · 항목 24개

- **로맨스 콘셉트** [user] · 24개: 정통 로맨스(`classic_romance`) — 두 사람의 사랑과 관계 변화; 로맨틱 코미디(`romantic_comedy`) — 사랑과 유머; 로맨스 판타지(`romance_fantasy`) — 마법, 운명, 귀족, 이세계; 시대극 로맨스(`period_romance`) — 역사적 배경 속 사랑; 궁중 로맨스(`palace_romance`) — 왕족, 신분 차이, 궁중 정치; 재벌 로맨스(`chaebol_romance`) — 신분 차이, 계약연애; 오피스 로맨스(`office_romance`) — 직장 동료, 상사와 부하; 학원 로맨스(`school_romance`) — 첫사랑, 짝사랑, 우정; 청춘 로맨스(`youth_romance`) — 성장, 불완전한 사랑; 타임슬립 로맨스(`timeslip_romance`) — 과거와 현재를 넘나드는 사랑; 회귀 로맨스(`regression_romance`) — 과거로 돌아가 사랑을 다시 선택; 환생 로맨스(`reincarnation_romance`) — 전생의 인연; 빙의 로맨스(`possession_romance`) — 소설·게임 속 인물로 살아가기; 계약결혼 로맨스(`contract_marriage`) — 가짜 관계에서 진짜 사랑으로; 혐관 로맨스(`enemies_to_lovers`) — 서로 싫어하다 사랑하게 되는 관계; 구원 로맨스(`salvation_romance`) — 서로의 상처를 치유; 집착 로맨스(`obsession_romance`) — 강한 소유욕과 관계 갈등; 금지된 사랑(`forbidden_love`) — 사회적·개인적 제약; 삼각관계 로맨스(`love_triangle`) — 세 사람의 감정 갈등; 재회 로맨스(`reunion_romance`) — 헤어진 연인들의 재회; 기억상실 로맨스(`amnesia_romance`) — 잃어버린 기억과 사랑; 좀비 로맨스(`zombie_romance`) — 생존 상황 속 사랑; 뱀파이어 로맨스(`vampire_romance`) — 인간과 초자연적 존재의 사랑; AI 로맨스(`ai_romance`) — 인간과 인공지능 사이의 관계

## 세계관 (`world`)

select=one · 선택 · 최종 분류 축 6 · 항목 29개

- **기본 세계관** [user] · 5개: 현실(`reality`); 대체역사(`alt_history`); 마법(`magic`); 아포칼립스(`apocalypse`); 이세계(`isekai_base`)
- **판타지·세계관 콘셉트** [user] · 24개: 하이 판타지(`high_fantasy`) — 독립된 세계, 종족, 마법 체계; 로우 판타지(`low_fantasy`) — 현실 세계에 초자연적 요소 개입; 어반 판타지(`urban_fantasy`) — 현대 도시와 마법의 결합; 다크 판타지(`dark_fantasy`) — 잔혹하고 어두운 판타지 세계; 로맨스 판타지(`romance_fantasy_world`) — 사랑, 마법, 귀족, 운명; 동양 판타지(`oriental_fantasy`) — 신선, 요괴, 도술, 영물; 무협(`murim_world`) — 강호, 무공, 문파, 비급; 선협(`xianxia_world`) — 수련, 영생, 신선, 천계; 퓨전 사극(`fusion_sageuk`) — 역사와 판타지의 결합; 이세계물(`isekai`) — 다른 세계로 이동; 회귀물(`regression`) — 과거 시점으로 돌아감; 환생물(`reincarnation`) — 새로운 인생으로 다시 태어남; 빙의물(`possession`) — 다른 인물의 몸이나 역할로 들어감; 헌터물(`hunter`) — 던전, 몬스터, 능력자; 아카데미물(`academy`) — 특수 능력을 배우는 학교; 시스템물(`system`) — 퀘스트, 레벨업, 상태창; 성좌물(`constellation`) — 초월적 존재의 후원과 경쟁; 게임 판타지(`game_fantasy`) — 게임 규칙이 현실을 지배; 스팀펑크(`steampunk`) — 증기기관 기반의 가상 기술 문명; 사이버펑크(`cyberpunk_world`) — 고도 기술과 사회적 불평등; 디젤펑크(`dieselpunk`) — 산업·전쟁 시대의 복고 미래상; 포스트 아포칼립스(`post_apocalypse`) — 문명 붕괴 이후의 세계; 좀비 아포칼립스(`zombie_apocalypse`) — 감염과 생존; 코즈믹 호러(`cosmic_horror`) — 인간이 이해할 수 없는 우주적 공포

## 이야기 성격 (`story_nature`)

select=one · 선택 · 최종 분류 축 5 · 항목 23개

- **이야기 성격별 콘셉트** [user] · 23개: 막장 드라마(`makjang`) — 극단적인 관계 갈등과 충격적 사건; 사이다 드라마(`cider`) — 억울함을 통쾌하게 해결; 복수극(`revenge`) — 배신과 응징; 피카레스크(`picaresque`) — 도덕적으로 결함 있는 인물이 중심; 안티히어로물(`antihero`) — 전형적인 영웅과 다른 주인공; 성장 드라마(`growth_drama`) — 인물의 내적 변화; 치유·힐링 드라마(`healing_drama`) — 상처 회복, 위로; 가족 드라마(`family_drama`) — 부모, 자녀, 형제 관계; 직장 드라마(`workplace_drama`) — 조직과 인간관계; 법정 드라마(`legal_drama`) — 재판, 정의, 갈등; 메디컬 드라마(`medical_drama`) — 의료 현장의 인간관계; 정치 드라마(`political_drama`) — 권력, 음모, 선택; 범죄 수사물(`crime_investigation`) — 사건 해결과 추적; 심리 스릴러(`psychological_thriller`) — 인간 심리와 불신; 데스게임(`death_game`) — 생존 경쟁과 선택; 재난 드라마(`disaster_drama`) — 위기 상황의 인간 군상; 밀실극(`locked_room`) — 제한된 공간에서 벌어지는 갈등; 군상극(`ensemble`) — 여러 인물의 이야기가 교차; 옴니버스극(`omnibus_story`) — 독립된 여러 이야기; 페이크 다큐(`fake_documentary`) — 실제 기록처럼 연출한 허구; 블랙코미디(`black_comedy_story`) — 불편한 현실을 웃음으로 풍자; 부조리 코미디(`absurd_comedy`) — 비논리적 상황 자체에서 웃음 유발; 일상물(`slice_of_life`) — 특별한 사건보다 일상의 감정과 관계 중심

## 소재·배경 (`setting`)

select=many · 선택 · 최대 3개 · 최종 분류 축 7 · 항목 20개

- **소재·배경** [user] · 6개: 학교(`school`); 직장(`workplace`); 재벌가(`chaebol_house`); 궁전(`palace`); 교회(`church`); 병원(`hospital`)
- **소재·배경(보강)** [proposed] · 14개: 면접실(`interview_room`); 카페(`cafe`); 편의점(`convenience_store`); 지하철(`subway`); 아파트(`apartment`); 옥상(`rooftop`); 골목(`alley`); 공중전화 부스(`phone_booth`); 법정(`courtroom`); 경찰서(`police_station`); 시골(`countryside`); 바닷가(`seaside`); 도서관(`library`); 방송국(`broadcast_station`)

## 인물 관계 (`relationship`)

select=many · 선택 · 최대 2개 · 최종 분류 축 8 · 항목 12개

- **인물 관계** [user] · 5개: 첫사랑(`first_love_rel`); 혐관(`enemies`); 계약결혼(`contract_marriage_rel`); 라이벌(`rival`); 가족(`family`)
- **인물 관계(보강)** [proposed] · 7개: 전 연인(`ex_lovers`); 짝사랑(`unrequited`); 상사-부하(`boss_subordinate`); 친구(`friends`); 선후배(`senior_junior`); 낯선 사람(`strangers`); 운명적 인연(`fated`)

## 서사 구조 (`narrative`)

select=one · 필수 · 최종 분류 축 9 · 항목 12개

- **스토리 전개 콘셉트** [user] · 12개: 결말 선공개형(`ending_first`, hook_weight=0.9, complexity=2) — 가장 충격적인 결말부터 보여주고 과거로 돌아감; 반전형(`twist`, hook_weight=0.7, complexity=2) — 마지막 장면에서 앞선 사건의 의미가 뒤집힘; 미스터리 회수형(`mystery_payoff`, hook_weight=0.8, complexity=2) — 처음 제시한 의문을 마지막에 해결; 타임루프형(`time_loop_structure`, hook_weight=0.7, complexity=3) — 같은 사건이 반복되지만 매번 새로운 사실이 드러남; 카운트다운형(`countdown`, hook_weight=0.8, complexity=1) — 제한 시간 안에 목표를 달성해야 함; 갈등 증폭형(`escalation`, hook_weight=0.6, complexity=1) — 작은 오해가 점차 커다란 사건으로 발전; 감정 반전형(`emotional_reversal`, hook_weight=0.6, complexity=2) — 코미디로 시작해 감동이나 비극으로 마무리; 복선 회수형(`foreshadow_payoff`, hook_weight=0.6, complexity=2) — 평범한 소품이나 행동이 결말의 핵심이 됨; 평행 서사형(`parallel`, hook_weight=0.5, complexity=3) — 서로 다른 두 인물의 이야기가 교차하다 연결됨; 열린 결말형(`open_ending`, hook_weight=0.5, complexity=1) — 해석을 시청자에게 맡겨 댓글과 토론 유도; 인과 역전형(`reverse_causality`, hook_weight=0.8, complexity=2) — 결과를 먼저 보여주고 원인을 역추적; 반복 변주형(`repetition_variation`, hook_weight=0.6, complexity=2) — 비슷한 상황을 반복하되 매번 예상과 다르게 변화

## 연출 콘셉트 (`direction`)

select=per_group · 필수 · 최종 분류 축 11 · 항목 42개

- **영상 질감** [user] · 6개: 포토리얼(`photoreal`); 시네마틱(`cinematic`); 필름룩(`film_look`); VHS(`vhs`); 레트로(`retro`); 다큐멘터리풍(`documentary_style`)
- **시점** [user] · 5개: 1인칭 POV(`pov`); 3인칭 관찰(`third_person`); CCTV(`cctv`); 바디캠(`bodycam`); 드론 시점(`drone`)
- **카메라** [user] · 5개: 원테이크(`one_take`, ai_difficulty=3); 핸드헬드(`handheld`, ai_difficulty=1); 고정 카메라(`locked_off`, ai_difficulty=0); 롱테이크(`long_take`, ai_difficulty=3); 빠른 카메라 워크(`fast_camera`, ai_difficulty=2)
- **화면 표현** [user] · 6개: 실사(`live_action`); 2D(`two_d`); 3D(`three_d`); 스톱모션(`stop_motion_expr`); 모션코믹(`motion_comic_expr`); 실사 애니매틱(`live_animatic`)
- **편집 리듬** [user] · 5개: 초고속 몽타주(`hyper_montage`, avg_cut_s=0.8); 리드미컬 컷(`rhythmic_cut`, avg_cut_s=2.0); 매치컷(`match_cut`, avg_cut_s=2.5); 점프컷(`jump_cut`, avg_cut_s=1.5); 롱테이크 중심(`long_take_based`, avg_cut_s=8.0)
- **색채·조명** [user] · 6개: 느와르(`noir`); 하이키(`high_key`); 로우키(`low_key`); 네온(`neon`); 파스텔(`pastel`); 흑백(`black_white`)
- **현실성** [user] · 4개: 극사실주의(`hyperrealism`); 초현실주의(`surrealism`); 마법적 리얼리즘(`magical_realism`); 몽환적 표현(`dreamlike`)
- **사운드** [user] · 5개: 무성(`silent`); 대사 중심(`dialogue_driven`); 내레이션 중심(`narration_driven`); 음악 중심(`music_driven`); ASMR(`asmr_sound`)

## 감정 목표(감정 곡선) (`emotion_arc`)

select=arc · 필수 · 최대 3개 · 최종 분류 축 10 · 항목 16개

- **감정 목표** [user] · 12개: 감동(`moved`); 긴장(`tension`); 웃음(`laughter`); 공감(`empathy`); 충격(`shock`); 설렘(`flutter`); 카타르시스(`catharsis`); 슬픔(`sadness`); 씁쓸함(`bitterness`); 먹먹한 감동(`lingering`); 호기심(`curiosity`); 불안(`anxiety`)
- **감정 목표(보강)** [proposed] · 4개: 공포(`fear`); 향수(`nostalgia`); 위로(`comfort`); 짜릿함(`thrill`)

## 시각적 미학 (`visual_aesthetic`)

select=one · 선택 · 최종 분류 축 11 · 항목 10개

- **시각적 미학** [user] · 5개: 레트로(`retro_analog`); 시네마틱(`cinematic_aes`); 느와르(`noir_aes`); 몽환적(`dreamy`); 하이틴(`highteen`)
- **시각적 미학(보강)** [proposed] · 5개: 미니멀(`minimal`); 빈티지 필름(`vintage_film`); Y2K 감성(`y2k_aes`); 사이버 네온(`cyber_neon`); 동화풍(`fairytale`)

## 제작 표현 방식 (`production_method`)

select=one · 필수 · 최종 분류 축 12 · 항목 8개

- **제작 표현 방식** [user] · 5개: 실사(`live_action_ai`, ai_difficulty=2); 2D(`two_d_anim`, ai_difficulty=1); 3D(`three_d_anim`, ai_difficulty=2); 스틱맨(`stickman_method`, ai_difficulty=0); 실사 애니매틱(`live_animatic_method`, ai_difficulty=1)
- **제작 표현 방식(보강)** [proposed] · 3개: 스톱모션(`stop_motion_method`, ai_difficulty=2); 모션코믹(`motion_comic_method`, ai_difficulty=1); 스틸 이미지 기반(`stills_only`, ai_difficulty=0)

## 후킹 전략 (`hook`)

select=one · 선택 · 항목 7개

- **후킹 전략** [proposed] · 7개: 결말 콜드 오픈(`cold_open_ending`) — 결말 장면/대사로 0~3초를 연다; 충격 대사(`shock_line`) — 맥락 없는 한 줄 대사로 시작; 질문형 자막(`question_caption`) — 시청자가 답을 궁금해할 질문 자막; 시각적 이상 징후(`visual_anomaly`) — 첫 프레임에 이상한 것 하나; 카운트다운 자막(`countdown_caption`) — 남은 시간 표시로 긴장; 공감 상황 제시(`relatable_situation`) — '이런 적 있지?' 형 일상 상황; 반전 예고(`twist_tease`) — '끝까지 보면…' 형 예고

## 영상 길이 (`duration`)

select=one · 필수 · 항목 4개

- **영상 길이(초)** [user] · 4개: 15초(`s15`, seconds=15); 30초(`s30`, seconds=30); 60초(`s60`, seconds=60); 90초(`s90`, seconds=90)

## 화면비 (`aspect`)

select=one · 필수 · 항목 4개

- **화면비** [proposed] · 4개: 9:16 세로(`r9_16`); 16:9 가로(`r16_9`); 1:1 정사각(`r1_1`); 4:5 피드(`r4_5`)

총 18개 축, 377개 항목.

## 프리셋

| id | 이름 | 선택값 |
|---|---|---|
| concept_a_zombie | 콘셉트 A — 60초 좀비 숏드라마 | `{"format": "short_drama", "genre": ["horror"], "subgenre": ["zombie", "survival"], "narrative": "ending_first", "direction": {"expression": "live_animatic"}, "production_method": "live_animatic_method", "emotion_arc": ["tension", "sadness"], "duration": "s60", "aspect": "r9_16"}` |
| concept_b_stickman | 콘셉트 B — 30초 스틱맨 블랙코미디 | `{"format": "sketch_comedy", "genre": ["comedy", "satire"], "subgenre": ["social_satire", "black_comedy"], "narrative": "escalation", "direction": {"sound": "silent", "expression": "two_d"}, "production_method": "stickman_method", "emotion_arc": ["laughter", "bitterness"], "duration": "s30", "aspect": "r9_16"}` |
| concept_c_first_love | 콘셉트 C — 90초 첫사랑 숏시네마 | `{"format": "short_film", "genre": ["romance"], "subgenre": ["first_love"], "narrative": "foreshadow_payoff", "direction": {"texture": "cinematic", "expression": "live_action"}, "production_method": "live_action_ai", "emotion_arc": ["flutter", "lingering"], "duration": "s90", "aspect": "r9_16"}` |
| sample_comedy_ending_first | 샘플 — 60초 코미디 숏드라마 · 시네마틱 실사 · 결말 선공개 | `{"format": "short_drama", "genre": ["comedy"], "subgenre": ["romcom"], "narrative": "ending_first", "direction": {"texture": "cinematic", "expression": "live_action"}, "production_method": "live_action_ai", "emotion_arc": ["shock", "laughter"], "duration": "s60", "aspect": "r9_16"}` |
| kdrama_1998_timeslip | 예시 — K-드라마 × 1990년대 × 로맨스 판타지 × 타임슬립 × 레트로 × 결말 선공개 | `{"format": "short_drama", "culture_style": "k_drama", "era": "y1990s", "genre": ["romance", "fantasy"], "romance_concept": "timeslip_romance", "narrative": "ending_first", "visual_aesthetic": "retro_analog", "direction": {"texture": "vhs"}, "production_method": "live_action_ai", "emotion_arc": ["curiosity", "flutter", "lingering"], "duration": "s60", "aspect": "r9_16"}` |
