import random
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
import trafilatura
from playwright.sync_api import sync_playwright

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


@dataclass
class ArticleContent:
    title: str
    text: str


class CrawlBlocked(RuntimeError):
    """요청이 차단되었거나(403) 본문 추출에 실패해 우회가 필요한 경우."""


def _check_robots_allowed(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = requests.get(robots_url, timeout=10)
    except requests.RequestException:
        return True

    if resp.status_code != 200:
        return True

    parser = urllib.robotparser.RobotFileParser()
    parser.parse(resp.text.splitlines())
    return parser.can_fetch("*", url)


def _parse_article_html(html: str, url: str) -> ArticleContent:
    text = trafilatura.extract(html) or ""
    metadata = trafilatura.extract_metadata(html)
    title = metadata.title if metadata and metadata.title else url

    if not text.strip():
        raise CrawlBlocked(f"본문 추출 실패 (빈 텍스트): {url}")

    return ArticleContent(title=title, text=text)


def _fetch_via_requests(url: str) -> ArticleContent:
    user_agent = random.choice(USER_AGENTS)
    resp = requests.get(url, timeout=15, headers={"User-Agent": user_agent})
    if resp.status_code == 403:
        raise CrawlBlocked(f"크롤링 차단됨: HTTP 403 ({url})")
    if resp.status_code != 200:
        raise RuntimeError(f"크롤링 실패: HTTP {resp.status_code} ({url})")
    return _parse_article_html(resp.text, url)


def _fetch_with_playwright(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(url, timeout=30000)
            return page.content()
        finally:
            browser.close()


def fetch_article(url: str) -> ArticleContent:
    if not _check_robots_allowed(url):
        raise RuntimeError(f"robots.txt에 의해 크롤링이 차단된 URL입니다: {url}")

    try:
        return _fetch_via_requests(url)
    except CrawlBlocked:
        html = _fetch_with_playwright(url)
        return _parse_article_html(html, url)
