"""타이틀 카드 레이아웃 — 상단 여백에 디자인된 훅 텍스트, 하단에 사진.

레퍼런스 구도: 밝은 단색 여백(상단 ~45%)에 크기·색이 다른 여러 줄 텍스트,
하단(~55%)에 가벼운 켄번즈가 적용된 사진, 맨 아래 기존 나레이션 자막 공존.

폴라로이드/스플릿과 같은 2계층: 순수 문자열 빌더(필터·ASS) + ffmpeg 실행 래퍼.
"""

import subprocess
from pathlib import Path

from shortform.captions import _split_phrases
from shortform.renderer import burn_ass_subtitles

CARD_BG_COLOR = "0xF5F2EC"            # 밝은 웜 화이트
PHOTO_HEIGHT = 1056                    # 하단 사진 영역 (~55%)
MARGIN_HEIGHT = 1920 - PHOTO_HEIGHT    # 상단 여백 864px (~45%)

ACCENT_FONT_SIZE = 100
BASE_FONT_SIZE = 54
ACCENT_COLOR = "&H004F7D2E&"           # 딥 그린 (#2E7D4F, BGR)
BASE_COLOR = "&H00303030&"             # 진회색

HOOK_ASS_HEADER = f"""[Script Info]
Title: Hook Title Card
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HookAccent,Malgun Gothic,{ACCENT_FONT_SIZE},{ACCENT_COLOR},&H000000FF,&H00FFFFFF,&H00FFFFFF,1,0,0,0,100,100,0,0,1,0,0,5,40,40,0,1
Style: HookBase,Malgun Gothic,{BASE_FONT_SIZE},{BASE_COLOR},&H000000FF,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,0,0,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_title_card_filter_complex(frame_count: int) -> str:
    return (
        f"color=c={CARD_BG_COLOR}:s=1080x1920:r=30[bg];"
        f"[0:v]scale=1080:{PHOTO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop=1080:{PHOTO_HEIGHT},scale=8000:-2,"
        f"zoompan=z='min(zoom+0.0005,1.08)':d={frame_count}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x{PHOTO_HEIGHT}:fps=30,"
        f"format=yuv420p[photo];"
        f"[bg][photo]overlay=x=0:y={MARGIN_HEIGHT}:shortest=1,format=yuv420p[v]"
    )


def _fmt_ass_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def build_hook_ass(hook_text: str, highlight_words, duration: float) -> str:
    """훅 텍스트를 상단 여백에 디자인 배치하는 ASS 문자열.

    구절 단위로 줄을 나누고, 핵심 키워드(highlight_words)가 든 줄은
    크고 진한 강조 스타일, 나머지는 작고 차분한 스타일로 세로 배치한다.
    구두점이 없어 한 줄이면 그 줄 자체가 훅이므로 강조 스타일을 쓴다.
    """
    phrases = _split_phrases(hook_text)
    words = [w for w in (highlight_words or []) if w]

    def is_accent(phrase: str) -> bool:
        return any(w in phrase for w in words)

    if len(phrases) == 1:
        styles = ["HookAccent"]
    else:
        styles = ["HookAccent" if is_accent(p) else "HookBase" for p in phrases]

    end = _fmt_ass_time(duration)
    lines = [HOOK_ASS_HEADER]
    n = len(phrases)
    for i, (phrase, style) in enumerate(zip(phrases, styles)):
        y = MARGIN_HEIGHT * (i + 1) / (n + 1)
        text = rf"{{\pos(540,{y:.0f})\fad(300,0)}}{phrase}"
        lines.append(f"Dialogue: 0,0:00:00.00,{end},{style},,0,0,0,,{text}")
    return "\n".join(lines)


def build_title_card_scene_clip(image_path, audio_path, duration, out_path,
                                hook_text, highlight_words=None):
    image_path = str(image_path)
    audio_path = str(audio_path)
    out_path = Path(out_path)

    frame_count = max(1, int(duration * 30))
    filter_complex = build_title_card_filter_complex(frame_count)

    raw_path = out_path.with_suffix(".raw.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-r", "30", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration),
        str(raw_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    ass_path = out_path.with_suffix(".ass")
    ass_path.write_text(build_hook_ass(hook_text, highlight_words, duration), encoding="utf-8")

    burn_ass_subtitles(raw_path, ass_path, out_path)
    return out_path
