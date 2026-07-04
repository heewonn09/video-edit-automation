# 전환/카메라 워크 다양화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 지금 항상 똑같이 반복되는 "중앙 확대 켄번즈 + 크로스페이드 전환"을, 씬마다 다른 팬 방향과 씬 경계마다 다른 전환 종류로 순환시켜 영상 편집 다양성을 높인다.

**Architecture:** `shortform/renderer.py`의 `build_scene_clip`(이미지 켄번즈)과 `assemble_with_transitions`(씬 간 전환)에 각각 "변형 목록을 인덱스로 순환 선택"하는 로직을 추가한다. `build_scene_clip`은 새 `pan_variant` 파라미터(기본값 0, 하위 호환)를 받아 4가지 zoompan 표현식 중 하나를 선택하고, `pipeline.py`가 씬마다 다른 값(`scene.index`)을 넘겨준다. `assemble_with_transitions`은 시그니처 변경 없이 내부적으로 경계 인덱스에 따라 `xfade`의 `transition=` 값을 4종 순환한다.

**Tech Stack:** 순수 ffmpeg 필터(zoompan의 `on` 프레임 변수, xfade의 `transition=` 파라미터) + Python. 새 pip 의존성 없음.

## Global Constraints

- `shortform/pipeline.py`, `shortform/renderer.py`만 수정한다. `shortform/captions.py`(이번 계획 이전에 이미 완성됨)는 무수정.
- 새 pip 의존성 금지.
- `build_scene_clip(media_path, media_type, audio_path, duration, out_path)`에 `pan_variant=0` 파라미터를 **추가만** 한다 — 기존 4개 위치 인자 순서/의미는 그대로 유지해 하위 호환을 지킨다. `video` 분기(실제 영상 파일)는 켄번즈 대상이 아니므로 `pan_variant`의 영향을 받지 않는다 — 무수정.
- `assemble_with_transitions(scene_clip_paths, durations, ass_text, out_path, transition_duration=0.5)` 시그니처는 그대로 유지한다 — 전환 종류 순환은 함수 내부 로직만 바뀐다.
- 모든 외부 호출(ffmpeg)은 `unittest.mock.patch`로 모킹 가능해야 한다 — 기존 테스트 컨벤션 그대로.
- ffmpeg `zoompan` 필터의 `on` 변수는 해당 클립 안에서의 0부터 시작하는 출력 프레임 번호다 (기존 `zoom` 변수가 이전 프레임의 확대 배율을 누적 참조하는 것과 별개).

---

## 1. File Structure

```
shortform/
├── renderer.py    # [수정] build_scene_clip에 pan_variant 파라미터 + 4종 zoompan 표현식,
│                  #        assemble_with_transitions 내부에서 전환 종류 4종 순환
└── pipeline.py    # [수정] build_scene_clip 호출 시 pan_variant=scene.index 전달
tests/
├── test_renderer.py    # [수정] pan_variant 4종 + 전환 종류 순환/랩어라운드 테스트 추가
└── test_pipeline.py    # [수정] build_scene_clip 호출 검증에 pan_variant 키워드 인자 추가
```

---

## 2. Current State (참고용)

`shortform/renderer.py`의 관련 부분 (수정 전 전체는 저장소에서 직접 확인 가능):

```python
def build_scene_clip(media_path, media_type, audio_path, duration, out_path):
    ...
    if media_type == "image":
        frame_count = max(1, int(duration * 30))
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", media_path,
            "-i", audio_path,
            "-filter_complex",
            (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,scale=8000:-2,"
                f"zoompan=z='min(zoom+0.0015,1.5)':d={frame_count}:"
                "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,"
                "format=yuv420p[v]"
            ),
            ...
        ]
    else:
        ...  # video 분기, 무수정 대상
```

