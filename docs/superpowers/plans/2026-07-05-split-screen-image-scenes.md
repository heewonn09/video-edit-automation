# 스플릿 스크린 스타일 이미지 씬 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 이미지 씬에 폴라로이드 스타일과 순환하는 두 번째 비주얼 스타일로, 같은 사진 한 장을 상/하 두 패널로 복제해 서로 다른 켄번즈 움직임을 주는 "스플릿 스크린" 스타일을 추가한다.

**Architecture:** 새 모듈 `shortform/split_screen.py`에 (1) 순수 문자열로 ffmpeg 합성 필터를 만드는 `build_split_screen_filter_complex`와 (2) 그 필터로 실제 ffmpeg를 실행하는 `build_split_screen_scene_clip`을 만든다. `shortform/pipeline.py`는 이미지 씬을 만날 때 씬 인덱스 짝/홀수로 폴라로이드와 스플릿 스크린을 순환시킨다.

**Tech Stack:** 순수 ffmpeg 필터(`split`, `zoompan`, `vstack`) + Python. 새 pip 의존성 없음.

## Global Constraints

- 새 파일 `shortform/split_screen.py` 하나 생성. `shortform/renderer.py`, `shortform/polaroid.py`는 완전히 무수정.
- `shortform/pipeline.py`만 추가로 수정한다 (이미지 씬 분기에 짝/홀수 조건 추가 + import 한 줄).
- 새 pip 의존성 금지.
- 캔버스 1080x1920, 각 패널 1080x960 (세로 절반씩). 상단 패널은 고정 줌(1.12)으로 좌→우 팬, 하단 패널은 중앙 확대(1.0→1.15)로 서로 다른 움직임을 준다.
- 같은 원본 이미지를 `split` 필터로 복제해서 두 패널에 각각 다르게 적용한다 (실제로 사진을 반으로 자르는 게 아니라, 같은 사진 전체를 두 번 다르게 크롭/확대해서 보여준다).
- 이미지 씬의 스타일 선택: `scene.index % 2 == 0`이면 기존 폴라로이드(`build_polaroid_scene_clip`), 아니면 스플릿 스크린(`build_split_screen_scene_clip`). 실제 영상 파일(`media_type == "video"`)은 인덱스와 무관하게 계속 기존 `build_scene_clip`.
- 모든 외부 호출(ffmpeg)은 `unittest.mock.patch`로 모킹 가능해야 한다.
- 필터가 복잡해서 문서상 숫자만으로 완벽을 보장하기 어렵다 — 마지막에 반드시 실제 렌더링 + 프레임 육안 확인 단계를 거친다.

---

## 1. File Structure

```
shortform/
├── split_screen.py    # [신규] build_split_screen_filter_complex(frame_count) -> str
│                       #        build_split_screen_scene_clip(image_path, audio_path, duration, out_path) -> Path
└── pipeline.py          # [수정] import 추가 + 이미지 씬 분기에 짝/홀수 조건 추가
tests/
├── test_split_screen.py   # [신규]
└── test_pipeline.py        # [수정] 기존 이미지 씬 테스트 2개 갱신(홀수 인덱스라 스플릿 스크린으로 라우팅됨을 반영) + 짝수 인덱스(폴라로이드) 신규 테스트 1개 추가
```

`shortform/renderer.py`, `shortform/polaroid.py`, `tests/test_renderer.py`, `tests/test_polaroid.py`는 이번 계획에서 건드리지 않는다.

---

## 2. Current State (참고용)

`shortform/pipeline.py`의 씬별 클립 생성 루프 (수정 전 — Stage 4a-후속4에서 폴라로이드 분기가 이미 들어간 상태):

```python
        try:
            if media.media_type == "image":
                build_polaroid_scene_clip(
                    media.path, audio_paths[scene.index], duration, clip_path,
                    tilt_variant=scene.index,
                )
            else:
                build_scene_clip(
                    media.path, media.media_type, audio_paths[scene.index], duration, clip_path,
                    pan_variant=scene.index,
                )
        except Exception as e:
            logger.warning(f"씬 {scene.index} 클립 생성 실패 ({e}) — 스킵")
            continue
```

