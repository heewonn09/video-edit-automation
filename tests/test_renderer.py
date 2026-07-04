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
    assert "-pix_fmt" in cmd
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert result == out_path


@patch("shortform.renderer.generate_whoosh_sound")
@patch("shortform.renderer.burn_ass_subtitles")
@patch("shortform.renderer.subprocess.run")
def test_assemble_with_transitions_chains_xfade_for_multiple_clips(mock_run, mock_burn, mock_whoosh, tmp_path):
    from shortform.renderer import assemble_with_transitions

    out_path = tmp_path / "final.mp4"
    mock_burn.return_value = out_path
    mock_whoosh.return_value = tmp_path / "whoosh.wav"

    result = assemble_with_transitions(
        [tmp_path / "c1.mp4", tmp_path / "c2.mp4", tmp_path / "c3.mp4"],
        [5.0, 4.0, 6.0],
        "ASS_TEXT",
        out_path,
        transition_duration=0.5,
    )

    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert filter_complex.count("xfade") == 2
    assert filter_complex.count("acrossfade") == 2
    assert "offset=4.5" in filter_complex
    assert "offset=8" in filter_complex
    assert "-pix_fmt" in cmd
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"

    mock_burn.assert_called_once()
    assert result == out_path


@patch("shortform.renderer.burn_ass_subtitles")
@patch("shortform.renderer.subprocess.run")
def test_assemble_with_transitions_single_clip_skips_xfade(mock_run, mock_burn, tmp_path):
    from shortform.renderer import assemble_with_transitions

    out_path = tmp_path / "final.mp4"
    mock_burn.return_value = out_path

    assemble_with_transitions([tmp_path / "c1.mp4"], [5.0], "ASS_TEXT", out_path)

    cmd = mock_run.call_args[0][0]
    assert "-filter_complex" not in cmd
    mock_burn.assert_called_once()


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