```python
def assemble_with_transitions(scene_clip_paths, durations, ass_text, out_path, transition_duration=0.5):
    ...
    for i in range(1, n):
        offset = cursor - transition_duration
        v_out, a_out = f"v{i}", f"a{i}"
        filter_parts.append(
            f"[{v_label}][{i}:v]xfade=transition=fade:duration={transition_duration}:offset={offset}[{v_out}]"
        )
        ...
```

`tests/test_pipeline.py`의 `test_render_script_wires_all_stages`가 `build_scene_clip`을 5개 위치 인자로 호출하는지 검증 중 (Task 1에서 이 부분을 갱신):

```python
    mock_clip.assert_called_once_with(
        tmp_path / "scene_01.png",
        "image",
        work_dir / "scene_01.mp3",
        4.0,
        work_dir / "clip_01.mp4"
    )
```

---

## 3. 상세 구현 계획 (TDD, 즉시 실행 가능)

### Task 1: 켄번즈 팬 방향 4종 순환 — `shortform/renderer.py`, `shortform/pipeline.py`

**Files:**
- Modify: `shortform/renderer.py` (`build_scene_clip` 이미지 분기만)
- Modify: `shortform/pipeline.py` (`build_scene_clip` 호출 한 줄)
- Test: `tests/test_renderer.py`, `tests/test_pipeline.py`

**Interfaces:**
- Produces: `build_scene_clip(media_path, media_type, audio_path, duration, out_path, pan_variant=0) -> Path` — `pan_variant`는 임의의 정수(음수 아님)를 받아 내부에서 `pan_variant % 4`로 4종 중 하나를 고른다. 호출자는 목록 길이를 몰라도 된다.
- Consumes: 없음 (기존 함수 확장).

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_renderer.py`에 추가 — 기존 `test_build_scene_clip_handles_image`는 그대로 두고 아래 5개를 추가)

```python
@patch("shortform.renderer.subprocess.run")
def test_build_scene_clip_pan_variant_0_is_center_zoom(mock_run, tmp_path):
    out_path = tmp_path / "clip.mp4"
    build_scene_clip(tmp_path / "scene.png", "image", tmp_path / "audio.mp3", 4.0, out_path, pan_variant=0)

    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "z='min(zoom+0.0015,1.5)'" in filter_complex
    assert "x='iw/2-(iw/zoom/2)'" in filter_complex
    assert "y='ih/2-(ih/zoom/2)'" in filter_complex


@patch("shortform.renderer.subprocess.run")
def test_build_scene_clip_pan_variant_1_is_left_to_right(mock_run, tmp_path):
    out_path = tmp_path / "clip.mp4"
    build_scene_clip(tmp_path / "scene.png", "image", tmp_path / "audio.mp3", 4.0, out_path, pan_variant=1)

    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "z='1.15'" in filter_complex
    assert "x='(iw-iw/zoom)*on/119'" in filter_complex
    assert "y='ih/2-(ih/zoom/2)'" in filter_complex


@patch("shortform.renderer.subprocess.run")
def test_build_scene_clip_pan_variant_2_is_right_to_left(mock_run, tmp_path):
    out_path = tmp_path / "clip.mp4"
    build_scene_clip(tmp_path / "scene.png", "image", tmp_path / "audio.mp3", 4.0, out_path, pan_variant=2)

    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "z='1.15'" in filter_complex
    assert "x='(iw-iw/zoom)*(1-on/119)'" in filter_complex


@patch("shortform.renderer.subprocess.run")
def test_build_scene_clip_pan_variant_3_is_zoom_out(mock_run, tmp_path):
    out_path = tmp_path / "clip.mp4"
    build_scene_clip(tmp_path / "scene.png", "image", tmp_path / "audio.mp3", 4.0, out_path, pan_variant=3)

    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "z='max(1.5-0.0015*on,1.15)'" in filter_complex
    assert "x='iw/2-(iw/zoom/2)'" in filter_complex


