import os
from pathlib import Path

from google import genai
from google.genai import types


def generate_scene_image(prompt: str, out_path, model: str = "gemini-2.5-flash-image"):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="9:16"),
        ),
    )
    image_part = next(p for p in response.parts if p.inline_data is not None)
    image = image_part.as_image()

    out_path = Path(out_path)
    image.save(str(out_path))
    return out_path
