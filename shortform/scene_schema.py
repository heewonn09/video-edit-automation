from dataclasses import dataclass, field


@dataclass
class Scene:
    index: int
    narration: str
    visual_description: str
    duration_hint_sec: float
    highlight_words: list = field(default_factory=list)


@dataclass
class Script:
    title: str
    scenes: list

    def total_duration_sec(self) -> float:
        return sum(s.duration_hint_sec for s in self.scenes)


def script_from_dict(data: dict) -> Script:
    scenes = [Scene(**s) for s in data["scenes"]]
    return Script(title=data["title"], scenes=scenes)
