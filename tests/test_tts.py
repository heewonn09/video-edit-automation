from unittest.mock import patch, MagicMock, AsyncMock
from shortform.tts import synthesize_narration, get_audio_duration


@patch("shortform.tts.edge_tts.Communicate")
def test_synthesize_narration_calls_edge_tts(mock_communicate_cls, tmp_path):
    mock_instance = MagicMock()
    mock_instance.save = AsyncMock()
    mock_communicate_cls.return_value = mock_instance

    out_path = tmp_path / "narration.mp3"
    result = synthesize_narration("안녕하세요", out_path, voice="ko-KR-SunHiNeural")

    mock_communicate_cls.assert_called_once_with("안녕하세요", "ko-KR-SunHiNeural")
    mock_instance.save.assert_awaited_once_with(str(out_path))
    assert result == out_path


@patch("shortform.tts.subprocess.run")
def test_get_audio_duration_parses_ffprobe_output(mock_run):
    mock_run.return_value = MagicMock(stdout="3.500000\n")
    duration = get_audio_duration("narration.mp3")
    assert duration == 3.5
