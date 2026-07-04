# 문구 단위 배경 박스 자막 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `shortform/captions.py`가 만드는 자막을, 씬 전체를 한 줄로 보여주던 방식에서 문구(쉼표/마침표 단위) 단위로 끊어 순차 등장시키고, 키워드 테두리 강조 대신 줄 전체에 불투명 배경 박스를 입혀 가독성과 트렌디함을 높인다.

**Architecture:** 씬의 나레이션을 문장부호 기준으로 여러 문구로 나누고, 씬에 배정된 시간을 문구별 글자수 비율로 재배분해 각 문구를 별도 `Dialogue` 줄로 만든다. ASS `[V4+ Styles]`에 `BorderStyle=3`(불투명 박스) 스타일을 추가해 줄 배경에 박스를 깔고, 하이라이트 키워드는 테두리 대신 글자색만 다르게 표시한다. 각 문구 등장 시 `\fad(200,0)`으로 짧게 페이드인한다.

**Tech Stack:** 순수 Python (표준 라이브러리 `re`만 사용), ASS 자막 포맷. 새 pip 의존성 없음.

## Global Constraints

- 이번 변경은 `shortform/captions.py` 한 파일만 수정한다. `shortform/renderer.py`, `shortform/pipeline.py`는 이미 "완성된 ASS 텍스트를 받아 burn만" 하는 구조이므로 무수정.
- 새 pip 의존성 금지 — 문구 분할은 표준 라이브러리 `re`로 구현한다.
- 기존 `build_ass_from_scenes(scenes, durations, transition_duration=0.5) -> str` 시그니처는 그대로 유지한다 (호출부인 `pipeline.py`가 이 시그니처로 호출 중이므로 변경 시 별도 작업 필요 — 이번 계획 범위 밖).
- 씬의 시작/끝 시각 계산(전환 압축 반영: `scene_end = cursor + duration`, 마지막 씬이 아니면 `- transition_duration`)은 기존 로직 그대로 유지하고, 그 위에 문구별 세부 타이밍을 얹는다.
- `tests/test_captions.py`의 기존 3개 테스트는 이번 변경으로 동작 자체가 바뀌므로(씬당 한 줄 → 문구당 여러 줄) **전면 재작성**한다 — 이는 Stage 4a Task 7에서 파이프라인 테스트를 갱신했던 것과 동일한, 계획에 의해 명시적으로 허용된 예외다.
- 이 프로젝트는 모든 외부 호출(ffmpeg 등)을 모킹하는 컨벤션이 있으나, `captions.py`는 순수 문자열 처리 함수라 모킹 대상이 없다 — 반환된 문자열 내용만 검증한다.

---

## 1. File Structure

```
shortform/
└── captions.py   # [수정] 전체 재작성 — 문구 분할, 문구별 타이밍 배분, 박스 스타일, 색상 강조, 페이드인
tests/
└── test_captions.py   # [수정] 전면 재작성 — 문구 분할/타이밍/스타일/강조/페이드/엣지케이스 검증
```

`shortform/renderer.py`, `shortform/pipeline.py`는 이번 계획에서 건드리지 않는다.

---

## 2. Current State (참고용 — 수정 전 `shortform/captions.py` 전체)

```python
ASS_HEADER = """[Script Info]
Title: Shortform Captions
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Malgun Gothic,72,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,4,0,2,60,60,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

HIGHLIGHT_OVERRIDE = r"{\1c&H000000&\3c&H00D7FF&\bord14\shad0}"
RESET_OVERRIDE = r"{\r}"


def _fmt_ass_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _highlight_line(narration: str, highlight_words) -> str:
    text = narration
    for word in highlight_words or []:
        if word and word in text:
            text = text.replace(word, f"{HIGHLIGHT_OVERRIDE}{word}{RESET_OVERRIDE}", 1)
    return text


def build_ass_from_scenes(scenes, durations, transition_duration=0.5) -> str:
    lines = [ASS_HEADER]
    n = len(durations)
    cursor = 0.0
    for i, (scene, duration) in enumerate(zip(scenes, durations)):
        scene_end = cursor + duration
        if i < n - 1:
            scene_end -= transition_duration
        start = _fmt_ass_time(cursor)
        end = _fmt_ass_time(scene_end)
        text = _highlight_line(scene.narration, scene.highlight_words)
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
        cursor = scene_end
    return "\n".join(lines)
```

`_fmt_ass_time`은 이번 계획에서도 그대로 재사용한다 (수정 없음).

---

## 3. 상세 구현 계획 (TDD, 즉시 실행 가능)

### Task 1: 문구 단위 배경 박스 자막으로 `captions.py` 전면 재작성

**Files:**
- Modify: `shortform/captions.py` (전체 재작성)
- Test: `tests/test_captions.py` (전면 재작성)