`tests/test_pipeline.py`의 기존 이미지 씬 테스트들은 씬 인덱스 1을 쓰고 있다 — 1은 홀수이므로 이번 변경 후에는 `build_polaroid_scene_clip`이 아니라 `build_split_screen_scene_clip`으로 라우팅된다. Task 3에서 이 테스트들의 모킹 대상을 갱신하고, 짝수 인덱스(폴라로이드 경로)를 검증하는 테스트를 새로 추가한다.

---

## 3. 상세 구현 계획 (TDD, 즉시 실행 가능)

### Task 1: 스플릿 스크린 합성 필터 문자열 빌더 — `shortform/split_screen.py` (신규, 함수 1개)

**Files:**
- Create: `shortform/split_screen.py` (이번 Task에서는 `build_split_screen_filter_complex`만 작성)
- Test: `tests/test_split_screen.py` (신규)

**Interfaces:**
- Produces: `build_split_screen_filter_complex(frame_count: int) -> str` — Task 2가 이 함수를 호출해 ffmpeg `-filter_complex` 인자로 그대로 사용한다.

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_split_screen.py`)

```python
from shortform.split_screen import build_split_screen_filter_complex


def test_build_split_screen_filter_complex_splits_source_before_branching():
    result = build_split_screen_filter_complex(120)
    assert "[0:v]split=2[top_src][bottom_src]" in result


def test_build_split_screen_filter_complex_top_panel_pans_left_to_right():
    result = build_split_screen_filter_complex(120)
    assert "z='1.12':d=120:" in result
    assert "x='(iw-iw/zoom)*on/119'" in result


def test_build_split_screen_filter_complex_bottom_panel_zooms_center():
    result = build_split_screen_filter_complex(120)
    assert "z='min(zoom+0.0006,1.15)':d=120:" in result


def test_build_split_screen_filter_complex_uses_half_height_panels():
    result = build_split_screen_filter_complex(120)
    assert "crop=1080:960" in result


def test_build_split_screen_filter_complex_stacks_panels_vertically():
    result = build_split_screen_filter_complex(120)
    assert "[top][bottom]vstack=inputs=2[v]" in result
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_split_screen.py -v`
Expected: `ModuleNotFoundError: No module named 'shortform.split_screen'`

- [ ] **Step 3: 최소 구현** (`shortform/split_screen.py`)

```python
PANEL_WIDTH = 1080
PANEL_HEIGHT = 960


def build_split_screen_filter_complex(frame_count: int) -> str:
    denom = max(frame_count - 1, 1)
    return (
        f"[0:v]split=2[top_src][bottom_src];"
        f"[top_src]scale={PANEL_WIDTH}:{PANEL_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={PANEL_WIDTH}:{PANEL_HEIGHT},scale=8000:-2,"
        f"zoompan=z='1.12':d={frame_count}:"
        f"x='(iw-iw/zoom)*on/{denom}':y='ih/2-(ih/zoom/2)':s={PANEL_WIDTH}x{PANEL_HEIGHT}:fps=30,"
        f"format=yuv420p[top];"
        f"[bottom_src]scale={PANEL_WIDTH}:{PANEL_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={PANEL_WIDTH}:{PANEL_HEIGHT},scale=8000:-2,"
        f"zoompan=z='min(zoom+0.0006,1.15)':d={frame_count}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={PANEL_WIDTH}x{PANEL_HEIGHT}:fps=30,"
        f"format=yuv420p[bottom];"
        f"[top][bottom]vstack=inputs=2[v]"
    )
```

(같은 원본을 두 번 다르게 처리해야 하므로 `[0:v]`를 `split=2`로 먼저 복제한다 — `shortform/polaroid.py`의 `build_polaroid_filter_complex`가 배경/사진을 나눌 때 쓴 것과 같은, 이미 검증된 패턴이다.)

- [ ] **Step 4: 테스트 통과 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_split_screen.py -v`
Expected: 5개 전부 PASS.

