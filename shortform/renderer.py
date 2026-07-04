import subprocess
from pathlib import Path

from process import _fmt_srt_time, _segments_to_srt, burn_subtitles, concat_clips

SCALE_FILTER = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"


def build_scene_clip(media_path, media_type, audio_path, duration, out_path):
    media_path = str(media_path)
    audio_path = str(audio_path)
    out_path = Path(out_path)

    if media_type == "image":
        frame_count = max(1, int(duration * 30))
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", media_path,
            "-i", audio_path,
            "-filter_complex",
            (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,scale=8000:-2,"
                f"zoompan=z='min(zoom+0.0015,1.5)':d={frame_count}:"
                "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,"
                "format=yuv420p[v]"
            ),
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-r", "30", "-pix_fmt", "yuv420p",
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
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out_path


def assemble_with_transitions(scene_clip_paths, durations, ass_text, out_path, transition_duration=0.5):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged_path = out_path.parent / "merged.mp4"

    n = len(scene_clip_paths)
    if n == 1:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(scene_clip_paths[0]),
            "-c", "copy",
            str(merged_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
    else:
        inputs = []
        for p in scene_clip_paths:
            inputs += ["-i", str(p)]

        filter_parts = []
        cursor = durations[0]
        v_label, a_label = "0:v", "0:a"
        for i in range(1, n):
            offset = cursor - transition_duration
            v_out, a_out = f"v{i}", f"a{i}"
            filter_parts.append(
                f"[{v_label}][{i}:v]xfade=transition=fade:duration={transition_duration}:offset={offset}[{v_out}]"
            )
            filter_parts.append(f"[{a_label}][{i}:a]acrossfade=d={transition_duration}[{a_out}]")
            v_label, a_label = v_out, a_out
            cursor += durations[i] - transition_duration
        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{v_label}]", "-map", f"[{a_label}]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(merged_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)

    ass_path = out_path.parent / "captions.ass"
    ass_path.write_text(ass_text, encoding="utf-8")
    return burn_ass_subtitles(merged_path, ass_path, out_path)