**Interfaces:**
- Consumes: `Scene`(`shortform/scene_schema.py`, 필드: `narration: str`, `highlight_words: list`), 기존과 동일.
- Produces: `build_ass_from_scenes(scenes, durations, transition_duration=0.5) -> str` — 시그니처 불변. `pipeline.py`는 무수정으로 계속 이 함수를 그대로 호출한다.
- 새로 추가되는 내부 헬퍼(모듈 비공개, 다른 파일에서 import 안 함): `_split_phrases(narration: str) -> list`, `_phrase_windows(phrases: list, start: float, end: float) -> list[tuple[float, float]]`.

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_captions.py` 전체를 아래 내용으로 교체)

```python
from shortform.captions import ASS_HEADER, build_ass_from_scenes
from shortform.scene_schema import Scene


def test_build_ass_includes_header_and_cumulative_timing():
    scenes = [
        Scene(1, "첫 문장", "v1", 5.0),
        Scene(2, "둘째 문장", "v2", 4.0),
        Scene(3, "셋째 문장", "v3", 6.0),
    ]
    ass = build_ass_from_scenes(scenes, [5.0, 4.0, 6.0], transition_duration=0.5)

    assert "[Script Info]" in ass
    assert "Style: Box," in ass
    assert "[Events]" in ass
    assert "0:00:00.00,0:00:04.50" in ass
    assert "첫 문장" in ass
    assert "0:00:04.50,0:00:08.00" in ass
    assert "둘째 문장" in ass
    assert "0:00:08.00,0:00:14.00" in ass
    assert "셋째 문장" in ass


def test_build_ass_splits_narration_into_phrases_with_proportional_timing():
    scenes = [Scene(1, "안녕하세요, 오늘은 날씨가 좋아요.", "v", 10.0)]
    ass = build_ass_from_scenes(scenes, [10.0])

    assert "0:00:00.00,0:00:03.33" in ass
    assert "안녕하세요," in ass
    assert "0:00:03.33,0:00:10.00" in ass
    assert "오늘은 날씨가 좋아요." in ass


def test_build_ass_dialogue_lines_use_box_style():
    scenes = [Scene(1, "문장.", "v", 5.0)]
    ass = build_ass_from_scenes(scenes, [5.0])

    assert "Dialogue: 0,0:00:00.00,0:00:05.00,Box,,0,0,0,," in ass


def test_build_ass_includes_fade_in_per_phrase():
    scenes = [Scene(1, "안녕하세요, 반가워요.", "v", 5.0)]
    ass = build_ass_from_scenes(scenes, [5.0])

    assert ass.count(r"{\fad(200,0)}") == 2


def test_build_ass_highlights_keyword_with_color_only_no_border():
    scenes = [Scene(1, "70만원이나 저렴해요.", "v", 5.0, highlight_words=["70만원"])]
    ass = build_ass_from_scenes(scenes, [5.0])

    assert r"{\1c&H00D7FF&}70만원{\r}" in ass
    assert r"\bord" not in ass


def test_build_ass_skips_highlight_word_not_found_in_narration():
    scenes = [Scene(1, "그냥 평범한 문장", "v", 5.0, highlight_words=["없는단어"])]
    ass = build_ass_from_scenes(scenes, [5.0])

    assert "그냥 평범한 문장" in ass
    assert r"\1c&H00D7FF&" not in ass


def test_build_ass_treats_narration_without_punctuation_as_single_phrase():
    scenes = [Scene(1, "문장부호가 없는 나레이션", "v", 5.0)]
    ass = build_ass_from_scenes(scenes, [5.0])

    assert ass.count("Dialogue:") == 1
    assert "0:00:00.00,0:00:05.00" in ass
    assert "문장부호가 없는 나레이션" in ass
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_captions.py -v`
Expected: 여러 테스트 FAIL — 예를 들어 `test_build_ass_dialogue_lines_use_box_style`는 `AssertionError` (아직 `Box` 스타일이 없고 `Default` 스타일만 있음), `test_build_ass_splits_narration_into_phrases_with_proportional_timing`은 문구 분할이 없어 실패.

- [ ] **Step 3: 최소 구현** (`shortform/captions.py` 전체를 아래 내용으로 교체)

```python
import re

