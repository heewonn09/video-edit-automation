import logging
from dataclasses import dataclass
from pathlib import Path

from shortform.asset_library import list_assets
from shortform.asset_matcher import match_assets
from shortform.media_generator import generate_scene_image
from shortform.motion import generate_scene_video

logger = logging.getLogger(__name__)


@dataclass
class SceneMedia:
    scene_index: int
    path: Path
    media_type: str


def resolve_scene_media(script, asset_folder, generated_dir, motion_indices=None) -> dict:
    assets = list_assets(asset_folder) if asset_folder else []
    matches = match_assets(script, assets)
    motion_indices = motion_indices or set()

    generated_dir = Path(generated_dir)
    generated_dir.mkdir(parents=True, exist_ok=True)

    result = {}
    for scene in script.scenes:
        matched = matches.get(scene.index)
        if matched is not None:
            result[scene.index] = SceneMedia(scene.index, matched.path, matched.kind)
            continue

        out_path = generated_dir / f"scene_{scene.index:02d}.png"
        try:
            generate_scene_image(scene.visual_description, out_path)
        except Exception as e:
            logger.warning(f"씬 {scene.index} 미디어 생성 실패 ({e}) — 스킵")
            continue

        # 모션 대상: 생성 이미지를 Veo로 영상화. 캐시 재사용으로 재생성 비용 방지,
        # 실패하면 이미지로 폴백 (영상은 항상 나온다).
        if scene.index in motion_indices:
            video_path = generated_dir / f"scene_{scene.index:02d}.mp4"
            if video_path.exists():
                result[scene.index] = SceneMedia(scene.index, video_path, "video")
                continue
            try:
                generate_scene_video(out_path, scene.visual_description, video_path)
                result[scene.index] = SceneMedia(scene.index, video_path, "video")
                continue
            except Exception as e:
                logger.warning(f"씬 {scene.index} Veo 영상 생성 실패 ({e}) — 이미지로 폴백")

        result[scene.index] = SceneMedia(scene.index, out_path, "image")
    return result
