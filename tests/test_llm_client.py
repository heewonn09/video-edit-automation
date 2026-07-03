from unittest.mock import patch, MagicMock
from shortform.llm_client import generate_script_json

@patch("shortform.llm_client.anthropic.Anthropic")
def test_generate_script_json_extracts_tool_use_input(mock_anthropic_cls, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    fake_block = MagicMock(type="tool_use", input={"title": "t", "scenes": []})
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(content=[fake_block])
    mock_anthropic_cls.return_value = mock_client

    result = generate_script_json("프롬프트 내용")

    assert result == {"title": "t", "scenes": []}
    mock_client.messages.create.assert_called_once()
    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["tool_choice"] == {"type": "tool", "name": "emit_script"}
