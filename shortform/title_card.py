"""타이틀 카드 레이아웃 — 상단 여백에 디자인된 훅 텍스트, 하단에 사진.

v2: 레퍼런스(부동산 숏폼)의 동적 기법 반영.
- 이미지 적응형 팔레트: 씬 이미지의 주조색에서 배경 틴트·강조색을 유도 (씬마다 다른 무드)
- 줄별 시차 등장: 위에서 아래로 한 줄씩 슬라이드+페이드 인
- 강조 줄 스케일 팝
- 숫자 카운트업: 훅 속 숫자가 목표값까지 올라가는 애니메이션 (예: 156→200)

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

ACCENT_FONT_SIZE = 100
BASE_FONT_SIZE = 54
ACCENT_COLOR = "&H004F7D2E&"           # 기본 강조: 딥 그린 (#2E7D4F, BGR)
BASE_COLOR = "&H00303030&"             # 진회색

LINE_STAGGER_SEC = 0.25                # 줄별 등장 시차
COUNTUP_STEPS = 8
COUNTUP_STEP_SEC = 0.09

_NUMBER = re.compile(r"\d[\d,]*")


def _ass_header(accent_color: str, base_color: str) -> str:
    return f"""[Script Info]
Title: Hook Title Card
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HookAccent,Malgun Gothic,{ACCENT_FONT_SIZE},{accent_color},&H000000FF,&H00FFFFFF,&H00FFFFFF,1,0,0,0,100,100,0,0,1,0,0,5,40,40,0,1
Style: HookBase,Malgun Gothic,{BASE_FONT_SIZE},{base_color},&H000000FF,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,0,0,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def derive_palette(image_path) -> dict:
    """씬 이미지의 주조색(채도 가중 평균 색상)에서 카드 팔레트를 유도한다.

    배경 = 같은 색상의 아주 옅은 틴트, 강조 = 같은 색상의 깊고 진한 톤.
    이미지가 사실상 무채색이거나 읽기 실패 시 기본 팔레트로 폴백.
    """
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
        if total_w < 20.0:  # 거의 무채색 이미지 — 색을 억지로 뽑지 않는다
            return default
        hue = (math.atan2(sum_y, sum_x) / (2 * math.pi)) % 1.0

        def to_rgb255(h, s, v):
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            return round(r * 255), round(g * 255), round(b * 255)

        ar, ag, ab = to_rgb255(hue, 0.68, 0.52)   # 깊은 강조색
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


def _layout_blocks(phrases, styles):
    """구절별 세로 중심 y 좌표. 감김(줄바꿈) 추정 높이를 반영해 여백 안에 고르게 쌓는다."""
    usable_width = 1080 - 80  # 좌우 마진 40px
    gap = 40
    heights = []
    for phrase, style in zip(phrases, styles):
        size = ACCENT_FONT_SIZE if style == "HookAccent" else BASE_FONT_SIZE
        chars_per_line = max(1, usable_width // size)  # 한글 전각 ≈ 폰트 크기
        est_lines = max(1, math.ceil(len(phrase) / chars_per_line))
        heights.append(est_lines * size * 1.25)
    total = sum(heights) + gap * (len(heights) - 1)
    cursor = max(40.0, (MARGIN_HEIGHT - total) / 2)
    centers = []
    for h in heights:
        centers.append(cursor + h / 2)
        cursor += h + gap
    return centers


def _countup_events(phrase, style, y, t_start, duration):
    """구절 속 첫 숫자를 목표값까지 올려 찍는 이벤트들 (레퍼런스의 156→200 기법)."""
    m = _NUMBER.search(phrase)
    target = int(m.group().replace(",", ""))
    use_comma = "," in m.group()
    start_val = 0 if target <= 100 else int(target * 0.6)

    def render(val):
        s = f"{val:,}" if use_comma else str(val)
        return phrase[:m.start()] + s + phrase[m.end():]

    events = []
    for k in range(COUNTUP_STEPS):
        val = round(start_val + (target - start_val) * (k + 1) / COUNTUP_STEPS)
        t0 = t_start + k * COUNTUP_STEP_SEC
        t1 = t_start + (k + 1) * COUNTUP_STEP_SEC
        fad = r"\fad(120,0)" if k == 0 else ""
        text = rf"{{\pos(540,{y:.0f}){fad}}}{render(val)}"
        events.append(f"Dialogue: 0,{_fmt_ass_time(t0)},{_fmt_ass_time(t1)},{style},,0,0,0,,{text}")

    t_final = t_start + COUNTUP_STEPS * COUNTUP_STEP_SEC
    pop = r"\fscx88\fscy88\t(0,160,\fscx100\fscy100)"
    text = rf"{{\pos(540,{y:.0f}){pop}}}{phrase}"
    events.append(
        f"Dialogue: 0,{_fmt_ass_time(t_final)},{_fmt_ass_time(duration)},{style},,0,0,0,,{text}"
    )
    return events


def build_hook_ass(hook_text: str, highlight_words, duration: float, palette=None) -> str:
    """훅 텍스트를 상단 여백에 동적으로 배치하는 ASS 문자열.

    - 구절 단위 줄 나눔, 키워드 든 줄 = 강조(크고 컬러), 나머지 = 작고 차분
    - 줄별 시차 등장(슬라이드+페이드), 강조 줄 스케일 팝
    - 강조 줄에 숫자가 있으면 카운트업 애니메이션
    """
    palette = palette or {}
    accent_color = palette.get("accent_ass", ACCENT_COLOR)
    base_color = palette.get("base_ass", BASE_COLOR)

    phrases = _split_phrases(hook_text)
    words = [w for w in (highlight_words or []) if w]

    def is_accent(phrase: str) -> bool:
        return any(w in phrase for w in words)

    if len(phrases) == 1:
        styles = ["HookAccent"]
    else:
        styles = ["HookAccent" if is_accent(p) else "HookBase" for p in phrases]

    centers = _layout_blocks(phrases, styles)
    end = _fmt_ass_time(duration)

    lines = [_ass_header(accent_color, base_color)]
    for i, (phrase, style, y) in enumerate(zip(phrases, styles, centers)):
        t_start = i * LINE_STAGGER_SEC

        if style == "HookAccent" and _NUMBER.search(phrase):
            lines.extend(_countup_events(phrase, style, y, t_start, duration))
            continue

        move = rf"\move(540,{y + 36:.0f},540,{y:.0f},0,220)"
        pop = r"\fscx84\fscy84\t(0,200,\fscx100\fscy100)" if style == "HookAccent" else ""
        text = rf"{{{move}\fad(220,0){pop}}}{phrase}"
        lines.append(
            f"Dialogue: 0,{_fmt_ass_time(t_start)},{end},{style},,0,0,0,,{text}"
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
