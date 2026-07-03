from unittest.mock import patch, call
from pathlib import Path
from shortform.pipeline import render_script
from shortform.scene_schema import Script, Scene
from shortform.media_matcher import SceneMedia


@patch("shortform.pipeline.assemble_final_video")
@patch("shortform.pipeline.build_scene_clip")
@patch("shortform.pipeline.build_srt_from_scenes")
@patch("shortform.pipeline.resolve_scene_media")
@patch("shortform.pipeline.get_audio_duration")
@patch("shortform.pipeline.synthesize_narration")
def test_render_script_wires_all_stages(
    mock_tts, mock_duration, mock_resolve, mock_srt, mock_clip, mock_assemble, tmp_path
):
    script = Script(title="T", scenes=[Scene(1, "나레이션", "골목길", 4.0)])
    work_dir = tmp_path / "media"
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {1: SceneMedia(1, tmp_path / "scene_01.png", "image")}
    mock_srt.return_value = "SRT_TEXT"
    mock_clip.return_value = work_dir / "clip_01.mp4"
    out_path = tmp_path / "final.mp4"
    mock_assemble.return_value = out_path

    result = render_script(script, out_path, asset_folder=None, work_dir=work_dir)

    # Verify TTS synthesis was called with correct scene narration and audio path
    mock_tts.assert_called_once_with("나레이션", work_dir / "scene_01.mp3")

    # Verify media resolution was called with script, asset_folder, and generated path
    mock_resolve.assert_called_once_with(script, None, work_dir / "generated")

    # Verify duration was measured for the synthesized audio
    mock_duration.assert_called_once_with(work_dir / "scene_01.mp3")

    # Highest-risk call: build_scene_clip with 5 positional args in correct order
    # media.path, media.media_type, audio_path for scene, duration, clip_path
    mock_clip.assert_called_once_with(
        tmp_path / "scene_01.png",  # media.path
        "image",                     # media.media_type
        work_dir / "scene_01.mp3",  # audio_paths[scene.index]
        4.0,                         # duration from mock_duration
        work_dir / "clip_01.mp4"    # clip_path
    )

    # Verify SRT was built from scenes and their durations
    mock_srt.assert_called_once_with(script.scenes, [4.0])

    # Verify final assembly was called
    mock_assemble.assert_called_once()

    assert result == out_path
