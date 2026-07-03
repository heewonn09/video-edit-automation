from unittest.mock import patch, MagicMock
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
    mock_duration.return_value = 4.0
    mock_resolve.return_value = {1: SceneMedia(1, tmp_path / "scene_01.png", "image")}
    mock_srt.return_value = "SRT_TEXT"
    mock_clip.return_value = tmp_path / "media" / "clip_01.mp4"
    out_path = tmp_path / "final.mp4"
    mock_assemble.return_value = out_path

    result = render_script(script, out_path, asset_folder=None, work_dir=tmp_path / "media")

    mock_tts.assert_called_once()
    mock_resolve.assert_called_once()
    mock_clip.assert_called_once()
    mock_assemble.assert_called_once()
    assert result == out_path
