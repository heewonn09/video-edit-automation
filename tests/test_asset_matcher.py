from pathlib import Path
from unittest.mock import patch, MagicMock
from shortform.asset_matcher import match_assets
from shortform.asset_library import AssetInfo
from shortform.scene_schema import Script, Scene


@patch("shortform.asset_matcher.anthropic.Anthropic")
def test_match_assets_maps_scene_to_asset(mock_anthropic_cls, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    fake_block = MagicMock(
        type="tool_use",
        input={"matches": [{"scene_index": 1, "filename": "alley.mp4"}]},
    )
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(content=[fake_block])
    mock_anthropic_cls.return_value = mock_client

    script = Script(title="T", scenes=[Scene(1, "n", "골목길 야간", 5.0)])
    assets = [AssetInfo(path=Path("alley.mp4"), filename="alley.mp4", kind="video")]

    result = match_assets(script, assets)

    assert result[1].filename == "alley.mp4"


def test_match_assets_returns_none_for_all_when_no_assets():
    script = Script(title="T", scenes=[Scene(1, "n", "골목길 야간", 5.0)])
    assert match_assets(script, []) == {1: None}
