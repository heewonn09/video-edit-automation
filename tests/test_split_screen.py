from shortform.split_screen import build_split_screen_filter_complex


def test_build_split_screen_filter_complex_splits_source_before_branching():
    result = build_split_screen_filter_complex(120)
    assert "[0:v]split=2[top_src][bottom_src]" in result


def test_build_split_screen_filter_complex_top_panel_pans_left_to_right():
    result = build_split_screen_filter_complex(120)
    assert "z='1.12':d=120:" in result
    assert "x='(iw-iw/zoom)*on/119'" in result


def test_build_split_screen_filter_complex_bottom_panel_zooms_center():
    result = build_split_screen_filter_complex(120)
    assert "z='min(zoom+0.0006,1.15)':d=120:" in result


def test_build_split_screen_filter_complex_uses_half_height_panels():
    result = build_split_screen_filter_complex(120)
    assert "crop=1080:960" in result


def test_build_split_screen_filter_complex_stacks_panels_vertically():
    result = build_split_screen_filter_complex(120)
    assert "[top][bottom]vstack=inputs=2[v]" in result
