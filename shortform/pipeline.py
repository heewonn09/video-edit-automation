from pathlib import Path

from shortform.media_matcher import resolve_scene_media
from shortform.renderer import assemble_final_video, build_scene_clip, build_srt_from_scenes
from shortform.tts import get_audio_duration, synthesize_narration

DEFAULT_RENDER_CONFIG = {
    "subtitle_font": "Malgun Gothic",
    "subtitle_font_size": 44,
}


def render_script(script, out_path, asset_folder=None, work_dir="output/media"):
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    audio_paths = {}
    durations = []
    for scene in script.scenes:
        audio_path = work_dir / f"scene_{scene.index:02d}.mp3"
        synthesize_narration(scene.narration, audio_path)
        audio_paths[scene.index] = audio_path
        durations.append(get_audio_duration(audio_path))

    scene_media = resolve_scene_media(script, asset_folder, work_dir / "generated")

    clip_paths = []
    for scene, duration in zip(script.scenes, durations):
        media = scene_media[scene.index]
        clip_path = work_dir / f"clip_{scene.index:02d}.mp4"
        build_scene_clip(media.path, media.media_type, audio_paths[scene.index], duration, clip_path)
        clip_paths.append(clip_path)

    srt_text = build_srt_from_scenes(script.scenes, durations)
    return assemble_final_video(clip_paths, srt_text, out_path, DEFAULT_RENDER_CONFIG)
