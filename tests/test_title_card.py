import re
from unittest.mock import patch

from shortform.title_card import (
    CARD_BG_COLOR,
    MARGIN_HEIGHT,
    PHOTO_HEIGHT,
    build_hook_ass,
    build_title_card_filter_complex,
    derive_palette,
)


def test_filter_complex_builds_solid_background_canvas():
    result = build_title_card_filter_complex(120)
    assert f"color=c={CARD_BG_COLOR}:s=1080x1920" in result


def test_filter_complex_accepts_custom_background_color():
    result = build_title_card_filter_complex(120, bg_color="0x101820")
    assert "color=c=0x101820:s=1080x1920" in result


def test_filter_complex_places_photo_in_bottom_area():
    result = build_title_card_filter_complex(120)
    assert f"crop=1080:{PHOTO_HEIGHT}" in result
    assert f"overlay=x=0:y={MARGIN_HEIGHT}" in result


def test_filter_complex_applies_gentle_zoom_to_photo():
    result = build_title_card_filter_complex(120)
    assert "zoompan=z='min(zoom+0.0005,1.08)':d=120:" in result


def test_derive_palette_falls_back_on_unreadable_image(tmp_path):
    palette = derive_palette(tmp_path / "missing.png")
    assert palette["bg"] == CARD_BG_COLOR
    assert palette["accent_ass"].startswith("&H00")
    assert palette["base_ass"].startswith("&H00")


def test_derive_palette_derives_tinted_colors_from_image(tmp_path):
    from PIL import Image
    img_path = tmp_path / "blue.png"
    Image.new("RGB", (64, 64), (30, 80, 200)).save(img_path)

    palette = derive_palette(img_path)
    # bg is a light tint (high value) and accent a deep saturated colour — both hue-derived,
    # so a blue image must not return the warm default background
    assert palette["bg"] != CARD_BG_COLOR
    assert re.fullmatch(r"0x[0-9A-F]{6}", palette["bg"])
    assert re.fullmatch(r"&H00[0-9A-F]{6}&", palette["accent_ass"])


def test_build_hook_ass_styles_highlight_phrase_as_accent():
    ass = build_hook_ass("주변 시세보다 무려, 어마어마한 퀄리티! 가능할까요?", ["퀄리티"], 4.0)
    accent_lines = [l for l in ass.splitlines() if l.startswith("Dialogue") and "HookAccent" in l]
    base_lines = [l for l in ass.splitlines() if l.startswith("Dialogue") and "HookBase" in l]
    assert len(accent_lines) == 1
    assert "퀄리티" in accent_lines[0]
    assert len(base_lines) == 2


def test_build_hook_ass_lines_enter_staggered_with_motion():
    ass = build_hook_ass("첫 줄입니다. 둘째 줄이에요. 셋째 줄!", [], 4.0)
    dialogue = [l for l in ass.splitlines() if l.startswith("Dialogue")]
    assert len(dialogue) == 3
    # staggered entrance: start times strictly increase
    starts = [l.split(",")[1] for l in dialogue]
    assert starts == sorted(starts) and len(set(starts)) == 3
    # motion + fade on every line
    for line in dialogue:
        assert r"\move(540," in line
        assert r"\fad(" in line
    # y destinations stay inside the top margin
    ys = [float(m.group(1)) for l in dialogue for m in [re.search(r"\\move\(540,[0-9.]+,540,([0-9.]+)", l)] if m]
    assert all(0 < y < MARGIN_HEIGHT for y in ys)


def test_build_hook_ass_accent_line_has_scale_pop():
    ass = build_hook_ass("평범한 도입부. 대박 사건!", ["대박"], 4.0)
    accent = [l for l in ass.splitlines() if l.startswith("Dialogue") and "HookAccent" in l][0]
    assert r"\fscx" in accent and r"\t(" in accent


def test_build_hook_ass_animates_number_count_up():
    ass = build_hook_ass("무려 70만 원 저렴합니다", ["70만 원"], 4.0)
    dialogue = [l for l in ass.splitlines() if l.startswith("Dialogue")]
    # count-up emits several short-lived events with increasing values, ending on the real number
    assert len(dialogue) >= 5
    values = [int(m.group(1)) for l in dialogue for m in [re.search(r"}[^0-9]*(\d+)만 원", l)] if m]
    assert values == sorted(values)
    assert values[-1] == 70
    assert "70만 원" in dialogue[-1]


def test_build_hook_ass_without_numbers_single_phrase_is_one_accent_event():
    ass = build_hook_ass("전세보다 훨씬 싸다", ["훨씬"], 4.0)
    dialogue = [l for l in ass.splitlines() if l.startswith("Dialogue")]
    assert len(dialogue) == 1
    assert "HookAccent" in dialogue[0]


def test_build_hook_ass_uses_palette_colors_in_styles():
    palette = {"bg": "0x101820", "accent_ass": "&H00AA5511&", "base_ass": "&H00222222&"}
    ass = build_hook_ass("한 줄 훅", [], 4.0, palette=palette)
    assert "&H00AA5511&" in ass
    assert "&H00222222&" in ass


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

    (raw_arg, ass_arg, final_arg) = mock_burn.call_args[0]
    assert str(ass_arg).endswith(".ass")
    ass_text = ass_arg.read_text(encoding="utf-8")
    assert "훅 문장입니다" in ass_text
    assert final_arg == out_path
    assert result == out_path
