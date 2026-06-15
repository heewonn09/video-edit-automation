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
