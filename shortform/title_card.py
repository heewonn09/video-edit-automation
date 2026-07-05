"""타이틀 카드 레이아웃 — 상단 여백에 배지/카드 디자인 훅, 하단에 사진.

v3: 레퍼런스(부동산 숏폼)의 카드 디자인 반영.
- 강조 구절 = 팔레트색 라운드 카드 + 흰 텍스트, 숫자만 거대 골드 (예: 분양가 [200] 만 원대)
- 일반 구절 = 흰색 필(pill) 배지 + 진회색 텍스트
- 카드 뒤 오프셋 그림자, 카드 팝 등장(스케일), 구절별 시차 등장
- 숫자 카운트업: 카드/그림자는 한 번만 그리고 숫자 텍스트만 갈아끼움 (156→200 기법)
- 이미지 적응형 팔레트: 씬 이미지 주조색 → 배경 틴트·카드색

폴라로이드/스플릿과 같은 2계층: 순수 문자열 빌더(필터·ASS) + ffmpeg 실행 래퍼.
"""

import colorsys
import math
import re
import subprocess
from pathlib import Path

from shortform.captions import _split_phrases
from shortform.renderer import burn_ass_subtitles

CARD_BG_COLOR = "0xF5F2EC"            # 기본 배경: 밝은 웜 화이트 (팔레트 유도 실패 시)
PHOTO_HEIGHT = 1056                    # 하단 사진 영역 (~55%)
MARGIN_HEIGHT = 1920 - PHOTO_HEIGHT    # 상단 여백 864px (~45%)

ACCENT_COLOR = "&H004F7D2E&"           # 기본 카드색: 딥 그린 (#2E7D4F, BGR)
BASE_COLOR = "&H00303030&"             # 필 배지 텍스트: 진회색
CARD_TEXT_COLOR = "&H00FFFFFF&"        # 카드 안 텍스트: 흰색
NUM_COLOR = "&H004FD2FF&"              # 숫자: 골드 (#FFD24F, BGR)

ACCENT_TEXT_SIZE = 64
NUM_FONT_SIZE = 140
PILL_TEXT_SIZE = 46

LINE_STAGGER_SEC = 0.28                # 구절별 등장 시차
COUNTUP_STEPS = 8
COUNTUP_STEP_SEC = 0.09

_NUMBER = re.compile(r"\d[\d,]*")


