from pathlib import Path
from unittest.mock import patch, MagicMock
from shortform.media_matcher import resolve_scene_media
from shortform.asset_library import AssetInfo
from shortform.scene_schema import Script, Scene


@patch("shortform.media_matcher.generate_scene_image")
@patch("shortform.media_matcher.match_assets")
@patch("shortform.media_matcher.list_assets")
def test_resolve_scene_media_prefers_asset_then_falls_back_to_gemini(
    mock_list_assets, mock_match_assets, mock_generate, tmp_path
):
    script = Script(
        title="T",
        scenes=[Scene(1, "n1", "골목길", 4.0), Scene(2, "n2", "카페", 5.0)],
    )
    matched_asset = AssetInfo(path=Path("alley.mp4"), filename="alley.mp4", kind="video")
    mock_list_assets.return_value = [matched_asset]
    mock_match_assets.return_value = {1: matched_asset, 2: None}
    mock_generate.return_value = tmp_path / "generated" / "scene_02.png"

    result = resolve_scene_media(script, "assets_dir", tmp_path / "generated")

    assert result[1].path == matched_asset.path
    assert result[1].media_type == "video"
    assert result[2].media_type == "image"
    mock_generate.assert_called_once_with("카페", tmp_path / "generated" / "scene_02.png")


@patch("shortform.media_matcher.generate_scene_image")
@patch("shortform.media_matcher.match_assets")
@patch("shortform.media_matcher.list_assets")
def test_resolve_scene_media_skips_scene_on_generation_failure(
    mock_list_assets, mock_match_assets, mock_generate, tmp_path, caplog
):
    script = Script(
        title="T",
        scenes=[Scene(1, "n1", "골목길", 4.0), Scene(2, "n2", "실패씬", 5.0)],
    )
    mock_list_assets.return_value = []
    mock_match_assets.return_value = {1: None, 2: None}
    mock_generate.side_effect = [tmp_path / "generated" / "scene_01.png", RuntimeError("Gemini 오류")]

    with caplog.at_level("WARNING"):
        result = resolve_scene_media(script, None, tmp_path / "generated")

    assert 1 in result
    assert 2 not in result
    assert "씬 2" in caplog.text
