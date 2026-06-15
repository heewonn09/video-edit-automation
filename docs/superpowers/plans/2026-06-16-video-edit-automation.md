# Video Edit Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `input/` 폴더의 영상들을 무음 제거 후 순서대로 합치고, Whisper로 한국어 자막을 생성해 `output/output.mp4`를 만든다.

**Architecture:** `process.py` 단일 스크립트로 파이프라인을 순차 실행한다. ffmpeg로 무음 감지/클립 추출/연결/자막 burn-in을, openai-whisper로 한국어 전사를 담당한다. 설정은 `config.json`에서 읽고 기본값으로 fallback한다.

**Tech Stack:** Python 3.x, ffmpeg (설치됨), openai-whisper, ffmpeg-python (subprocess 직접 사용)

---

## File Map

| 파일 | 역할 |
|------|------|
| `process.py` | 메인 파이프라인 스크립트 (모든 함수 포함) |
| `config.json` | 사용자 설정 (무음 임계값, Whisper 모델 등) |
| `requirements.txt` | Python 의존성 |
| `input/.gitkeep` | input 폴더 추적용 |
| `output/.gitkeep` | output 폴더 추적용 |
| `tests/test_process.py` | 단위 테스트 |

---

## Task 1: 프로젝트 스캐폴딩

**Files:**
- Create: `requirements.txt`
- Create: `config.json`
- Create: `input/.gitkeep`
- Create: `output/.gitkeep`
- Create: `tests/__init__.py`

- [ ] **Step 1: requirements.txt 생성**

```
openai-whisper
```

- [ ] **Step 2: config.json 생성**

```json
{
  "silence_threshold": "-35dB",
  "min_silence_duration": 0.5,
  "silence_padding": 0.1,
  "whisper_model": "medium",
  "output_filename": "output.mp4",
  "subtitle_font": "Malgun Gothic",
  "subtitle_font_size": 24
}
```

- [ ] **Step 3: 폴더 및 빈 파일 생성**

```bash
mkdir -p input output tests
touch input/.gitkeep output/.gitkeep tests/__init__.py
```

- [ ] **Step 4: 의존성 설치**

```bash
pip install -r requirements.txt
```

첫 실행 시 Whisper 모델 다운로드로 수 분 소요될 수 있음.

- [ ] **Step 5: 커밋**

```bash
git add requirements.txt config.json input/.gitkeep output/.gitkeep tests/__init__.py
git commit -m "feat: scaffold project structure"
```

---

## Task 2: load_config + get_input_files

**Files:**
- Create: `process.py`
- Create: `tests/test_process.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_process.py`:
```python
import json
import pytest
from pathlib import Path


def test_load_config_returns_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from process import load_config
    cfg = load_config()
    assert cfg["silence_threshold"] == "-35dB"
    assert cfg["min_silence_duration"] == 0.5
    assert cfg["silence_padding"] == 0.1
    assert cfg["whisper_model"] == "medium"
    assert cfg["output_filename"] == "output.mp4"


def test_load_config_overrides_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"whisper_model": "small", "subtitle_font_size": 32}))
    from process import load_config
    cfg = load_config()
    assert cfg["whisper_model"] == "small"
    assert cfg["subtitle_font_size"] == 32
    assert cfg["silence_threshold"] == "-35dB"  # default 유지


def test_get_input_files_sorted_by_name(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "003.mp4").touch()
    (input_dir / "001.mp4").touch()
    (input_dir / "002.mov").touch()
    (input_dir / "notes.txt").touch()   # 제외 대상
    (input_dir / "image.jpg").touch()   # 제외 대상
    from process import get_input_files
    files = get_input_files(str(input_dir))
    assert [f.name for f in files] == ["001.mp4", "002.mov", "003.mp4"]


def test_get_input_files_empty_dir(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    from process import get_input_files
    assert get_input_files(str(input_dir)) == []
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_process.py -v
```

Expected: `ModuleNotFoundError: No module named 'process'` 또는 `ImportError`

- [ ] **Step 3: process.py 생성 — load_config + get_input_files 구현**

