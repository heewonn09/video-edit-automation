# 폴라로이드 스타일 이미지 씬 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI 생성 정적 이미지 씬을 화면 꽉 채우는 켄번즈 대신, 흐린 배경 위에 흰 테두리+그림자+살짝 기울어진 폴라로이드 사진으로 보여준다.

**Architecture:** 새 모듈 `shortform/polaroid.py`에 (1) 순수 문자열로 ffmpeg 합성 필터를 만드는 `build_polaroid_filter_complex`와 (2) 그 필터로 실제 ffmpeg를 실행하는 `build_polaroid_scene_clip`을 만든다. `shortform/pipeline.py`는 씬의 미디어 타입이 이미지면 이 새 함수를, 실제 영상 파일이면 기존 `build_scene_clip`을 그대로 호출하도록 분기한다.

**Tech Stack:** 순수 ffmpeg 필터(`gblur`, `eq`, `zoompan`, `pad`, `split`, `colorchannelmixer`, `rotate`, `overlay`) + Python. 새 pip 의존성 없음.

## Global Constraints

- 새 파일 `shortform/polaroid.py` 하나 생성. `shortform/renderer.py`는 **완전히 무수정** — 기존 `build_scene_clip`의 이미지 전체화면 켄번즈 로직(Stage 4a-후속2에서 만든 `pan_variant` 4종 순환)은 절대 지우거나 고치지 않는다. 이 기능은 실제 영상 파일(`media_type == "video"`) 씬에서 계속 쓰이므로 그대로 둔다.
- `shortform/pipeline.py`만 추가로 수정한다 (씬별 클립 생성 분기 + import 한 줄).
- 새 pip 의존성 금지.
- 폴라로이드 스타일은 **이미지 씬에만** 적용한다 — 실제 업로드 영상(`media_type == "video"`)은 기존 `build_scene_clip` 그대로 사용, 무수정.
- 모든 외부 호출(ffmpeg)은 `unittest.mock.patch`로 모킹 가능해야 한다.
- 캔버스 1080x1920, 사진 영역 800x1420, 테두리 좌/우/위 20px, 아래 90px(두껍게 — 클래식 폴라로이드 모양), 기울임 ±6도, 씬마다 번갈아 적용.
- 필터 체인이 복잡해서(회전+그림자+흐림 겹침) 문서상 숫자만으로 완벽을 보장하기 어렵다 — 마지막에 반드시 실제 렌더링 + 프레임 육안 확인 단계를 거친다.

---

## 1. File Structure

```
shortform/
├── polaroid.py    # [신규] build_polaroid_filter_complex(frame_count, tilt_deg) -> str
│                  #        build_polaroid_scene_clip(image_path, audio_path, duration, out_path, tilt_variant=0) -> Path
└── pipeline.py     # [수정] import 추가 + 씬별 클립 생성 시 media_type으로 분기
tests/
├── test_polaroid.py   # [신규]
└── test_pipeline.py    # [수정] 이미지 씬 테스트가 build_polaroid_scene_clip을 모킹하도록 갱신 + video 분기 신규 테스트 추가
```

`shortform/renderer.py`, `tests/test_renderer.py`는 이번 계획에서 건드리지 않는다.

---

## 2. Current State (참고용)

`shortform/pipeline.py`의 씬별 클립 생성 루프 (수정 전):

```python
    successful_scenes = []
    clip_paths = []
    durations = []
    for scene in script.scenes:
        if scene.index not in audio_paths or scene.index not in scene_media:
            continue
        media = scene_media[scene.index]
        duration = durations_by_index[scene.index]
        clip_path = work_dir / f"clip_{scene.index:02d}.mp4"
        try:
            build_scene_clip(
                media.path, media.media_type, audio_paths[scene.index], duration, clip_path,
                pan_variant=scene.index,
            )
        except Exception as e:
            logger.warning(f"씬 {scene.index} 클립 생성 실패 ({e}) — 스킵")
            continue
        successful_scenes.append(scene)
        clip_paths.append(clip_path)
        durations.append(duration)
```

