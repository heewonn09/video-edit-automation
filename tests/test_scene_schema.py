import pytest

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


def test_scene_layout_and_transition_default():
    scene = Scene(1, "안녕하세요", "골목길", 5.0)
    assert scene.layout == "fullscreen"
    assert scene.transition_in == "dissolve"


def test_script_from_dict_passes_through_layout_and_transition():
    data = {
        "title": "T",
        "scenes": [
            {
                "index": 1,
                "narration": "비교해볼게요",
                "visual_description": "전후 사진",
                "duration_hint_sec": 5,
                "layout": "split",
                "transition_in": "wipe",
            }
        ],
    }
    script = script_from_dict(data)
    assert script.scenes[0].layout == "split"
    assert script.scenes[0].transition_in == "wipe"


def test_script_from_dict_defaults_layout_and_transition_when_missing():
    data = {
        "title": "T",
        "scenes": [
            {"index": 1, "narration": "안녕", "visual_description": "v", "duration_hint_sec": 4},
        ],
    }
    script = script_from_dict(data)
    assert script.scenes[0].layout == "fullscreen"
    assert script.scenes[0].transition_in == "dissolve"


def test_script_from_dict_passes_through_chips():
    data = {
        "title": "T",
        "scenes": [
            {"index": 1, "narration": "n", "visual_description": "v", "duration_hint_sec": 4,
             "chips": [{"icon": "🏠", "label": "2층 주택"}]},
        ],
    }
    script = script_from_dict(data)
    assert script.scenes[0].chips == [{"icon": "🏠", "label": "2층 주택"}]


def test_scene_chips_default_to_empty():
    scene = Scene(1, "n", "v", 4.0)
    assert scene.chips == []


def test_script_from_dict_passes_through_hook_fields():
    data = {
        "title": "T",
        "hook_candidates": ["훅1", "훅2", "훅3"],
        "hook_reason": "숫자가 구체적이라 시선을 끔",
        "scenes": [
            {"index": 1, "narration": "훅1", "visual_description": "v", "duration_hint_sec": 4},
        ],
    }
    script = script_from_dict(data)
    assert script.hook_candidates == ["훅1", "훅2", "훅3"]
    assert script.hook_reason == "숫자가 구체적이라 시선을 끔"


def test_script_hook_fields_default_when_missing():
    data = {
        "title": "T",
        "scenes": [
            {"index": 1, "narration": "n", "visual_description": "v", "duration_hint_sec": 4},
        ],
    }
    script = script_from_dict(data)
    assert script.hook_candidates == []
    assert script.hook_reason == ""


def test_script_from_dict_skips_malformed_scene_and_keeps_the_rest():
    data = {
        "title": "T",
        "scenes": [
            {"index": 1, "narration": "정상 씬", "visual_description": "v", "duration_hint_sec": 4},
            {"index": 2, "narority": "오타난 필드", "visual_description": "v", "duration_hint_sec": 5},
            {"index": 3, "narration": "정상 씬2", "visual_description": "v", "duration_hint_sec": 6},
        ],
    }
    script = script_from_dict(data)
    assert len(script.scenes) == 2
    assert script.scenes[0].narration == "정상 씬"
    assert script.scenes[1].narration == "정상 씬2"


def test_script_from_dict_raises_when_every_scene_is_malformed():
    data = {
        "title": "T",
        "scenes": [
            {"index": 1, "narority": "오타", "visual_description": "v", "duration_hint_sec": 4},
        ],
    }
    with pytest.raises(RuntimeError):
        script_from_dict(data)
