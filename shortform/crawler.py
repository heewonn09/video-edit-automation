from dataclasses import dataclass

import requests
import trafilatura


@dataclass
class ArticleContent:
    title: str
    text: str


def fetch_article(url: str) -> ArticleContent:
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    if resp.status_code != 200:
        raise RuntimeError(f"크롤링 실패: HTTP {resp.status_code} ({url})")

    text = trafilatura.extract(resp.text) or ""
    metadata = trafilatura.extract_metadata(resp.text)
    title = metadata.title if metadata and metadata.title else url

    if not text.strip():
        raise RuntimeError(f"본문 추출 실패 (빈 텍스트): {url}")

    return ArticleContent(title=title, text=text)
