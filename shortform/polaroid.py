import math
import subprocess
from pathlib import Path

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920
PHOTO_WIDTH = 800
PHOTO_HEIGHT = 1420
BORDER_SIDE = 20
BORDER_TOP = 20
BORDER_BOTTOM = 90
FRAMED_WIDTH = PHOTO_WIDTH + 2 * BORDER_SIDE
FRAMED_HEIGHT = PHOTO_HEIGHT + BORDER_TOP + BORDER_BOTTOM


def build_polaroid_filter_complex(frame_count: int, tilt_deg: float) -> str:
    angle = f"{tilt_deg * math.pi / 180:.6f}"
    return (
        f"[0:v]scale={CANVAS_WIDTH}:{CANVAS_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={CANVAS_WIDTH}:{CANVAS_HEIGHT},split=2[bg_raw][photo_src];"
        f"[bg_raw]gblur=sigma=20,eq=brightness=-0.15[bg];"
        f"[photo_src]scale={PHOTO_WIDTH}:{PHOTO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={PHOTO_WIDTH}:{PHOTO_HEIGHT},scale=8000:-2,"
        f"zoompan=z='min(zoom+0.0005,1.08)':d={frame_count}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={PHOTO_WIDTH}x{PHOTO_HEIGHT}:fps=30,"
        f"format=yuva420p[photo_motion];"
        f"[photo_motion]pad={FRAMED_WIDTH}:{FRAMED_HEIGHT}:{BORDER_SIDE}:{BORDER_TOP}:color=white[framed];"
        f"[framed]split=2[framed_photo][framed_shadow_src];"
        f"[framed_shadow_src]colorchannelmixer=rr=0:gg=0:bb=0:aa=0.45,"
        f"rotate={angle}:c=none:ow=rotw({angle}):oh=roth({angle})[rotated_shadow];"
        f"[framed_photo]rotate={angle}:c=none:ow=rotw({angle}):oh=roth({angle})[rotated_photo];"
        f"[bg][rotated_shadow]overlay=(W-w)/2+12:(H-h)/2+16:format=auto[bg_shadow];"
        f"[bg_shadow][rotated_photo]overlay=(W-w)/2:(H-h)/2:format=auto[v]"
    )


def build_polaroid_scene_clip(image_path, audio_path, duration, out_path, tilt_variant=0):
    image_path = str(image_path)
    audio_path = str(audio_path)
    out_path = Path(out_path)

    frame_count = max(1, int(duration * 30))
    tilt_deg = -6 if tilt_variant % 2 == 0 else 6
    filter_complex = build_polaroid_filter_complex(frame_count, tilt_deg)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
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
