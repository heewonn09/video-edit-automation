"""타이틀 카드 레이아웃 — 피그마식 UI 컴포넌트로 디자인된 훅 씬.

v4 디자인 시스템 (레퍼런스: 부동산 숏폼의 디자인 오버레이):
- 투톤 헤드라인: 숫자 없는 강조 구절 — 1행 딥 컬러 + 2행 골드, 카드 없이 타이포만
- 스탯 카드: 숫자 든 강조 구절 — 팔레트색 라운드 카드 + 거대 골드 숫자 + 카운트업
- 필 배지: 일반 구절 — 흰 필 + 진회색 텍스트
- 아이콘 칩: 흰 원 + 이모지 아이콘 + 라벨 (LLM이 씬 핵심 포인트로 생성)
- PIP 인셋: 같은 이미지의 다른 크롭을 흰 보더로 사진 경계에 겹침
- 공통: 오프셋 그림자, 시차 팝 등장, 이미지 적응형 팔레트

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

ACCENT_COLOR = "&H004F7D2E&"           # 기본 강조: 딥 그린 (#2E7D4F, BGR)
BASE_COLOR = "&H00303030&"             # 필/라벨 텍스트: 진회색
CARD_TEXT_COLOR = "&H00FFFFFF&"        # 카드 안 텍스트: 흰색
NUM_COLOR = "&H004FD2FF&"              # 숫자·골드 라인: 골드 (#FFD24F, BGR)

HEADLINE_SIZE = 84
HEADLINE_SUB_SIZE = 64
ACCENT_TEXT_SIZE = 64
NUM_FONT_SIZE = 140
PILL_TEXT_SIZE = 46
CHIP_RADIUS = 62
CHIP_ICON_SIZE = 58
CHIP_LABEL_SIZE = 32

LINE_STAGGER_SEC = 0.28                # 블록별 등장 시차
COUNTUP_STEPS = 8
COUNTUP_STEP_SEC = 0.09

# PIP 인셋 (같은 이미지의 다른 크롭)
PIP_W, PIP_H = 352, 264
PIP_BORDER = 10
PIP_X = 660
PIP_Y = MARGIN_HEIGHT - 120            # 여백/사진 경계에 걸침

_NUMBER = re.compile(r"\d[\d,]*")
# '70만 원' 같은 수량 단위가 줄바꿈에서 갈라지지 않도록 NBSP로 묶는다.
_UNIT_GLUE = re.compile(r"(\d[\d,]*[만억천]?)\s+(원|명|개|년|일|시간|분|가지)")

POP = r"\fscx90\fscy90\t(0,180,\fscx100\fscy100)"
FAD = r"\fad(150,0)"


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
Style: ChipIcon,Segoe UI Emoji,{CHIP_ICON_SIZE},{base_color},&H000000FF,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: ChipLabel,Malgun Gothic,{CHIP_LABEL_SIZE},{base_color},&H000000FF,&H00FFFFFF,&H00FFFFFF,1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

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

        ar, ag, ab = to_rgb255(hue, 0.62, 0.45)   # 깊은 강조색
        br, bg_, bb = to_rgb255(hue, 0.07, 0.97)  # 옅은 배경 틴트
        return {
            "bg": f"0x{br:02X}{bg_:02X}{bb:02X}",
            "accent_ass": f"&H00{ab:02X}{ag:02X}{ar:02X}&",
            "base_ass": BASE_COLOR,
        }
    except Exception:
        return default


def build_title_card_filter_complex(frame_count: int, bg_color: str = CARD_BG_COLOR) -> str:
    """배경 + 메인 사진(젠틀 줌) + PIP 인셋(같은 이미지 다른 크롭, 흰 보더)."""
    return (
        f"color=c={bg_color}:s=1080x1920:r=30[bg];"
        f"[0:v]split=2[main_src][pip_src];"
        f"[main_src]scale=1080:{PHOTO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop=1080:{PHOTO_HEIGHT},scale=8000:-2,"
        f"zoompan=z='min(zoom+0.0005,1.08)':d={frame_count}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x{PHOTO_HEIGHT}:fps=30,"
        f"format=yuv420p[photo];"
        f"[pip_src]crop=iw*0.55:ih*0.55:iw*0.4:ih*0.4,"
        f"scale={PIP_W}:{PIP_H}:force_original_aspect_ratio=increase,crop={PIP_W}:{PIP_H},"
        f"pad={PIP_W + 2 * PIP_BORDER}:{PIP_H + 2 * PIP_BORDER}:{PIP_BORDER}:{PIP_BORDER}:white[pip];"
        f"[bg][photo]overlay=x=0:y={MARGIN_HEIGHT}[base];"
        f"[base][pip]overlay=x={PIP_X}:y={PIP_Y}:shortest=1,format=yuv420p[v]"
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
        if ch in (" ", " "):
            w += fs * 0.35
        elif ord(ch) < 0x2E80:
            w += fs * 0.56
        else:
            w += fs
    return w


def _wrap(text: str, fs: float, max_w: float) -> list:
    """어절(공백) 경계에서만 최대 2줄로 감는다 — 수량 단위는 NBSP로 묶여 안 갈라진다."""
    text = _UNIT_GLUE.sub("\\1 \\2", text)
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


def _shadow_and_card(path, y, t0, end, fill):
    return [
        f"Dialogue: 0,{t0},{end},HookCard,,0,0,0,,"
        rf"{{\pos(546,{y + 8:.0f})\an5{FAD}{POP}\p1\c&H101010&\1a&H82&\bord0\shad0}}{path}",
        f"Dialogue: 1,{t0},{end},HookCard,,0,0,0,,"
        rf"{{\pos(540,{y:.0f})\an5{FAD}{POP}\p1\c{fill}\bord0\shad0}}{path}",
    ]


def build_hook_ass(hook_text: str, highlight_words, duration: float,
                   palette=None, chips=None) -> str:
    """훅 텍스트 + 아이콘 칩을 피그마식 UI 컴포넌트로 상단 여백에 배치한다."""
    palette = palette or {}
    accent = palette.get("accent_ass", ACCENT_COLOR)
    base_color = palette.get("base_ass", BASE_COLOR)

    phrases = _split_phrases(hook_text)
    words = [w for w in (highlight_words or []) if w]

    def is_accent(phrase: str) -> bool:
        return any(w in phrase for w in words)

    if len(phrases) == 1:
        kinds = ["accent"]
    else:
        kinds = ["accent" if is_accent(p) else "pill" for p in phrases]

    # ---- 블록 구성: (종류, 페이로드, 높이) ----
    blocks = []
    for phrase, kind in zip(phrases, kinds):
        if kind == "accent" and not _NUMBER.search(phrase):
            lines = _wrap(phrase, HEADLINE_SIZE, 920)
            h = HEADLINE_SIZE * 1.25 + (HEADLINE_SUB_SIZE * 1.25 if len(lines) > 1 else 0)
            blocks.append(("headline", lines, h))
        elif kind == "accent":
            lines = _wrap(phrase, ACCENT_TEXT_SIZE, 760)
            metrics = [_accent_line_metrics(l) for l in lines]
            card_w = min(1000, max(w for w, _ in metrics) + 112)
            card_h = sum(h for _, h in metrics) + 80
            blocks.append(("card", (phrase, lines, card_w, card_h), card_h))
        else:
            lines = _wrap(phrase, PILL_TEXT_SIZE, 800)
            pill_w = min(980, max(_est_w(l, PILL_TEXT_SIZE) for l in lines) + 96)
            pill_h = len(lines) * PILL_TEXT_SIZE * 1.35 + 52
            blocks.append(("pill", (lines, pill_w, pill_h), pill_h))
    if chips:
        blocks.append(("chips", list(chips)[:4], CHIP_RADIUS * 2 + 74))

    gap = 44
    total = sum(h for *_x, h in blocks) + gap * (len(blocks) - 1)
    cursor = max(30.0, (MARGIN_HEIGHT - total) / 2)
    end = _fmt_ass_time(duration)

    out = [_ass_header(base_color)]
    for i, (kind, payload, block_h) in enumerate(blocks):
        y = cursor + block_h / 2
        cursor += block_h + gap
        t_start = i * LINE_STAGGER_SEC
        t0 = _fmt_ass_time(t_start)

        if kind == "headline":
            lines = payload
            styled = rf"{{\fs{HEADLINE_SIZE}\c{accent}\b1}}{lines[0]}"
            if len(lines) > 1:
                styled += rf"\N{{\fs{HEADLINE_SUB_SIZE}\c{NUM_COLOR}\b1}}{lines[1]}"
            out.append(
                f"Dialogue: 2,{t0},{end},HookAccent,,0,0,0,,"
                rf"{{\pos(540,{y:.0f})\an5\q2{FAD}{POP}\bord0\shad0}}{styled}"
            )

        elif kind == "card":
            phrase, lines, card_w, card_h = payload
            path = _rounded_rect(card_w, card_h, 28)
            out.extend(_shadow_and_card(path, y, t0, end, accent))
            m = _NUMBER.search(phrase)
            if m:
                target = int(m.group().replace(",", ""))
                use_comma = "," in m.group()
                start_val = 0 if target <= 100 else int(target * 0.6)

                def render(val):
                    s = f"{val:,}" if use_comma else str(val)
                    swapped = phrase[:m.start()] + s + phrase[m.end():]
                    relines = _wrap(swapped, ACCENT_TEXT_SIZE, 760) if len(lines) > 1 else [swapped]
                    return r"\N".join(_style_number(l) for l in relines)

                step_tags = rf"{{\pos(540,{y:.0f})\an5\q2}}"
                for k in range(COUNTUP_STEPS):
                    val = round(start_val + (target - start_val) * (k + 1) / COUNTUP_STEPS)
                    s0 = _fmt_ass_time(t_start + k * COUNTUP_STEP_SEC)
                    s1 = _fmt_ass_time(t_start + (k + 1) * COUNTUP_STEP_SEC)
                    tags = rf"{{\pos(540,{y:.0f})\an5\q2{FAD}}}" if k == 0 else step_tags
                    out.append(f"Dialogue: 2,{s0},{s1},HookAccent,,0,0,0,,{tags}{render(val)}")
                t_final = _fmt_ass_time(t_start + COUNTUP_STEPS * COUNTUP_STEP_SEC)
                out.append(
                    f"Dialogue: 2,{t_final},{end},HookAccent,,0,0,0,,{step_tags}{render(target)}"
                )
            else:
                text = r"\N".join(_style_number(l) for l in lines)
                out.append(
                    f"Dialogue: 2,{t0},{end},HookAccent,,0,0,0,,"
                    rf"{{\pos(540,{y:.0f})\an5\q2{FAD}{POP}}}{text}"
                )

        elif kind == "pill":
            lines, pill_w, pill_h = payload
            path = _rounded_rect(pill_w, pill_h, pill_h / 2)
            out.extend(_shadow_and_card(path, y, t0, end, "&H00FFFFFF&"))
            out.append(
                f"Dialogue: 2,{t0},{end},HookBase,,0,0,0,,"
                rf"{{\pos(540,{y:.0f})\an5\q2{FAD}{POP}}}{'\\N'.join(lines)}"
            )

        elif kind == "chips":
            chips_list = payload
            n = len(chips_list)
            spacing = 250
            x0 = 540 - spacing * (n - 1) / 2
            circle = _rounded_rect(CHIP_RADIUS * 2, CHIP_RADIUS * 2, CHIP_RADIUS)
            cy = y - 22
            for j, chip in enumerate(chips_list):
                cx = x0 + j * spacing
                ct = _fmt_ass_time(t_start + j * 0.12)
                icon = str(chip.get("icon", "")) if isinstance(chip, dict) else str(chip)
                label = str(chip.get("label", "")) if isinstance(chip, dict) else ""
                out.append(
                    f"Dialogue: 0,{ct},{end},HookCard,,0,0,0,,"
                    rf"{{\pos({cx + 5:.0f},{cy + 7:.0f})\an5{FAD}{POP}\p1\c&H101010&\1a&H85&\bord0\shad0}}{circle}"
                )
                out.append(
                    f"Dialogue: 1,{ct},{end},HookCard,,0,0,0,,"
                    rf"{{\pos({cx:.0f},{cy:.0f})\an5{FAD}{POP}\p1\c&H00FFFFFF&\bord0\shad0}}{circle}"
                )
                if icon:
                    out.append(
                        f"Dialogue: 2,{ct},{end},ChipIcon,,0,0,0,,"
                        rf"{{\pos({cx:.0f},{cy:.0f})\an5{FAD}{POP}\c{accent}}}{icon}"
                    )
                if label:
                    out.append(
                        f"Dialogue: 2,{ct},{end},ChipLabel,,0,0,0,,"
                        rf"{{\pos({cx:.0f},{cy + CHIP_RADIUS + 34:.0f})\an5{FAD}}}{label}"
                    )
    return "\n".join(out)


def build_title_card_scene_clip(image_path, audio_path, duration, out_path,
                                hook_text, highlight_words=None, chips=None):
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
        build_hook_ass(hook_text, highlight_words, duration, palette=palette, chips=chips),
        encoding="utf-8",
    )

    burn_ass_subtitles(raw_path, ass_path, out_path)
    return out_path
