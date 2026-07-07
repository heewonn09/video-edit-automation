from unittest.mock import patch
from pathlib import Path
from shortform.pipeline import render_script, TRANSITION_DURATION_SEC
from shortform.scene_schema import Script, Scene
from shortform.media_matcher import SceneMedia
from shortform.editing_director import ScenePlan


@patch("shortform.pipeline.mix_bgm")
@patch("shortform.pipeline.select_bgm_track")
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_scene_clip")
@patch("shortform.pipeline.resolve_editing_plan")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_wires_all_stages(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_plan, mock_clip,
    mock_assemble, mock_select, mock_mix, tmp_path
):
    script = Script(title="T", scenes=[Scene(1, "나레이션", "골목길", 4.0)])
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {1: SceneMedia(1, tmp_path / "scene_01.png", "image")}
    mock_ass.return_value = "ASS_TEXT"
    mock_plan.return_value = [ScenePlan(layout="fullscreen", transition="fade")]
    mock_clip.return_value = work_dir / "clip_01.mp4"
    pre_bgm = work_dir / "pre_bgm.mp4"
    mock_assemble.return_value = pre_bgm
    mock_select.return_value = tmp_path / "calm_track.mp3"
    out_path = tmp_path / "final.mp4"
    mock_mix.return_value = out_path

    result = render_script(script, out_path, asset_folder=None, work_dir=work_dir)

    mock_tts.assert_called_once_with("나레이션", work_dir / "scene_01.mp3")

    call_args = mock_resolve.call_args
    assert call_args[0][1] is None
    assert call_args[0][2] == work_dir / "generated"
    filtered_script = call_args[0][0]
    assert filtered_script.title == script.title
    assert len(filtered_script.scenes) == 1
    assert filtered_script.scenes[0].index == 1

    mock_duration.assert_called_once_with(work_dir / "scene_01.mp3")

    # fullscreen layout routes image scenes to build_scene_clip with media_type "image"
    mock_clip.assert_called_once_with(
        tmp_path / "scene_01.png",
        "image",
        work_dir / "scene_01.mp3",
        4.0,
        work_dir / "clip_01.mp4",
        pan_variant=1,
    )

    mock_ass.assert_called_once_with(script.scenes, [4.0], TRANSITION_DURATION_SEC)
    # assembly renders to the intermediate pre-bgm path, then bgm is mixed onto out_path
    assert mock_assemble.call_args[0][3] == work_dir / "pre_bgm.mp4"
    assert mock_assemble.call_args.kwargs["transitions"] == ["fade"]
    mock_mix.assert_called_once_with(pre_bgm, tmp_path / "calm_track.mp3", out_path, music_volume=0.15)
    assert result == out_path


@patch("shortform.pipeline.mix_bgm")
@patch("shortform.pipeline.select_bgm_track")
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_polaroid_scene_clip")
@patch("shortform.pipeline.resolve_editing_plan")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_routes_polaroid_layout_to_polaroid_builder(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_plan, mock_polaroid,
    mock_assemble, mock_select, mock_mix, tmp_path
):
    script = Script(title="T", scenes=[Scene(2, "나레이션", "골목길", 4.0)])
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {2: SceneMedia(2, tmp_path / "scene_02.png", "image")}
    mock_ass.return_value = "ASS_TEXT"
    mock_plan.return_value = [ScenePlan(layout="polaroid", transition="fade")]
    mock_polaroid.return_value = work_dir / "clip_02.mp4"
    mock_assemble.return_value = work_dir / "pre_bgm.mp4"
    mock_select.return_value = tmp_path / "t.mp3"
    mock_mix.return_value = tmp_path / "final.mp4"

    render_script(script, tmp_path / "final.mp4", asset_folder=None, work_dir=work_dir)

    mock_polaroid.assert_called_once_with(
        tmp_path / "scene_02.png",
        work_dir / "scene_02.mp3",
        4.0,
        work_dir / "clip_02.mp4",
        tilt_variant=2,
    )


