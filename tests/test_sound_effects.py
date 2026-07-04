from unittest.mock import patch


@patch("shortform.sound_effects.subprocess.run")
def test_generate_whoosh_sound_calls_ffmpeg_lavfi_synth(mock_run, tmp_path):
    from shortform.sound_effects import generate_whoosh_sound

    out_path = tmp_path / "whoosh.wav"
    result = generate_whoosh_sound(out_path)

    cmd = mock_run.call_args[0][0]
    assert "-f" in cmd
    assert "lavfi" in cmd
    assert any("anoisesrc=d=0.4" in str(arg) for arg in cmd)
    assert any("afade=t=in:d=0.05" in str(arg) for arg in cmd)
    assert any("afade=t=out:st=0.250:d=0.15" in str(arg) for arg in cmd)
    assert result == out_path


@patch("shortform.sound_effects.subprocess.run")
def test_generate_whoosh_sound_custom_duration_adjusts_fade_out_start(mock_run, tmp_path):
    from shortform.sound_effects import generate_whoosh_sound

    out_path = tmp_path / "whoosh.wav"
    generate_whoosh_sound(out_path, duration=0.5)

    cmd = mock_run.call_args[0][0]
    assert any("anoisesrc=d=0.5" in str(arg) for arg in cmd)
    assert any("afade=t=out:st=0.350:d=0.15" in str(arg) for arg in cmd)
