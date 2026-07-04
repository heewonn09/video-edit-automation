import subprocess
from pathlib import Path


def generate_whoosh_sound(out_path, duration=0.4):
    out_path = Path(out_path)
    fade_out_start = max(duration - 0.15, 0)
    audio_filter = (
        "highpass=f=500,lowpass=f=6000,"
        "afade=t=in:d=0.05,"
        f"afade=t=out:st={fade_out_start:.3f}:d=0.15"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anoisesrc=d={duration}:c=pink:r=44100",
        "-af", audio_filter,
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out_path