- [ ] **Step 5: 전체 회귀 테스트**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/ -v`
Expected: 전체 통과 (이 계획 작성 시점 기준 92개 기존 + 5개 신규 = 97개).

- [ ] **Step 6: Commit**

```bash
git add shortform/split_screen.py tests/test_split_screen.py
git commit -m "feat: add split-screen composite filter string builder"
```

---

### Task 2: 스플릿 스크린 씬 클립 생성 함수 — `shortform/split_screen.py` (함수 추가)

**Files:**
- Modify: `shortform/split_screen.py` (함수 추가, Task 1의 상수/함수는 무수정)
- Test: `tests/test_split_screen.py` (테스트 추가)

**Interfaces:**
- Consumes: `build_split_screen_filter_complex(frame_count) -> str` (Task 1).
- Produces: `build_split_screen_scene_clip(image_path, audio_path, duration, out_path) -> Path` — Task 3이 `shortform.split_screen`에서 이 함수를 직접 import해 사용한다.

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_split_screen.py`에 추가)

```python
from unittest.mock import patch


@patch("shortform.split_screen.subprocess.run")
def test_build_split_screen_scene_clip_calls_ffmpeg_with_filter(mock_run, tmp_path):
    from shortform.split_screen import build_split_screen_scene_clip

    out_path = tmp_path / "clip.mp4"
    result = build_split_screen_scene_clip(tmp_path / "scene.png", tmp_path / "audio.mp3", 4.0, out_path)

    cmd = mock_run.call_args[0][0]
    assert "-filter_complex" in cmd
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "vstack=inputs=2" in filter_complex
    assert "-map" in cmd
    assert "[v]" in cmd
    assert "-t" in cmd
    assert "4.0" in cmd
    assert result == out_path
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_split_screen.py -v`
Expected: `ImportError: cannot import name 'build_split_screen_scene_clip'`

- [ ] **Step 3: 최소 구현** (`shortform/split_screen.py` 맨 위에 import 2줄 추가, 파일 맨 아래에 함수 추가 — Task 1의 상수/`build_split_screen_filter_complex`는 무수정)

파일 맨 위, 기존 코드 앞에 추가:

```python
import subprocess
from pathlib import Path
```

파일 맨 아래에 추가:

```python
def build_split_screen_scene_clip(image_path, audio_path, duration, out_path):
    image_path = str(image_path)
    audio_path = str(audio_path)
    out_path = Path(out_path)

    frame_count = max(1, int(duration * 30))
    filter_complex = build_split_screen_filter_complex(frame_count)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-r", "30", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration),
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out_path
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_split_screen.py -v`
Expected: 6개 전부 PASS.

- [ ] **Step 5: 전체 회귀 테스트**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/ -v`
Expected: 전체 통과 (Task 1 완료 후 97개 + 이번 1개 = 98개).

- [ ] **Step 6: Commit**

```bash
git add shortform/split_screen.py tests/test_split_screen.py
git commit -m "feat: add ffmpeg-invoking split-screen scene clip builder"
```

---

### Task 3: 파이프라인에서 폴라로이드/스플릿 스크린 순환 — `shortform/pipeline.py` (수정)

**Files:**
- Modify: `shortform/pipeline.py` (import 한 줄 + 이미지 씬 분기에 짝/홀수 조건 추가)
- Test: `tests/test_pipeline.py` (기존 이미지 씬 테스트 2개의 모킹 대상 갱신 + 신규 1개 테스트)

**Interfaces:**
- Consumes: `build_split_screen_scene_clip(image_path, audio_path, duration, out_path) -> Path` (Task 2), 기존 `build_polaroid_scene_clip`.
- `render_script`의 공개 시그니처는 그대로 유지한다.

- [ ] **Step 1: 기존 테스트 갱신 + 신규 테스트 추가** (`tests/test_pipeline.py`)

`test_render_script_wires_all_stages`를 아래로 전체 교체 (씬 인덱스 1은 홀수이므로 이제 `build_split_screen_scene_clip`으로 라우팅된다):

```python
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_split_screen_scene_clip")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_wires_all_stages(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_split, mock_assemble, tmp_path
):
    script = Script(title="T", scenes=[Scene(1, "나레이션", "골목길", 4.0)])
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {1: SceneMedia(1, tmp_path / "scene_01.png", "image")}
    mock_ass.return_value = "ASS_TEXT"
    mock_split.return_value = work_dir / "clip_01.mp4"
    out_path = tmp_path / "final.mp4"
    mock_assemble.return_value = out_path

    result = render_script(script, out_path, asset_folder=None, work_dir=work_dir)

    mock_tts.assert_called_once_with("나레이션", work_dir / "scene_01.mp3")

    call_args = mock_resolve.call_args
    assert call_args[0][1] is None
    assert call_args[0][2] == work_dir / "generated"
    filtered_script = call_args[0][0]
    assert filtered_script.title == script.title
    assert len(filtered_script.scenes) == 1
    assert filtered_script.scenes[0].index == 1

    mock_duration.assert_called_once_with(work_dir / "scene_01.mp3")

    # Odd scene index routes image scenes to build_split_screen_scene_clip
    mock_split.assert_called_once_with(
        tmp_path / "scene_01.png",
        work_dir / "scene_01.mp3",
        4.0,
        work_dir / "clip_01.mp4",
    )

    mock_ass.assert_called_once_with(script.scenes, [4.0], TRANSITION_DURATION_SEC)
    mock_assemble.assert_called_once()
    assert result == out_path
