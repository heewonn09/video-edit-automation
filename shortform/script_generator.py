from shortform.crawler import fetch_article
from shortform.input_handler import classify_input
from shortform.llm_client import generate_script_json
from shortform.scene_schema import Script, script_from_dict

TOPIC_PROMPT_TEMPLATE = """\
다음 주제로 30~60초 분량의 숏폼 영상 나레이션 스크립트를 작성해줘.
영상 전체를 대표하는 짧고 매력적인 제목을 title로 함께 지어줘.
씬 단위로 나누고, 각 씬마다 나레이션과 어울리는 영상 연출 지시(visual_description)를 함께 제시해줘.
각 씬의 나레이션 문장 안에 실제로 등장하는 단어 중, 시청자 시선을 끌 핵심 키워드를 1~3개 골라 highlight_words로 표시해줘.

주제: {topic}
"""

ARTICLE_PROMPT_TEMPLATE = """\
다음 기사 내용을 바탕으로 30~60초 분량의 숏폼 영상 나레이션 스크립트를 작성해줘.
영상 전체를 대표하는 짧고 매력적인 제목을 title로 함께 지어줘(기사 제목을 그대로 쓰지 말고 숏폼에 맞게 재구성).
핵심 내용을 요약하고, 씬 단위로 나누어 각 씬마다 나레이션과 어울리는 영상 연출 지시(visual_description)를 함께 제시해줘.
각 씬의 나레이션 문장 안에 실제로 등장하는 단어 중, 시청자 시선을 끌 핵심 키워드를 1~3개 골라 highlight_words로 표시해줘.

기사 제목: {title}
기사 본문: {text}
"""


def generate_script(raw_input: str) -> Script:
    input_type = classify_input(raw_input)

    if input_type == "url":
        article = fetch_article(raw_input)
        prompt = ARTICLE_PROMPT_TEMPLATE.format(title=article.title, text=article.text)
        fallback_title = article.title
    else:
        prompt = TOPIC_PROMPT_TEMPLATE.format(topic=raw_input)
        fallback_title = raw_input

    data = generate_script_json(prompt)
    if not data.get("title"):
        data["title"] = fallback_title
    return script_from_dict(data)
