from dataclasses import dataclass
from pathlib import Path

from shortform.asset_library import list_assets
from shortform.asset_matcher import match_assets
from shortform.media_generator import generate_scene_image


@dataclass
class SceneMedia:
    scene_index: int
    path: Path
    media_type: str


def resolve_scene_media(script, asset_folder, generated_dir) -> dict:
    assets = list_assets(asset_folder) if asset_folder else []
    matches = match_assets(script, assets)

    generated_dir = Path(generated_dir)
    generated_dir.mkdir(parents=True, exist_ok=True)

    result = {}
    for scene in script.scenes:
        matched = matches.get(scene.index)
        if matched is not None:
            result[scene.index] = SceneMedia(scene.index, matched.path, matched.kind)
        else:
            out_path = generated_dir / f"scene_{scene.index:02d}.png"
            generate_scene_image(scene.visual_description, out_path)
            result[scene.index] = SceneMedia(scene.index, out_path, "image")
    return result
