# 프롬프트 템플릿

## 이미지(시작/끝 프레임)
```
[구도] {{shot_size}}, {{lens_mm}}mm 느낌, {{angle}}
[인물] {{identity_anchor}} — {{wardrobe}} — {{holding}} — 화면 {{position}}
[장소·조명] {{location}}, {{lighting}}
[스타일] {{look}}
[네거티브] 화면 속 글자·자막, 워터마크, 로고, 'Made with AI' 등 코너 라벨, 손가락 변형, 얼굴 변형, 인물 바뀜
[참조] {{refs}}  [SSOT] character v{{v_character}}, scene v{{v_scene}}
```

## 영상(시작→끝 프레임)
```
시작 프레임 {{start_ref}} 에서 종료 프레임 {{end_ref}} 로.
동작: {{action}} (속도 {{speed}}, 방향 {{direction}}).
카메라: {{movement}}, {{shot_size}}. 길이 {{duration}}초.
사운드: {{audio}}.
인물 얼굴·의상·소품 위치는 시작 프레임과 동일하게 유지.
```
모델별 문법 변환은 실행 직전에 `ai-camera-control`(R19)과 공급자 스킬이 한다.
