# 편집 감독 레이어 (Editing Director) — Design Spec

_Date: 2026-07-05_

## Overview

지금 파이프라인은 이미지 씬의 편집 스타일을 `scene.index % 2` (짝수→폴라로이드, 홀수→스플릿 스크린)로 **기계적으로** 배정한다. 콘텐츠와 무관하게 순서만으로 정해지므로, 같은 이미지를 넣어도 항상 같은 방식으로 편집된다.

이 스펙은 그 자리에 **편집 감독 레이어**를 넣는다. LLM이 스크립트를 생성할 때 각 씬의 나레이션 내용을 근거로 레이아웃과 전환을 함께 결정하고, 코드는 최소한의 가드레일(훅 보장 + 단조로움 방지 + 잘못된 값 폴백)만 얹는다. 목표는 *"데이터를 보고 데이터에 맞는 편집을 자연스럽고 유연하게"* — 이미지를 넣는다고 꼭 정해진 방식으로 편집되지 않는 것.

레퍼런스는 숏폼 자동화 서비스 mirr(mirra.my)의 핵심 특성 *"every scene looks different — layout styles optimized for virality를 AI가 씬마다 선택"*. 이 스펙은 그 엔진 부분을 구현한다(웹 UI는 범위 밖, 추후 별도 작업).

---

## Scope

**In scope:**
- LLM이 씬마다 `layout`·`transition_in`을 출력 (기존 스크립트 생성 호출 확장 — 새 API 호출 없음)
- 편집 감독 가드레일 모듈 (순수 함수)
- 파이프라인이 `index % 2` 대신 편집 계획을 사용
- `assemble_with_transitions`가 씬별 전환을 받도록 확장 (하위호환 유지)

**Out of scope (YAGNI):**
- 웹 UI / 서버 / 파일 업로드
- 모션(켄번즈 팬)까지 LLM이 결정 — 이번엔 레이아웃 + 전환만 (팬은 기존 순환 유지)
- 훅 여러 개 생성 후 선택 / BGM 자동 삽입 — 향후 별도 스테이지
- 실제 촬영본이 필요한 기법(점프컷·매치컷·크로스컷·컷어웨이 등) — 정지 이미지 1장 구조상 불가

---

## Palette

편집 감독이 씬마다 고르는 두 축.

### Layout (이미지 씬 렌더 스타일)

| 값 | 렌더 함수 | 언제 |
|----|----------|------|
| `fullscreen` | `build_scene_clip` (전체화면 켄번즈) | 풍경·전체 임팩트·훅 |
| `polaroid` | `build_polaroid_scene_clip` | 인물·특정 순간 강조 |
| `split` | `build_split_screen_scene_clip` | 비교·전후·둘 |

기본값: `fullscreen`. 비디오 씬(`media_type == "video"`)은 layout과 무관하게 항상 `build_scene_clip`.

### Transition (씬으로 들어올 때 전환)

LLM은 친숙한 이름으로 출력하고, 코드가 xfade 이름으로 매핑한다.

| LLM 값 | xfade | 언제 |
|--------|-------|------|
| `dissolve` | `fade` | 회상·감정 |
| `slide` | `slideleft` | 리스트/항목 전환 |
| `wipe` | `wipeup` | 장면·장소 전환 |
| `zoom` | `circleopen` | 강조·훅 |

기본값: `dissolve`. 첫 씬의 `transition_in`은 앞에 붙일 클립이 없으므로 사용되지 않는다(무시).

---

## Components

### 1. `scene_schema.py` (수정)

`Scene` dataclass에 필드 2개 추가 (기본값 있음 → 하위호환):

```python
@dataclass
class Scene:
    index: int
    narration: str
    visual_description: str
    duration_hint_sec: float
    highlight_words: list = field(default_factory=list)
    layout: str = "fullscreen"
    transition_in: str = "dissolve"
```

`script_from_dict`는 두 필드를 `.get("layout", "fullscreen")` / `.get("transition_in", "dissolve")`로 방어적으로 파싱한다(기존 씬 파싱 try/except 패턴 유지).

### 2. `llm_client.py` (수정)

`SCRIPT_TOOL.input_schema`의 scene `properties`에 추가:

