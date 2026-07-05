# 훅 시스템 + 디자인 타이틀 카드 — Design Spec

_Date: 2026-07-05_

## Overview

mirr(mirra.my) 비교에서 확인된 두 번째 빈 곳을 채운다: **훅(Hook)**. 조회수에 직결되는 오프닝을 강화하기 위해 (1) LLM이 훅 후보 여러 개를 만들고 가장 강한 것을 골라 첫 씬 나레이션으로 쓰며, (2) 그 훅을 사진 위 자막이 아니라 **여백 + 디자인된 텍스트 UI**를 가진 "타이틀 카드" 레이아웃으로 렌더한다.

레퍼런스: 사용자가 제공한 부동산 숏폼 캡처 — 상단 여백(밝은 단색)에 크기·색이 다른 여러 줄 텍스트("주변 시세보다 무려 / **-70만 원** / 이런 퀄리티가 가능할까요?"), 하단에 사진, 맨 아래 기존 나레이션 자막이 공존하는 구도.

**사용자 확정 방향:**
- 훅 선택 = **완전 자동 + 로그** (LLM이 생성·선택, 탈락 후보와 이유를 script JSON에 기록 — 나중에 사람이 검토/교체 가능)
- 훅 생성 시점 = **기존 스크립트 생성 호출 확장** (새 API 호출 없음, 편집 감독과 같은 패턴)
- 범위 = **훅 텍스트 + 디자인 타이틀 카드를 한 스테이지에서** — 초기 버전을 만들고 실제 영상을 보면서 사용자가 원하는 방향으로 반복 튜닝

## Scope

**In scope:**
- LLM: `hook_candidates`(3개) + `hook_reason` 출력, 선택된 훅 = 첫 씬 나레이션
- `Script`에 두 필드 저장 → CLI의 script JSON에 자동 기록
- 신규 레이아웃 `titlecard`: 상단 여백 + 디자인 텍스트, 하단 사진
- 편집 감독: `LAYOUTS`에 titlecard 추가, 가드레일 1을 "첫 씬 강제 fullscreen" → "첫 씬 강제 titlecard"로 변경
- 파이프라인 titlecard 분기

**Out of scope (YAGNI):**
- 웹 UI에서 훅 고르기 (JSON에 기록해두는 것까지만 — 추후 웹 UI의 재료)
- 훅 강도 자동 A/B 테스트
- 라운드 모서리 배지/카드 등 고급 UI 요소 — 초기 버전은 단순 구도, 이후 육안 튜닝으로 추가 여부 결정
- BGM (다음 후보 스테이지)

---

## Components

### 1. `llm_client.py` (수정)

`SCRIPT_TOOL.input_schema` 최상위 properties에 추가 (required 아님):

```python
"hook_candidates": {"type": "array", "items": {"type": "string"}},
"hook_reason": {"type": "string"},
```

기존 `"scenes" not in data` 검증은 그대로.

### 2. `script_generator.py` (수정)

프롬프트에 훅 지시 단락 추가 (topic/article 공통):

> 영상 첫 3초에 시청자를 붙잡을 오프닝 훅 후보를 3개 만들어 hook_candidates로 출력해줘.
> 그중 가장 강한 하나를 골라 **첫 번째 씬의 나레이션으로 그대로 사용**하고, 왜 그것을 골랐는지 hook_reason에 한 줄로 적어줘.
> 좋은 훅: 구체적 숫자, 의외성, 질문, 시청자가 자기 얘기라고 느끼는 표현.

### 3. `scene_schema.py` (수정)

```python
@dataclass
class Script:
    title: str
    scenes: list
    hook_candidates: list = field(default_factory=list)
    hook_reason: str = ""
```

`script_from_dict`가 `.get("hook_candidates", [])` / `.get("hook_reason", "")`로 방어적 파싱. CLI는 이미 `asdict(script)`로 저장하므로 무수정으로 JSON에 기록됨.

### 4. `title_card.py` (신규)

폴라로이드/스플릿과 같은 2계층 구조:

```python
CARD_BG_COLOR = "0xF5F2EC"       # 밝은 웜 화이트 (레퍼런스 톤)
PHOTO_HEIGHT = 1056               # 하단 사진 영역 (~55%)
MARGIN_HEIGHT = 1920 - PHOTO_HEIGHT  # 상단 여백 864px (~45%)

def build_title_card_filter_complex(frame_count: int) -> str: ...
def build_hook_ass(hook_text: str, highlight_words: list) -> str: ...
def build_title_card_scene_clip(image_path, audio_path, duration, out_path,
                                hook_text, highlight_words=None) -> Path: ...
```

