from shortform.crawler import fetch_article
from shortform.input_handler import classify_input
from shortform.llm_client import generate_script_json
from shortform.scene_schema import Script, script_from_dict

TOPIC_PROMPT_TEMPLATE = """\
다음 주제로 30~60초 분량의 숏폼 영상 나레이션 스크립트를 작성해줘.
씬 단위로 나누고, 각 씬마다 나레이션과 어울리는 영상 연출 지시(visual_description)를 함께 제시해줘.

주제: {topic}
"""

ARTICLE_PROMPT_TEMPLATE = """\
다음 기사 내용을 바탕으로 30~60초 분량의 숏폼 영상 나레이션 스크립트를 작성해줘.
핵심 내용을 요약하고, 씬 단위로 나누어 각 씬마다 나레이션과 어울리는 영상 연출 지시(visual_description)를 함께 제시해줘.

기사 제목: {title}
기사 본문: {text}
"""


def generate_script(raw_input: str) -> Script:
    input_type = classify_input(raw_input)

    if input_type == "url":
        article = fetch_article(raw_input)
        prompt = ARTICLE_PROMPT_TEMPLATE.format(title=article.title, text=article.text)
    else:
        prompt = TOPIC_PROMPT_TEMPLATE.format(topic=raw_input)

    data = generate_script_json(prompt)
    return script_from_dict(data)
