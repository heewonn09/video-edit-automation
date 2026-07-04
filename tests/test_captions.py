from shortform.captions import build_ass_from_scenes
from shortform.scene_schema import Scene


def test_build_ass_includes_header_and_cumulative_timing():
    scenes = [
        Scene(1, "첫 문장", "v1", 5.0),
        Scene(2, "둘째 문장", "v2", 4.0),
        Scene(3, "셋째 문장", "v3", 6.0),
    ]
    ass = build_ass_from_scenes(scenes, [5.0, 4.0, 6.0], transition_duration=0.5)

    assert "[Script Info]" in ass
    assert "[V4+ Styles]" in ass
    assert "[Events]" in ass
    assert "0:00:00.00,0:00:04.50" in ass
    assert "첫 문장" in ass
    assert "0:00:04.50,0:00:08.00" in ass
    assert "둘째 문장" in ass
    assert "0:00:08.00,0:00:14.00" in ass
    assert "셋째 문장" in ass


def test_build_ass_highlights_matching_word():
    scenes = [Scene(1, "70만원이나 저렴해요", "v", 5.0, highlight_words=["70만원"])]
    ass = build_ass_from_scenes(scenes, [5.0])

    assert r"{\1c&H00D7FF&\3c&H00D7FF&\bord14\shad0}70만원{\r}" in ass
    assert "이나 저렴해요" in ass


def test_build_ass_skips_highlight_word_not_found_in_narration():
    scenes = [Scene(1, "그냥 평범한 문장", "v", 5.0, highlight_words=["없는단어"])]
    ass = build_ass_from_scenes(scenes, [5.0])

    assert "그냥 평범한 문장" in ass
    assert r"\bord14" not in ass
