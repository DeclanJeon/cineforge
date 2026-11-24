# 미디어 제작 프로바이더 MCP 조사 (2026-11-24)

출처: mcp.film 레지스트리(https://mcp.film/api/registry.json, 항목별 verified 날짜 포함) + 공식 페이지 직접 확인.
선정 기준: 벤더 공식(official) + 호스팅 원격 URL(설치 불필요). 인증은 OAuth(브라우저 로그인) 또는 API 키.

공식 페이지로 직접 확인한 항목: Runway(runway.com/mcp, OAuth, API 키 불필요), Pika(mcp.pika.art/mcp, OAuth), HeyGen(mcp.heygen.com/mcp/v1, OAuth), Hedra(mcp.hedra.com, OAuth), Synthesia(mcp.synthesia.io/mcp, 로그인), fal(mcp.fal.ai, OAuth/API 키), Shotstack(mcp.shotstack.io, OAuth), Creatomate(api.creatomate.com/mcp, API 키), ElevenLabs(api.elevenlabs.io/v1/mcp, OAuth), Suno(api.suno.com/mcp, OAuth), Fish Audio(api.fish.audio/mcp, OAuth), Krea(api.krea.ai/mcp, OAuth), Vidu(service.vidu.com/vidu/mcp), MiniMax(로컬 stdio, API 키), Google GenMedia(로컬 바이너리, GCP 인증).

주의: docs.runway.team은 다른 회사(모바일 릴리스 관리 Runway)다. 영상 Runway는 mcp.runwayml.com.
Replicate 원격 주소는 /sse(레거시 SSE)라 Pi 등 일부 에이전트는 미지원.

| 분류 | 서비스 | 공급사 | 인증 | MCP URL | 확인일 |
|---|---|---|---|---|---|
| 영상 생성 | Magic Hour MCP | Magic Hour | api_key | https://mcp.magichour.ai/ | 2026-10-27 |
| 영상 생성 | VideoGen MCP Server | VideoGen | api_key | https://mcp.videogen.io/mcp | 2026-10-10 |
| 영상 생성 | Vivideo MCP | Vivideo | api_key | https://api.vivideo.ai/mcp | 2026-11-15 |
| 영상 생성 | Clip Studio MCP | Clip Studio | oauth | https://clipstudio.ai/api/mcp | 2026-11-05 |
| 영상 생성 | Everygen MCP | Everygen (Viewmax LLC) | oauth | https://everygen.ai/api/mcp | 2026-10-27 |
| 영상 생성 | Higgsfield MCP | Higgsfield AI | oauth | https://mcp.higgsfield.ai/mcp | 2026-10-27 |
| 영상 생성 | Incarn | Incarn | oauth | https://api.incarn.co/mcp | 2026-10-10 |
| 영상 생성 | Kleo | Kleo (single maintainer) | oauth | https://mcp.kleooai.com/mcp | 2026-10-10 |
| 영상 생성 | Kling MCP (Official) | Kling AI (Kuaishou) | oauth | https://kling.ai/mcp | 2026-10-20 |
| 영상 생성 | MakeAIVideo MCP | MakeAIVideo | oauth | https://mcp.makeaivideo.ai | 2026-10-18 |
| 영상 생성 | Mosaic Motion MCP | Mosaic | oauth | https://mcp.motion.so/mcp | 2026-11-15 |
| 영상 생성 | MotionVid | MotionVid (motionvid.ai) | oauth | https://motionvid.ai/mcp | 2026-11-22 |
| 영상 생성 | Pictory MCP | Pictory | oauth | https://mcp.pictory.ai/mcp | 2026-10-31 |
| 영상 생성 | Pika MCP | Pika Labs | oauth | https://mcp.pika.art/mcp | 2026-10-19 |
| 영상 생성 | ReelsFarm MCP | ReelsFarm | oauth | https://mcp.reelsfarm.com/mcp | 2026-11-06 |
| 영상 생성 | Revid | Revid.ai | oauth | https://www.revid.ai/api/mcp | 2026-10-24 |
| 영상 생성 | Runway MCP | Runway | oauth | https://mcp.runwayml.com/mcp | 2026-10-10 |
| 영상 생성 | varg | vargai Inc. | oauth | https://mcp.varg.ai/mcp | 2026-10-18 |
| 영상 생성 | Wireflow | Wireflow | oauth | https://www.wireflow.ai/api/mcp | 2026-10-21 |
| 모델 허브(영상·이미지 다수) | Apiframe MCP | Apiframe (Katario LLC) | api_key | https://mcp.apiframe.ai | 2026-11-13 |
| 모델 허브(영상·이미지 다수) | Civitai Orchestration MCP | Civitai | api_key | https://orchestration.civitai.com/mcp/v2 | 2026-11-07 |
| 모델 허브(영상·이미지 다수) | fal MCP Server | fal.ai | api_key | https://mcp.fal.ai/mcp | 2026-10-02 |
| 모델 허브(영상·이미지 다수) | GenMagic MCP | GenMagic (single-developer gateway) | api_key | https://genmagic.co/api/mcp | 2026-10-10 |
| 모델 허브(영상·이미지 다수) | inference.sh MCP Server | inference.sh | api_key | https://api.inference.sh/mcp | 2026-10-07 |
| 모델 허브(영상·이미지 다수) | Promptibus MCP | Promptibus | api_key | https://promptibus.com/api/mcp | 2026-10-05 |
| 모델 허브(영상·이미지 다수) | RunAPI MCP Server | RunAPI | api_key | https://mcp.runapi.ai/mcp | 2026-10-04 |
| 모델 허브(영상·이미지 다수) | Artlist MCP | Artlist | oauth | https://mcp.artlist.io/mcp | 2026-11-01 |
| 모델 허브(영상·이미지 다수) | BudgetPixel MCP | BudgetPixel | oauth | https://mcp.budgetpixel.com/mcp | 2026-10-25 |
| 모델 허브(영상·이미지 다수) | Comfy MCP | Comfy Org | oauth | https://cloud.comfy.org/mcp | 2026-10-11 |
| 모델 허브(영상·이미지 다수) | EmpirioLabs AI MCP | EmpirioLabs.ai LLC | oauth | https://mcp.empiriolabs.ai/mcp | 2026-10-25 |
| 모델 허브(영상·이미지 다수) | getimg.ai MCP | getimg.ai | oauth | https://getimg.ai/mcp | 2026-11-02 |
| 모델 허브(영상·이미지 다수) | Hedra MCP (Official) | Hedra | oauth | https://mcp.hedra.com | 2026-10-23 |
| 모델 허브(영상·이미지 다수) | Imagera MCP | Imagera AI | oauth | https://mcp.imagera.ai/mcp | 2026-11-15 |
| 모델 허브(영상·이미지 다수) | Imagine MCP | ImagineArt (Vyro AI) | oauth | https://mcp.imagine.art | 2026-10-25 |
| 모델 허브(영상·이미지 다수) | Krea MCP Server | Krea | oauth | https://api.krea.ai/mcp | 2026-10-27 |
| 모델 허브(영상·이미지 다수) | Mage MCP | Mage (mage.space) | oauth | https://mcp.mage.space/mcp | 2026-10-25 |
| 모델 허브(영상·이미지 다수) | MaxVideoAI | MaxVideoAI (camgraphe) | oauth | https://api.maxvideoai.com/mcp | 2026-11-01 |
| 모델 허브(영상·이미지 다수) | Picsart MCP | Picsart | oauth | https://api.picsart.com/gen-ai/mcp | 2026-10-30 |
| 모델 허브(영상·이미지 다수) | Popcraft MCP | Popcraft | oauth | https://popcraft.ai/api/mcp | 2026-10-03 |
| 모델 허브(영상·이미지 다수) | PopNow MCP | PopNow | oauth | https://api.popnow.ai/mcp | 2026-10-26 |
| 모델 허브(영상·이미지 다수) | Replicate MCP Server | Replicate | oauth | https://mcp.replicate.com/sse | 2026-10-03 |
| 모델 허브(영상·이미지 다수) | WaveSpeed MCP | WaveSpeed AI | oauth | https://api.wavespeed.ai/mcp | 2026-10-19 |
| 아바타·립싱크 | AKOOL MCP | AKOOL | api_key | https://openapi.akool.com/mcp/v1 | 2026-10-04 |
| 아바타·립싱크 | bitHuman MCP | bitHuman | api_key | https://mcp.bithuman.ai/mcp | 2026-10-08 |
| 아바타·립싱크 | CraftStory MCP | CraftStory (itseez3d) | api_key | https://mcp.craftstory.com/mcp | 2026-10-20 |
| 아바타·립싱크 | D-ID MCP Server | D-ID | api_key | https://docs.d-id.com/mcp | 2026-10-22 |
| 아바타·립싱크 | Sync MCP Server | Sync (sync.so) | api_key | https://mcp.sync.so/mcp | 2026-10-27 |
| 아바타·립싱크 | Apatero Studio MCP | Apatero | oauth | https://mcp.apatero.ai/mcp | 2026-11-04 |
| 아바타·립싱크 | Clipwright MCP | Clipwright (Dimantika sp. z o.o.) | oauth | https://mcp.clipwright.io/mcp | 2026-10-26 |
| 아바타·립싱크 | HeyGen Remote MCP | HeyGen | oauth | https://mcp.heygen.com/mcp/v1/ | 2026-10-20 |
| 아바타·립싱크 | VEED Fabric MCP | VEED | oauth | https://www.veed.io/api/v1/mcp | 2026-11-10 |
| 음성·TTS | AudioPod MCP | AudioPod AI | api_key | https://mcp.audiopod.ai | 2026-11-04 |
| 음성·TTS | Cartesia MCP | Cartesia | oauth | https://mcp.cartesia.ai/mcp | 2026-11-07 |
| 음성·TTS | ElevenLabs MCP | ElevenLabs | oauth | https://api.elevenlabs.io/v1/mcp | 2026-10-29 |
| 음성·TTS | Fish Audio MCP | Fish Audio | oauth | https://api.fish.audio/mcp | 2026-10-26 |
| 음악 | Epidemic Sound MCP Server | Epidemic Sound | api_key | https://www.epidemicsound.com/a/mcp-service/mcp | 2026-10-02 |
| 음악 | Artyfile Music Licensing | Artyfile LTD | none | https://artyfile.com/api/mcp | 2026-10-10 |
| 음악 | Doseedo Film Score | Doseedo | oauth | https://api.doseedo.com/mcp/film | 2026-11-07 |
| 음악 | Suno MCP (beta) | Suno | oauth | https://api.suno.com/mcp | 2026-11-03 |
| 음악 | Words into Music | Words into Music (Savuko) | oauth | https://mcp.wordsintomusic.com/mcp | 2026-10-26 |
| 효과음 | AudioLab MCP | AudioLaunch | api_key | https://audiolab.tools/mcp | 2026-11-09 |
| 효과음 | Mirelo MCP | Mirelo AI | oauth | https://mcp.mirelo.ai/mcp | 2026-10-03 |
| 이미지 | FLUX MCP | Black Forest Labs | oauth | https://mcp.bfl.ai | 2026-10-08 |
| 이미지 | Ideogram MCP | Ideogram | oauth | https://mcp.ideogram.ai/mcp | 2026-10-09 |
| 이미지 | Recraft MCP Server | Recraft | oauth | https://mcp.recraft.ai/mcp | 2026-10-08 |
| 편집·후반 | Adobe Run-Workflow MCP | Adobe | api_key | https://run-workflow.adobe.io/mcp | 2026-10-14 |
| 편집·후반 | Adobe for Creativity | Adobe | oauth | https://adobe-creativity.adobe.io/mcp | 2026-10-10 |
| 편집·후반 | AskEditor | AskEditor | oauth | https://mcp.askeditor.com/mcp | 2026-11-07 |
| 편집·후반 | ChatCut | ChatCut | oauth | https://api.chatcut.io/api/external-mcp/mcp | 2026-10-26 |
| 편집·후반 | Clueso MCP | Clueso | oauth | https://connect.clueso.io/mcp | 2026-10-12 |
| 편집·후반 | Descript MCP | Descript | oauth | https://api.descript.com/v2/mcp | 2026-10-30 |
| 편집·후반 | Eddie AI MCP | Eddie AI (Press Play Labs, Inc.) | oauth | https://mcp.heyeddie.ai/api/mcp | 2026-11-17 |
| 편집·후반 | Kapwing MCP | Kapwing | oauth | https://www.kapwing.com/mcp | 2026-10-28 |
| 편집·후반 | OpusClip MCP | OpusClip | oauth | https://mcp.opus.pro/mcp | 2026-11-16 |
| 편집·후반 | reap MCP | reap | oauth | https://mcp.reap.video/mcp | 2026-10-24 |
| 편집·후반 | Shotstack MCP | Shotstack | oauth | https://mcp.shotstack.io/ | 2026-10-11 |
| 편집·후반 | TwelveLabs Jockey | TwelveLabs | oauth | https://mcp.twelvelabs.io/jockey/mcp | 2026-10-10 |
| 편집·후반 | Valmera Video Editor | Valmera (DIYAR TAREQ TRADING L.L.C, UAE) | oauth | https://valmera.io/mcp/server | 2026-11-07 |
| 편집·후반 | Valossa Video Assistant MCP | Valossa | oauth | https://mcp-assistant.valossa.com/mcp | 2026-10-07 |
| 통합 제작 스튜디오 | Cinegenta Studio | Cinegenta | api_key | https://cinegenta.com/api/mcp | 2026-10-27 |
| 통합 제작 스튜디오 | Framesail | Framesail | api_key | https://api.framesail.com/mcp | 2026-10-31 |
| 통합 제작 스튜디오 | FilmLab | TheFilmRadar | oauth | https://mcp-lab.thefilmradar.com/mcp | 2026-11-22 |
| 통합 제작 스튜디오 | Frameo MCP | Frameo (Dashverse) | oauth | https://mcp.frameo.ai/mcp | 2026-10-10 |
| 통합 제작 스튜디오 | Genflick MCP | Genflick | oauth | https://genflick.com/mcp/studios | 2026-11-07 |
| 통합 제작 스튜디오 | invideo MCP Server | invideo | oauth | https://mcp.invideo.io/mcp | 2026-10-27 |
| 통합 제작 스튜디오 | Martini | Martini (C47) | oauth | https://www.martini.film/mcp | 2026-10-26 |
| 통합 제작 스튜디오 | Reverie Movies MCP | Reverie Movies (Justin Crosbie) | oauth | https://api.reveriemovies.com/mcp | 2026-11-07 |
| 업스케일 | Magnific MCP | Magnific | oauth | https://mcp.magnific.com | 2026-11-05 |

## 레지스트리 밖 공식 서버 (직접 확인)
| 분류 | 서비스 | 인증 | 주소 |
|---|---|---|---|
| 영상 생성 | Ludyte | OAuth | (현재 Codex 설정에 등록된 원격 URL) |
| 아바타 | Synthesia | 로그인(OAuth) | https://mcp.synthesia.io/mcp |
| 영상 생성 | Vidu | API 키/로그인 확인 필요 | https://service.vidu.com/vidu/mcp |
| 편집·렌더 | Creatomate | API 키 | https://api.creatomate.com/mcp |
| 영상·이미지·TTS | MiniMax | API 키(로컬 uvx) | uvx minimax-mcp |
| 영상(Veo)·음악(Lyria)·TTS(Chirp) | Google GenMedia | GCP(Vertex) | 로컬 Go 바이너리 |
| 음성 | Typecast | 로그인(Cast CLI) | MCP 아님, CLI |
