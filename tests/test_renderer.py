from unittest.mock import patch, MagicMock
from shortform.renderer import build_scene_clip


@patch("shortform.renderer.subprocess.run")
def test_build_scene_clip_handles_image(mock_run, tmp_path):
    out_path = tmp_path / "clip.mp4"
    result = build_scene_clip(tmp_path / "scene.png", "image", tmp_path / "audio.mp3", 4.0, out_path)

    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "-loop" in cmd
    assert result == out_path


@patch("shortform.renderer.subprocess.run")
def test_build_scene_clip_handles_video(mock_run, tmp_path):
    out_path = tmp_path / "clip.mp4"
    build_scene_clip(tmp_path / "scene.mp4", "video", tmp_path / "audio.mp3", 4.0, out_path)

    cmd = mock_run.call_args[0][0]
    assert "-stream_loop" in cmd
