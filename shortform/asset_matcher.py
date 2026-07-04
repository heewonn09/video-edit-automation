import os

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

ASSET_MATCH_TOOL = {
    "name": "emit_matches",
    "description": "각 씬 번호에 가장 적합한 로컬 자산 파일명을 매칭한다. 적합한 자산이 없으면 null을 반환한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "matches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "scene_index": {"type": "integer"},
                        "filename": {"type": ["string", "null"]},
                    },
                    "required": ["scene_index", "filename"],
                },
            },
        },
        "required": ["matches"],
    },
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_anthropic(client, model, prompt):
    return client.messages.create(
        model=model,
        max_tokens=1024,
        tools=[ASSET_MATCH_TOOL],
        tool_choice={"type": "tool", "name": "emit_matches"},
        messages=[{"role": "user", "content": prompt}],
    )


def match_assets(script, assets, model: str = "claude-sonnet-5") -> dict:
    if not assets:
        return {scene.index: None for scene in script.scenes}

    scene_lines = "\n".join(f"- 씬 {s.index}: {s.visual_description}" for s in script.scenes)
    asset_lines = "\n".join(f"- {a.filename}" for a in assets)
    prompt = (
        "다음은 숏폼 영상의 씬별 연출 지시와, 사용 가능한 로컬 미디어 파일 목록이다.\n"
        "각 씬에 가장 잘 어울리는 파일을 하나씩 선택해라. 적합한 파일이 없으면 filename을 null로 남겨라.\n\n"
        f"씬 목록:\n{scene_lines}\n\n"
        f"파일 목록:\n{asset_lines}\n"
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    client = anthropic.Anthropic(api_key=api_key)
    response = _call_anthropic(client, model, prompt)
    tool_use_block = next(b for b in response.content if b.type == "tool_use")

    assets_by_filename = {a.filename: a for a in assets}
    result = {}
    for m in tool_use_block.input["matches"]:
        filename = m["filename"]
        result[m["scene_index"]] = assets_by_filename.get(filename) if filename else None
    return result