```python
"layout": {"type": "string", "enum": ["fullscreen", "polaroid", "split"]},
"transition_in": {"type": "string", "enum": ["dissolve", "slide", "wipe", "zoom"]},
```

`required`에는 넣지 않는다 — LLM이 빠뜨려도 스키마 검증/파싱이 깨지지 않게. `_call_anthropic`의 기존 `"scenes" not in data` 검증은 그대로.

### 3. `script_generator.py` (수정)

`TOPIC_PROMPT_TEMPLATE` / `ARTICLE_PROMPT_TEMPLATE`에 팔레트와 판단 기준 한 단락 추가. 예:

> 각 씬마다 내용에 맞는 화면 구성(layout)과 전환(transition_in)을 함께 정해줘.
> layout: 풍경·전체 임팩트·강한 시작은 fullscreen, 인물·특정 순간 강조는 polaroid, 비교·전후·둘을 보여줄 땐 split.
> transition_in: 회상·감정은 dissolve, 항목 나열 전환은 slide, 장소·장면이 바뀌면 wipe, 강조·훅은 zoom.
> 영상이 단조롭지 않도록 연속된 씬은 되도록 다른 layout을 쓰되, 억지로 바꾸지는 말고 내용에 맞게 정해줘.

### 4. `editing_director.py` (신규, 순수 함수)

LLM/ffmpeg 의존 없이 완전히 단위 테스트 가능한 가드레일 계층.

```python
LAYOUTS = {"fullscreen", "polaroid", "split"}
TRANSITION_MAP = {
    "dissolve": "fade",
    "slide": "slideleft",
    "wipe": "wipeup",
    "zoom": "circleopen",
}
DEFAULT_LAYOUT = "fullscreen"
DEFAULT_TRANSITION = "dissolve"

@dataclass
class ScenePlan:
    layout: str          # LAYOUTS 중 하나
    transition: str      # xfade 이름 (매핑 완료된 값)

def resolve_editing_plan(scenes) -> list[ScenePlan]:
    ...
```

동작 순서:
1. **검증·기본값**: 각 씬의 `scene.layout`이 `LAYOUTS`에 없으면 `DEFAULT_LAYOUT`. `scene.transition_in`이 `TRANSITION_MAP`에 없으면 `DEFAULT_TRANSITION`. 매핑 적용해 xfade 이름으로 변환.
2. **가드레일 1 (훅)**: `plans[0].layout = "fullscreen"` 강제 (전체화면 + 큰 자막 = 가장 강한 오프닝).
3. **가드레일 2 (단조로움 방지)**: 같은 layout이 3연속이 되면 3번째를 다른 유효 layout으로 교체(결정적으로: `LAYOUTS`에서 직전 두 개와 다른 첫 값 선택). 결과가 뒤 씬과 또 3연속을 만들지 않도록 앞에서 뒤로 한 번 훑는다.

주의: 이 함수는 스크립트 씬 메타데이터만 보고 동작하며 media_type(이미지/비디오)은 모른다. layout은 이미지 씬에서만 실제로 쓰이고 비디오 씬에선 파이프라인이 media_type 검사로 무시한다. 단조로움 방지는 전체 씬 시퀀스 기준으로 근사한다(이 파이프라인은 대부분 Gemini 이미지라 실무상 충분).

### 5. `renderer.py` — `assemble_with_transitions` (수정, 하위호환)

시그니처에 선택 인자 추가:

```python
def assemble_with_transitions(scene_clip_paths, durations, ass_text, out_path,
                              transition_duration=0.5, transitions=None):
```

- `transitions`가 `None`이면 기존 동작(`["fade","slideleft","wipeup","circleopen"]`를 `(i-1)%4`로 순환) 유지 → 기존 호출·테스트 무영향.
- `transitions`가 주어지면 씬 `i`로 들어오는 xfade에 `transitions[i]` 사용(리스트는 씬과 1:1, index 0의 값은 쓰이지 않음). 리스트 길이가 모자라면 안전하게 기본 순환으로 폴백.

### 6. `pipeline.py` (수정)

- `resolve_editing_plan(successful_scenes 또는 script.scenes)` 호출로 `plans` 확보.
- 이미지 씬 분기의 `if scene.index % 2 == 0` 폐기 → `plan.layout`으로 3분기:
  - `fullscreen` → `build_scene_clip(media.path, "image", audio, duration, clip_path, pan_variant=scene.index)`
  - `polaroid` → `build_polaroid_scene_clip(..., tilt_variant=scene.index)`
  - `split` → `build_split_screen_scene_clip(...)`
