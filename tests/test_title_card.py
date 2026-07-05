from unittest.mock import patch

from shortform.title_card import (
    CARD_BG_COLOR,
    MARGIN_HEIGHT,
    PHOTO_HEIGHT,
    build_hook_ass,
    build_title_card_filter_complex,
)


def test_filter_complex_builds_solid_background_canvas():
    result = build_title_card_filter_complex(120)
    assert f"color=c={CARD_BG_COLOR}:s=1080x1920" in result


def test_filter_complex_places_photo_in_bottom_area():
    result = build_title_card_filter_complex(120)
    assert f"crop=1080:{PHOTO_HEIGHT}" in result
    assert f"overlay=x=0:y={MARGIN_HEIGHT}" in result


def test_filter_complex_applies_gentle_zoom_to_photo():
    result = build_title_card_filter_complex(120)
    assert "zoompan=z='min(zoom+0.0005,1.08)':d=120:" in result


def test_build_hook_ass_styles_highlight_phrase_as_accent():
    ass = build_hook_ass("주변 시세보다 무려, -70만 원! 가능할까요?", ["-70만 원"], 4.0)
    # the phrase containing the highlight word uses the accent style
    accent_lines = [l for l in ass.splitlines() if l.startswith("Dialogue") and "HookAccent" in l]
    base_lines = [l for l in ass.splitlines() if l.startswith("Dialogue") and "HookBase" in l]
    assert len(accent_lines) == 1
    assert "-70만 원" in accent_lines[0]
    assert len(base_lines) == 2


def test_build_hook_ass_positions_lines_in_top_margin():
    ass = build_hook_ass("첫 줄입니다. 둘째 줄!", [], 4.0)
    dialogue = [l for l in ass.splitlines() if l.startswith("Dialogue")]
    for line in dialogue:
        assert r"\pos(540," in line
        assert r"\fad(300,0)" in line
    # all y positions inside the top margin
    import re
    ys = [float(m.group(1)) for l in dialogue for m in [re.search(r"\\pos\(540,([0-9.]+)\)", l)] if m]
    assert all(0 < y < MARGIN_HEIGHT for y in ys)


def test_build_hook_ass_without_punctuation_is_single_accent_line():
    ass = build_hook_ass("전세보다 70만원 싸다", ["70만원"], 4.0)
    dialogue = [l for l in ass.splitlines() if l.startswith("Dialogue")]
    assert len(dialogue) == 1
    assert "HookAccent" in dialogue[0]


@patch("shortform.title_card.burn_ass_subtitles")
@patch("shortform.title_card.subprocess.run")
def test_build_title_card_scene_clip_composes_then_burns(mock_run, mock_burn, tmp_path):
    from shortform.title_card import build_title_card_scene_clip

    out_path = tmp_path / "clip.mp4"
    mock_burn.return_value = out_path

    result = build_title_card_scene_clip(
        tmp_path / "scene.png", tmp_path / "audio.mp3", 4.0, out_path,
        hook_text="훅 문장입니다", highlight_words=["훅"],
    )

    cmd = mock_run.call_args[0][0]
    assert "-filter_complex" in cmd
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "overlay" in filter_complex
    assert "-t" in cmd and "4.0" in cmd

    # ASS written next to the clip and burned onto the composed raw clip
    (raw_arg, ass_arg, final_arg) = mock_burn.call_args[0]
    assert str(ass_arg).endswith(".ass")
    ass_text = ass_arg.read_text(encoding="utf-8")
    assert "훅 문장입니다" in ass_text
    assert final_arg == out_path
    assert result == out_path
