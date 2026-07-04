ASS_HEADER = """[Script Info]
Title: Shortform Captions
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Malgun Gothic,72,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,4,0,2,60,60,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

HIGHLIGHT_OVERRIDE = r"{\1c&H00D7FF&\3c&H00D7FF&\bord14\shad0}"
RESET_OVERRIDE = r"{\r}"


def _fmt_ass_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _highlight_line(narration: str, highlight_words) -> str:
    text = narration
    for word in highlight_words or []:
        if word and word in text:
            text = text.replace(word, f"{HIGHLIGHT_OVERRIDE}{word}{RESET_OVERRIDE}", 1)
    return text


def build_ass_from_scenes(scenes, durations) -> str:
    lines = [ASS_HEADER]
    cursor = 0.0
    for scene, duration in zip(scenes, durations):
        start = _fmt_ass_time(cursor)
        end = _fmt_ass_time(cursor + duration)
        text = _highlight_line(scene.narration, scene.highlight_words)
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
        cursor += duration
    return "\n".join(lines)
