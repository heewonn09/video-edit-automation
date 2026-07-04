# 전환 사운드 효과 (후쉬) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 씬 전환(크로스페이드/슬라이드/와이프 등) 지점마다 자연스러운 "후쉬(whoosh)" 효과음을 삽입해서 컷 전환의 편집감을 높인다.

**Architecture:** 새 모듈 `shortform/sound_effects.py`에 ffmpeg의 `lavfi` 가상 입력(`anoisesrc`)만으로 후쉬 소리를 합성하는 `generate_whoosh_sound` 함수를 만든다 (외부 음원 파일/새 pip 의존성 없음). `shortform/renderer.py`의 `assemble_with_transitions`는 이미 각 전환 경계의 정확한 시작 시각(`offset`)을 xfade용으로 계산해 두고 있으므로, 그 값을 그대로 재사용해 합성된 후쉬를 `adelay`로 해당 시각까지 지연시킨 뒤 나레이션 오디오와 `amix`로 믹싱한다.

**Tech Stack:** 순수 ffmpeg 오디오 필터(`anoisesrc`, `highpass`, `lowpass`, `afade`, `adelay`, `amix`) + Python. 새 pip 의존성 없음, 외부 음원 파일 없음.

## Global Constraints

- 새 파일 `shortform/sound_effects.py` 하나 생성, `shortform/renderer.py`의 `assemble_with_transitions`만 수정한다. `shortform/pipeline.py`, `shortform/captions.py`는 무수정 (시그니처 변화 없음).
- 새 pip 의존성 금지. 외부 사운드 에셋 파일 금지 — 반드시 ffmpeg `lavfi` 필터로 순수 합성한다.
- `assemble_with_transitions(scene_clip_paths, durations, ass_text, out_path, transition_duration=0.5)`의 공개 시그니처는 그대로 유지한다.
- 씬이 1개뿐이라 전환이 없는 경우(`n == 1` 분기)는 후쉬를 생성하지도, 믹싱하지도 않는다 — 전환이 없으니 후쉬도 없다.
- 후쉬 길이는 항상 `transition_duration`과 같게 맞춘다 — 별도의 하드코딩된 길이 상수를 만들지 않는다.
- 후쉬는 나레이션보다 작은 볼륨(`volume=0.4`)으로 믹싱해서 대사를 가리지 않게 한다.
- 모든 외부 호출(ffmpeg)은 `unittest.mock.patch`로 모킹 가능해야 한다.

---

## 1. File Structure

```
shortform/
├── sound_effects.py   # [신규] generate_whoosh_sound(out_path, duration=0.4) -> Path
└── renderer.py         # [수정] assemble_with_transitions 다중 클립 분기에 후쉬 믹싱 추가
tests/
├── test_sound_effects.py   # [신규]
└── test_renderer.py         # [수정] 후쉬 믹싱 테스트 추가
```

---

## 2. Current State (참고용)

`shortform/renderer.py`의 `assemble_with_transitions` (수정 전, 전체는 저장소에서 직접 확인 가능):

```python
def assemble_with_transitions(scene_clip_paths, durations, ass_text, out_path, transition_duration=0.5):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged_path = out_path.parent / "merged.mp4"

    n = len(scene_clip_paths)
    if n == 1:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(scene_clip_paths[0]),
            "-c", "copy",
            str(merged_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
    else:
        inputs = []
        for p in scene_clip_paths:
            inputs += ["-i", str(p)]

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

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{v_label}]", "-map", f"[{a_label}]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(merged_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)

    ass_path = out_path.parent / "captions.ass"
    ass_path.write_text(ass_text, encoding="utf-8")
    return burn_ass_subtitles(merged_path, ass_path, out_path)
```

`durations=[5.0, 4.0, 6.0]`, `transition_duration=0.5`일 때 각 전환의 `offset`은 `4.5`와 `8.0` — 이 값들이 Task 2에서 후쉬 지연(`adelay`) 시각으로 그대로 재사용된다.

---

## 3. 상세 구현 계획 (TDD, 즉시 실행 가능)

### Task 1: 후쉬 사운드 합성 — `shortform/sound_effects.py` (신규)

**Files:**
- Create: `shortform/sound_effects.py`
- Test: `tests/test_sound_effects.py` (신규)

**Interfaces:**
- Produces: `generate_whoosh_sound(out_path, duration=0.4) -> Path` — Task 2가 `shortform.renderer`에서 `from shortform.sound_effects import generate_whoosh_sound`로 가져와 사용한다.

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_sound_effects.py`)

```python
from unittest.mock import patch


@patch("shortform.sound_effects.subprocess.run")
def test_generate_whoosh_sound_calls_ffmpeg_lavfi_synth(mock_run, tmp_path):
    from shortform.sound_effects import generate_whoosh_sound

    out_path = tmp_path / "whoosh.wav"
    result = generate_whoosh_sound(out_path)

    cmd = mock_run.call_args[0][0]
    assert "-f" in cmd
    assert "lavfi" in cmd
    assert any("anoisesrc=d=0.4" in str(arg) for arg in cmd)
    assert any("afade=t=in:d=0.05" in str(arg) for arg in cmd)
    assert any("afade=t=out:st=0.250:d=0.15" in str(arg) for arg in cmd)
    assert result == out_path


