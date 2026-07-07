import json
from unittest.mock import patch, MagicMock
from shortform.tts import synthesize_narration, get_audio_duration


def _fake_communicate(chunks):
    """stream()이 주어진 청크들을 내보내는 Communicate 목."""
    instance = MagicMock()

    async def _stream():
        for c in chunks:
            yield c

    instance.stream = _stream
    return instance


@patch("shortform.tts.edge_tts.Communicate")
def test_synthesize_narration_writes_audio_and_word_sidecar(mock_cls, tmp_path):
    mock_cls.return_value = _fake_communicate([
        {"type": "audio", "data": b"AUDIO1"},
        {"type": "WordBoundary", "offset": 1_000_000, "duration": 7_625_000, "text": "안녕하세요"},
        {"type": "audio", "data": b"AUDIO2"},
        {"type": "WordBoundary", "offset": 8_750_000, "duration": 4_125_000, "text": "여러분"},
    ])

    out_path = tmp_path / "narration.mp3"
    result = synthesize_narration("안녕하세요 여러분", out_path, voice="ko-KR-SunHiNeural")

    # WordBoundary를 받으려면 boundary 파라미터가 필수 (edge-tts 7.x)
    assert mock_cls.call_args.kwargs["boundary"] == "WordBoundary"
    assert mock_cls.call_args[0] == ("안녕하세요 여러분", "ko-KR-SunHiNeural")

    assert out_path.read_bytes() == b"AUDIO1AUDIO2"
    words = json.loads(out_path.with_suffix(".words.json").read_text(encoding="utf-8"))
    assert words == [
        {"text": "안녕하세요", "start": 0.1, "end": 0.8625},
        {"text": "여러분", "start": 0.875, "end": 1.2875},
    ]
    assert result == out_path


@patch("shortform.tts.edge_tts.Communicate")
def test_synthesize_narration_skips_sidecar_when_no_boundaries(mock_cls, tmp_path):
    mock_cls.return_value = _fake_communicate([{"type": "audio", "data": b"A"}])

    out_path = tmp_path / "narration.mp3"
    synthesize_narration("텍스트", out_path)

    assert out_path.read_bytes() == b"A"
    assert not out_path.with_suffix(".words.json").exists()


@patch("shortform.tts.subprocess.run")
def test_get_audio_duration_parses_ffprobe_output(mock_run):
    mock_run.return_value = MagicMock(stdout="3.500000\n")
    duration = get_audio_duration("narration.mp3")
    assert duration == 3.5
