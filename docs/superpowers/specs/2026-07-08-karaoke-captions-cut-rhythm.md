# 자막 카라오케 + 컷 리듬 — Design Spec

_Date: 2026-07-08_

## Overview

숏폼 체감 퀄리티의 다음 단계 두 가지 (둘 다 API 비용 0원):

1. **카라오케 자막** — 지금은 구절 단위 박스가 통째로 떴다 사라진다. 이걸 **말소리에 맞춰 단어가 하나씩 차오르는** 카라오케로. 타이밍은 추정이 아니라 edge-tts의 WordBoundary 이벤트(어절별 offset/duration, 100ns 단위)를 합성 시점에 수집해 사용 — 플래닝 프로브로 동작 확인 완료 (`boundary='WordBoundary'` 필요, edge-tts 7.2.8).
2. **컷 리듬** — 5초 이상 긴 fullscreen 이미지 씬이 한 켄번즈로 늘어지면 지루하다. 같은 이미지를 **중간에 하드 컷**으로 나눠 서로 다른 카메라 모션 두 개를 이어붙인다 (점프컷 템포감).

## Components

### 1. `tts.py` — WordBoundary 수집 (수정)

`synthesize_narration`을 `communicate.save()` 대신 `stream()` 기반으로:
- audio 청크 → out_path에 그대로 기록 (기존과 동일한 mp3)
- `WordBoundary` 청크 → `[{"text", "start", "end"}]` (초 단위, offset/1e7) 수집
- 사이드카 저장: `out_path.with_suffix(".words.json")` (예: scene_01.words.json)
- 반환값은 기존처럼 out_path (하위호환). 사이드카는 있으면 쓰고 없으면 무시되는 부가물.

### 2. `captions.py` — 카라오케 렌더 (수정, 폴백 유지)

`build_ass_from_scenes(scenes, durations, transition_duration=0.5, word_timings=None)`
- `word_timings`: `{scene.index: [{"text","start","end"}]}` 또는 None
- None이거나 해당 씬 타이밍이 없으면 **기존 구절 비례 배분 동작 그대로** (폴백)
- 있으면: 구절 분할은 유지하되, 구절 안 단어들에 ASS `\kf` 카라오케 태그:
  - 단어별 센티초 = (이 단어 end − 직전 단어 end), 첫 단어는 (end − 구절 시작)
  - 스타일: SecondaryColour = 옅은 회백(아직 안 읽음) → PrimaryColour로 차오름
  - highlight_words에 든 단어는 인라인 `\1c` 골드 오버라이드 → 회백→골드로 차오름, 나머지는 회백→흰색
  - 구절의 시간 창은 단어 타이밍에서 직접 산출 (첫 단어 start ~ 마지막 단어 end, 씬 시작 오프셋 + 크로스페이드 압축 반영)
- 단어→구절 매핑: 구절별 어절 수(`len(phrase.split())`)만큼 순서대로 배정. 총 어절 수가 안 맞으면 그 씬만 폴백 (LLM 텍스트와 TTS 어절이 어긋나는 예외 방어)

### 3. `pipeline.py` — 타이밍 배선 (수정)

- TTS 후 각 씬의 `scene_NN.words.json`이 존재하면 로드 → `word_timings` dict 구성
- `build_ass_from_scenes(..., word_timings=word_timings)` 전달
- 사이드카 없음/파싱 실패 → None 항목 (그 씬만 폴백)

### 4. `renderer.py` — 컷 리듬 클립 (함수 추가)

`CUT_RHYTHM_THRESHOLD_SEC = 5.0`

`build_rhythm_cut_clip(media_path, audio_path, duration, out_path, pan_variant=0)`
- 한 ffmpeg 호출: `[0:v]split=2` → 전반부 켄번즈 variant A(=pan_variant), 후반부 variant B(=(pan_variant+2)%4, 반대 계열 모션) 각각 duration/2 프레임 → `concat=n=2:v=1:a=0` 하드 컷 → 나레이션 오디오 먹싱
- 출력 규격 기존과 동일 (1080x1920, 30fps, yuv420p, aac)

### 5. `pipeline.py` — 컷 리듬 분기 (수정)

fullscreen 이미지 씬에서 `duration >= CUT_RHYTHM_THRESHOLD_SEC`이면 `build_rhythm_cut_clip`, 아니면 기존 `build_scene_clip`. polaroid/split/titlecard/비디오 씬은 무변경.

## Error Handling

- WordBoundary 수집 실패/빈 목록 → 사이드카 미생성 → 자막은 기존 방식 폴백
- 어절 수 불일치 → 해당 씬만 폴백
- 컷 리듬은 순수 ffmpeg — 실패 시 기존 per-scene 부분 실패 처리

## Testing

- tts: stream mock (audio+WordBoundary 청크) → mp3 바이트 기록 + words.json 내용/단위 변환 검증
- captions: word_timings 있음 → `\kf` 태그·센티초 값·골드 오버라이드, 없음 → 기존 출력과 동일(기존 테스트 무변경 통과), 어절 수 불일치 → 폴백
- renderer: rhythm cut 필터에 split/두 zoompan variant/concat 존재, 오디오 먹싱
- pipeline: words.json 로드 배선, 임계 이상 fullscreen → rhythm cut 라우팅
- 수동 렌더 + 사용자 육안/청취: 카라오케 차오름이 발화와 맞는지, 컷 리듬이 어색하지 않은지

## Files

```
shortform/tts.py         # [수정] stream 기반 + words.json 사이드카
shortform/captions.py    # [수정] word_timings 카라오케 (+폴백)
shortform/renderer.py    # [수정] build_rhythm_cut_clip 추가
shortform/pipeline.py    # [수정] 타이밍 로드 + 컷 리듬 분기
tests/ (해당 테스트들)
```

무수정: `title_card.py`, `polaroid.py`, `split_screen.py`, `bgm.py`, `motion.py`, `llm_client.py`(스키마 변화 없음 — 이번 스테이지는 LLM 무관).