@patch("shortform.sound_effects.subprocess.run")
def test_generate_whoosh_sound_custom_duration_adjusts_fade_out_start(mock_run, tmp_path):
    from shortform.sound_effects import generate_whoosh_sound

    out_path = tmp_path / "whoosh.wav"
    generate_whoosh_sound(out_path, duration=0.5)

    cmd = mock_run.call_args[0][0]
    assert any("anoisesrc=d=0.5" in str(arg) for arg in cmd)
    assert any("afade=t=out:st=0.350:d=0.15" in str(arg) for arg in cmd)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_sound_effects.py -v`
Expected: `ModuleNotFoundError: No module named 'shortform.sound_effects'`

- [ ] **Step 3: 최소 구현** (`shortform/sound_effects.py`)

```python
import subprocess
from pathlib import Path


def generate_whoosh_sound(out_path, duration=0.4):
    out_path = Path(out_path)
    fade_out_start = max(duration - 0.15, 0)
    audio_filter = (
        "highpass=f=500,lowpass=f=6000,"
        "afade=t=in:d=0.05,"
        f"afade=t=out:st={fade_out_start:.3f}:d=0.15"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anoisesrc=d={duration}:c=pink:r=44100",
        "-af", audio_filter,
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out_path
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_sound_effects.py -v`
Expected: 2개 PASS.

- [ ] **Step 5: 전체 회귀 테스트**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/ -v`
Expected: 전체 통과 (이 계획 작성 시점 기준 80개 기존 + 2개 신규 = 82개).

- [ ] **Step 6: Commit**

```bash
git add shortform/sound_effects.py tests/test_sound_effects.py
git commit -m "feat: synthesize whoosh transition sound via ffmpeg lavfi"
```

---

### Task 2: 전환 지점에 후쉬 믹싱 — `shortform/renderer.py` (수정)

**Files:**
- Modify: `shortform/renderer.py` (import 추가 + `assemble_with_transitions`의 다중 클립 분기만)
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `generate_whoosh_sound(out_path, duration=0.4) -> Path` (Task 1).
- Produces: `assemble_with_transitions`의 공개 시그니처/동작은 그대로 — 다중 클립일 때만 내부적으로 후쉬가 섞인다.

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_renderer.py`에 추가 — 기존 `assemble_with_transitions` 테스트들은 그대로 둔다)

```python
@patch("shortform.renderer.generate_whoosh_sound")
@patch("shortform.renderer.burn_ass_subtitles")
@patch("shortform.renderer.subprocess.run")
def test_assemble_with_transitions_mixes_whoosh_at_each_boundary(mock_run, mock_burn, mock_whoosh, tmp_path):
    from shortform.renderer import assemble_with_transitions

    out_path = tmp_path / "final.mp4"
    mock_burn.return_value = out_path
    mock_whoosh.return_value = tmp_path / "whoosh.wav"

    assemble_with_transitions(
        [tmp_path / "c1.mp4", tmp_path / "c2.mp4", tmp_path / "c3.mp4"],
        [5.0, 4.0, 6.0],
        "ASS_TEXT",
        out_path,
        transition_duration=0.5,
    )

    mock_whoosh.assert_called_once_with(tmp_path / "whoosh.wav", duration=0.5)

    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert filter_complex.count("adelay=") == 2
    assert "adelay=4500|4500" in filter_complex
    assert "adelay=8000|8000" in filter_complex
    assert "volume=0.4" in filter_complex
    assert "amix=inputs=3:" in filter_complex


@patch("shortform.renderer.generate_whoosh_sound")
@patch("shortform.renderer.burn_ass_subtitles")
@patch("shortform.renderer.subprocess.run")
def test_assemble_with_transitions_single_clip_skips_whoosh(mock_run, mock_burn, mock_whoosh, tmp_path):
    from shortform.renderer import assemble_with_transitions

    out_path = tmp_path / "final.mp4"
    mock_burn.return_value = out_path

    assemble_with_transitions([tmp_path / "c1.mp4"], [5.0], "ASS_TEXT", out_path)

    mock_whoosh.assert_not_called()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_renderer.py -v`
Expected: `AttributeError` 또는 `ImportError` (아직 `shortform.renderer`에 `generate_whoosh_sound`가 없어 `@patch("shortform.renderer.generate_whoosh_sound")`가 실패).

- [ ] **Step 3: 최소 구현** (`shortform/renderer.py` 상단에 import 한 줄 추가, `assemble_with_transitions`의 `else:` 블록만 아래로 교체 — `if n == 1:` 블록과 함수 마지막의 ASS burn 부분은 무수정)

파일 상단 import 블록에 추가:

```python
from shortform.sound_effects import generate_whoosh_sound
```

`else:` 블록(다중 클립 분기) 전체를 아래로 교체:

```python
    else:
        inputs = []
        for p in scene_clip_paths:
            inputs += ["-i", str(p)]

        filter_parts = []
        offsets = []
        cursor = durations[0]
        v_label, a_label = "0:v", "0:a"
        transition_types = ["fade", "slideleft", "wipeup", "circleopen"]
        for i in range(1, n):
            offset = cursor - transition_duration
            offsets.append(offset)
            v_out, a_out = f"v{i}", f"a{i}"
            transition = transition_types[(i - 1) % len(transition_types)]
            filter_parts.append(
                f"[{v_label}][{i}:v]xfade=transition={transition}:duration={transition_duration}:offset={offset}[{v_out}]"
            )
            filter_parts.append(f"[{a_label}][{i}:a]acrossfade=d={transition_duration}[{a_out}]")
            v_label, a_label = v_out, a_out
            cursor += durations[i] - transition_duration

        whoosh_path = out_path.parent / "whoosh.wav"
        generate_whoosh_sound(whoosh_path, duration=transition_duration)

        whoosh_labels = []
        for idx, offset in enumerate(offsets):
            delay_ms = int(offset * 1000)
            src_index = n + idx
            inputs += ["-i", str(whoosh_path)]
            label = f"wh{idx}"
            filter_parts.append(f"[{src_index}:a]adelay={delay_ms}|{delay_ms},volume=0.4[{label}]")
            whoosh_labels.append(f"[{label}]")

        mix_inputs = f"[{a_label}]" + "".join(whoosh_labels)
        filter_parts.append(
            f"{mix_inputs}amix=inputs={len(whoosh_labels) + 1}:duration=first:dropout_transition=0[aout]"
        )
        a_label = "aout"

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{v_label}]", "-map", f"[{a_label}]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(merged_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
```

(`whoosh_path`는 매번 같은 파일 하나만 생성하고, ffmpeg 입력으로는 그 파일을 전환 개수만큼 반복해서 `-i`로 추가한다 — ffmpeg는 같은 파일을 여러 번 입력으로 받는 것을 허용한다.)

- [ ] **Step 4: 테스트 통과 확인**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/test_renderer.py -v`
Expected: 전부 PASS.

- [ ] **Step 5: 전체 회귀 테스트**

Run: `/c/Users/이희원/AppData/Local/Python/bin/python.exe -m pytest tests/ -v`
Expected: 전체 통과 (Task 1 완료 후 82개 + 이번 2개 = 84개).

- [ ] **Step 6: Commit**

```bash
git add shortform/renderer.py tests/test_renderer.py
git commit -m "feat: mix whoosh sound effect at each scene transition"
```

---

## 4. Verification (수동 청취 테스트, 필수)

이번 기능은 **오디오**가 핵심이라 프레임 추출로는 확인할 수 없다. 두 Task 완료 후 반드시 다음을 수행한다:

1. `output/scripts/`의 기존 스크립트 JSON, `output/media/`에 캐싱된 씬별 오디오(`scene_NN.mp3`)와 이미지(`generated/scene_NN.png`)를 재사용해 API 비용 없이 클립을 다시 만들고 조립한다:
   ```python
   import json
   from pathlib import Path
   from shortform.scene_schema import script_from_dict
   from shortform.renderer import build_scene_clip, assemble_with_transitions
   from shortform.captions import build_ass_from_scenes
   from shortform.tts import get_audio_duration

   data = json.loads(Path("output/scripts/<파일명>.json").read_text(encoding="utf-8"))
   script = script_from_dict(data)
   work_dir = Path("output/media")
   generated_dir = work_dir / "generated"

   scenes, durations, clip_paths = [], [], []
   for scene in script.scenes:
       image_path = generated_dir / f"scene_{scene.index:02d}.png"
       if not image_path.exists():
           continue
       duration = get_audio_duration(work_dir / f"scene_{scene.index:02d}.mp3")
       clip_path = work_dir / f"clip_v3_{scene.index:02d}.mp4"
       build_scene_clip(image_path, "image", work_dir / f"scene_{scene.index:02d}.mp3", duration, clip_path, pan_variant=scene.index)
       scenes.append(scene); durations.append(duration); clip_paths.append(clip_path)

   ass_text = build_ass_from_scenes(scenes, durations, 0.5)
   assemble_with_transitions(clip_paths, durations, ass_text, Path("output/whoosh_check.mp4"), transition_duration=0.5)
   ```
2. `ffmpeg -i output/whoosh_check.mp4 -af volumedetect -f null -` 로 오디오 트랙에 실제로 신호가 섞였는지(무음이 아닌지) 확인한다.
3. Windows 기본 플레이어로 직접 재생해서 들어본다: (a) 각 전환 지점마다 "후쉬" 소리가 실제로 들리는지, (b) 나레이션을 가릴 정도로 크지 않은지, (c) 타이밍이 화면 전환과 어긋나지 않는지.
4. 너무 크거나 작으면 `volume=0.4` 값을, 소리가 어색하면 `highpass`/`lowpass`의 주파수 범위나 `afade` 길이를 조정하고 1~3을 반복한다.
