from unittest.mock import patch, MagicMock
from shortform.crawler import fetch_article


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
