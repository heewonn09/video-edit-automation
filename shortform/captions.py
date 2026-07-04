import re

ASS_HEADER = """[Script Info]
Title: Shortform Captions
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Box,Malgun Gothic,64,&H00FFFFFF,&H000000FF,&H60101010,&H60101010,1,0,0,0,100,100,0,0,3,10,0,2,60,60,140,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

HIGHLIGHT_OVERRIDE = r"{\1c&H00D7FF&}"
RESET_OVERRIDE = r"{\r}"
FADE_IN = r"{\fad(200,0)}"

_PHRASE_BOUNDARY = re.compile(r"(?<=[,.!?])\s+")


def _fmt_ass_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _split_phrases(narration: str) -> list:
    parts = [p for p in _PHRASE_BOUNDARY.split(narration) if p.strip()]
    return parts if parts else [narration]


def _phrase_windows(phrases, start: float, end: float):
    total_chars = sum(len(p) for p in phrases) or 1
    total_duration = end - start
    last = len(phrases) - 1
    windows = []
    cursor = start
    for i, phrase in enumerate(phrases):
        if i == last:
            phrase_end = end
        else:
            phrase_end = cursor + total_duration * (len(phrase) / total_chars)
        windows.append((cursor, phrase_end))
        cursor = phrase_end
    return windows


def _highlight_line(text: str, highlight_words) -> str:
    for word in highlight_words or []:
        if word and word in text:
            text = text.replace(word, f"{HIGHLIGHT_OVERRIDE}{word}{RESET_OVERRIDE}", 1)
    return text


def build_ass_from_scenes(scenes, durations, transition_duration=0.5) -> str:
    lines = [ASS_HEADER]
    n = len(durations)
    cursor = 0.0
    for i, (scene, duration) in enumerate(zip(scenes, durations)):
        scene_end = cursor + duration
        if i < n - 1:
            scene_end -= transition_duration

        phrases = _split_phrases(scene.narration)
        windows = _phrase_windows(phrases, cursor, scene_end)
        for phrase, (p_start, p_end) in zip(phrases, windows):
            start = _fmt_ass_time(p_start)
            end = _fmt_ass_time(p_end)
            text = _highlight_line(phrase, scene.highlight_words)
            lines.append(f"Dialogue: 0,{start},{end},Box,,0,0,0,,{FADE_IN}{text}")

        cursor = scene_end
    return "\n".join(lines)
