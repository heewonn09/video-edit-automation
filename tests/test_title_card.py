import re
from unittest.mock import patch

from shortform.title_card import (
    CARD_BG_COLOR,
    MARGIN_HEIGHT,
    NUM_COLOR,
    PHOTO_HEIGHT,
    build_hook_ass,
    build_title_card_filter_complex,
    derive_palette,
)


def _dialogues(ass):
    return [l for l in ass.splitlines() if l.startswith("Dialogue")]


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
    assert palette["bg"] != CARD_BG_COLOR
    assert re.fullmatch(r"0x[0-9A-F]{6}", palette["bg"])
    assert re.fullmatch(r"&H00[0-9A-F]{6}&", palette["accent_ass"])


def test_accent_phrase_gets_rounded_card_with_shadow_behind():
    ass = build_hook_ass("평범한 도입부. 대박 사건!", ["대박"], 4.0)
    dialogue = _dialogues(ass)
    # drawing events (\p1) exist: one shadow + one card for the accent phrase
    drawings = [l for l in dialogue if r"\p1" in l]
    assert len(drawings) >= 2
    # shadow sits on a lower layer than the card, card lower than text
    layers = [int(l.split(",")[0].split(" ")[1]) for l in dialogue]
    assert min(layers) == 0 and max(layers) >= 2
    # rounded-rect path uses bezier corners
    assert any(" b " in l for l in drawings)


def test_accent_card_uses_palette_color_as_fill():
    palette = {"bg": "0x101820", "accent_ass": "&H00AA5511&", "base_ass": "&H00222222&"}
    ass = build_hook_ass("최대 70만 원 아낍니다!", ["70만 원"], 4.0, palette=palette)
    drawings = [l for l in _dialogues(ass) if r"\p1" in l]
    assert any("&H00AA5511&" in l for l in drawings)


def test_accent_without_number_renders_two_tone_headline():
    ass = build_hook_ass("프리미엄 이층 단독주택 완전 대박 풀옵션입니다!", ["프리미엄"], 4.0)
    dialogue = _dialogues(ass)
    # headline is naked typography — no card drawing for it
    assert not any(r"\p1" in l for l in dialogue)
    headline = dialogue[0]
    from shortform.title_card import ACCENT_COLOR
    assert ACCENT_COLOR in headline      # line 1: deep accent colour
    assert NUM_COLOR in headline         # line 2: gold
    assert r"\N" in headline


def test_chips_render_circles_icons_and_labels():
    chips = [
        {"icon": "🏠", "label": "2층 주택"},
        {"icon": "🌳", "label": "넓은 정원"},
        {"icon": "🚗", "label": "주차 2대"},
    ]
    ass = build_hook_ass("대박 훅!", ["대박"], 4.0, chips=chips)
    dialogue = _dialogues(ass)
    circles = [l for l in dialogue if r"\p1" in l and "&H00FFFFFF&" in l]
    assert len(circles) == 3
    assert len([l for l in dialogue if "ChipIcon" in l]) == 3
    labels = [l for l in dialogue if "ChipLabel" in l]
    assert len(labels) == 3
    assert any("넓은 정원" in l for l in labels)


def test_filter_complex_includes_pip_inset():
    result = build_title_card_filter_complex(120)
    assert "split=2[main_src][pip_src]" in result
    assert ":white[pip]" in result           # white border via pad
    assert result.count("overlay") == 2      # photo + pip


def test_base_phrase_gets_white_pill():
    ass = build_hook_ass("평범한 도입부. 대박 사건!", ["대박"], 4.0)
    drawings = [l for l in _dialogues(ass) if r"\p1" in l]
    assert any("&H00FFFFFF&" in l for l in drawings)


def test_number_inside_accent_card_is_big_and_gold():
    ass = build_hook_ass("최대 70만 원 아낍니다", ["70만 원"], 4.0)
    texts = [l for l in _dialogues(ass) if r"\p1" not in l]
    final = texts[-1]
    assert NUM_COLOR in final
    assert r"\fs" in final  # inline size mixing around the number


def test_count_up_reemits_text_but_draws_card_once():
    ass = build_hook_ass("최대 70만 원 아낍니다", ["70만 원"], 4.0)
    dialogue = _dialogues(ass)
    texts = [l for l in dialogue if r"\p1" not in l]
    drawings = [l for l in dialogue if r"\p1" in l]
    plains = [re.sub(r"\{[^}]*\}", "", l) for l in texts]
    values = [int(m.group(1)) for p in plains for m in [re.search(r"(\d+)만", p)] if m]
    assert len(values) >= 5
    assert values == sorted(values)
    assert values[-1] == 70
    # card + shadow drawn exactly once each (no flicker during count-up)
    assert len(drawings) == 2


def test_phrases_enter_staggered():
    ass = build_hook_ass("첫 문장입니다. 둘째 문장이에요!", [], 4.0)
    dialogue = _dialogues(ass)
    starts = sorted({l.split(",")[1] for l in dialogue})
    assert len(starts) >= 2  # later phrase starts later


def test_cards_pop_in_with_scale_animation():
    ass = build_hook_ass("대박 사건!", ["대박"], 4.0)
    dialogue = _dialogues(ass)
    assert any(r"\fscx" in l and r"\t(" in l for l in dialogue)


def test_long_phrase_wraps_at_word_boundary():
    ass = build_hook_ass("렌트카 최대 70만 원 아끼는 방법을 알려드립니다", ["70만 원"], 4.0)
    texts = [l for l in _dialogues(ass) if r"\p1" not in l]
    final = texts[-1]
    assert r"\N" in final
    # the wrap must not split the number unit "70만"
    plain = re.sub(r"\{[^}]*\}", "", final).replace(r"\N", "")
    assert "70만" in plain


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