```

`test_render_script_skips_scene_with_failed_tts`를 아래로 전체 교체 (성공한 유일한 씬의 인덱스가 1로 홀수이므로 마찬가지로 `build_split_screen_scene_clip`으로 라우팅된다):

```python
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_split_screen_scene_clip")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_skips_scene_with_failed_tts(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_split, mock_assemble, tmp_path, caplog
):
    script = Script(
        title="T",
        scenes=[
            Scene(1, "성공 나레이션", "골목길", 4.0),
            Scene(2, "실패 나레이션", "카페", 5.0),
        ],
    )
    mock_tts.side_effect = [None, RuntimeError("TTS 실패")]
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {
        1: SceneMedia(1, tmp_path / "scene_01.png", "image"),
        2: SceneMedia(2, tmp_path / "scene_02.png", "image"),
    }
    mock_ass.return_value = "ASS_TEXT"
    mock_split.return_value = tmp_path / "clip_01.mp4"
    out_path = tmp_path / "final.mp4"
    mock_assemble.return_value = out_path

    with caplog.at_level("WARNING"):
        result = render_script(script, out_path, work_dir=tmp_path / "media")

    call_args = mock_resolve.call_args
    filtered_script = call_args[0][0]
    assert len(filtered_script.scenes) == 1
    assert filtered_script.scenes[0].index == 1

    mock_split.assert_called_once()
    assert mock_ass.call_args[0][0] == [script.scenes[0]]
    assert mock_ass.call_args[0][2] == TRANSITION_DURATION_SEC
    assert "씬 2" in caplog.text
    assert result == out_path
```

새 테스트를 파일 맨 아래에 추가 (짝수 인덱스 이미지 씬은 여전히 폴라로이드로 라우팅되는지 확인):

```python
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_polaroid_scene_clip")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_routes_even_index_image_scene_to_polaroid(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_polaroid, mock_assemble, tmp_path
):
    script = Script(title="T", scenes=[Scene(2, "나레이션", "골목길", 4.0)])
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {2: SceneMedia(2, tmp_path / "scene_02.png", "image")}
    mock_ass.return_value = "ASS_TEXT"
    mock_polaroid.return_value = work_dir / "clip_02.mp4"
    out_path = tmp_path / "final.mp4"
    mock_assemble.return_value = out_path

    render_script(script, out_path, asset_folder=None, work_dir=work_dir)

    mock_polaroid.assert_called_once_with(
        tmp_path / "scene_02.png",
        work_dir / "scene_02.mp3",
        4.0,
        work_dir / "clip_02.mp4",
        tilt_variant=2,
    )
```

(`test_render_script_routes_video_media_to_build_scene_clip`은 미디어 타입이 `"video"`라 인덱스 짝/홀수와 무관하게 계속 `build_scene_clip`으로 가므로 무수정.)

- [ ] **Step 2: 테스트 실패 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_pipeline.py -v`
Expected: 갱신된 2개 테스트가 `AttributeError`(아직 `pipeline.py`가 `build_split_screen_scene_clip`을 import하지 않음)로 실패, 신규 테스트는 아직 짝/홀수 분기가 없어 실패.

