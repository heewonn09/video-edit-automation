from unittest.mock import patch, MagicMock
from pathlib import Path
from shortform.renderer import build_scene_clip
from shortform.scene_schema import Scene


@patch("shortform.renderer.subprocess.run")
def test_build_scene_clip_handles_image(mock_run, tmp_path):
    out_path = tmp_path / "clip.mp4"
    result = build_scene_clip(tmp_path / "scene.png", "image", tmp_path / "audio.mp3", 4.0, out_path)

    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "-loop" in cmd
    assert any("zoompan" in str(arg) for arg in cmd)
    assert result == out_path


@patch("shortform.renderer.subprocess.run")
def test_build_scene_clip_handles_video(mock_run, tmp_path):
    out_path = tmp_path / "clip.mp4"
    build_scene_clip(tmp_path / "scene.mp4", "video", tmp_path / "audio.mp3", 4.0, out_path)

    cmd = mock_run.call_args[0][0]
    assert "-stream_loop" in cmd


def test_build_srt_from_scenes_uses_cumulative_timing():
    from shortform.renderer import build_srt_from_scenes

    scenes = [Scene(1, "첫 문장", "v1", 4.0), Scene(2, "둘째 문장", "v2", 3.0)]
    srt = build_srt_from_scenes(scenes, [4.0, 3.0])

    assert "00:00:00,000 --> 00:00:04,000" in srt
    assert "첫 문장" in srt
    assert "00:00:04,000 --> 00:00:07,000" in srt
    assert "둘째 문장" in srt


@patch("shortform.renderer.burn_subtitles")
@patch("shortform.renderer.concat_clips")
def test_assemble_final_video_concats_then_burns(mock_concat, mock_burn, tmp_path):
    from shortform.renderer import assemble_final_video

    out_path = tmp_path / "final.mp4"
    mock_concat.return_value = tmp_path / "merged.mp4"
    mock_burn.return_value = out_path

    result = assemble_final_video(
        [tmp_path / "c1.mp4", tmp_path / "c2.mp4"],
        "1\n00:00:00,000 --> 00:00:04,000\n첫 문장\n",
        out_path,
        {"subtitle_font": "Malgun Gothic", "subtitle_font_size": 44},
    )

    mock_concat.assert_called_once()
    mock_burn.assert_called_once()
    assert result == out_path


@patch("shortform.renderer.subprocess.run")
def test_burn_ass_subtitles_calls_ffmpeg_with_ass_filter(mock_run, tmp_path):
    from shortform.renderer import burn_ass_subtitles

    out_path = tmp_path / "final.mp4"
    result = burn_ass_subtitles(tmp_path / "merged.mp4", tmp_path / "captions.ass", out_path)

    cmd = mock_run.call_args[0][0]
    assert any("ass=" in str(arg) for arg in cmd)
    assert result == out_path