`process.py`:
```python
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

DEFAULT_CONFIG = {
    "silence_threshold": "-35dB",
    "min_silence_duration": 0.5,
    "silence_padding": 0.1,
    "whisper_model": "medium",
    "output_filename": "output.mp4",
    "subtitle_font": "Malgun Gothic",
    "subtitle_font_size": 24,
}

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def load_config(config_path="config.json"):
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def get_input_files(input_dir="input"):
    files = [
        f for f in Path(input_dir).iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files, key=lambda f: f.name)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_process.py -v
```

Expected: 4개 PASS

- [ ] **Step 5: 커밋**

```bash
git add process.py tests/test_process.py
git commit -m "feat: add load_config and get_input_files"
```

---

## Task 3: _segments_to_srt 헬퍼

**Files:**
- Modify: `process.py` (함수 추가)
- Modify: `tests/test_process.py` (테스트 추가)

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_process.py` 끝에 추가:
```python
def test_segments_to_srt_basic():
    from process import _segments_to_srt
    segments = [
        {"start": 0.0, "end": 2.5, "text": " 안녕하세요"},
        {"start": 3.0, "end": 65.123, "text": " 반갑습니다"},
    ]
    srt = _segments_to_srt(segments)
    assert "1\n00:00:00,000 --> 00:00:02,500\n안녕하세요" in srt
    assert "2\n00:00:03,000 --> 00:01:05,123\n반갑습니다" in srt


