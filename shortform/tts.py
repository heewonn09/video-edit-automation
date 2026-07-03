import asyncio
import subprocess
from pathlib import Path

import edge_tts


def synthesize_narration(text: str, out_path, voice: str = "ko-KR-SunHiNeural"):
    out_path = Path(out_path)

    async def _run():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(out_path))

    asyncio.run(_run())
    return out_path


def get_audio_duration(audio_path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())
