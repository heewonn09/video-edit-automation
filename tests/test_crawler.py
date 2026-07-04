from unittest.mock import patch, MagicMock
from shortform.crawler import fetch_article, USER_AGENTS


@patch("shortform.crawler.trafilatura.extract")
@patch("shortform.crawler.requests.get")
def test_fetch_article_extracts_title_and_text(mock_get, mock_extract):
    mock_get.return_value = MagicMock(status_code=200, text="<html>...</html>")
    mock_extract.return_value = "본문 내용입니다."

    with patch("shortform.crawler.trafilatura.extract_metadata") as mock_meta:
        mock_meta.return_value = MagicMock(title="기사 제목")
        result = fetch_article("https://example.com/a")

    assert result.title == "기사 제목"
    assert result.text == "본문 내용입니다."


@patch("shortform.crawler.requests.get")
def test_fetch_article_raises_on_http_error(mock_get):
    mock_get.return_value = MagicMock(status_code=404, text="")
    try:
        fetch_article("https://example.com/missing")
        assert False, "expected exception"
    except RuntimeError as e:
        assert "404" in str(e)


@patch("shortform.crawler.requests.get")
def test_fetch_article_raises_when_robots_disallows(mock_get):
    def fake_get(url, **kwargs):
        if url.endswith("/robots.txt"):
            return MagicMock(status_code=200, text="User-agent: *\nDisallow: /\n")
        return MagicMock(status_code=200, text="<html>...</html>")

    mock_get.side_effect = fake_get

    try:
        fetch_article("https://example.com/blocked")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "robots.txt" in str(e)


@patch("shortform.crawler.trafilatura.extract_metadata")
@patch("shortform.crawler.trafilatura.extract")
@patch("shortform.crawler.requests.get")
def test_fetch_article_uses_rotating_user_agent(mock_get, mock_extract, mock_meta):
    def fake_get(url, headers=None, **kwargs):
        if url.endswith("/robots.txt"):
            return MagicMock(status_code=404, text="")
        assert headers["User-Agent"] in USER_AGENTS
        return MagicMock(status_code=200, text="<html>...</html>")

    mock_get.side_effect = fake_get
    mock_extract.return_value = "본문"
    mock_meta.return_value = MagicMock(title="제목")

    fetch_article("https://example.com/a")
