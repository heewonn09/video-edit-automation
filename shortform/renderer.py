import subprocess
from pathlib import Path

from process import _fmt_srt_time, _segments_to_srt, burn_subtitles, concat_clips

SCALE_FILTER = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"


def build_scene_clip(media_path, media_type, audio_path, duration, out_path):
    media_path = str(media_path)
    audio_path = str(audio_path)
    out_path = Path(out_path)

    if media_type == "image":
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", media_path,
            "-i", audio_path,
            "-vf", SCALE_FILTER,
            "-r", "30",
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(duration),
            str(out_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", media_path,
            "-i", audio_path,
            "-vf", SCALE_FILTER,
            "-r", "30",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(duration),
            str(out_path),
        ]

    subprocess.run(cmd, capture_output=True, check=True)
    return out_path


def build_srt_from_scenes(scenes, durations) -> str:
    segments = []
    cursor = 0.0
    for scene, duration in zip(scenes, durations):
        segments.append({"start": cursor, "end": cursor + duration, "text": scene.narration})
        cursor += duration
    return _segments_to_srt(segments)


def assemble_final_video(scene_clip_paths, srt_text, out_path, cfg):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    merged_path = out_path.parent / "merged.mp4"
    concat_clips(scene_clip_paths, merged_path)

    srt_path = out_path.parent / "subtitles.srt"
    srt_path.write_text(srt_text, encoding="utf-8")

    return burn_subtitles(merged_path, srt_path, out_path, cfg)


def burn_ass_subtitles(video_path, ass_path, out_path):
    video_path = str(video_path)
    ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
    out_path = Path(out_path)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"ass='{ass_escaped}'",
        "-c:a", "copy",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out_path
