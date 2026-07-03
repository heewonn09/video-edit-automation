import os

import anthropic

SCRIPT_TOOL = {
    "name": "emit_script",
    "description": "숏폼 영상 나레이션 스크립트를 씬 단위로 반환한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "narration": {"type": "string"},
                        "visual_description": {"type": "string"},
                        "duration_hint_sec": {"type": "number"},
                    },
                    "required": ["index", "narration", "visual_description", "duration_hint_sec"],
                },
            },
        },
        "required": ["title", "scenes"],
    },
}


def generate_script_json(prompt: str, model: str = "claude-sonnet-5") -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        tools=[SCRIPT_TOOL],
        tool_choice={"type": "tool", "name": "emit_script"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    return tool_use_block.input
