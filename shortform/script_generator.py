from shortform.crawler import fetch_article
from shortform.input_handler import classify_input
from shortform.llm_client import generate_script_json
from shortform.scene_schema import Script, script_from_dict

EDITING_DIRECTION_GUIDE = """\
각 씬마다 내용에 맞는 화면 구성(layout)과 전환(transition_in)을 함께 정해줘.
- layout: 풍경·전체 임팩트는 fullscreen, 인물·특정 순간 강조는 polaroid, 비교·전후·둘을 나란히 보여줄 땐 split, 핵심 문구를 디자인된 텍스트로 크게 보여줄 땐 titlecard.
- transition_in: 회상·감정은 dissolve, 항목을 나열하며 넘어갈 땐 slide, 장소·장면이 바뀌면 wipe, 강조·훅은 zoom.
영상이 단조롭지 않도록 연속된 씬은 되도록 다른 layout을 쓰되, 억지로 바꾸지 말고 내용에 맞게 정해줘.

영상 첫 3초에 시청자를 붙잡을 오프닝 훅 후보를 3개 만들어 hook_candidates로 출력해줘.
그중 가장 강한 하나를 골라 첫 번째 씬의 나레이션으로 그대로 사용하고, 왜 그것을 골랐는지 hook_reason에 한 줄로 적어줘.
좋은 훅: 구체적 숫자, 의외성, 질문, 시청자가 자기 얘기라고 느끼는 표현.
첫 번째 씬(훅)에는 영상의 핵심 포인트를 요약하는 chips를 2~3개 담아줘 — 각각 icon(내용에 어울리는 이모지 1개)과 label(2~6자 짧은 문구).
영상 전체 분위기에 맞는 배경음악 무드를 mood로 골라줘 — bright(밝고 경쾌), calm(잔잔·차분), exciting(긴장감·에너지), emotional(감성·따뜻)."""

TOPIC_PROMPT_TEMPLATE = """\
다음 주제로 30~60초 분량의 숏폼 영상 나레이션 스크립트를 작성해줘.
영상 전체를 대표하는 짧고 매력적인 제목을 title로 함께 지어줘.
씬 단위로 나누고, 각 씬마다 나레이션과 어울리는 영상 연출 지시(visual_description)를 함께 제시해줘.
각 씬의 나레이션 문장 안에 실제로 등장하는 단어 중, 시청자 시선을 끌 핵심 키워드를 1~3개 골라 highlight_words로 표시해줘.
{editing_guide}

주제: {topic}
"""

ARTICLE_PROMPT_TEMPLATE = """\
다음 기사 내용을 바탕으로 30~60초 분량의 숏폼 영상 나레이션 스크립트를 작성해줘.
영상 전체를 대표하는 짧고 매력적인 제목을 title로 함께 지어줘(기사 제목을 그대로 쓰지 말고 숏폼에 맞게 재구성).
핵심 내용을 요약하고, 씬 단위로 나누어 각 씬마다 나레이션과 어울리는 영상 연출 지시(visual_description)를 함께 제시해줘.
각 씬의 나레이션 문장 안에 실제로 등장하는 단어 중, 시청자 시선을 끌 핵심 키워드를 1~3개 골라 highlight_words로 표시해줘.
{editing_guide}

기사 제목: {title}
기사 본문: {text}
"""


def generate_script(raw_input: str) -> Script:
    input_type = classify_input(raw_input)

    if input_type == "url":
        article = fetch_article(raw_input)
        prompt = ARTICLE_PROMPT_TEMPLATE.format(
            title=article.title, text=article.text, editing_guide=EDITING_DIRECTION_GUIDE
        )
        fallback_title = article.title
    else:
        prompt = TOPIC_PROMPT_TEMPLATE.format(topic=raw_input, editing_guide=EDITING_DIRECTION_GUIDE)
        fallback_title = raw_input

    data = generate_script_json(prompt)
    if not data.get("title"):
        data["title"] = fallback_title
    return script_from_dict(data)
