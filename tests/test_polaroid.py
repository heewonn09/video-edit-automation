from unittest.mock import patch

from shortform.polaroid import build_polaroid_filter_complex


def test_build_polaroid_filter_complex_includes_background_blur():
    result = build_polaroid_filter_complex(120, -6)
    assert "gblur=sigma=20" in result
    assert "eq=brightness=-0.15" in result


def test_build_polaroid_filter_complex_includes_gentle_zoom_on_photo():
    result = build_polaroid_filter_complex(120, -6)
    assert "zoompan=z='min(zoom+0.0005,1.08)':d=120:" in result


def test_build_polaroid_filter_complex_includes_asymmetric_white_border():
    result = build_polaroid_filter_complex(120, -6)
    assert "pad=840:1530:20:20:color=white" in result


def test_build_polaroid_filter_complex_rotates_by_tilt_angle():
    result_negative = build_polaroid_filter_complex(120, -6)
    assert "rotate=-0.104720:" in result_negative

    result_positive = build_polaroid_filter_complex(120, 6)
    assert "rotate=0.104720:" in result_positive


def test_build_polaroid_filter_complex_includes_offset_shadow_overlay():
    result = build_polaroid_filter_complex(120, -6)
    assert "colorchannelmixer=rr=0:gg=0:bb=0:aa=0.45" in result
    assert "overlay=(W-w)/2+12:(H-h)/2+16" in result


@patch("shortform.polaroid.subprocess.run")
def test_build_polaroid_scene_clip_calls_ffmpeg_with_filter(mock_run, tmp_path):
    from shortform.polaroid import build_polaroid_scene_clip

    out_path = tmp_path / "clip.mp4"
    result = build_polaroid_scene_clip(tmp_path / "scene.png", tmp_path / "audio.mp3", 4.0, out_path)

    cmd = mock_run.call_args[0][0]
    assert "-filter_complex" in cmd
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "rotate=-0.104720:" in filter_complex
    assert "-map" in cmd
    assert "[v]" in cmd
    assert "-t" in cmd
    assert "4.0" in cmd
    assert result == out_path


@patch("shortform.polaroid.subprocess.run")
def test_build_polaroid_scene_clip_tilt_variant_alternates_direction(mock_run, tmp_path):
    from shortform.polaroid import build_polaroid_scene_clip

    out_path = tmp_path / "clip.mp4"
    build_polaroid_scene_clip(tmp_path / "scene.png", tmp_path / "audio.mp3", 4.0, out_path, tilt_variant=1)

    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "rotate=0.104720:" in filter_complex