- **`build_title_card_filter_complex`**: `color=c=...:s=1080x1920` 배경 + 이미지를 1080x{PHOTO_HEIGHT}로 scale/crop → 가벼운 zoompan (기존 폴라로이드의 gentle zoom 계열) → 하단에 overlay. `[v]` 출력.
- **`build_hook_ass`**: 훅 텍스트를 상단 여백에 디자인 배치하는 ASS 문자열 생성.
  - 훅을 구절 단위로 줄 나눔 (captions.py의 `_PHRASE_BOUNDARY` 재사용 가능하면 재사용)
  - highlight_words가 포함된 줄은 큰 폰트 + 강조색(레퍼런스의 그린 계열 `&H2E7D4F&` 근처), 나머지 줄은 작고 진회색
  - `\pos`로 여백 중앙 배치, `\fad(300,0)` 페이드인
  - BorderStyle은 박스 없이 (밝은 배경 위 텍스트라 박스 불필요)
- **`build_title_card_scene_clip`**: filter로 무자막 클립 생성 → per-clip ASS 파일 작성 → 기존 `renderer.burn_ass_subtitles` 재사용해 번인 → 최종 클립 반환. (오디오는 filter 단계에서 `-map 1:a`)

주의: 전체 조립 때 하단 나레이션 자막이 또 들어감 — 레퍼런스도 상단 타이틀 + 하단 자막 공존 구도이므로 의도된 동작.

### 5. `editing_director.py` (수정)

- `ORDERED_LAYOUTS = ["fullscreen", "polaroid", "split", "titlecard"]`
- 가드레일 1: `plans[0].layout = "titlecard"` (기존 fullscreen에서 변경)
- LLM enum에도 titlecard 추가 (`llm_client.py` layout enum) — 중간 씬 챕터 전환용으로 LLM이 선택 가능

### 6. `pipeline.py` (수정)

titlecard 분기 추가:

```python
elif plan.layout == "titlecard":
    build_title_card_scene_clip(
        media.path, audio_paths[scene.index], duration, clip_path,
        hook_text=scene.narration, highlight_words=scene.highlight_words,
    )
```

(중간 씬이 titlecard여도 그 씬 나레이션이 타이틀 텍스트가 되므로 일반화됨.)

---

## Data Flow

```
LLM 호출 1번
  → hook_candidates 3개 + hook_reason + scenes (scenes[0].narration = 선택된 훅)
  → Script(hook_candidates, hook_reason) → CLI가 script JSON에 기록
  → 편집 감독: 첫 씬 강제 titlecard
  → build_title_card_scene_clip: 배경+사진 합성 → 훅 ASS 번인
  → 조립(전환/자막/whoosh 기존 흐름)
```

## Error Handling

- LLM이 hook_candidates/hook_reason 누락 → 기본값(빈 리스트/빈 문자열), 첫 씬 나레이션은 어차피 존재하므로 titlecard는 그대로 렌더
- highlight_words 없음 → 전체 줄을 기본 스타일로
- titlecard 렌더 실패 → 기존 per-scene 부분 실패 철학(경고 + 스킵)

## Testing

- `title_card.py`: filter 문자열 검증(배경색, overlay 위치, zoompan), ASS 생성(강조줄/일반줄 스타일 분리, \pos, \fad), scene clip이 ffmpeg 2회(합성+번인) 호출하는지 mock 검증
- `editing_director.py`: 첫 씬 titlecard 강제, titlecard가 유효 레이아웃, 기존 가드레일 테스트 갱신
- `scene_schema.py` / `llm_client.py` / `script_generator.py`: 새 필드 파싱·스키마·프롬프트
- `pipeline.py`: titlecard 라우팅 1케이스
- **수동 렌더 + 사용자 육안 검증 (핵심 루프)**: 캐시 이미지로 타이틀 카드 렌더 → 프레임 추출 → 사용자가 보고 색/크기/비율/폰트 피드백 → 상수 튜닝 반복

## Files

```
shortform/
├── title_card.py         # [신규]
├── editing_director.py   # [수정] titlecard 레이아웃 + 가드레일 1 변경
├── scene_schema.py       # [수정] Script에 hook_candidates/hook_reason
├── llm_client.py         # [수정] hook 필드 + layout enum에 titlecard
├── script_generator.py   # [수정] 훅 프롬프트 단락
└── pipeline.py           # [수정] titlecard 분기
tests/
├── test_title_card.py        # [신규]
├── test_editing_director.py  # [수정]
├── test_scene_schema.py      # [수정]
├── test_llm_client.py        # [수정]
├── test_script_generator.py  # [수정]
└── test_pipeline.py          # [수정]
```

무수정: `polaroid.py`, `split_screen.py`, `captions.py`(재사용만), `tts.py`, `renderer.py`(burn_ass_subtitles 재사용만), `process.py`.
