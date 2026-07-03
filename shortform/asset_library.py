from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}


@dataclass
class AssetInfo:
    path: Path
    filename: str
    kind: str


def list_assets(folder) -> list[AssetInfo]:
    folder = Path(folder)
    if not folder.exists():
        return []

    files = [
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    ]
    files.sort(key=lambda f: f.name)

    return [
        AssetInfo(
            path=f,
            filename=f.name,
            kind="image" if f.suffix.lower() in IMAGE_EXTENSIONS else "video",
        )
        for f in files
    ]
