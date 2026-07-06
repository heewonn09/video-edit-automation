from unittest.mock import patch

from shortform.bgm import mix_bgm, select_bgm_track, synthesize_bgm_pad


def test_select_bgm_track_matches_mood_prefix(tmp_path):
    (tmp_path / "calm_river.mp3").write_bytes(b"x")
    (tmp_path / "bright_day.mp3").write_bytes(b"x")
    assert select_bgm_track("calm", tmp_path).name == "calm_river.mp3"
    assert select_bgm_track("bright", tmp_path).name == "bright_day.mp3"


def test_select_bgm_track_is_deterministic_with_multiple_matches(tmp_path):
    (tmp_path / "calm_b.mp3").write_bytes(b"x")
    (tmp_path / "calm_a.mp3").write_bytes(b"x")
    assert select_bgm_track("calm", tmp_path).name == "calm_a.mp3"


def test_select_bgm_track_falls_back_to_any_audio_when_mood_missing(tmp_path):
    (tmp_path / "bright_day.wav").write_bytes(b"x")
    assert select_bgm_track("emotional", tmp_path).name == "bright_day.wav"


def test_select_bgm_track_returns_none_when_no_audio_or_no_dir(tmp_path):
    assert select_bgm_track("calm", tmp_path) is None
    assert select_bgm_track("calm", tmp_path / "missing") is None


@patch("shortform.bgm.subprocess.run")
def test_synthesize_bgm_pad_layers_mood_chord_sines(mock_run, tmp_path):
    out = tmp_path / "pad.wav"
    result = synthesize_bgm_pad("bright", 12.0, out)

    cmd = mock_run.call_args[0][0]
    joined = " ".join(cmd)
    # one lavfi sine input per chord note, each with the requested duration
    assert joined.count("sine=frequency=") >= 2
    assert "duration=12.0" in joined
    assert "amix=inputs=" in joined
    assert "lowpass" in joined and "tremolo" in joined
    assert result == out


@patch("shortform.bgm.subprocess.run")
def test_synthesize_bgm_pad_moods_use_different_chords(mock_run, tmp_path):
    synthesize_bgm_pad("bright", 5.0, tmp_path / "a.wav")
    bright_cmd = " ".join(mock_run.call_args[0][0])
    synthesize_bgm_pad("emotional", 5.0, tmp_path / "b.wav")
    emotional_cmd = " ".join(mock_run.call_args[0][0])
    bright_freqs = {p for p in bright_cmd.split() if "sine=frequency=" in p}
    emotional_freqs = {p for p in emotional_cmd.split() if "sine=frequency=" in p}
    assert bright_freqs != emotional_freqs


@patch("shortform.bgm.get_audio_duration", return_value=50.0)
@patch("shortform.bgm.subprocess.run")
def test_mix_bgm_loops_ducks_and_fades_under_narration(mock_run, mock_dur, tmp_path):
    out = tmp_path / "final.mp4"
    result = mix_bgm(tmp_path / "video.mp4", tmp_path / "track.mp3", out)

    cmd = mock_run.call_args[0][0]
    # bgm input is looped so short tracks cover the whole video
    li = cmd.index("-stream_loop")
    assert cmd[li + 1] == "-1"
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "volume=0.15" in fc
    assert "afade=t=in:d=1" in fc
    assert "afade=t=out:st=48.0:d=2" in fc      # duration 50 → fade-out starts at 48
    # normalize=0: amix must not attenuate the narration to make room for bgm
    assert "amix=inputs=2:duration=first:dropout_transition=0:normalize=0" in fc
    # video stream is copied, not re-encoded
    ci = cmd.index("-c:v")
    assert cmd[ci + 1] == "copy"
    assert result == out


@patch("shortform.bgm.get_audio_duration", return_value=50.0)
@patch("shortform.bgm.subprocess.run")
def test_mix_bgm_respects_custom_music_volume(mock_run, mock_dur, tmp_path):
    mix_bgm(tmp_path / "v.mp4", tmp_path / "t.mp3", tmp_path / "o.mp4", music_volume=0.3)
    fc = mock_run.call_args[0][0][mock_run.call_args[0][0].index("-filter_complex") + 1]
    assert "volume=0.3" in fc
