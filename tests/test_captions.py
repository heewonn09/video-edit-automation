from shortform.captions import ASS_HEADER, build_ass_from_scenes
from shortform.scene_schema import Scene


def test_build_ass_includes_header_and_cumulative_timing():
    scenes = [
        Scene(1, "첫 문장", "v1", 5.0),
        Scene(2, "둘째 문장", "v2", 4.0),
        Scene(3, "셋째 문장", "v3", 6.0),
    ]
    ass = build_ass_from_scenes(scenes, [5.0, 4.0, 6.0], transition_duration=0.5)

    assert "[Script Info]" in ass
    assert "Style: Box," in ass
    assert "[Events]" in ass
    assert "0:00:00.00,0:00:04.50" in ass
    assert "첫 문장" in ass
    assert "0:00:04.50,0:00:08.00" in ass
    assert "둘째 문장" in ass
    assert "0:00:08.00,0:00:14.00" in ass
    assert "셋째 문장" in ass


def test_build_ass_splits_narration_into_phrases_with_proportional_timing():
    scenes = [Scene(1, "안녕하세요, 오늘은 날씨가 좋아요.", "v", 10.0)]
    ass = build_ass_from_scenes(scenes, [10.0])

    assert "0:00:00.00,0:00:03.33" in ass
    assert "안녕하세요," in ass
    assert "0:00:03.33,0:00:10.00" in ass
    assert "오늘은 날씨가 좋아요." in ass


def test_build_ass_dialogue_lines_use_box_style():
    scenes = [Scene(1, "문장.", "v", 5.0)]
    ass = build_ass_from_scenes(scenes, [5.0])

    assert "Dialogue: 0,0:00:00.00,0:00:05.00,Box,,0,0,0,," in ass


def test_build_ass_includes_fade_in_per_phrase():
    scenes = [Scene(1, "안녕하세요, 반가워요.", "v", 5.0)]
    ass = build_ass_from_scenes(scenes, [5.0])

    assert ass.count(r"{\fad(200,0)}") == 2


def test_build_ass_highlights_keyword_with_color_only_no_border():
    scenes = [Scene(1, "70만원이나 저렴해요.", "v", 5.0, highlight_words=["70만원"])]
    ass = build_ass_from_scenes(scenes, [5.0])

    assert r"{\1c&H00D7FF&}70만원{\r}" in ass
    assert r"\bord" not in ass


def test_build_ass_skips_highlight_word_not_found_in_narration():
    scenes = [Scene(1, "그냥 평범한 문장", "v", 5.0, highlight_words=["없는단어"])]
    ass = build_ass_from_scenes(scenes, [5.0])

    assert "그냥 평범한 문장" in ass
    assert r"\1c&H00D7FF&" not in ass


def test_build_ass_treats_narration_without_punctuation_as_single_phrase():
    scenes = [Scene(1, "문장부호가 없는 나레이션", "v", 5.0)]
    ass = build_ass_from_scenes(scenes, [5.0])

    assert ass.count("Dialogue:") == 1
    assert "0:00:00.00,0:00:05.00" in ass
    assert "문장부호가 없는 나레이션" in ass
