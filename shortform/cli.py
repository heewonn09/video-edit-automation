import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from shortform.script_generator import generate_script


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w가-힣]+", "_", title).strip("_")
    return slug[:40] or "script"


def main(argv=None):
    load_dotenv()
    parser = argparse.ArgumentParser(description="AI 숏폼 스크립트 생성기")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--topic", help="주제/아이디어 텍스트")
    group.add_argument("--url", help="크롤링할 URL")
    args = parser.parse_args(argv)

    raw_input = args.topic if args.topic else args.url
    script = generate_script(raw_input)

    out_dir = Path("output") / "scripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"script_{_slugify(script.title)}.json"
    out_path.write_text(
        json.dumps(asdict(script), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"제목: {script.title}")
    for scene in script.scenes:
        print(f"  [씬 {scene.index}] ({scene.duration_hint_sec}s) {scene.narration}")
        print(f"    연출: {scene.visual_description}")
    print(f"\n저장 위치: {out_path}")


if __name__ == "__main__":
    main(sys.argv[1:])
