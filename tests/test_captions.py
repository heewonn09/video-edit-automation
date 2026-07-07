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


def test_build_ass_does_not_create_phantom_punctuation_only_phrases():
    scenes = [Scene(1, "정말... 그래요.", "v", 5.0)]
    ass = build_ass_from_scenes(scenes, [5.0])

    assert ass.count("Dialogue:") == 2
    assert "정말..." in ass
    assert "그래요." in ass


def test_build_ass_karaoke_uses_word_timings():
    scenes = [Scene(1, "안녕하세요 여러분, 반갑습니다", "v", 4.0)]
    timings = {1: [
        {"text": "안녕하세요", "start": 0.1, "end": 0.8},
        {"text": "여러분,", "start": 0.9, "end": 1.4},
        {"text": "반갑습니다", "start": 1.6, "end": 2.4},
    ]}
    result = build_ass_from_scenes(scenes, [4.0], 0.5, word_timings=timings)
    # 구절 1 "안녕하세요 여러분,": 첫 단어 (0.8-0.1)=70cs, 둘째 (1.4-0.8)=60cs
    assert r"{\kf70}안녕하세요" in result
    assert r"{\kf60}여러분," in result
    # 구절 2 "반갑습니다": (2.4-1.6)=80cs
    assert r"{\kf80}반갑습니다" in result
    # 구절 시작 시각 = 첫 단어 start
    assert "0:00:00.10" in result
    assert "0:00:01.60" in result


def test_build_ass_karaoke_highlights_keyword_word_gold():
    scenes = [Scene(1, "무려 70만원 아꼈어요", "v", 3.0, highlight_words=["70만원"])]
    timings = {1: [
        {"text": "무려", "start": 0.0, "end": 0.4},
        {"text": "70만원", "start": 0.5, "end": 1.1},
        {"text": "아꼈어요", "start": 1.2, "end": 1.9},
    ]}
    result = build_ass_from_scenes(scenes, [3.0], 0.5, word_timings=timings)
    assert r"\1c&H00D7FF&" in result
    assert "70만원" in result
    assert r"\kf" in result


def test_build_ass_falls_back_when_word_count_mismatch():
    scenes = [Scene(1, "어절 수가 다른 문장", "v", 4.0)]
    timings = {1: [{"text": "어절", "start": 0.0, "end": 0.5}]}  # 1개 vs 실제 4어절
    result = build_ass_from_scenes(scenes, [4.0], 0.5, word_timings=timings)
    assert r"\kf" not in result   # 그 씬은 구절 비례 배분으로 폴백
    assert "어절 수가 다른 문장" in result


def test_build_ass_second_scene_words_offset_by_compressed_timeline():
    scenes = [Scene(1, "첫 씬", "v", 4.0), Scene(2, "둘째 씬", "v", 4.0)]
    timings = {
        1: [{"text": "첫", "start": 0.0, "end": 0.5}, {"text": "씬", "start": 0.6, "end": 1.0}],
        2: [{"text": "둘째", "start": 0.2, "end": 0.7}, {"text": "씬", "start": 0.8, "end": 1.2}],
    }
    result = build_ass_from_scenes(scenes, [4.0, 4.0], 0.5, word_timings=timings)
    # 둘째 씬 시작 = 4.0 - 0.5(크로스페이드 압축) = 3.5 → 첫 단어 3.5+0.2=3.70
    assert "0:00:03.70" in result


def test_build_ass_karaoke_header_uses_dim_secondary_colour():
    assert "&H00AAAAAA" in ASS_HEADER   # 아직 안 읽은 단어의 색 (카라오케 스윕 시작색)
