"""BGM 자동 삽입 — 무드 맞춤 트랙 선택 + 합성 폴백 + 나레이션 아래 저볼륨 믹스.

소스 정책 (사용자 확정): 로컬 `bgm/` 폴더의 음원을 우선 사용하고(파일명이
`{mood}_*`인 것을 매칭, 저작권은 사용자가 넣는 무료 음원으로 관리),
폴더가 비어 있으면 ffmpeg lavfi로 무드별 앰비언트 패드를 합성해 항상 동작한다.
"""

import subprocess
from pathlib import Path

from shortform.tts import get_audio_duration

MOODS = {"bright", "calm", "exciting", "emotional"}
DEFAULT_MOOD = "calm"

AUDIO_EXTS = (".mp3", ".wav", ".m4a")

# 무드별 코드 구성음(Hz)과 트레몰로 속도 — 합성 패드의 성격을 가른다.
MOOD_CHORDS = {
    "bright": ((523.25, 659.25, 783.99), 0.30),     # C5 E5 G5 — 밝은 메이저
    "calm": ((261.63, 392.00), 0.15),               # C4 G4 — 넓은 5도, 느리게
    "exciting": ((220.00, 261.63, 329.63), 0.60),   # A3 C4 E4 — 마이너, 빠른 맥동
    "emotional": ((196.00, 233.08, 293.66), 0.20),  # G3 Bb3 D4 — 따뜻한 마이너
}


def select_bgm_track(mood, bgm_dir="bgm"):
    """`{bgm_dir}/{mood}_*` 음원을 정렬 후 첫 파일로 결정적 선택.

    무드 매칭이 없으면 폴더 내 아무 음원, 그것도 없으면 None.
    """
    bgm_dir = Path(bgm_dir)
    if not bgm_dir.is_dir():
        return None
    for pattern_prefix in (f"{mood}_", ""):
        matches = sorted(
            p for p in bgm_dir.iterdir()
            if p.suffix.lower() in AUDIO_EXTS and p.name.startswith(pattern_prefix)
        )
        if matches:
            return matches[0]
    return None


def synthesize_bgm_pad(mood, duration, out_path):
    """무드별 코드 사인파를 겹친 앰비언트 패드를 합성한다 (폴백용)."""
    out_path = Path(out_path)
    freqs, trem_speed = MOOD_CHORDS.get(mood, MOOD_CHORDS[DEFAULT_MOOD])

    cmd = ["ffmpeg", "-y"]
    for f in freqs:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={f}:duration={duration}"]
    filter_complex = (
        f"amix=inputs={len(freqs)}:duration=first,"
        f"lowpass=f=1400,"
        f"tremolo=f={trem_speed}:d=0.3,"
        f"volume=0.5[a]"
    )
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[a]",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out_path


def mix_bgm(video_path, bgm_path, out_path, music_volume=0.15):
    """완성 영상의 오디오 아래에 BGM을 저볼륨으로 깐다.

    BGM은 무한 루프(-stream_loop -1)로 영상 길이를 채우고, 1초 페이드인 +
    끝 2초 페이드아웃. 비디오 스트림은 재인코딩하지 않는다(-c:v copy).
    """
    out_path = Path(out_path)
    duration = get_audio_duration(video_path)
    fade_out_start = max(duration - 2, 0)

    filter_complex = (
        f"[1:a]volume={music_volume},"
        f"afade=t=in:d=1,"
        f"afade=t=out:st={fade_out_start}:d=2[m];"
        f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-stream_loop", "-1", "-i", str(bgm_path),
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out_path
