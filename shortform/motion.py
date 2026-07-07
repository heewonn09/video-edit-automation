"""AI 모션 씬 — 생성 이미지를 Veo 이미지-투-비디오로 움직이게 만든다.

프로브(Task 0)로 확정된 사항:
- 모델: veo-3.1-fast-generate-preview (env VEO_MODEL로 오버라이드)
- Developer API 모드에서 generate_audio 파라미터 금지 (Vertex 전용)
- 출력 720x1280 — 기존 렌더 경로의 스케일 필터가 1080x1920으로 처리
- 다운로드: client.files.download(file=video) 후 video.save(path)
- 비용 보호: 자동 재시도 없음 (실패 → 상위에서 이미지 폴백)
"""

import os
import time
from pathlib import Path

from google import genai
from google.genai import types

DEFAULT_VIDEO_MODEL = "veo-3.1-fast-generate-preview"
VIDEO_DURATION_SEC = 6          # 씬 평균(5~6초)에 맞춰 루프 티 최소화
MOTION_PROMPT_SUFFIX = ", 자연스러운 카메라 움직임과 부드러운 동작"


def select_motion_scenes(scenes, max_count=2) -> set:
    """motion 플래그된 씬 index를 씬 순서대로 최대 max_count개 고른다.

    첫 씬(훅)은 제외 — 훅은 타이틀 카드 디자인을 유지한다.
    max_count=0이면 기능 끔.
    """
    if max_count <= 0 or not scenes:
        return set()
    hook_index = scenes[0].index
    picked = [s.index for s in scenes if s.motion and s.index != hook_index]
    return set(picked[:max_count])


def generate_scene_video(image_path, prompt, out_path, model=None,
                         poll_interval=10, timeout=360):
    """이미지를 첫 프레임으로 Veo 영상 생성 → 폴링 → 저장."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    model = model or os.environ.get("VEO_MODEL", DEFAULT_VIDEO_MODEL)
    client = genai.Client(api_key=api_key)

    op = client.models.generate_videos(
        model=model,
        prompt=f"{prompt}{MOTION_PROMPT_SUFFIX}",
        image=types.Image.from_file(location=str(image_path)),
        config=types.GenerateVideosConfig(
            aspect_ratio="9:16",
            duration_seconds=VIDEO_DURATION_SEC,
            number_of_videos=1,
        ),
    )

    start = time.monotonic()
    while not op.done:
        if time.monotonic() - start > timeout:
            raise TimeoutError(f"Veo 영상 생성이 {timeout}초 안에 끝나지 않았습니다")
        time.sleep(poll_interval)
        op = client.operations.get(op)

    video = op.response.generated_videos[0].video
    client.files.download(file=video)
    video.save(str(out_path))
    return Path(out_path)