ASS_HEADER = """[Script Info]
Title: Shortform Captions
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Box,Malgun Gothic,64,&H00FFFFFF,&H000000FF,&H60101010,&H60101010,1,0,0,0,100,100,0,0,3,10,0,2,60,60,140,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

HIGHLIGHT_OVERRIDE = r"{\1c&H00D7FF&}"
RESET_OVERRIDE = r"{\r}"
FADE_IN = r"{\fad(200,0)}"

_PHRASE_BOUNDARY = re.compile(r"(?<=[,.!?])\s*")


def _fmt_ass_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _split_phrases(narration: str) -> list:
    parts = [p for p in _PHRASE_BOUNDARY.split(narration) if p.strip()]
    return parts if parts else [narration]


def _phrase_windows(phrases, start: float, end: float):
    total_chars = sum(len(p) for p in phrases) or 1
    total_duration = end - start
    last = len(phrases) - 1
    windows = []
    cursor = start
    for i, phrase in enumerate(phrases):
        if i == last:
            phrase_end = end
        else:
            phrase_end = cursor + total_duration * (len(phrase) / total_chars)
        windows.append((cursor, phrase_end))
        cursor = phrase_end
    return windows


def _highlight_line(text: str, highlight_words) -> str:
    for word in highlight_words or []:
        if word and word in text:
            text = text.replace(word, f"{HIGHLIGHT_OVERRIDE}{word}{RESET_OVERRIDE}", 1)
    return text


def build_ass_from_scenes(scenes, durations, transition_duration=0.5) -> str:
    lines = [ASS_HEADER]
    n = len(durations)
    cursor = 0.0
    for i, (scene, duration) in enumerate(zip(scenes, durations)):
        scene_end = cursor + duration
        if i < n - 1:
            scene_end -= transition_duration

        phrases = _split_phrases(scene.narration)
        windows = _phrase_windows(phrases, cursor, scene_end)
        for phrase, (p_start, p_end) in zip(phrases, windows):
            start = _fmt_ass_time(p_start)
            end = _fmt_ass_time(p_end)
            text = _highlight_line(phrase, scene.highlight_words)
            lines.append(f"Dialogue: 0,{start},{end},Box,,0,0,0,,{FADE_IN}{text}")

        cursor = scene_end
    return "\n".join(lines)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_captions.py -v`
Expected: 7개 테스트 전부 PASS.

- [ ] **Step 5: 전체 회귀 테스트**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/ -v`
Expected: 전체 통과 (이 계획 작성 시점 기준 67개 기존 테스트 중 `test_captions.py`의 3개가 이번 7개로 교체되어 총 71개 — `pipeline.py`/`renderer.py`는 무수정이므로 그 외 테스트는 전부 그대로 통과해야 함). 회귀가 있다면 원인을 찾아 고치고 다시 실행한다.

- [ ] **Step 6: Commit**

```bash
git add shortform/captions.py tests/test_captions.py
git commit -m "feat: split captions into phrase-timed boxes with color-only keyword emphasis"
```

---

## 4. Verification (수동 스모크 테스트)

단위 테스트만으로는 ASS 렌더링 결과가 실제로 어떻게 보이는지 확인할 수 없다 — Stage 4a에서 하이라이트 색상 버그(테두리와 글자색이 같아 글자가 안 보이던 문제)가 단위 테스트를 다 통과한 채로 실제 렌더링에서만 발견됐던 전례가 있다. 따라서 이번 Task 완료 후 반드시 다음을 수행한다:

1. `output/scripts/`에 저장된 기존 스크립트 JSON과 `output/media/`에 캐싱된 씬별 클립(`clip_NN.mp4`, `scene_NN.mp3`)을 재사용해 API 비용 없이 재조립한다:
   ```python
   import json
   from pathlib import Path
   from shortform.scene_schema import script_from_dict
   from shortform.captions import build_ass_from_scenes
   from shortform.renderer import assemble_with_transitions
   from shortform.tts import get_audio_duration

   data = json.loads(Path("output/scripts/<파일명>.json").read_text(encoding="utf-8"))
   script = script_from_dict(data)
   work_dir = Path("output/media")
   clip_paths = [work_dir / f"clip_{s.index:02d}.mp4" for s in script.scenes]
   durations = [get_audio_duration(work_dir / f"scene_{s.index:02d}.mp3") for s in script.scenes]
   ass_text = build_ass_from_scenes(script.scenes, durations, 0.5)
   assemble_with_transitions(clip_paths, durations, ass_text, Path("output/recheck2.mp4"), transition_duration=0.5)
   ```
2. `ffmpeg -i output/recheck2.mp4 -vf fps=4 <프레임 폴더>/f_%03d.jpg`로 프레임을 추출한다.
3. 프레임을 직접 읽어 다음을 육안 확인한다: (a) 자막이 씬 전체가 아니라 문구 단위로 끊어져 순차 등장하는지, (b) 자막 뒤에 반투명 배경 박스가 실제로 보이는지 (글자만 있고 박스가 안 보이면 `BorderStyle=3` 관련 값 조정 필요), (c) 하이라이트 키워드가 박스 안에서 색상만 다르게 보이는지, 글자가 안 보이거나 뭉개지지 않는지.
4. 문제가 있으면 (예: 박스가 너무 진하거나 연함, `Outline` 패딩 값이 부적절함) `ASS_HEADER`의 `Style: Box` 필드 값(특히 `OutlineColour`의 알파값, `Outline` 패딩)을 조정하고 1~3을 반복한다.
