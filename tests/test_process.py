import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


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
    (input_dir / "notes.txt").touch()
    (input_dir / "image.jpg").touch()
    from process import get_input_files
    files = get_input_files(str(input_dir))
    assert [f.name for f in files] == ["001.mp4", "002.mov", "003.mp4"]


def test_get_input_files_empty_dir(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    from process import get_input_files
    assert get_input_files(str(input_dir)) == []


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
            MagicMock(stdout=ffprobe_out, stderr="", returncode=0),
            MagicMock(stdout="", stderr=ffmpeg_err, returncode=0),
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