def _ass_header(base_color: str) -> str:
    return f"""[Script Info]
Title: Hook Title Card
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HookAccent,Malgun Gothic,{ACCENT_TEXT_SIZE},{CARD_TEXT_COLOR},&H000000FF,&H00FFFFFF,&H00FFFFFF,1,0,0,0,100,100,0,0,1,0,0,5,40,40,0,1
Style: HookBase,Malgun Gothic,{PILL_TEXT_SIZE},{base_color},&H000000FF,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,0,0,5,40,40,0,1
Style: HookCard,Malgun Gothic,20,&H00FFFFFF&,&H000000FF,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def derive_palette(image_path) -> dict:
    """씬 이미지의 주조색(채도 가중 평균 색상)에서 카드 팔레트를 유도한다."""
    default = {"bg": CARD_BG_COLOR, "accent_ass": ACCENT_COLOR, "base_ass": BASE_COLOR}
    try:
        from PIL import Image

        img = Image.open(image_path).convert("RGB").resize((48, 48))
        sum_x = sum_y = total_w = 0.0
        for r, g, b in img.getdata():
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            w = s * v
            if w <= 0:
                continue
            sum_x += w * math.cos(2 * math.pi * h)
            sum_y += w * math.sin(2 * math.pi * h)
            total_w += w
        if total_w < 20.0:  # 거의 무채색 — 색을 억지로 뽑지 않는다
            return default
        hue = (math.atan2(sum_y, sum_x) / (2 * math.pi)) % 1.0

        def to_rgb255(h, s, v):
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            return round(r * 255), round(g * 255), round(b * 255)

        ar, ag, ab = to_rgb255(hue, 0.62, 0.45)   # 깊은 카드색
        br, bg_, bb = to_rgb255(hue, 0.07, 0.97)  # 옅은 배경 틴트
        return {
            "bg": f"0x{br:02X}{bg_:02X}{bb:02X}",
            "accent_ass": f"&H00{ab:02X}{ag:02X}{ar:02X}&",
            "base_ass": BASE_COLOR,
        }
    except Exception:
        return default


def build_title_card_filter_complex(frame_count: int, bg_color: str = CARD_BG_COLOR) -> str:
    return (
        f"color=c={bg_color}:s=1080x1920:r=30[bg];"
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


def _est_w(text: str, fs: float) -> float:
    """대략적 렌더 폭 추정 — 한글 전각 ≈ fs, 라틴/숫자 ≈ 0.56fs."""
    w = 0.0
    for ch in text:
        if ch == " ":
            w += fs * 0.35
        elif ord(ch) < 0x2E80:
            w += fs * 0.56
        else:
            w += fs
    return w

def _wrap(text: str, fs: float, max_w: float) -> list:
    """어절(공백) 경계에서만 최대 2줄로 감는다 — '70만 원' 같은 단위가 갈라지지 않게."""
    if _est_w(text, fs) <= max_w:
        return [text]
    words = text.split(" ")
    best = None
    for i in range(1, len(words)):
        l1, l2 = " ".join(words[:i]), " ".join(words[i:])
        widest = max(_est_w(l1, fs), _est_w(l2, fs))
        if best is None or widest < best[0]:
            best = (widest, [l1, l2])
    return best[1] if best else [text]


def _accent_line_metrics(line: str):
    """숫자가 든 줄은 숫자만 큰 폰트로 치므로 폭/높이를 구간별로 계산."""
    m = _NUMBER.search(line)
    if not m:
        return _est_w(line, ACCENT_TEXT_SIZE), ACCENT_TEXT_SIZE * 1.3
    w = (_est_w(line[:m.start()], ACCENT_TEXT_SIZE)
         + _est_w(m.group(), NUM_FONT_SIZE)
         + _est_w(line[m.end():], ACCENT_TEXT_SIZE))
    return w, NUM_FONT_SIZE * 1.15


def _rounded_rect(w: float, h: float, r: float) -> str:
    w, h = int(w), int(h)
    r = int(min(r, w / 2, h / 2))
    return (
        f"m {r} 0 l {w - r} 0 b {w} 0 {w} 0 {w} {r} "
        f"l {w} {h - r} b {w} {h} {w} {h} {w - r} {h} "
        f"l {r} {h} b 0 {h} 0 {h} 0 {h - r} "
        f"l 0 {r} b 0 0 0 0 {r} 0"
    )


def _style_number(text: str) -> str:
    """줄 속 첫 숫자를 거대 골드로 — 레퍼런스의 '평당 [200] 만 원대' 타이포 믹스."""
    m = _NUMBER.search(text)
    if not m:
        return text
    return (
        text[:m.start()]
        + rf"{{\fs{NUM_FONT_SIZE}\c{NUM_COLOR}\b1}}{m.group()}"
        + rf"{{\fs{ACCENT_TEXT_SIZE}\c{CARD_TEXT_COLOR}}}"
        + text[m.end():]
    )


POP = r"\fscx90\fscy90\t(0,180,\fscx100\fscy100)"
FAD = r"\fad(150,0)"


def _card_events(kind, phrase, fill, y, t_start, duration, palette_base):
    """한 구절의 그림자/카드/텍스트 이벤트 묶음. kind: 'accent' | 'pill'."""
    if kind == "accent":
        lines = _wrap(phrase, ACCENT_TEXT_SIZE, 760)
        metrics = [_accent_line_metrics(l) for l in lines]
        text_w = max(w for w, _ in metrics)
        text_h = sum(h for _, h in metrics)
        pad_x, pad_y, radius = 56, 40, 28
        text = r"\N".join(_style_number(l) for l in lines)
        style = "HookAccent"
    else:
        lines = _wrap(phrase, PILL_TEXT_SIZE, 800)
        text_w = max(_est_w(l, PILL_TEXT_SIZE) for l in lines)
        text_h = len(lines) * PILL_TEXT_SIZE * 1.35
        pad_x, pad_y = 48, 26
        radius = (text_h + 2 * pad_y) / 2
        text = r"\N".join(lines)
        style = "HookBase"

    card_w = min(1000, text_w + 2 * pad_x)
    card_h = text_h + 2 * pad_y
    path = _rounded_rect(card_w, card_h, radius)

    t0 = _fmt_ass_time(t_start)
    end = _fmt_ass_time(duration)
    events = [
        # 그림자 (오프셋 + 반투명 블랙)
        f"Dialogue: 0,{t0},{end},HookCard,,0,0,0,,"
        rf"{{\pos(546,{y + 8:.0f})\an5{FAD}{POP}\p1\c&H101010&\1a&H82&\bord0\shad0}}{path}",
        # 카드
        f"Dialogue: 1,{t0},{end},HookCard,,0,0,0,,"
        rf"{{\pos(540,{y:.0f})\an5{FAD}{POP}\p1\c{fill}\bord0\shad0}}{path}",
    ]
    text_tags = rf"{{\pos(540,{y:.0f})\an5\q2{FAD}{POP}}}"
    return events, text, style, text_tags, card_h


def build_hook_ass(hook_text: str, highlight_words, duration: float, palette=None) -> str:
    """훅 텍스트를 배지/카드 디자인으로 상단 여백에 배치하는 ASS 문자열."""
    palette = palette or {}
    accent_fill = palette.get("accent_ass", ACCENT_COLOR)
    base_color = palette.get("base_ass", BASE_COLOR)

    phrases = _split_phrases(hook_text)
    words = [w for w in (highlight_words or []) if w]

    def is_accent(phrase: str) -> bool:
        return any(w in phrase for w in words)

    if len(phrases) == 1:
        kinds = ["accent"]
    else:
        kinds = ["accent" if is_accent(p) else "pill" for p in phrases]

    # 1차: 카드 높이를 계산해 세로 배치를 정한다.
    built = []
    for i, (phrase, kind) in enumerate(zip(phrases, kinds)):
        fill = accent_fill if kind == "accent" else "&H00FFFFFF&"
        built.append(_card_events(kind, phrase, fill, 0, i * LINE_STAGGER_SEC, duration, base_color))
    gap = 44
    total = sum(card_h for *_rest, card_h in built) + gap * (len(built) - 1)
    cursor = max(30.0, (MARGIN_HEIGHT - total) / 2)

    lines = [_ass_header(base_color)]
    for i, (phrase, kind) in enumerate(zip(phrases, kinds)):
        card_h = built[i][4]
        y = cursor + card_h / 2
        cursor += card_h + gap
        t_start = i * LINE_STAGGER_SEC
        fill = accent_fill if kind == "accent" else "&H00FFFFFF&"

        events, text, style, text_tags, _h = _card_events(
            kind, phrase, fill, y, t_start, duration, base_color
        )
        lines.extend(events)

        m = _NUMBER.search(phrase) if kind == "accent" else None
        if m:
            # 카운트업: 카드는 위에서 한 번만 그렸고, 숫자 텍스트만 갈아끼운다.
            target = int(m.group().replace(",", ""))
            use_comma = "," in m.group()
            start_val = 0 if target <= 100 else int(target * 0.6)
            wrapped = _wrap(phrase, ACCENT_TEXT_SIZE, 760)

            def render(val):
                s = f"{val:,}" if use_comma else str(val)
                swapped = phrase[:m.start()] + s + phrase[m.end():]
                relines = _wrap(swapped, ACCENT_TEXT_SIZE, 760) if len(wrapped) > 1 else [swapped]
                return r"\N".join(_style_number(l) for l in relines)

            step_tags = rf"{{\pos(540,{y:.0f})\an5\q2}}"
            for k in range(COUNTUP_STEPS):
                val = round(start_val + (target - start_val) * (k + 1) / COUNTUP_STEPS)
                s0 = t_start + k * COUNTUP_STEP_SEC
                s1 = t_start + (k + 1) * COUNTUP_STEP_SEC
                fad = FAD if k == 0 else ""
                tags = rf"{{\pos(540,{y:.0f})\an5\q2{fad}}}" if fad else step_tags
                lines.append(
                    f"Dialogue: 2,{_fmt_ass_time(s0)},{_fmt_ass_time(s1)},{style},,0,0,0,,{tags}{render(val)}"
                )
            t_final = t_start + COUNTUP_STEPS * COUNTUP_STEP_SEC
            lines.append(
                f"Dialogue: 2,{_fmt_ass_time(t_final)},{_fmt_ass_time(duration)},{style},,0,0,0,,{step_tags}{render(target)}"
            )
        else:
            lines.append(
                f"Dialogue: 2,{_fmt_ass_time(t_start)},{_fmt_ass_time(duration)},{style},,0,0,0,,{text_tags}{text}"
            )
    return "\n".join(lines)


def build_title_card_scene_clip(image_path, audio_path, duration, out_path,
                                hook_text, highlight_words=None):
    image_path = str(image_path)
    audio_path = str(audio_path)
    out_path = Path(out_path)

    palette = derive_palette(image_path)
    frame_count = max(1, int(duration * 30))
    filter_complex = build_title_card_filter_complex(frame_count, bg_color=palette["bg"])

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
    ass_path.write_text(
        build_hook_ass(hook_text, highlight_words, duration, palette=palette),
        encoding="utf-8",
    )

    burn_ass_subtitles(raw_path, ass_path, out_path)
    return out_path
