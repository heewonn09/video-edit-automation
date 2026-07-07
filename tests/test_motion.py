import pytest
from unittest.mock import MagicMock, patch

from shortform.motion import DEFAULT_VIDEO_MODEL, generate_scene_video, select_motion_scenes
from shortform.scene_schema import Scene


def _scene(index, motion=False):
    return Scene(index, "n", "v", 4.0, motion=motion)


def test_select_motion_scenes_caps_at_max_count():
    scenes = [_scene(1), _scene(2, True), _scene(3, True), _scene(4, True)]
    assert select_motion_scenes(scenes, max_count=2) == {2, 3}


def test_select_motion_scenes_excludes_hook_scene():
    scenes = [_scene(1, True), _scene(2, True)]
    assert select_motion_scenes(scenes, max_count=2) == {2}


def test_select_motion_scenes_zero_disables():
    scenes = [_scene(1, True), _scene(2, True)]
    assert select_motion_scenes(scenes, max_count=0) == set()


def test_select_motion_scenes_empty_when_none_flagged():
    scenes = [_scene(1), _scene(2), _scene(3)]
    assert select_motion_scenes(scenes, max_count=2) == set()


def _mock_client_with_op(done_after=1):
    """generate_videos → op(done=False), operations.get를 done_after번 호출하면 done=True."""
    client = MagicMock()
    pending = MagicMock(done=False)
    finished = MagicMock(done=True)
    video = MagicMock()
    finished.response.generated_videos = [MagicMock(video=video)]
    client.models.generate_videos.return_value = pending
    client.operations.get.side_effect = [pending] * (done_after - 1) + [finished]
    return client, video


@patch("shortform.motion.genai.Client")
def test_generate_scene_video_polls_then_downloads(mock_client_cls, monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    client, video = _mock_client_with_op(done_after=2)
    mock_client_cls.return_value = client

    img = tmp_path / "scene.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")   # Image.from_file reads real bytes
    out = tmp_path / "scene.mp4"
    result = generate_scene_video(img, "해변을 걷는 사람", out, poll_interval=0)

    kwargs = client.models.generate_videos.call_args.kwargs
    assert kwargs["model"] == DEFAULT_VIDEO_MODEL
    assert "해변을 걷는 사람" in kwargs["prompt"]
    assert kwargs["config"].aspect_ratio == "9:16"
    assert client.operations.get.call_count == 2
    client.files.download.assert_called_once_with(file=video)
    video.save.assert_called_once_with(str(out))
    assert result == out


@patch("shortform.motion.genai.Client")
def test_generate_scene_video_times_out(mock_client_cls, monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    client = MagicMock()
    pending = MagicMock(done=False)
    client.models.generate_videos.return_value = pending
    client.operations.get.return_value = pending
    mock_client_cls.return_value = client

    img = tmp_path / "s.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    with pytest.raises(TimeoutError):
        generate_scene_video(img, "p", tmp_path / "o.mp4",
                             poll_interval=0, timeout=0)


def test_generate_scene_video_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        generate_scene_video(tmp_path / "s.png", "p", tmp_path / "o.mp4")