@patch("shortform.renderer.subprocess.run")
def test_build_scene_clip_pan_variant_wraps_around(mock_run, tmp_path):
    out_path = tmp_path / "clip.mp4"
    build_scene_clip(tmp_path / "scene.png", "image", tmp_path / "audio.mp3", 4.0, out_path, pan_variant=4)

    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "z='min(zoom+0.0015,1.5)'" in filter_complex


@patch("shortform.renderer.subprocess.run")
def test_build_scene_clip_pan_variant_defaults_to_center_zoom(mock_run, tmp_path):
    out_path = tmp_path / "clip.mp4"
    build_scene_clip(tmp_path / "scene.png", "image", tmp_path / "audio.mp3", 4.0, out_path)

    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "z='min(zoom+0.0015,1.5)'" in filter_complex
```

(`test_build_scene_clip_handles_video`는 무수정 — `video` 분기는 이번 Task의 대상이 아니다.)

- [ ] **Step 2: 테스트 실패 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_renderer.py -v`
Expected: 새로 추가한 테스트 중 `pan_variant=1/2/3`을 요구하는 것들이 `TypeError: build_scene_clip() got an unexpected keyword argument 'pan_variant'`로 실패.

- [ ] **Step 3: 최소 구현** (`shortform/renderer.py`의 `build_scene_clip` 함수 시그니처와 이미지 분기만 아래로 교체 — `video` 분기(`else:` 블록)는 무수정)

```python
def build_scene_clip(media_path, media_type, audio_path, duration, out_path, pan_variant=0):
    media_path = str(media_path)
    audio_path = str(audio_path)
    out_path = Path(out_path)

    if media_type == "image":
        frame_count = max(1, int(duration * 30))
        denom = max(frame_count - 1, 1)
        variant = pan_variant % 4
        if variant == 1:
            z_expr = "1.15"
            x_expr = f"(iw-iw/zoom)*on/{denom}"
        elif variant == 2:
            z_expr = "1.15"
            x_expr = f"(iw-iw/zoom)*(1-on/{denom})"
        elif variant == 3:
            z_expr = "max(1.5-0.0015*on,1.15)"
            x_expr = "iw/2-(iw/zoom/2)"
        else:
            z_expr = "min(zoom+0.0015,1.5)"
            x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", media_path,
            "-i", audio_path,
            "-filter_complex",
            (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,scale=8000:-2,"
                f"zoompan=z='{z_expr}':d={frame_count}:"
                f"x='{x_expr}':y='{y_expr}':s=1080x1920:fps=30,"
                "format=yuv420p[v]"
            ),
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-r", "30", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(duration),
            str(out_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", media_path,
            "-i", audio_path,
            "-vf", SCALE_FILTER,
            "-r", "30",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(duration),
            str(out_path),
        ]

    subprocess.run(cmd, capture_output=True, check=True)
    return out_path
```

(`duration=4.0`일 때 `frame_count = int(4.0*30) = 120`, `denom = max(120-1,1) = 119` — Step 1 테스트의 `on/119`, `1-on/119` 숫자와 정확히 일치한다.)

- [ ] **Step 4: 테스트 통과 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_renderer.py -v`
Expected: 전부 PASS.

- [ ] **Step 5: `pipeline.py` 호출부 갱신 + 기존 테스트 업데이트**

`shortform/pipeline.py`에서 `build_scene_clip` 호출 줄(현재 `build_scene_clip(media.path, media.media_type, audio_paths[scene.index], duration, clip_path)`)을 아래로 교체:

```python
            build_scene_clip(
                media.path, media.media_type, audio_paths[scene.index], duration, clip_path,
                pan_variant=scene.index,
            )
```

`tests/test_pipeline.py`의 `test_render_script_wires_all_stages`에서 아래 어서션을:

```python
    mock_clip.assert_called_once_with(
        tmp_path / "scene_01.png",
        "image",
        work_dir / "scene_01.mp3",
        4.0,
        work_dir / "clip_01.mp4"
    )