@patch("shortform.pipeline.mix_bgm")
@patch("shortform.pipeline.select_bgm_track")
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_split_screen_scene_clip")
@patch("shortform.pipeline.resolve_editing_plan")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_routes_split_layout_to_split_builder(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_plan, mock_split,
    mock_assemble, mock_select, mock_mix, tmp_path
):
    script = Script(title="T", scenes=[Scene(3, "나레이션", "골목길", 4.0)])
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {3: SceneMedia(3, tmp_path / "scene_03.png", "image")}
    mock_ass.return_value = "ASS_TEXT"
    mock_plan.return_value = [ScenePlan(layout="split", transition="fade")]
    mock_split.return_value = work_dir / "clip_03.mp4"
    mock_assemble.return_value = work_dir / "pre_bgm.mp4"
    mock_select.return_value = tmp_path / "t.mp3"
    mock_mix.return_value = tmp_path / "final.mp4"

    render_script(script, tmp_path / "final.mp4", asset_folder=None, work_dir=work_dir)

    mock_split.assert_called_once_with(
        tmp_path / "scene_03.png",
        work_dir / "scene_03.mp3",
        4.0,
        work_dir / "clip_03.mp4",
    )


@patch("shortform.pipeline.mix_bgm")
@patch("shortform.pipeline.select_bgm_track")
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_title_card_scene_clip")
@patch("shortform.pipeline.resolve_editing_plan")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_routes_titlecard_layout_to_title_card_builder(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_plan, mock_card,
    mock_assemble, mock_select, mock_mix, tmp_path
):
    script = Script(
        title="T",
        scenes=[Scene(1, "훅 나레이션", "골목길", 4.0, highlight_words=["훅"])],
    )
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {1: SceneMedia(1, tmp_path / "scene_01.png", "image")}
    mock_ass.return_value = "ASS_TEXT"
    mock_plan.return_value = [ScenePlan(layout="titlecard", transition="circleopen")]
    mock_card.return_value = work_dir / "clip_01.mp4"
    mock_assemble.return_value = work_dir / "pre_bgm.mp4"
    mock_select.return_value = tmp_path / "t.mp3"
    mock_mix.return_value = tmp_path / "final.mp4"

    render_script(script, tmp_path / "final.mp4", asset_folder=None, work_dir=work_dir)

    mock_card.assert_called_once_with(
        tmp_path / "scene_01.png",
        work_dir / "scene_01.mp3",
        4.0,
        work_dir / "clip_01.mp4",
        hook_text="훅 나레이션",
        highlight_words=["훅"],
        chips=[],
    )


@patch("shortform.pipeline.mix_bgm")
@patch("shortform.pipeline.select_bgm_track")
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_scene_clip")
@patch("shortform.pipeline.resolve_editing_plan")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_forwards_per_scene_transitions_in_order(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_plan, mock_clip,
    mock_assemble, mock_select, mock_mix, tmp_path
):
    script = Script(
        title="T",
        scenes=[
            Scene(1, "n1", "v1", 4.0),
            Scene(2, "n2", "v2", 4.0),
            Scene(3, "n3", "v3", 4.0),
        ],
    )
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {
        1: SceneMedia(1, tmp_path / "scene_01.png", "image"),
        2: SceneMedia(2, tmp_path / "scene_02.png", "image"),
        3: SceneMedia(3, tmp_path / "scene_03.png", "image"),
    }
    mock_ass.return_value = "ASS_TEXT"
    mock_plan.return_value = [
        ScenePlan(layout="fullscreen", transition="fade"),
        ScenePlan(layout="fullscreen", transition="wipeup"),
        ScenePlan(layout="fullscreen", transition="circleopen"),
    ]
    mock_clip.side_effect = lambda *a, **k: a[4]  # return clip_path
    mock_assemble.return_value = work_dir / "pre_bgm.mp4"
    mock_select.return_value = tmp_path / "t.mp3"
    mock_mix.return_value = tmp_path / "final.mp4"

    render_script(script, tmp_path / "final.mp4", asset_folder=None, work_dir=work_dir)

    assert mock_assemble.call_args.kwargs["transitions"] == ["fade", "wipeup", "circleopen"]


