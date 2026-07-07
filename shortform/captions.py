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
Style: Box,Malgun Gothic,64,&H00FFFFFF,&H00AAAAAA,&H60101010,&H60101010,1,0,0,0,100,100,0,0,3,10,0,2,60,60,140,1

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


def _proportional_events(scene, cursor, scene_end):
    """기존 동작: 구절을 글자 수 비례로 배분 (단어 타이밍이 없을 때의 폴백)."""
    events = []
    phrases = _split_phrases(scene.narration)
    windows = _phrase_windows(phrases, cursor, scene_end)
    for phrase, (p_start, p_end) in zip(phrases, windows):
        start = _fmt_ass_time(p_start)
        end = _fmt_ass_time(p_end)
        text = _highlight_line(phrase, scene.highlight_words)
        events.append(f"Dialogue: 0,{start},{end},Box,,0,0,0,,{FADE_IN}{text}")
    return events


def _karaoke_events(scene, words, cursor, scene_end):
    """어절별 발화 타이밍(\\kf 스윕) 카라오케. 어절 수가 안 맞으면 None → 폴백."""
    phrases = _split_phrases(scene.narration)
    counts = [len(p.split()) for p in phrases]
    if sum(counts) != len(words):
        return None

    events = []
    wi = 0
    for pi, (phrase, count) in enumerate(zip(phrases, counts)):
        pw = words[wi:wi + count]
        wi += count
        p_start = cursor + pw[0]["start"]
        # 구절 박스는 다음 구절의 발화 시작까지 유지 (자막 공백 방지)
        if pi < len(phrases) - 1:
            p_end = cursor + words[wi]["start"]
        else:
            p_end = scene_end
        p_end = max(p_end, cursor + pw[-1]["end"])

        parts = []
        prev = pw[0]["start"]
        for token, w in zip(phrase.split(), pw):
            k_cs = max(1, round((w["end"] - prev) * 100))
            prev = w["end"]
            if any(hw and hw in token for hw in (scene.highlight_words or [])):
                token = rf"{{\1c&H00D7FF&}}{token}{{\1c&HFFFFFF&}}"
            parts.append(rf"{{\kf{k_cs}}}{token}")
        text = " ".join(parts)
        events.append(
            f"Dialogue: 0,{_fmt_ass_time(p_start)},{_fmt_ass_time(p_end)},Box,,0,0,0,,{FADE_IN}{text}"
        )
    return events


def build_ass_from_scenes(scenes, durations, transition_duration=0.5, word_timings=None) -> str:
    lines = [ASS_HEADER]
    n = len(durations)
    cursor = 0.0
    word_timings = word_timings or {}
    for i, (scene, duration) in enumerate(zip(scenes, durations)):
        scene_end = cursor + duration
        if i < n - 1:
            scene_end -= transition_duration

        words = word_timings.get(scene.index)
        events = _karaoke_events(scene, words, cursor, scene_end) if words else None
        if events is None:
            events = _proportional_events(scene, cursor, scene_end)
        lines.extend(events)

        cursor = scene_end
    return "\n".join(lines)
