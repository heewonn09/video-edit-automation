import logging
import shutil
from pathlib import Path

from shortform.bgm import (
    PAD_MIX_VOLUME,
    TRACK_MIX_VOLUME,
    mix_bgm,
    select_bgm_track,
    synthesize_bgm_pad,
)
from shortform.captions import build_ass_from_scenes
from shortform.editing_director import resolve_editing_plan
from shortform.media_matcher import resolve_scene_media
from shortform.polaroid import build_polaroid_scene_clip
from shortform.renderer import assemble_with_transitions, build_scene_clip
from shortform.split_screen import build_split_screen_scene_clip
from shortform.title_card import build_title_card_scene_clip
from shortform.scene_schema import Script
from shortform.tts import get_audio_duration, synthesize_narration

logger = logging.getLogger(__name__)

DEFAULT_RENDER_CONFIG = {
    "subtitle_font": "Malgun Gothic",
    "subtitle_font_size": 44,
}

# Shared between build_ass_from_scenes and assemble_with_transitions so caption
# timing always matches the crossfade-compressed video timeline.
TRANSITION_DURATION_SEC = 0.5


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

    # 편집 감독: 실제로 렌더될 씬만 대상으로 레이아웃/전환 계획을 세운다.
    # (훅 강제·단조 방지 가드레일이 첫 렌더 씬과 실제 시퀀스 기준으로 적용됨)
    renderable_scenes = [
        scene for scene in script.scenes
        if scene.index in audio_paths and scene.index in scene_media
    ]
    plans = resolve_editing_plan(renderable_scenes)
    plans_by_index = {scene.index: plan for scene, plan in zip(renderable_scenes, plans)}

    successful_scenes = []
    clip_paths = []
    durations = []
    transitions = []
    for scene in script.scenes:
        if scene.index not in audio_paths or scene.index not in scene_media:
            continue
        media = scene_media[scene.index]
        duration = durations_by_index[scene.index]
        plan = plans_by_index[scene.index]
        clip_path = work_dir / f"clip_{scene.index:02d}.mp4"
        try:
            if media.media_type == "image":
                if plan.layout == "polaroid":
                    build_polaroid_scene_clip(
                        media.path, audio_paths[scene.index], duration, clip_path,
                        tilt_variant=scene.index,
                    )
                elif plan.layout == "split":
                    build_split_screen_scene_clip(
                        media.path, audio_paths[scene.index], duration, clip_path,
                    )
                elif plan.layout == "titlecard":
                    build_title_card_scene_clip(
                        media.path, audio_paths[scene.index], duration, clip_path,
                        hook_text=scene.narration,
                        highlight_words=scene.highlight_words,
                        chips=scene.chips,
                    )
                else:  # fullscreen
                    build_scene_clip(
                        media.path, "image", audio_paths[scene.index], duration, clip_path,
                        pan_variant=scene.index,
                    )
            else:
                build_scene_clip(
                    media.path, media.media_type, audio_paths[scene.index], duration, clip_path,
                    pan_variant=scene.index,
                )
        except Exception as e:
            logger.warning(f"씬 {scene.index} 클립 생성 실패 ({e}) — 스킵")
            continue
        successful_scenes.append(scene)
        clip_paths.append(clip_path)
        durations.append(duration)
        transitions.append(plan.transition)

    logger.info(f"씬 처리 완료: {len(successful_scenes)}/{len(script.scenes)}개 성공")

    if not clip_paths:
        raise RuntimeError("모든 씬 처리에 실패하여 영상을 생성할 수 없습니다.")

    ass_text = build_ass_from_scenes(successful_scenes, durations, TRANSITION_DURATION_SEC)
    pre_bgm = assemble_with_transitions(
        clip_paths, durations, ass_text, work_dir / "pre_bgm.mp4",
        transition_duration=TRANSITION_DURATION_SEC, transitions=transitions,
    )

    # BGM: bgm/ 폴더의 무드 트랙 우선, 없으면 합성 패드 폴백.
    # 어떤 실패든 BGM 없이 영상은 나온다 (부분 실패 철학).
    try:
        track = select_bgm_track(script.mood)
        if track is None:
            track = synthesize_bgm_pad(
                script.mood, get_audio_duration(pre_bgm), work_dir / "bgm_pad.wav"
            )
            music_volume = PAD_MIX_VOLUME     # 합성 패드는 자체가 조용해 덜 감쇠
        else:
            music_volume = TRACK_MIX_VOLUME   # 실음원은 나레이션 아래로 크게 감쇠
        return mix_bgm(pre_bgm, track, out_path, music_volume=music_volume)
    except Exception as e:
        logger.warning(f"BGM 삽입 실패 ({e}) — BGM 없이 완성합니다")
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pre_bgm, out_path)
        return out_path
