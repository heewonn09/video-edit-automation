import json
import os
import re
import shutil
import subprocess
from pathlib import Path

DEFAULT_CONFIG = {
    "silence_threshold": "-35dB",
    "min_silence_duration": 0.5,
    "silence_padding": 0.1,
    "whisper_model": "medium",
    "output_filename": "output.mp4",
    "subtitle_font": "Malgun Gothic",
    "subtitle_font_size": 24,
}

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def load_config(config_path="config.json"):
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def _fmt_srt_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _segments_to_srt(segments):
    if not segments:
        return ""
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_srt_time(seg['start'])} --> {_fmt_srt_time(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines)


def get_input_files(input_dir="input"):
    files = [
        f for f in Path(input_dir).iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files, key=lambda f: f.name)


def detect_voice_segments(video_path, cfg):
    """ffmpeg silencedetect로 음성 구간 (start, end) 목록 반환."""
    threshold = cfg["silence_threshold"]
    min_dur = cfg["min_silence_duration"]
    padding = cfg["silence_padding"]

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    duration = float(probe.stdout.strip())

    result = subprocess.run(
        [
            "ffmpeg", "-i", str(video_path),
            "-af", f"silencedetect=noise={threshold}:d={min_dur}",
            "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )
    output = result.stderr

    silence_starts = [float(x) for x in re.findall(r"silence_start: (\d+\.?\d*)", output)]
    silence_ends = [float(x) for x in re.findall(r"silence_end: (\d+\.?\d*)", output)]

    silences = [
        (max(0.0, s - padding), min(duration, e + padding))
        for s, e in zip(silence_starts, silence_ends)
    ]

    voice_segments = []
    cursor = 0.0
    for s_start, s_end in silences:
        if s_start > cursor + 0.05:
            voice_segments.append((round(cursor, 3), round(s_start, 3)))
        cursor = s_end
    if duration - cursor > 0.05:
        voice_segments.append((round(cursor, 3), round(duration, 3)))

    return voice_segments


def extract_segments(video_path, segments, out_dir):
    """각 음성 구간을 개별 mp4 클립으로 추출."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(video_path).stem
    clip_paths = []

    for i, (start, end) in enumerate(segments):
        out_path = out_dir / f"{stem}_seg{i:04d}.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-ss", str(start),
                "-to", str(end),
                "-c", "copy",
                str(out_path),
            ],
            capture_output=True,
            check=True,
        )
        clip_paths.append(out_path)

    return clip_paths


def concat_clips(clip_paths, out_path):
    """ffmpeg concat demuxer로 클립들을 하나로 연결."""
    out_path = Path(out_path)
    list_path = out_path.parent / "concat_list.txt"

    with open(list_path, "w", encoding="utf-8") as f:
        for p in clip_paths:
            f.write(f"file '{Path(p).as_posix()}'\n")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            str(out_path),
        ],
        capture_output=True,
        check=True,
    )
    list_path.unlink(missing_ok=True)
    return out_path


def transcribe_audio(video_path, cfg, srt_path):
    """Whisper로 한국어 전사 후 SRT 저장."""
    import whisper

    audio_path = Path(video_path).with_suffix(".wav")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(audio_path),
        ],
        capture_output=True,
        check=True,
    )

    model = whisper.load_model(cfg["whisper_model"])
    result = model.transcribe(str(audio_path), language="ko")
    audio_path.unlink(missing_ok=True)

    srt_content = _segments_to_srt(result["segments"])
    srt_path = Path(srt_path)
    srt_path.write_text(srt_content, encoding="utf-8")
    return srt_path


def burn_subtitles(video_path, srt_path, out_path, cfg):
    """SRT 자막을 영상에 burn-in."""
    font = cfg["subtitle_font"]
    size = cfg["subtitle_font_size"]

    # Windows 경로의 콜론을 ffmpeg subtitles 필터 문법에 맞게 이스케이프
    srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf",
            (
                f"subtitles='{srt_escaped}':force_style='"
                f"FontName={font},FontSize={size},"
                f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=1'"
            ),
            "-c:a", "copy",
            str(out_path),
        ],
        capture_output=True,
        check=True,
    )
    return Path(out_path)
