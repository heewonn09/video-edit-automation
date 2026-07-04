from unittest.mock import patch
from shortform.script_generator import ARTICLE_PROMPT_TEMPLATE, TOPIC_PROMPT_TEMPLATE, generate_script


def test_topic_prompt_asks_for_a_title():
    prompt = TOPIC_PROMPT_TEMPLATE.format(topic="주제")
    assert "제목" in prompt


def test_article_prompt_asks_for_a_title():
    prompt = ARTICLE_PROMPT_TEMPLATE.format(title="기사 제목", text="본문")
    assert "제목" in prompt.split("기사 제목:")[0]


@patch("shortform.script_generator.generate_script_json")
def test_generate_script_from_topic(mock_llm):
    mock_llm.return_value = {"title": "T", "scenes": [
        {"index": 1, "narration": "n", "visual_description": "v", "duration_hint_sec": 5}
    ]}
    script = generate_script("강아지 산책 꿀팁")
    assert script.title == "T"
    prompt_arg = mock_llm.call_args[0][0]
    assert "강아지 산책 꿀팁" in prompt_arg


@patch("shortform.script_generator.generate_script_json")
@patch("shortform.script_generator.fetch_article")
def test_generate_script_from_url(mock_fetch, mock_llm):
    from shortform.crawler import ArticleContent
    mock_fetch.return_value = ArticleContent(title="기사", text="본문 내용")
    mock_llm.return_value = {"title": "T2", "scenes": []}

    script = generate_script("https://example.com/news/1")

    mock_fetch.assert_called_once_with("https://example.com/news/1")
    prompt_arg = mock_llm.call_args[0][0]
    assert "본문 내용" in prompt_arg
    assert script.title == "T2"
