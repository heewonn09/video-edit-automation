from unittest.mock import patch, call
from pathlib import Path
from shortform.pipeline import render_script, TRANSITION_DURATION_SEC
from shortform.scene_schema import Script, Scene
from shortform.media_matcher import SceneMedia


@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_split_screen_scene_clip")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_wires_all_stages(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_split, mock_assemble, tmp_path
):
    script = Script(title="T", scenes=[Scene(1, "나레이션", "골목길", 4.0)])
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {1: SceneMedia(1, tmp_path / "scene_01.png", "image")}
    mock_ass.return_value = "ASS_TEXT"
    mock_split.return_value = work_dir / "clip_01.mp4"
    out_path = tmp_path / "final.mp4"
    mock_assemble.return_value = out_path

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

    # Odd scene index routes image scenes to build_split_screen_scene_clip
    mock_split.assert_called_once_with(
        tmp_path / "scene_01.png",
        work_dir / "scene_01.mp3",
        4.0,
        work_dir / "clip_01.mp4",
    )

    mock_ass.assert_called_once_with(script.scenes, [4.0], TRANSITION_DURATION_SEC)
    mock_assemble.assert_called_once()
    assert result == out_path


@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_split_screen_scene_clip")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_skips_scene_with_failed_tts(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_split, mock_assemble, tmp_path, caplog
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
    mock_split.return_value = tmp_path / "clip_01.mp4"
    out_path = tmp_path / "final.mp4"
    mock_assemble.return_value = out_path

    with caplog.at_level("WARNING"):
        result = render_script(script, out_path, work_dir=tmp_path / "media")

    # Verify resolve_scene_media was called with only the successful scene (scene 1)
    call_args = mock_resolve.call_args
    filtered_script = call_args[0][0]
    assert len(filtered_script.scenes) == 1
    assert filtered_script.scenes[0].index == 1

    mock_split.assert_called_once()
    assert mock_ass.call_args[0][0] == [script.scenes[0]]
    assert mock_ass.call_args[0][2] == TRANSITION_DURATION_SEC
    assert "씬 2" in caplog.text
    assert result == out_path


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


@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_polaroid_scene_clip")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_routes_even_index_image_scene_to_polaroid(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_polaroid, mock_assemble, tmp_path
):
    script = Script(title="T", scenes=[Scene(2, "나레이션", "골목길", 4.0)])
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {2: SceneMedia(2, tmp_path / "scene_02.png", "image")}
    mock_ass.return_value = "ASS_TEXT"
    mock_polaroid.return_value = work_dir / "clip_02.mp4"
    out_path = tmp_path / "final.mp4"
    mock_assemble.return_value = out_path

    render_script(script, out_path, asset_folder=None, work_dir=work_dir)

    mock_polaroid.assert_called_once_with(
        tmp_path / "scene_02.png",
        work_dir / "scene_02.mp3",
        4.0,
        work_dir / "clip_02.mp4",
        tilt_variant=2,
    )


@patch("shortform.pipeline.assemble_with_transitions")
@patch("shortform.pipeline.build_scene_clip")
@patch("shortform.pipeline.build_ass_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_routes_video_media_to_build_scene_clip(
    mock_tts, mock_duration, mock_resolve, mock_ass, mock_clip, mock_assemble, tmp_path
):
    script = Script(title="T", scenes=[Scene(1, "나레이션", "골목길", 4.0)])
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {1: SceneMedia(1, tmp_path / "scene_01.mp4", "video")}
    mock_ass.return_value = "ASS_TEXT"
    mock_clip.return_value = work_dir / "clip_01.mp4"
    out_path = tmp_path / "final.mp4"
    mock_assemble.return_value = out_path

    render_script(script, out_path, asset_folder=None, work_dir=work_dir)

    mock_clip.assert_called_once_with(
        tmp_path / "scene_01.mp4",
        "video",
        work_dir / "scene_01.mp3",
        4.0,
        work_dir / "clip_01.mp4",
        pan_variant=1,
    )
