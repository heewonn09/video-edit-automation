import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

_HNS = 10_000_000  # WordBoundary offset/duration 단위: 100ns


def synthesize_narration(text: str, out_path, voice: str = "ko-KR-SunHiNeural"):
    """나레이션 합성 + 어절별 발화 타이밍 사이드카(.words.json) 기록.

    edge-tts 7.x는 boundary='WordBoundary'를 줘야 WordBoundary 이벤트를 보낸다.
    사이드카는 카라오케 자막용 부가물 — 없어도 자막은 구절 비례 배분으로 폴백한다.
    """
    out_path = Path(out_path)

    async def _run():
        communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary")
        words = []
        with open(out_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start = chunk["offset"] / _HNS
                    words.append({
                        "text": chunk["text"],
                        "start": round(start, 4),
                        "end": round(start + chunk["duration"] / _HNS, 4),
                    })
        if words:
            out_path.with_suffix(".words.json").write_text(
                json.dumps(words, ensure_ascii=False), encoding="utf-8"
            )

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