def test_segments_to_srt_empty():
    from process import _segments_to_srt
    assert _segments_to_srt([]) == ""
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_process.py::test_segments_to_srt_basic tests/test_process.py::test_segments_to_srt_empty -v
```

Expected: `ImportError: cannot import name '_segments_to_srt'`

- [ ] **Step 3: _segments_to_srt 구현 — process.py에 추가**

`load_config` 함수 아래에 추가:
```python
def _fmt_srt_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _segments_to_srt(segments):
    if not segments:
        return ""
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_srt_time(seg['start'])} --> {_fmt_srt_time(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_process.py -v
```

Expected: 6개 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add process.py tests/test_process.py
git commit -m "feat: add _segments_to_srt helper"
```

---

## Task 4: detect_voice_segments

**Files:**
- Modify: `process.py` (함수 추가)
- Modify: `tests/test_process.py` (테스트 추가)

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_process.py` 끝에 추가:
```python
from unittest.mock import patch, MagicMock


def test_detect_voice_segments_middle_silence(tmp_path):
    """무음이 중간에 있는 경우: 앞뒤 음성 구간 2개 반환"""
    from process import detect_voice_segments

    ffprobe_out = "10.0\n"
    ffmpeg_err = (
        "[silencedetect] silence_start: 3.000000\n"
        "[silencedetect] silence_end: 6.000000 | silence_duration: 3.000000\n"
    )
    cfg = {"silence_threshold": "-35dB", "min_silence_duration": 0.5, "silence_padding": 0.1}

    fake_video = tmp_path / "test.mp4"
    fake_video.touch()

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(stdout=ffprobe_out, stderr="", returncode=0),   # ffprobe
            MagicMock(stdout="", stderr=ffmpeg_err, returncode=0),    # silencedetect
        ]
        segments = detect_voice_segments(fake_video, cfg)

    # silence (3.0, 6.0) padded → (2.9, 6.1)
    # voice: (0.0, 2.9), (6.1, 10.0)
    assert len(segments) == 2
    assert abs(segments[0][0] - 0.0) < 0.01
    assert abs(segments[0][1] - 2.9) < 0.01
    assert abs(segments[1][0] - 6.1) < 0.01
    assert abs(segments[1][1] - 10.0) < 0.01


def test_detect_voice_segments_no_silence(tmp_path):
    """무음 없음: 전체 영상이 하나의 음성 구간"""
    from process import detect_voice_segments

    cfg = {"silence_threshold": "-35dB", "min_silence_duration": 0.5, "silence_padding": 0.1}
    fake_video = tmp_path / "test.mp4"
    fake_video.touch()

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(stdout="5.0\n", stderr="", returncode=0),
            MagicMock(stdout="", stderr="", returncode=0),
        ]
        segments = detect_voice_segments(fake_video, cfg)

    assert len(segments) == 1
    assert abs(segments[0][0] - 0.0) < 0.01
    assert abs(segments[0][1] - 5.0) < 0.01
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_process.py::test_detect_voice_segments_middle_silence tests/test_process.py::test_detect_voice_segments_no_silence -v
```

Expected: `ImportError: cannot import name 'detect_voice_segments'`

- [ ] **Step 3: detect_voice_segments 구현 — process.py에 추가**

`_segments_to_srt` 아래에 추가:
```python
def detect_voice_segments(video_path, cfg):
    """ffmpeg silencedetect로 음성 구간 (start, end) 목록 반환."""
    threshold = cfg["silence_threshold"]
    min_dur = cfg["min_silence_duration"]
    padding = cfg["silence_padding"]

    # 영상 길이 조회
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    duration = float(probe.stdout.strip())

    # 무음 감지
    result = subprocess.run(
        [
            "ffmpeg", "-i", str(video_path),
            "-af", f"silencedetect=noise={threshold}:d={min_dur}",
            "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )
    output = result.stderr

    silence_starts = [float(x) for x in re.findall(r"silence_start: (\d+\.?\d*)", output)]
    silence_ends = [float(x) for x in re.findall(r"silence_end: (\d+\.?\d*)", output)]

    # 무음 구간을 padding만큼 확장 → 반전하면 음성 구간
    silences = [
        (max(0.0, s - padding), min(duration, e + padding))
        for s, e in zip(silence_starts, silence_ends)
    ]

    voice_segments = []
    cursor = 0.0
    for s_start, s_end in silences:
        if s_start > cursor + 0.05:
            voice_segments.append((round(cursor, 3), round(s_start, 3)))
        cursor = s_end
    if duration - cursor > 0.05:
        voice_segments.append((round(cursor, 3), round(duration, 3)))

    return voice_segments
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_process.py -v
```

Expected: 8개 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add process.py tests/test_process.py
git commit -m "feat: add detect_voice_segments"
```

---

## Task 5: extract_segments + concat_clips

**Files:**
- Modify: `process.py` (함수 추가)
- Modify: `tests/test_process.py` (테스트 추가)

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_process.py` 끝에 추가:
```python
def test_extract_segments_calls_ffmpeg_per_segment(tmp_path):
    from process import extract_segments

    fake_video = tmp_path / "clip.mp4"
    fake_video.touch()
    segments = [(0.0, 2.0), (5.0, 8.0)]
    out_dir = tmp_path / "clips"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        paths = extract_segments(fake_video, segments, out_dir)

    assert mock_run.call_count == 2
    assert len(paths) == 2
    assert paths[0].suffix == ".mp4"


def test_concat_clips_writes_list_and_calls_ffmpeg(tmp_path):
    from process import concat_clips

    clips = [tmp_path / "a.mp4", tmp_path / "b.mp4"]
    out_path = tmp_path / "merged.mp4"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = concat_clips(clips, out_path)

    assert mock_run.call_count == 1
    cmd = mock_run.call_args[0][0]
    assert "-f" in cmd
    assert "concat" in cmd
    assert result == out_path
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_process.py::test_extract_segments_calls_ffmpeg_per_segment tests/test_process.py::test_concat_clips_writes_list_and_calls_ffmpeg -v
```

Expected: `ImportError`

- [ ] **Step 3: extract_segments + concat_clips 구현 — process.py에 추가**

`detect_voice_segments` 아래에 추가:
```python
def extract_segments(video_path, segments, out_dir):
    """각 음성 구간을 개별 mp4 클립으로 추출."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(video_path).stem
    clip_paths = []

    for i, (start, end) in enumerate(segments):
        out_path = out_dir / f"{stem}_seg{i:04d}.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-ss", str(start),
                "-to", str(end),
                "-c", "copy",
                str(out_path),
            ],
            capture_output=True,
            check=True,
        )
        clip_paths.append(out_path)

    return clip_paths


def concat_clips(clip_paths, out_path):
    """ffmpeg concat demuxer로 클립들을 하나로 연결."""
    out_path = Path(out_path)
    list_path = out_path.parent / "concat_list.txt"

    with open(list_path, "w", encoding="utf-8") as f:
        for p in clip_paths:
            f.write(f"file '{Path(p).as_posix()}'\n")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            str(out_path),
        ],
        capture_output=True,
        check=True,
    )
    list_path.unlink(missing_ok=True)
    return out_path
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_process.py -v
```

Expected: 10개 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add process.py tests/test_process.py
git commit -m "feat: add extract_segments and concat_clips"
```

---

## Task 6: transcribe_audio

**Files:**
- Modify: `process.py` (함수 추가)
- Modify: `tests/test_process.py` (테스트 추가)

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_process.py` 끝에 추가:
```python
def test_transcribe_audio_writes_srt(tmp_path):
    from process import transcribe_audio

    fake_video = tmp_path / "merged.mp4"
    fake_video.touch()
    srt_path = tmp_path / "subtitles.srt"
    cfg = {"whisper_model": "medium"}

    fake_segments = [
        {"start": 0.0, "end": 2.0, "text": " 안녕하세요"},
        {"start": 3.0, "end": 5.0, "text": " 반갑습니다"},
    ]

    with patch("subprocess.run") as mock_ffmpeg, \
         patch("whisper.load_model") as mock_load:
        mock_ffmpeg.return_value = MagicMock(returncode=0)
        mock_load.return_value.transcribe.return_value = {"segments": fake_segments}

        result = transcribe_audio(fake_video, cfg, srt_path)

    assert result == srt_path
    content = srt_path.read_text(encoding="utf-8")
    assert "안녕하세요" in content
    assert "반갑습니다" in content
    assert "00:00:00,000 --> 00:00:02,000" in content
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_process.py::test_transcribe_audio_writes_srt -v
```

Expected: `ImportError: cannot import name 'transcribe_audio'`

- [ ] **Step 3: transcribe_audio 구현 — process.py에 추가**

`concat_clips` 아래에 추가:
```python
def transcribe_audio(video_path, cfg, srt_path):
    """Whisper로 한국어 전사 후 SRT 저장."""
    import whisper

    audio_path = Path(video_path).with_suffix(".wav")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(audio_path),
        ],
        capture_output=True,
        check=True,
    )

    model = whisper.load_model(cfg["whisper_model"])
    result = model.transcribe(str(audio_path), language="ko")
    audio_path.unlink(missing_ok=True)

    srt_content = _segments_to_srt(result["segments"])
    srt_path = Path(srt_path)
    srt_path.write_text(srt_content, encoding="utf-8")
    return srt_path
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_process.py -v
```

Expected: 11개 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add process.py tests/test_process.py
git commit -m "feat: add transcribe_audio with Whisper"
```

---

## Task 7: burn_subtitles

**Files:**
- Modify: `process.py` (함수 추가)
- Modify: `tests/test_process.py` (테스트 추가)

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_process.py` 끝에 추가:
```python
def test_burn_subtitles_calls_ffmpeg(tmp_path):
    from process import burn_subtitles

    video = tmp_path / "merged.mp4"
    video.touch()
    srt = tmp_path / "subtitles.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\n테스트\n", encoding="utf-8")
    out = tmp_path / "output.mp4"
    cfg = {"subtitle_font": "Malgun Gothic", "subtitle_font_size": 24}

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = burn_subtitles(video, srt, out, cfg)

    assert mock_run.call_count == 1
    cmd = " ".join(mock_run.call_args[0][0])
    assert "subtitles" in cmd
    assert "Malgun Gothic" in cmd
    assert result == out
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_process.py::test_burn_subtitles_calls_ffmpeg -v
```

Expected: `ImportError: cannot import name 'burn_subtitles'`

- [ ] **Step 3: burn_subtitles 구현 — process.py에 추가**

`transcribe_audio` 아래에 추가:
```python
def burn_subtitles(video_path, srt_path, out_path, cfg):
    """SRT 자막을 영상에 burn-in."""
    font = cfg["subtitle_font"]
    size = cfg["subtitle_font_size"]

    # Windows 경로의 콜론을 ffmpeg subtitles 필터 문법에 맞게 이스케이프
    srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf",
            (
                f"subtitles='{srt_escaped}':force_style='"
                f"FontName={font},FontSize={size},"
                f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=1'"
            ),
            "-c:a", "copy",
            str(out_path),
        ],
        capture_output=True,
        check=True,
    )
    return Path(out_path)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_process.py -v
```

Expected: 12개 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add process.py tests/test_process.py
git commit -m "feat: add burn_subtitles"
```

---

## Task 8: main() 오케스트레이션

**Files:**
- Modify: `process.py` (main 함수 추가)
- Modify: `tests/test_process.py` (통합 테스트 추가)

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_process.py` 끝에 추가:
```python
def test_main_no_input_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()
    (tmp_path / "config.json").write_text(json.dumps({}))

    from process import main
    main()

    captured = capsys.readouterr()
    assert "없습니다" in captured.out


def test_main_full_pipeline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "001.mp4").touch()
    (tmp_path / "output").mkdir()
    (tmp_path / "config.json").write_text(json.dumps({}))

    fake_segments = [{"start": 0.0, "end": 3.0, "text": " 테스트"}]

    with patch("subprocess.run") as mock_run, \
         patch("whisper.load_model") as mock_load, \
         patch("shutil.rmtree") as mock_rmtree:

        mock_run.return_value = MagicMock(stdout="5.0\n", stderr="", returncode=0)
        mock_load.return_value.transcribe.return_value = {"segments": fake_segments}

        from process import main
        main()

    # ffprobe + silencedetect + extract(1 segment) + concat + wav추출 + burn = 6번 이상
    assert mock_run.call_count >= 6
    assert mock_rmtree.called
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_process.py::test_main_no_input_files tests/test_process.py::test_main_full_pipeline -v
```

Expected: `ImportError: cannot import name 'main'`

- [ ] **Step 3: main() 구현 — process.py 끝에 추가**

```python
def main():
    cfg = load_config()

    input_files = get_input_files("input")
    if not input_files:
        print("input/ 폴더에 영상 파일이 없습니다. 영상을 넣고 다시 실행하세요.")
        return

    Path("output").mkdir(exist_ok=True)
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)

    all_clips = []
    for video in input_files:
        print(f"[1/4] 무음 제거 중: {video.name}")
        try:
            segments = detect_voice_segments(video, cfg)
            if not segments:
                print(f"  경고: {video.name}에서 음성 구간 없음 — 스킵")
                continue
            clips = extract_segments(video, segments, temp_dir / video.stem)
            all_clips.extend(clips)
        except Exception as e:
            print(f"  경고: {video.name} 처리 실패 ({e}) — 스킵")

    if not all_clips:
        print("처리할 클립이 없습니다.")
        shutil.rmtree(temp_dir)
        return

    merged_path = temp_dir / "merged.mp4"
    print("[2/4] 클립 연결 중...")
    concat_clips(all_clips, merged_path)

    srt_path = temp_dir / "subtitles.srt"
    print("[3/4] 한국어 자막 생성 중 (Whisper)... (수 분 소요)")
    transcribe_audio(merged_path, cfg, srt_path)

    out_path = Path("output") / cfg["output_filename"]
    print("[4/4] 자막 입히는 중...")
    burn_subtitles(merged_path, srt_path, out_path, cfg)

    shutil.rmtree(temp_dir)
    print(f"\n완료! 결과물: {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_process.py -v
```

Expected: 14개 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add process.py tests/test_process.py
git commit -m "feat: add main orchestration pipeline"
```

---

## Task 9: 최종 검증

- [ ] **Step 1: 전체 테스트 스위트 통과 확인**

```bash
pytest tests/ -v
```

Expected: 14개 전부 PASS, 0 FAIL

- [ ] **Step 2: 실제 영상으로 smoke test**

`input/` 폴더에 짧은 한국어 영상(30초 이하)을 하나 넣고:

```bash
python process.py
```

Expected 출력:
```
[1/4] 무음 제거 중: <파일명>
[2/4] 클립 연결 중...
[3/4] 한국어 자막 생성 중 (Whisper)... (수 분 소요)
[4/4] 자막 입히는 중...

완료! 결과물: output/output.mp4
```

`output/output.mp4` 를 열어 자막이 한국어로 표시되는지 확인.

- [ ] **Step 3: 최종 커밋**

```bash
git add .
git commit -m "feat: complete video-edit-automation pipeline"
```