- 비디오 씬은 기존대로 `build_scene_clip(media.path, media.media_type, ...)`.
- `assemble_with_transitions(...)`에 성공한 씬들의 `plan.transition` 리스트를 `transitions=`로 전달.

플랜과 씬/클립/전환 리스트의 정렬은 `successful_scenes`와 동일 순서를 유지해 구조적으로 일치시킨다.

---

## Data Flow

```
raw_input (topic|url)
  → generate_script
      → LLM (SCRIPT_TOOL, layout·transition_in 포함)
      → script_from_dict → Script(scenes[layout, transition_in])
  → render_script
      → TTS / media 해결 (기존)
      → resolve_editing_plan(scenes) → [ScenePlan(layout, xfade_transition)]
      → 씬별 클립 생성: plan.layout으로 fullscreen|polaroid|split 분기
      → assemble_with_transitions(..., transitions=[plan.transition ...])
      → 자막 burn-in (기존)
  → output/*.mp4
```

---

## Error Handling

- LLM이 `layout`/`transition_in`을 누락 → dataclass 기본값 + director 검증으로 안전.
- LLM이 허용 목록 밖 값 출력 → director가 기본값으로 폴백.
- 잘못된 조합/단조로운 출력 → 가드레일이 훅·다양성 보정.
- `transitions` 리스트 길이 부족 → 기본 순환 폴백.
- 기존 per-scene 부분 실패 철학(한 씬 실패해도 나머지 진행) 유지.

---

## Testing

- `editing_director.py`: 순수 함수라 ffmpeg/LLM 없이 전부 단위 테스트.
  - 기본값 폴백(빈/이상값), 매핑 정확성
  - 가드레일 1: 첫 씬 강제 fullscreen (LLM이 polaroid를 줘도)
  - 가드레일 2: 3연속 layout 분해(예: `[polaroid, polaroid, polaroid]` → 3번째 교체), 교체 결과가 새 3연속을 안 만드는지
  - 빈 씬 리스트 / 단일 씬 엣지케이스
- `llm_client.py`: 스키마에 layout·transition_in enum 포함, 여전히 `scenes`만 required 확인.
- `scene_schema.py`: `script_from_dict`가 layout/transition_in 파싱, 누락 시 기본값.
- `renderer.py`: `transitions=None`이면 기존 순환(기존 테스트 무변경), `transitions` 주면 해당 씬에 해당 xfade 사용.
- `pipeline.py`: 이미지 씬이 `plan.layout`대로 3함수에 라우팅되는지(3케이스), `assemble_with_transitions`에 transitions가 전달되는지, 비디오 씬은 여전히 build_scene_clip.
- **수동 스모크 테스트(필수)**: 캐시된 이미지/스크립트로 API 비용 없이 실제 렌더 → 프레임 추출해 (a) 씬마다 레이아웃이 실제로 다른지, (b) 전환이 지정대로 나오는지, (c) 첫 씬이 fullscreen 훅인지 육안 확인.

---

## Files

```
shortform/
├── editing_director.py   # [신규] resolve_editing_plan(scenes) -> list[ScenePlan]
├── scene_schema.py       # [수정] Scene에 layout·transition_in 필드
├── llm_client.py         # [수정] SCRIPT_TOOL 스키마에 두 필드(enum, non-required)
├── script_generator.py   # [수정] 프롬프트에 팔레트·판단 기준 한 단락
├── renderer.py           # [수정] assemble_with_transitions에 transitions= 선택 인자
└── pipeline.py           # [수정] index%2 폐기 → plan.layout 분기 + transitions 전달
tests/
├── test_editing_director.py  # [신규]
├── test_scene_schema.py      # [수정] 새 필드 파싱/기본값
├── test_llm_client.py        # [수정] 스키마 enum 확인
├── test_renderer.py          # [수정] transitions 인자 동작
└── test_pipeline.py          # [수정] plan.layout 라우팅 + transitions 전달
```

무수정: `polaroid.py`, `split_screen.py`, `captions.py`, `tts.py`, `crawler.py`, `media_matcher.py`, `sound_effects.py`, `process.py`.
