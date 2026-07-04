import logging
from pathlib import Path

from shortform.media_matcher import resolve_scene_media
from shortform.renderer import assemble_final_video, build_scene_clip, build_srt_from_scenes
from shortform.scene_schema import Script
from shortform.tts import get_audio_duration, synthesize_narration

logger = logging.getLogger(__name__)

DEFAULT_RENDER_CONFIG = {
    "subtitle_font": "Malgun Gothic",
    "subtitle_font_size": 44,
}


def render_script(script, out_path, asset_folder=None, work_dir="output/media"):
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    audio_paths = {}
    durations_by_index = {}
    for scene in script.scenes:
        audio_path = work_dir / f"scene_{scene.index:02d}.mp3"
        try:
            synthesize_narration(scene.narration, audio_path)
            durations_by_index[scene.index] = get_audio_duration(audio_path)
            audio_paths[scene.index] = audio_path
        except Exception as e:
            logger.warning(f"씬 {scene.index} 나레이션 생성 실패 ({e}) — 스킵")

    # Only resolve media for scenes with successful TTS
    if audio_paths:
        filtered_scenes = [scene for scene in script.scenes if scene.index in audio_paths]
        filtered_script = Script(title=script.title, scenes=filtered_scenes)
        scene_media = resolve_scene_media(filtered_script, asset_folder, work_dir / "generated")
    else:
        scene_media = {}

    successful_scenes = []
    clip_paths = []
    durations = []
    for scene in script.scenes:
        if scene.index not in audio_paths or scene.index not in scene_media:
            continue
        media = scene_media[scene.index]
        duration = durations_by_index[scene.index]
        clip_path = work_dir / f"clip_{scene.index:02d}.mp4"
        try:
            build_scene_clip(media.path, media.media_type, audio_paths[scene.index], duration, clip_path)
        except Exception as e:
            logger.warning(f"씬 {scene.index} 클립 생성 실패 ({e}) — 스킵")
            continue
        successful_scenes.append(scene)
        clip_paths.append(clip_path)
        durations.append(duration)

    logger.info(f"씬 처리 완료: {len(successful_scenes)}/{len(script.scenes)}개 성공")

    if not clip_paths:
        raise RuntimeError("모든 씬 처리에 실패하여 영상을 생성할 수 없습니다.")

    srt_text = build_srt_from_scenes(successful_scenes, durations)
    return assemble_final_video(clip_paths, srt_text, out_path, DEFAULT_RENDER_CONFIG)
