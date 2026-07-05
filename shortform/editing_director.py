"""편집 감독 레이어 — LLM이 씬마다 낸 layout/transition 결정을 검증하고
훅 보장·단조로움 방지 가드레일을 얹어 실제 렌더에 쓸 편집 계획으로 변환한다.

순수 함수만 두어 ffmpeg/LLM 없이 완전히 단위 테스트 가능하다.
"""

from dataclasses import dataclass

# 렌더 가능한 레이아웃. ORDERED_LAYOUTS는 결정적 교체(가드레일 2)에 쓴다.
ORDERED_LAYOUTS = ["fullscreen", "polaroid", "split", "titlecard"]
LAYOUTS = set(ORDERED_LAYOUTS)

# LLM이 내는 친숙한 전환 이름 → ffmpeg xfade 이름.
TRANSITION_MAP = {
    "dissolve": "fade",
    "slide": "slideleft",
    "wipe": "wipeup",
    "zoom": "circleopen",
}

DEFAULT_LAYOUT = "fullscreen"
DEFAULT_TRANSITION = "dissolve"


@dataclass
class ScenePlan:
    layout: str      # LAYOUTS 중 하나
    transition: str  # 매핑 완료된 xfade 이름


def resolve_editing_plan(scenes) -> list:
    """씬 리스트 → 씬별 ScenePlan 리스트.

    1. 검증·기본값: 허용 목록 밖 값은 기본값으로 폴백하고 전환은 xfade로 매핑.
    2. 가드레일 1(훅): 첫 씬 layout을 fullscreen으로 강제.
    3. 가드레일 2(단조 방지): 같은 layout 3연속이면 3번째를 결정적으로 교체.
    """
    plans = []
    for scene in scenes:
        layout = scene.layout if scene.layout in LAYOUTS else DEFAULT_LAYOUT
        name = scene.transition_in if scene.transition_in in TRANSITION_MAP else DEFAULT_TRANSITION
        plans.append(ScenePlan(layout=layout, transition=TRANSITION_MAP[name]))

    if not plans:
        return plans

    # 가드레일 1: 강한 오프닝 — 훅을 디자인된 타이틀 카드로 시작.
    plans[0].layout = "titlecard"

    # 가드레일 2: 앞→뒤 1회 스캔하며 3연속 동일 layout을 깬다.
    # 3번째를 직전 두 개(=같은 값)와 다른 첫 유효 layout으로 바꾼다.
    # 3번째만 바꾸므로 plans[i] != plans[i-1]이 되어 다음 창은 새 3연속을 못 만든다.
    for i in range(2, len(plans)):
        if plans[i].layout == plans[i - 1].layout == plans[i - 2].layout:
            for candidate in ORDERED_LAYOUTS:
                if candidate != plans[i].layout:
                    plans[i].layout = candidate
                    break

    return plans