```

아래로 교체 (씬 index가 1이므로 `pan_variant=1`이 되어야 함):

```python
    mock_clip.assert_called_once_with(
        tmp_path / "scene_01.png",
        "image",
        work_dir / "scene_01.mp3",
        4.0,
        work_dir / "clip_01.mp4",
        pan_variant=1,
    )
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_renderer.py tests/test_pipeline.py -v`
Expected: 전부 PASS.

- [ ] **Step 7: 전체 회귀 테스트**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/ -v`
Expected: 전체 통과 (이 계획 작성 시점 기준 72개 기존 테스트 + 이번에 추가된 6개 = 78개).

- [ ] **Step 8: Commit**

```bash
git add shortform/renderer.py shortform/pipeline.py tests/test_renderer.py tests/test_pipeline.py
git commit -m "feat: cycle Ken Burns pan direction per scene"
```

---

### Task 2: 씬 전환 종류 4종 순환 — `shortform/renderer.py`

**Files:**
- Modify: `shortform/renderer.py` (`assemble_with_transitions` 내부 루프만)
- Test: `tests/test_renderer.py`

**Interfaces:**
- Produces: `assemble_with_transitions`의 공개 시그니처는 그대로. 내부적으로 `n`개 클립의 `n-1`개 전환 경계마다 `["fade", "slideleft", "wipeup", "circleopen"]`을 인덱스 `(i-1) % 4`로 순환 선택한다 (`i`는 기존 루프의 `range(1, n)` 인덱스).
- Consumes: Task 1과 독립 — 이 Task는 Task 1의 변경 사항을 사용하지 않는다.

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_renderer.py`에 추가 — 기존 `test_assemble_with_transitions_chains_xfade_for_multiple_clips`, `test_assemble_with_transitions_single_clip_skips_xfade`는 그대로 둔다)

```python
@patch("shortform.renderer.burn_ass_subtitles")
@patch("shortform.renderer.subprocess.run")
def test_assemble_with_transitions_cycles_transition_types(mock_run, mock_burn, tmp_path):
    from shortform.renderer import assemble_with_transitions

    out_path = tmp_path / "final.mp4"
    mock_burn.return_value = out_path

    assemble_with_transitions(
        [tmp_path / f"c{i}.mp4" for i in range(1, 6)],
        [4.0, 4.0, 4.0, 4.0, 4.0],
        "ASS_TEXT",
        out_path,
        transition_duration=0.5,
    )

    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "xfade=transition=fade:" in filter_complex
    assert "xfade=transition=slideleft:" in filter_complex
    assert "xfade=transition=wipeup:" in filter_complex
    assert "xfade=transition=circleopen:" in filter_complex


@patch("shortform.renderer.burn_ass_subtitles")
@patch("shortform.renderer.subprocess.run")
def test_assemble_with_transitions_wraps_transition_cycle(mock_run, mock_burn, tmp_path):
    from shortform.renderer import assemble_with_transitions

    out_path = tmp_path / "final.mp4"
    mock_burn.return_value = out_path

    assemble_with_transitions(
        [tmp_path / f"c{i}.mp4" for i in range(1, 7)],
        [4.0] * 6,
        "ASS_TEXT",
        out_path,
        transition_duration=0.5,
    )

    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert filter_complex.count("xfade=transition=fade:") == 2
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_renderer.py -v`
Expected: 새 테스트 2개가 `AssertionError`로 실패 (지금은 항상 `transition=fade`만 사용해서 `slideleft`/`wipeup`/`circleopen`이 필터 문자열에 없고, wrap 테스트는 `fade`가 2번이 아니라 6번 나옴).

- [ ] **Step 3: 최소 구현** (`shortform/renderer.py`의 `assemble_with_transitions` 함수 중 `else:` 블록(다중 클립 분기) 안의 루프만 아래로 교체 — 함수 시그니처, `if n == 1:` 블록, 이후 ASS burn 부분은 무수정)

```python
        filter_parts = []
        cursor = durations[0]
        v_label, a_label = "0:v", "0:a"
        transition_types = ["fade", "slideleft", "wipeup", "circleopen"]
        for i in range(1, n):
            offset = cursor - transition_duration
            v_out, a_out = f"v{i}", f"a{i}"
            transition = transition_types[(i - 1) % len(transition_types)]
            filter_parts.append(
                f"[{v_label}][{i}:v]xfade=transition={transition}:duration={transition_duration}:offset={offset}[{v_out}]"
            )
            filter_parts.append(f"[{a_label}][{i}:a]acrossfade=d={transition_duration}[{a_out}]")
            v_label, a_label = v_out, a_out
            cursor += durations[i] - transition_duration
        filter_complex = ";".join(filter_parts)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_renderer.py -v`
Expected: 전부 PASS.

- [ ] **Step 5: 전체 회귀 테스트**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/ -v`
Expected: 전체 통과 (Task 1 완료 후 78개 + 이번 2개 = 80개).

