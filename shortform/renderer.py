import subprocess
from pathlib import Path

from process import _fmt_srt_time, _segments_to_srt, burn_subtitles, concat_clips
from shortform.sound_effects import generate_whoosh_sound

SCALE_FILTER = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"

# 이 길이 이상의 fullscreen 이미지 씬은 중간 하드 컷으로 템포를 만든다.
CUT_RHYTHM_THRESHOLD_SEC = 5.0


def _pan_exprs(variant, denom):
    """켄번즈 팬 4종의 zoompan 수식 (z, x). y는 공통."""
    variant = variant % 4
    if variant == 1:
        return "1.15", f"(iw-iw/zoom)*on/{denom}"
    if variant == 2:
        return "1.15", f"(iw-iw/zoom)*(1-on/{denom})"
    if variant == 3:
        return "max(1.5-0.0015*on,1.15)", "iw/2-(iw/zoom/2)"
    return "min(zoom+0.0015,1.5)", "iw/2-(iw/zoom/2)"


def build_scene_clip(media_path, media_type, audio_path, duration, out_path, pan_variant=0):
    media_path = str(media_path)
    audio_path = str(audio_path)
    out_path = Path(out_path)

    if media_type == "image":
        frame_count = max(1, int(duration * 30))
        denom = max(frame_count - 1, 1)
        z_expr, x_expr = _pan_exprs(pan_variant, denom)
        y_expr = "ih/2-(ih/zoom/2)"

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", media_path,
            "-i", audio_path,
            "-filter_complex",
            (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,scale=8000:-2,"
                f"zoompan=z='{z_expr}':d={frame_count}:"
                f"x='{x_expr}':y='{y_expr}':s=1080x1920:fps=30,"
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


def build_rhythm_cut_clip(media_path, audio_path, duration, out_path, pan_variant=0):
    """긴 이미지 씬을 중간 하드 컷으로 나눠 서로 다른 카메라 모션 두 개를 잇는다.

    같은 이미지의 점프컷 템포감 — 전반부는 pan_variant, 후반부는 반대 계열
    모션((pan_variant+2)%4)으로 렌더 후 concat. 나레이션 오디오는 끊김 없이 이어진다.
    """
    media_path = str(media_path)
    audio_path = str(audio_path)
    out_path = Path(out_path)

    half_frames = max(1, int(duration * 30 / 2))
    denom = max(half_frames - 1, 1)
    z_a, x_a = _pan_exprs(pan_variant, denom)
    z_b, x_b = _pan_exprs(pan_variant + 2, denom)
    y_expr = "ih/2-(ih/zoom/2)"

    def branch(label_in, label_out, z, x):
        return (
            f"[{label_in}]zoompan=z='{z}':d={half_frames}:"
            f"x='{x}':y='{y_expr}':s=1080x1920:fps=30,"
            f"trim=end_frame={half_frames},setpts=PTS-STARTPTS,format=yuv420p[{label_out}]"
        )

    filter_complex = (
        f"[0:v]{SCALE_FILTER},scale=8000:-2,split=2[src_a][src_b];"
        f"{branch('src_a', 'va', z_a, x_a)};"
        f"{branch('src_b', 'vb', z_b, x_b)};"
        f"[va][vb]concat=n=2:v=1:a=0[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", media_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-r", "30", "-pix_fmt", "yuv420p",
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


def assemble_with_transitions(scene_clip_paths, durations, ass_text, out_path,
                              transition_duration=0.5, transitions=None):
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
        offsets = []
        cursor = durations[0]
        v_label, a_label = "0:v", "0:a"
        default_types = ["fade", "slideleft", "wipeup", "circleopen"]
        # Per-scene transitions[i] = xfade INTO scene i (index 0 unused). Fall back to
        # the default cycle if not supplied or too short to cover every scene.
        use_per_scene = transitions is not None and len(transitions) >= n
        for i in range(1, n):
            offset = cursor - transition_duration
            offsets.append(offset)
            v_out, a_out = f"v{i}", f"a{i}"
            if use_per_scene:
                transition = transitions[i]
            else:
                transition = default_types[(i - 1) % len(default_types)]
            filter_parts.append(
                f"[{v_label}][{i}:v]xfade=transition={transition}:duration={transition_duration}:offset={offset}[{v_out}]"
            )
            filter_parts.append(f"[{a_label}][{i}:a]acrossfade=d={transition_duration}[{a_out}]")
            v_label, a_label = v_out, a_out
            cursor += durations[i] - transition_duration

        whoosh_path = out_path.parent / "whoosh.wav"
        generate_whoosh_sound(whoosh_path, duration=transition_duration)

        whoosh_labels = []
        for idx, offset in enumerate(offsets):
            delay_ms = int(offset * 1000)
            src_index = n + idx
            inputs += ["-i", str(whoosh_path)]
            label = f"wh{idx}"
            filter_parts.append(f"[{src_index}:a]adelay={delay_ms}|{delay_ms},volume=0.4[{label}]")
            whoosh_labels.append(f"[{label}]")

        mix_inputs = f"[{a_label}]" + "".join(whoosh_labels)
        filter_parts.append(
            f"{mix_inputs}amix=inputs={len(whoosh_labels) + 1}:duration=first:dropout_transition=0[aout]"
        )
        a_label = "aout"

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
