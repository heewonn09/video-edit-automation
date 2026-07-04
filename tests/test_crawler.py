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


@patch("shortform.crawler._parse_article_html")
@patch("shortform.crawler._fetch_with_playwright")
@patch("shortform.crawler._fetch_via_requests")
@patch("shortform.crawler._check_robots_allowed")
def test_fetch_article_falls_back_to_playwright_on_block(
    mock_robots, mock_via_requests, mock_playwright_fetch, mock_parse
):
    from shortform.crawler import CrawlBlocked, ArticleContent

    mock_robots.return_value = True
    mock_via_requests.side_effect = CrawlBlocked("크롤링 차단됨: HTTP 403 (blocked)")
    mock_playwright_fetch.return_value = "<html>렌더링된 페이지</html>"
    mock_parse.return_value = ArticleContent(title="폴백 제목", text="폴백 본문")

    result = fetch_article("https://example.com/blocked-by-bots")

    mock_playwright_fetch.assert_called_once_with("https://example.com/blocked-by-bots")
    mock_parse.assert_called_once_with("<html>렌더링된 페이지</html>", "https://example.com/blocked-by-bots")
    assert result.title == "폴백 제목"
