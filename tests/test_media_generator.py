from unittest.mock import patch, MagicMock
from shortform.media_generator import generate_scene_image


@patch("shortform.media_generator.genai.Client")
def test_generate_scene_image_saves_file(mock_client_cls, tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mock_image = MagicMock()
    mock_part = MagicMock(inline_data=object())
    mock_part.as_image.return_value = mock_image
    mock_response = MagicMock(parts=[mock_part])
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_client_cls.return_value = mock_client

    out_path = tmp_path / "scene1.png"
    result = generate_scene_image("골목길, 야간, 시네마틱", out_path)

    mock_image.save.assert_called_once_with(str(out_path))
    assert result == out_path


def test_generate_scene_image_raises_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    try:
        generate_scene_image("prompt", tmp_path / "x.png")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "GEMINI_API_KEY" in str(e)