`tests/test_pipeline.py`의 관련 기존 테스트들은 `SceneMedia(1, tmp_path / "scene_01.png", "image")`처럼 이미지 미디어를 쓰고 있어서, 이번 분기 도입 후에는 `build_scene_clip` 대신 `build_polaroid_scene_clip`으로 라우팅된다 — Task 3에서 이 테스트들의 모킹 대상을 갱신한다.

---

## 3. 상세 구현 계획 (TDD, 즉시 실행 가능)

### Task 1: 폴라로이드 합성 필터 문자열 빌더 — `shortform/polaroid.py` (신규, 함수 1개)

**Files:**
- Create: `shortform/polaroid.py` (이번 Task에서는 `build_polaroid_filter_complex`만 작성)
- Test: `tests/test_polaroid.py` (신규)

**Interfaces:**
- Produces: `build_polaroid_filter_complex(frame_count: int, tilt_deg: float) -> str` — Task 2가 이 함수를 호출해 ffmpeg `-filter_complex` 인자로 그대로 사용한다.

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_polaroid.py`)

```python
from shortform.polaroid import build_polaroid_filter_complex


def test_build_polaroid_filter_complex_includes_background_blur():
    result = build_polaroid_filter_complex(120, -6)
    assert "gblur=sigma=20" in result
    assert "eq=brightness=-0.15" in result


def test_build_polaroid_filter_complex_includes_gentle_zoom_on_photo():
    result = build_polaroid_filter_complex(120, -6)
    assert "zoompan=z='min(zoom+0.0005,1.08)':d=120:" in result


def test_build_polaroid_filter_complex_includes_asymmetric_white_border():
    result = build_polaroid_filter_complex(120, -6)
    assert "pad=840:1530:20:20:color=white" in result


def test_build_polaroid_filter_complex_rotates_by_tilt_angle():
    result_negative = build_polaroid_filter_complex(120, -6)
    assert "rotate=-0.104720:" in result_negative

    result_positive = build_polaroid_filter_complex(120, 6)
    assert "rotate=0.104720:" in result_positive


def test_build_polaroid_filter_complex_includes_offset_shadow_overlay():
    result = build_polaroid_filter_complex(120, -6)
    assert "colorchannelmixer=rr=0:gg=0:bb=0:aa=0.45" in result
    assert "overlay=(W-w)/2+12:(H-h)/2+16" in result
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_polaroid.py -v`
Expected: `ModuleNotFoundError: No module named 'shortform.polaroid'`

- [ ] **Step 3: 최소 구현** (`shortform/polaroid.py`)

```python
import math

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920
PHOTO_WIDTH = 800
PHOTO_HEIGHT = 1420
BORDER_SIDE = 20
BORDER_TOP = 20
BORDER_BOTTOM = 90
FRAMED_WIDTH = PHOTO_WIDTH + 2 * BORDER_SIDE
FRAMED_HEIGHT = PHOTO_HEIGHT + BORDER_TOP + BORDER_BOTTOM