- [ ] **Step 3: 최소 구현** (`shortform/pipeline.py`의 import 블록과 이미지 씬 분기만 교체)

import 블록에 한 줄 추가 (`from shortform.polaroid import build_polaroid_scene_clip` 다음 줄 등 적절한 위치에):

```python
from shortform.split_screen import build_split_screen_scene_clip
```

씬별 클립 생성 루프의 `try:` 블록을 아래로 교체:

```python
        try:
            if media.media_type == "image":
                if scene.index % 2 == 0:
                    build_polaroid_scene_clip(
                        media.path, audio_paths[scene.index], duration, clip_path,
                        tilt_variant=scene.index,
                    )
                else:
                    build_split_screen_scene_clip(
                        media.path, audio_paths[scene.index], duration, clip_path,
                    )
            else:
                build_scene_clip(
                    media.path, media.media_type, audio_paths[scene.index], duration, clip_path,
                    pan_variant=scene.index,
                )
        except Exception as e:
            logger.warning(f"씬 {scene.index} 클립 생성 실패 ({e}) — 스킵")
            continue
```

(그 앞뒤의 `successful_scenes`/`clip_paths`/`durations` 갱신 로직은 무수정.)

- [ ] **Step 4: 테스트 통과 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_pipeline.py -v`
Expected: 전부 PASS.

- [ ] **Step 5: 전체 회귀 테스트**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/ -v`
Expected: 전체 통과 (Task 2 완료 후 98개 + 이번 1개 신규 = 99개. `test_renderer.py`, `test_polaroid.py`는 이 계획에서 전혀 건드리지 않으므로 그대로 통과해야 한다).

- [ ] **Step 6: Commit**

```bash
git add shortform/pipeline.py tests/test_pipeline.py
git commit -m "feat: cycle image scenes between polaroid and split-screen styles"
```

---

## 4. Verification (수동 스모크 테스트 + 육안 튜닝, 필수)

세 Task 완료 후 반드시 다음을 수행한다:

1. `output/media/generated/`에 캐싱된 이미지와 `output/scripts/`의 스크립트 JSON을 재사용해 API 비용 없이 스플릿 스크린 클립을 만든다:
   ```python
   import json
   from pathlib import Path
   from shortform.scene_schema import script_from_dict
   from shortform.split_screen import build_split_screen_scene_clip
   from shortform.tts import get_audio_duration

   data = json.loads(Path("output/scripts/<파일명>.json").read_text(encoding="utf-8"))
   script = script_from_dict(data)
   work_dir = Path("output/media")
   generated_dir = work_dir / "generated"

   for scene in script.scenes:
       image_path = generated_dir / f"scene_{scene.index:02d}.png"
       if not image_path.exists():
           continue
       duration = get_audio_duration(work_dir / f"scene_{scene.index:02d}.mp3")
       out_path = Path(f"output/split_check_{scene.index:02d}.mp4")
       build_split_screen_scene_clip(image_path, work_dir / f"scene_{scene.index:02d}.mp3", duration, out_path)
       print("wrote", out_path)
   ```
2. `ffmpeg -i output/split_check_01.mp4 -vf fps=3 <프레임 폴더>/f_%03d.jpg`로 프레임을 추출해서 직접 읽어 확인한다: (a) 위/아래 두 패널이 실제로 서로 다르게 움직이는지(같은 사진이지만 지루하게 똑같이 보이지 않는지), (b) 두 패널의 경계가 어색하지 않은지, (c) 각 패널 안에서 사진이 잘리는 부분이 부자연스럽지 않은지.
3. `pipeline.py`를 통해 실제로 짝/홀수 순환이 눈에 보이는지도 확인한다 — 이전에 만든 `output/polaroid_check_NN.mp4`(짝수 인덱스, 폴라로이드)와 이번 `output/split_check_NN.mp4`(홀수 인덱스, 스플릿 스크린)를 나란히 비교한다.
4. 문제가 있으면 `shortform/split_screen.py`의 상수(`PANEL_HEIGHT`, 줌 배율/속도)를 조정하고 1~2를 반복한다.
