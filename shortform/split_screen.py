import subprocess
from pathlib import Path

PANEL_WIDTH = 1080
PANEL_HEIGHT = 960


def build_split_screen_filter_complex(frame_count: int) -> str:
    denom = max(frame_count - 1, 1)
    return (
        f"[0:v]split=2[top_src][bottom_src];"
        f"[top_src]scale={PANEL_WIDTH}:{PANEL_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={PANEL_WIDTH}:{PANEL_HEIGHT},scale=8000:-2,"
        f"zoompan=z='1.12':d={frame_count}:"
        f"x='(iw-iw/zoom)*on/{denom}':y='ih/2-(ih/zoom/2)':s={PANEL_WIDTH}x{PANEL_HEIGHT}:fps=30,"
        f"format=yuv420p[top];"
        f"[bottom_src]scale={PANEL_WIDTH}:{PANEL_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={PANEL_WIDTH}:{PANEL_HEIGHT},scale=8000:-2,"
        f"zoompan=z='min(zoom+0.0006,1.15)':d={frame_count}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={PANEL_WIDTH}x{PANEL_HEIGHT}:fps=30,"
        f"format=yuv420p[bottom];"
        f"[top][bottom]vstack=inputs=2[v]"
    )


def build_split_screen_scene_clip(image_path, audio_path, duration, out_path):
    image_path = str(image_path)
    audio_path = str(audio_path)
    out_path = Path(out_path)

    frame_count = max(1, int(duration * 30))
    filter_complex = build_split_screen_filter_complex(frame_count)

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
