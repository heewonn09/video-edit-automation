import re

_URL_RE = re.compile(r"^(https?://|www\.)[^\s]+\.[a-z]{2,}(/.*)?$", re.IGNORECASE)


def classify_input(raw: str) -> str:
    raw = raw.strip()
    return "url" if _URL_RE.match(raw) else "topic"