@patch("shortform.pipeline.mix_bgm")
@patch("shortform.pipeline.select_bgm_track")
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_scene_clip")
@patch("shortform.pipeline.resolve_editing_plan")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_routes_video_media_to_build_scene_clip(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_plan, mock_clip,
    mock_assemble, mock_select, mock_mix, tmp_path
):
    script = Script(title="T", scenes=[Scene(1, "나레이션", "골목길", 4.0)])
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {1: SceneMedia(1, tmp_path / "scene_01.mp4", "video")}
    mock_ass.return_value = "ASS_TEXT"
    # Even if the director suggests an image layout, video media always uses build_scene_clip
    mock_plan.return_value = [ScenePlan(layout="polaroid", transition="fade")]
    mock_clip.return_value = work_dir / "clip_01.mp4"
    mock_assemble.return_value = work_dir / "pre_bgm.mp4"
    mock_select.return_value = tmp_path / "t.mp3"
    mock_mix.return_value = tmp_path / "final.mp4"

    render_script(script, tmp_path / "final.mp4", asset_folder=None, work_dir=work_dir)

    mock_clip.assert_called_once_with(
        tmp_path / "scene_01.mp4",
        "video",
        work_dir / "scene_01.mp3",
        4.0,
        work_dir / "clip_01.mp4",
        pan_variant=1,
    )


@patch("shortform.pipeline.mix_bgm")
@patch("shortform.pipeline.select_bgm_track")
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_title_card_scene_clip")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_skips_scene_with_failed_tts(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_clip,
    mock_assemble, mock_select, mock_mix, tmp_path, caplog
):
    script = Script(
        title="T",
        scenes=[
            Scene(1, "성공 나레이션", "골목길", 4.0),
            Scene(2, "실패 나레이션", "카페", 5.0),
        ],
    )
    mock_tts.side_effect = [None, RuntimeError("TTS 실패")]
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {
        1: SceneMedia(1, tmp_path / "scene_01.png", "image"),
        2: SceneMedia(2, tmp_path / "scene_02.png", "image"),
    }
    mock_ass.return_value = "ASS_TEXT"
    mock_clip.return_value = tmp_path / "clip_01.mp4"
    mock_assemble.return_value = tmp_path / "media" / "pre_bgm.mp4"
    mock_select.return_value = tmp_path / "t.mp3"
    out_path = tmp_path / "final.mp4"
    mock_mix.return_value = out_path

    with caplog.at_level("WARNING"):
        result = render_script(script, out_path, work_dir=tmp_path / "media")

    # Verify resolve_scene_media was called with only the successful scene (scene 1)
    call_args = mock_resolve.call_args
    filtered_script = call_args[0][0]
    assert len(filtered_script.scenes) == 1
    assert filtered_script.scenes[0].index == 1

    # Scene 1 (first renderable, forced titlecard hook) routes to the title card builder
    mock_clip.assert_called_once()
    assert mock_ass.call_args[0][0] == [script.scenes[0]]
    assert mock_ass.call_args[0][2] == TRANSITION_DURATION_SEC
    assert "씬 2" in caplog.text
    assert result == out_path


@patch("shortform.pipeline.mix_bgm")
@patch("shortform.pipeline.select_bgm_track")
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_scene_clip")
@patch("shortform.pipeline.resolve_editing_plan")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_passes_motion_indices_to_media_resolution(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_plan, mock_clip,
    mock_assemble, mock_select, mock_mix, tmp_path
):
    # scene 1 is the hook (excluded), scenes 2 and 3 are flagged, scene 4 flagged but over the cap
    script = Script(
        title="T",
        scenes=[
            Scene(1, "n", "v", 4.0, motion=True),
            Scene(2, "n", "v", 4.0, motion=True),
            Scene(3, "n", "v", 4.0, motion=True),
            Scene(4, "n", "v", 4.0, motion=True),
        ],
    )
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {i: SceneMedia(i, tmp_path / f"s{i}.png", "image") for i in range(1, 5)}
    mock_ass.return_value = "ASS_TEXT"
    mock_plan.return_value = [ScenePlan(layout="fullscreen", transition="fade")] * 4
    mock_clip.side_effect = lambda *a, **k: a[4]
    mock_assemble.return_value = work_dir / "pre_bgm.mp4"
    mock_select.return_value = tmp_path / "t.mp3"
    mock_mix.return_value = tmp_path / "final.mp4"

    # 특수한 경우에만 명시적으로 켠다 (기본값은 0=꺼짐)
    render_script(script, tmp_path / "final.mp4", asset_folder=None, work_dir=work_dir,
                  max_motion_scenes=2)
    assert mock_resolve.call_args.kwargs["motion_indices"] == {2, 3}

    # 기본값: 모션 꺼짐 — Veo 비용 0
    render_script(script, tmp_path / "final.mp4", asset_folder=None, work_dir=work_dir)
    assert mock_resolve.call_args.kwargs["motion_indices"] == set()