- [ ] **Step 6: Commit**

```bash
git add shortform/renderer.py tests/test_renderer.py
git commit -m "feat: cycle scene transition type per boundary"
```

---

## 4. Verification (수동 스모크 테스트, 필수)

이 프로젝트에서는 ASS/ffmpeg 렌더링 관련 버그(자막 색상 겹침, 재생 불가 픽셀 포맷 등)가 문자열 기반 유닛 테스트를 전부 통과한 채로 실제 렌더링에서만 발견된 전례가 여러 번 있었다. 두 Task 모두 완료 후, 반드시 다음을 수행한다:

1. `output/scripts/`의 기존 스크립트 JSON과 `output/media/`에 캐싱된 씬별 오디오(`scene_NN.mp3`)를 재사용해 API 비용 없이 클립을 다시 만든다 (이번엔 `build_scene_clip` 자체가 바뀌었으므로 기존 `clip_NN.mp4`를 그대로 쓰지 말고 다시 생성해야 한다):
   ```python
   import json
   from pathlib import Path
   from shortform.scene_schema import script_from_dict
   from shortform.media_matcher import resolve_scene_media
   from shortform.renderer import build_scene_clip, assemble_with_transitions
   from shortform.captions import build_ass_from_scenes
   from shortform.tts import get_audio_duration

   data = json.loads(Path("output/scripts/<파일명>.json").read_text(encoding="utf-8"))
   script = script_from_dict(data)
   work_dir = Path("output/media")
   durations = [get_audio_duration(work_dir / f"scene_{s.index:02d}.mp3") for s in script.scenes]

   scene_media = resolve_scene_media(script, "input", work_dir / "generated")
   clip_paths = []
   for scene, duration in zip(script.scenes, durations):
       media = scene_media[scene.index]
       clip_path = work_dir / f"clip_v2_{scene.index:02d}.mp4"
       build_scene_clip(media.path, media.media_type, work_dir / f"scene_{scene.index:02d}.mp3", duration, clip_path, pan_variant=scene.index)
       clip_paths.append(clip_path)

   ass_text = build_ass_from_scenes(script.scenes, durations, 0.5)
   assemble_with_transitions(clip_paths, durations, ass_text, Path("output/camera_variety_check.mp4"), transition_duration=0.5)
   ```
2. `ffmpeg -i output/camera_variety_check.mp4 -vf fps=4 <프레임 폴더>/f_%03d.jpg`로 프레임을 추출한다.
3. 프레임을 직접 읽어 육안 확인: (a) 씬마다 팬 방향이 실제로 다르게 보이는지(중앙 확대만 반복되지 않는지), (b) 좌→우/우→좌 팬이 검은 여백 없이 자연스럽게 화면을 채우는지, (c) 줌 아웃 씬이 어색하지 않은지, (d) 씬 전환 지점마다 크로스페이드 외의 슬라이드/와이프/서클오픈 전환이 실제로 보이는지.
4. 문제가 있으면(예: 팬이 너무 빠르거나 느림, 줌 고정값 1.15가 부적절함) 해당 상수를 조정하고 1~3을 반복한다.
