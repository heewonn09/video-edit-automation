from shortform.editing_director import resolve_editing_plan, ScenePlan
from shortform.scene_schema import Scene


def _scene(index, layout="fullscreen", transition_in="dissolve"):
    return Scene(index, "나레이션", "연출", 4.0, layout=layout, transition_in=transition_in)


def test_maps_transition_names_to_xfade():
    scenes = [
        _scene(1, "fullscreen", "dissolve"),
        _scene(2, "polaroid", "slide"),
        _scene(3, "split", "wipe"),
        _scene(4, "fullscreen", "zoom"),
    ]
    plans = resolve_editing_plan(scenes)
    assert [p.transition for p in plans] == ["fade", "slideleft", "wipeup", "circleopen"]
    assert [p.layout for p in plans] == ["fullscreen", "polaroid", "split", "fullscreen"]


def test_invalid_layout_falls_back_to_fullscreen():
    scenes = [_scene(1, "fullscreen"), _scene(2, "banana"), _scene(3, "polaroid")]
    plans = resolve_editing_plan(scenes)
    assert plans[1].layout == "fullscreen"


def test_invalid_transition_falls_back_to_dissolve():
    scenes = [_scene(1, transition_in="dissolve"), _scene(2, transition_in="nonsense")]
    plans = resolve_editing_plan(scenes)
    assert plans[1].transition == "fade"


def test_first_scene_is_forced_fullscreen_hook():
    scenes = [_scene(1, "polaroid"), _scene(2, "split")]
    plans = resolve_editing_plan(scenes)
    assert plans[0].layout == "fullscreen"


def test_breaks_three_in_a_row_layout():
    scenes = [
        _scene(1, "fullscreen"),
        _scene(2, "polaroid"),
        _scene(3, "polaroid"),
        _scene(4, "polaroid"),
    ]
    plans = resolve_editing_plan(scenes)
    layouts = [p.layout for p in plans]
    # No layout appears 3 times consecutively
    for i in range(2, len(layouts)):
        assert not (layouts[i] == layouts[i - 1] == layouts[i - 2])
    # The 4th (index 3) is the one that got changed away from polaroid
    assert layouts[3] != "polaroid"


def test_break_does_not_create_new_three_run():
    scenes = [_scene(i, "split") for i in range(1, 7)]  # all split
    plans = resolve_editing_plan(scenes)
    layouts = [p.layout for p in plans]
    for i in range(2, len(layouts)):
        assert not (layouts[i] == layouts[i - 1] == layouts[i - 2])


def test_empty_scenes_returns_empty():
    assert resolve_editing_plan([]) == []


def test_single_scene_is_forced_fullscreen():
    plans = resolve_editing_plan([_scene(1, "split", "wipe")])
    assert len(plans) == 1
    assert plans[0].layout == "fullscreen"
    assert plans[0].transition == "wipeup"


def test_returns_scene_plan_dataclass():
    plans = resolve_editing_plan([_scene(1)])
    assert isinstance(plans[0], ScenePlan)
