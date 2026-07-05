import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Scene:
    index: int
    narration: str
    visual_description: str
    duration_hint_sec: float
    highlight_words: list = field(default_factory=list)
    layout: str = "fullscreen"
    transition_in: str = "dissolve"
    chips: list = field(default_factory=list)  # [{"icon": 이모지, "label": 짧은 라벨}]


@dataclass
class Script:
    title: str
    scenes: list
    hook_candidates: list = field(default_factory=list)
    hook_reason: str = ""

    def total_duration_sec(self) -> float:
        return sum(s.duration_hint_sec for s in self.scenes)


def script_from_dict(data: dict) -> Script:
    scenes = []
    for i, s in enumerate(data["scenes"]):
        try:
            scenes.append(Scene(
                index=s["index"],
                narration=s["narration"],
                visual_description=s["visual_description"],
                duration_hint_sec=s["duration_hint_sec"],
                highlight_words=s.get("highlight_words", []),
                layout=s.get("layout", "fullscreen"),
                transition_in=s.get("transition_in", "dissolve"),
                chips=s.get("chips", []),
            ))
        except KeyError as e:
            logger.warning(f"씬 {i} 파싱 실패 (누락된 필드: {e}) — 스킵")

    if data["scenes"] and not scenes:
        raise RuntimeError("모든 씬 파싱에 실패하여 스크립트를 생성할 수 없습니다.")

    return Script(
        title=data["title"],
        scenes=scenes,
        hook_candidates=data.get("hook_candidates", []),
        hook_reason=data.get("hook_reason", ""),
    )
