import os

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

SCRIPT_TOOL = {
    "name": "emit_script",
    "description": "숏폼 영상 나레이션 스크립트를 씬 단위로 반환한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "hook_candidates": {"type": "array", "items": {"type": "string"}},
            "hook_reason": {"type": "string"},
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "narration": {"type": "string"},
                        "visual_description": {"type": "string"},
                        "duration_hint_sec": {"type": "number"},
                        "highlight_words": {"type": "array", "items": {"type": "string"}},
                        "layout": {"type": "string", "enum": ["fullscreen", "polaroid", "split", "titlecard"]},
                        "transition_in": {"type": "string", "enum": ["dissolve", "slide", "wipe", "zoom"]},
                    },
                    "required": ["index", "narration", "visual_description", "duration_hint_sec"],
                },
            },
        },
        "required": ["title", "scenes"],
    },
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_anthropic(client, model, prompt):
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        tools=[SCRIPT_TOOL],
        tool_choice={"type": "tool", "name": "emit_script"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    data = tool_use_block.input
    if "scenes" not in data:
        raise ValueError(f"LLM 응답에 필수 필드가 누락되었습니다: {list(data.keys())}")
    return data


def generate_script_json(prompt: str, model: str = "claude-sonnet-5") -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
    client = anthropic.Anthropic(api_key=api_key)
    return _call_anthropic(client, model, prompt)
