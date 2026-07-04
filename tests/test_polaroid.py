from shortform.polaroid import build_polaroid_filter_complex


def test_build_polaroid_filter_complex_includes_background_blur():
    result = build_polaroid_filter_complex(120, -6)
    assert "gblur=sigma=20" in result
    assert "eq=brightness=-0.15" in result


def test_build_polaroid_filter_complex_includes_gentle_zoom_on_photo():
    result = build_polaroid_filter_complex(120, -6)
    assert "zoompan=z='min(zoom+0.0005,1.08)':d=120:" in result


def test_build_polaroid_filter_complex_includes_asymmetric_white_border():
    result = build_polaroid_filter_complex(120, -6)
    assert "pad=840:1530:20:20:color=white" in result


def test_build_polaroid_filter_complex_rotates_by_tilt_angle():
    result_negative = build_polaroid_filter_complex(120, -6)
    assert "rotate=-0.104720:" in result_negative

    result_positive = build_polaroid_filter_complex(120, 6)
    assert "rotate=0.104720:" in result_positive


def test_build_polaroid_filter_complex_includes_offset_shadow_overlay():
    result = build_polaroid_filter_complex(120, -6)
    assert "colorchannelmixer=rr=0:gg=0:bb=0:aa=0.45" in result
    assert "overlay=(W-w)/2+12:(H-h)/2+16" in result