@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_raises_when_all_scenes_fail(mock_tts, mock_duration, mock_resolve, tmp_path):
    script = Script(title="T", scenes=[Scene(1, "n", "v", 4.0)])
    mock_tts.side_effect = RuntimeError("TTS 실패")

    try:
        render_script(script, tmp_path / "final.mp4", work_dir=tmp_path / "media")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "모든 씬" in str(e)

    # Verify resolve_scene_media was NOT called when all TTS failed
    mock_resolve.assert_not_called()


@patch("shortform.pipeline.synthesize_bgm_pad")
@patch("shortform.pipeline.mix_bgm")
@patch("shortform.pipeline.select_bgm_track")
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_scene_clip")
@patch("shortform.pipeline.resolve_editing_plan")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_synthesizes_pad_when_no_local_track(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_plan, mock_clip,
    mock_assemble, mock_select, mock_mix, mock_synth, tmp_path
):
    script = Script(title="T", scenes=[Scene(1, "n", "v", 4.0)], mood="exciting")
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {1: SceneMedia(1, tmp_path / "s.png", "image")}
    mock_ass.return_value = "ASS_TEXT"
    mock_plan.return_value = [ScenePlan(layout="fullscreen", transition="fade")]
    mock_clip.return_value = work_dir / "clip_01.mp4"
    pre_bgm = work_dir / "pre_bgm.mp4"
    mock_assemble.return_value = pre_bgm
    mock_select.return_value = None                    # no local track
    pad = work_dir / "bgm_pad.wav"
    mock_synth.return_value = pad
    out_path = tmp_path / "final.mp4"
    mock_mix.return_value = out_path

    result = render_script(script, out_path, asset_folder=None, work_dir=work_dir)

    mock_select.assert_called_once_with("exciting")
    mock_synth.assert_called_once_with("exciting", 4.0, work_dir / "bgm_pad.wav")
    # synth pad is already quiet → mixed hotter than a full-scale local track
    mock_mix.assert_called_once_with(pre_bgm, pad, out_path, music_volume=0.6)
    assert result == out_path


@patch("shortform.pipeline.mix_bgm")
@patch("shortform.pipeline.select_bgm_track")
@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_scene_clip")
@patch("shortform.pipeline.resolve_editing_plan")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_falls_back_without_bgm_on_mix_failure(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_plan, mock_clip,
    mock_assemble, mock_select, mock_mix, tmp_path, caplog
):
    script = Script(title="T", scenes=[Scene(1, "n", "v", 4.0)])
    work_dir = tmp_path / "media"
    work_dir.mkdir()
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {1: SceneMedia(1, tmp_path / "s.png", "image")}
    mock_ass.return_value = "ASS_TEXT"
    mock_plan.return_value = [ScenePlan(layout="fullscreen", transition="fade")]
    mock_clip.return_value = work_dir / "clip_01.mp4"
    pre_bgm = work_dir / "pre_bgm.mp4"
    pre_bgm.write_bytes(b"FAKE_VIDEO")               # real file so the fallback copy works
    mock_assemble.return_value = pre_bgm
    mock_select.return_value = tmp_path / "t.mp3"
    mock_mix.side_effect = RuntimeError("mix 실패")
    out_path = tmp_path / "final.mp4"

    with caplog.at_level("WARNING"):
        result = render_script(script, out_path, asset_folder=None, work_dir=work_dir)

    # video still ships, just without bgm
    assert result == out_path
    assert out_path.read_bytes() == b"FAKE_VIDEO"
    assert "BGM" in caplog.text
