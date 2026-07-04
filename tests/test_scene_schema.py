from shortform.scene_schema import Scene, Script, script_from_dict

def test_script_from_dict_builds_scenes():
    data = {
        "title": "고양이 건강 팁",
        "scenes": [
            {"index": 1, "narration": "안녕하세요", "visual_description": "고양이 클로즈업", "duration_hint_sec": 4},
            {"index": 2, "narration": "오늘은...", "visual_description": "사료 그릇", "duration_hint_sec": 5},
        ],
    }
    script = script_from_dict(data)
    assert script.title == "고양이 건강 팁"
    assert len(script.scenes) == 2
    assert isinstance(script.scenes[0], Scene)
    assert script.scenes[0].narration == "안녕하세요"
    assert script.total_duration_sec() == 9


def test_scene_highlight_words_defaults_to_empty_list():
    scene = Scene(1, "안녕하세요", "골목길", 5.0)
    assert scene.highlight_words == []


def test_script_from_dict_passes_through_highlight_words():
    data = {
        "title": "T",
        "scenes": [
            {
                "index": 1,
                "narration": "70만원이나 저렴해요",
                "visual_description": "집",
                "duration_hint_sec": 5,
                "highlight_words": ["70만원"],
            }
        ],
    }
    script = script_from_dict(data)
    assert script.scenes[0].highlight_words == ["70만원"]