def build_polaroid_filter_complex(frame_count: int, tilt_deg: float) -> str:
    angle = f"{tilt_deg * math.pi / 180:.6f}"
    return (
        f"[0:v]scale={CANVAS_WIDTH}:{CANVAS_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={CANVAS_WIDTH}:{CANVAS_HEIGHT},split=2[bg_raw][photo_src];"
        f"[bg_raw]gblur=sigma=20,eq=brightness=-0.15[bg];"
        f"[photo_src]scale={PHOTO_WIDTH}:{PHOTO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={PHOTO_WIDTH}:{PHOTO_HEIGHT},scale=8000:-2,"
        f"zoompan=z='min(zoom+0.0005,1.08)':d={frame_count}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={PHOTO_WIDTH}x{PHOTO_HEIGHT}:fps=30,"
        f"format=yuva420p[photo_motion];"
        f"[photo_motion]pad={FRAMED_WIDTH}:{FRAMED_HEIGHT}:{BORDER_SIDE}:{BORDER_TOP}:color=white[framed];"
        f"[framed]split=2[framed_photo][framed_shadow_src];"
        f"[framed_shadow_src]colorchannelmixer=rr=0:gg=0:bb=0:aa=0.45,"
        f"rotate={angle}:c=none:ow=rotw({angle}):oh=roth({angle})[rotated_shadow];"
        f"[framed_photo]rotate={angle}:c=none:ow=rotw({angle}):oh=roth({angle})[rotated_photo];"
        f"[bg][rotated_shadow]overlay=(W-w)/2+12:(H-h)/2+16:format=auto[bg_shadow];"
        f"[bg_shadow][rotated_photo]overlay=(W-w)/2:(H-h)/2:format=auto[v]"
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_polaroid.py -v`
Expected: 5개 전부 PASS.

- [ ] **Step 5: 전체 회귀 테스트**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/ -v`
Expected: 전체 통과 (이 계획 작성 시점 기준 84개 기존 + 5개 신규 = 89개).

- [ ] **Step 6: Commit**

```bash
git add shortform/polaroid.py tests/test_polaroid.py
git commit -m "feat: add polaroid composite filter string builder"
```

---

### Task 2: 폴라로이드 씬 클립 생성 함수 — `shortform/polaroid.py` (함수 추가)

**Files:**
- Modify: `shortform/polaroid.py` (함수 추가, Task 1의 상수/함수는 무수정)
- Test: `tests/test_polaroid.py` (테스트 추가)

**Interfaces:**
- Consumes: `build_polaroid_filter_complex(frame_count, tilt_deg) -> str` (Task 1).
- Produces: `build_polaroid_scene_clip(image_path, audio_path, duration, out_path, tilt_variant=0) -> Path` — Task 3이 `shortform.polaroid`에서 이 함수를 직접 import해 사용한다 (`build_ass_from_scenes`를 `pipeline.py`가 `shortform.captions`에서 직접 가져오는 것과 같은 패턴 — `renderer.py`를 거치지 않는다).

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_polaroid.py`에 추가)

```python
from unittest.mock import patch


@patch("shortform.polaroid.subprocess.run")
def test_build_polaroid_scene_clip_calls_ffmpeg_with_filter(mock_run, tmp_path):
    from shortform.polaroid import build_polaroid_scene_clip

    out_path = tmp_path / "clip.mp4"
    result = build_polaroid_scene_clip(tmp_path / "scene.png", tmp_path / "audio.mp3", 4.0, out_path)

    cmd = mock_run.call_args[0][0]
    assert "-filter_complex" in cmd
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "rotate=-0.104720:" in filter_complex
    assert "-map" in cmd
    assert "[v]" in cmd
    assert "-t" in cmd
    assert "4.0" in cmd
    assert result == out_path


@patch("shortform.polaroid.subprocess.run")
def test_build_polaroid_scene_clip_tilt_variant_alternates_direction(mock_run, tmp_path):
    from shortform.polaroid import build_polaroid_scene_clip

    out_path = tmp_path / "clip.mp4"
    build_polaroid_scene_clip(tmp_path / "scene.png", tmp_path / "audio.mp3", 4.0, out_path, tilt_variant=1)

    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "rotate=0.104720:" in filter_complex
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_polaroid.py -v`
Expected: `ImportError: cannot import name 'build_polaroid_scene_clip'`

- [ ] **Step 3: 최소 구현** (`shortform/polaroid.py` 맨 위에 import 2줄 추가, 파일 맨 아래에 함수 추가 — Task 1의 상수/`build_polaroid_filter_complex`는 무수정)

파일 맨 위, `import math` 다음 줄에 추가:

```python
import subprocess
from pathlib import Path
```

파일 맨 아래에 추가:

```python
def build_polaroid_scene_clip(image_path, audio_path, duration, out_path, tilt_variant=0):
    image_path = str(image_path)
    audio_path = str(audio_path)
    out_path = Path(out_path)

    frame_count = max(1, int(duration * 30))
    tilt_deg = -6 if tilt_variant % 2 == 0 else 6
    filter_complex = build_polaroid_filter_complex(frame_count, tilt_deg)

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

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_polaroid.py -v`
Expected: 7개 전부 PASS.

- [ ] **Step 5: 전체 회귀 테스트**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/ -v`
Expected: 전체 통과 (Task 1 완료 후 89개 + 이번 2개 = 91개).

- [ ] **Step 6: Commit**

```bash
git add shortform/polaroid.py tests/test_polaroid.py
git commit -m "feat: add ffmpeg-invoking polaroid scene clip builder"
```

---

### Task 3: 파이프라인에서 이미지/영상 분기 — `shortform/pipeline.py` (수정)

**Files:**
- Modify: `shortform/pipeline.py` (import 한 줄 + 씬별 클립 생성 루프)
- Test: `tests/test_pipeline.py` (기존 2개 테스트의 모킹 대상 갱신 + 신규 1개 테스트)

**Interfaces:**
- Consumes: `build_polaroid_scene_clip(image_path, audio_path, duration, out_path, tilt_variant=0) -> Path` (Task 2).
- `render_script`의 공개 시그니처는 그대로 유지한다.

- [ ] **Step 1: 기존 테스트 갱신 + 신규 테스트 추가** (`tests/test_pipeline.py`)

`test_render_script_wires_all_stages`를 아래로 전체 교체 (이미지 미디어를 쓰므로 `build_scene_clip` 대신 `build_polaroid_scene_clip`을 모킹하도록 갱신):

```python
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_polaroid_scene_clip")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_wires_all_stages(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_polaroid, mock_assemble, tmp_path
):
    script = Script(title="T", scenes=[Scene(1, "나레이션", "골목길", 4.0)])
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {1: SceneMedia(1, tmp_path / "scene_01.png", "image")}
    mock_ass.return_value = "ASS_TEXT"
    mock_polaroid.return_value = work_dir / "clip_01.mp4"
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

    # Image scenes route to build_polaroid_scene_clip, not build_scene_clip
    mock_polaroid.assert_called_once_with(
        tmp_path / "scene_01.png",
        work_dir / "scene_01.mp3",
        4.0,
        work_dir / "clip_01.mp4",
        tilt_variant=1,
    )

    mock_ass.assert_called_once_with(script.scenes, [4.0], TRANSITION_DURATION_SEC)
    mock_assemble.assert_called_once()
    assert result == out_path
```

`test_render_script_skips_scene_with_failed_tts`에서 `@patch("shortform.pipeline.build_scene_clip")`를 `@patch("shortform.pipeline.build_polaroid_scene_clip")`로, 파라미터명 `mock_clip`을 `mock_polaroid`로 바꾸고, `mock_clip.return_value = tmp_path / "clip_01.mp4"`를 `mock_polaroid.return_value = tmp_path / "clip_01.mp4"`로, `mock_clip.assert_called_once()`를 `mock_polaroid.assert_called_once()`로 바꾼다 (이 테스트의 성공 씬도 `scene_01.png`, 즉 이미지이므로 동일한 라우팅 변경이 적용된다). 그 외 로직(TTS 실패 시뮬레이션, 로그 검증 등)은 그대로 둔다.

새 테스트를 파일 맨 아래에 추가 (영상 미디어는 여전히 기존 `build_scene_clip`으로 라우팅되는지 확인):

```python
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_scene_clip")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_routes_video_media_to_build_scene_clip(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_clip, mock_assemble, tmp_path
):
    script = Script(title="T", scenes=[Scene(1, "나레이션", "골목길", 4.0)])
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {1: SceneMedia(1, tmp_path / "scene_01.mp4", "video")}
    mock_ass.return_value = "ASS_TEXT"
    mock_clip.return_value = work_dir / "clip_01.mp4"
    out_path = tmp_path / "final.mp4"
    mock_assemble.return_value = out_path

    render_script(script, out_path, asset_folder=None, work_dir=work_dir)

    mock_clip.assert_called_once_with(
        tmp_path / "scene_01.mp4",
        "video",
        work_dir / "scene_01.mp3",
        4.0,
        work_dir / "clip_01.mp4",
        pan_variant=1,
    )
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_pipeline.py -v`
Expected: 갱신된 2개 테스트가 `AttributeError`(아직 `pipeline.py`가 `build_polaroid_scene_clip`을 import하지 않음)로 실패, 신규 테스트는 아직 분기가 없어 `build_scene_clip`이 이미지 인자로 호출되는 형태로 실패(assert 불일치).

- [ ] **Step 3: 최소 구현** (`shortform/pipeline.py`의 import 블록과 씬별 클립 생성 루프만 교체)

import 블록에 한 줄 추가 (`from shortform.media_matcher import resolve_scene_media` 다음 줄 등 적절한 위치에):

```python
from shortform.polaroid import build_polaroid_scene_clip
```

씬별 클립 생성 루프(`try:` 블록 안의 `build_scene_clip(...)` 호출부)를 아래로 교체:

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

(그 앞뒤의 `successful_scenes`/`clip_paths`/`durations` 갱신 로직은 무수정.)

- [ ] **Step 4: 테스트 통과 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_pipeline.py -v`
Expected: 전부 PASS.

- [ ] **Step 5: 전체 회귀 테스트**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/ -v`
Expected: 전체 통과 (Task 2 완료 후 91개 + 이번 1개 신규 = 92개. `test_renderer.py`의 `build_scene_clip` 관련 테스트들은 이 계획에서 전혀 건드리지 않으므로 그대로 통과해야 한다).

- [ ] **Step 6: Commit**

```bash
git add shortform/pipeline.py tests/test_pipeline.py
git commit -m "feat: route image scenes to polaroid style, keep video scenes on Ken Burns"
```

---

## 4. Verification (수동 스모크 테스트 + 육안 튜닝, 필수)

이 계획의 필터 체인(배경 흐림 + 사진 확대 + 흰 테두리 + 회전 + 그림자 + 합성)은 단위 테스트로 "필터 문자열에 원하는 조각이 들어있는지"만 확인할 뿐, 실제로 그럴듯하게 보이는지는 전혀 보장하지 않는다. Stage 4a에서 하이라이트 자막 색상이 텍스트와 테두리가 같은 색이라 안 보이던 버그처럼, 이런 종류의 문제는 실제 렌더링 전에는 절대 드러나지 않는다. 세 Task 완료 후 반드시 다음을 수행한다:

1. `output/media/generated/`에 캐싱된 이미지와 `output/scripts/`의 스크립트 JSON을 재사용해 API 비용 없이 폴라로이드 클립을 만든다:
   ```python
   import json
   from pathlib import Path
   from shortform.scene_schema import script_from_dict
   from shortform.polaroid import build_polaroid_scene_clip
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
       out_path = Path(f"output/polaroid_check_{scene.index:02d}.mp4")
       build_polaroid_scene_clip(image_path, work_dir / f"scene_{scene.index:02d}.mp3", duration, out_path, tilt_variant=scene.index)
       print("wrote", out_path)
   ```
2. `ffmpeg -i output/polaroid_check_01.mp4 -vf fps=3 <프레임 폴더>/f_%03d.jpg`로 프레임을 추출해서 직접 읽어 확인한다: (a) 흰 테두리가 아래쪽만 두껍게 보이는지(폴라로이드 모양), (b) 사진이 살짝 기울어져 있는지, (c) 뒤에 그림자가 자연스럽게 보이는지(너무 진하거나 아예 안 보이지 않는지), (d) 배경이 과하게 밝거나 사진과 색이 부딪히지 않는지, (e) 사진 안쪽의 약한 확대 움직임이 어색하지 않은지.
3. 문제가 있으면 `shortform/polaroid.py`의 상수(`gblur=sigma=20`, `eq=brightness=-0.15`, `colorchannelmixer=...aa=0.45`, `overlay=...+12:...+16`, `BORDER_*` 값들)를 조정하고 1~2를 반복한다.
4. 여러 씬을 한 번에 이어붙여서(예: 기존 `assemble_with_transitions` 재사용) 최종 결과물에서도 자연스러운지 확인한다.
