import argparse
import json
import logging
import re
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from shortform.script_generator import generate_script
from shortform.pipeline import render_script

logger = logging.getLogger(__name__)


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w가-힣]+", "_", title).strip("_")
    return slug[:40] or "script"


def _process_one(raw_input: str, assets):
    script = generate_script(raw_input)

    out_dir = Path("output") / "scripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(script.title)
    out_path = out_dir / f"script_{slug}.json"
    out_path.write_text(
        json.dumps(asdict(script), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"제목: {script.title}")
    for scene in script.scenes:
        print(f"  [씬 {scene.index}] ({scene.duration_hint_sec}s) {scene.narration}")
        print(f"    연출: {scene.visual_description}")
    print(f"\n스크립트 저장 위치: {out_path}")

    video_path = render_script(script, Path("output") / f"{slug}.mp4", assets)
    print(f"영상 저장 위치: {video_path}")


def main(argv=None):
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="AI 숏폼 스크립트 생성기")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--topic", help="주제/아이디어 텍스트")
    group.add_argument("--url", help="크롤링할 URL")
    group.add_argument("--batch", help="주제/URL을 한 줄씩 적은 파일 경로 (순차 처리)")
    parser.add_argument("--assets", default=None, help="씬 매칭에 사용할 로컬 자산 폴더 (선택)")
    args = parser.parse_args(argv)

    if args.batch:
        lines = [
            line.strip()
            for line in Path(args.batch).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for i, raw_input in enumerate(lines, 1):
            print(f"\n=== [{i}/{len(lines)}] {raw_input} ===")
            try:
                _process_one(raw_input, args.assets)
            except Exception as e:
                logger.error(f"배치 항목 실패 ({raw_input}): {e}")
                continue
        return

    raw_input = args.topic if args.topic else args.url
    _process_one(raw_input, args.assets)


if __name__ == "__main__":
    main(sys.argv[1:])
