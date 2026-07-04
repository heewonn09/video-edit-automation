import pytest
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


def test_generate_script_json_raises_runtime_error_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        generate_script_json("test")
    assert "ANTHROPIC_API_KEY가 설정되지 않았습니다" in str(exc_info.value)


@patch("shortform.llm_client.anthropic.Anthropic")
def test_generate_script_json_retries_on_transient_error(mock_anthropic_cls, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    fake_block = MagicMock(type="tool_use", input={"title": "t", "scenes": []})
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [RuntimeError("일시적 오류"), MagicMock(content=[fake_block])]
    mock_anthropic_cls.return_value = mock_client

    result = generate_script_json("프롬프트")

    assert result == {"title": "t", "scenes": []}
    assert mock_client.messages.create.call_count == 2


def test_script_tool_schema_includes_highlight_words():
    from shortform.llm_client import SCRIPT_TOOL
    scene_props = SCRIPT_TOOL["input_schema"]["properties"]["scenes"]["items"]["properties"]
    assert "highlight_words" in scene_props
    assert scene_props["highlight_words"]["type"] == "array"
