# Video Edit Automation — Design Spec
_Date: 2026-06-16_

## Overview

Python + ffmpeg 기반 자동 영상 편집 파이프라인.  
`input/` 폴더에 영상을 넣으면 무음 구간을 제거하고, 한국어 자막을 붙인 결과물을 `output/`에 생성한다.

---

## Folder Structure

```
video-edit-automation/
├── input/                  # 원본 영상 투입 폴더
├── output/                 # 최종 결과물 폴더
├── temp/                   # 중간 처리 파일 (처리 후 자동 삭제)
├── process.py              # 메인 실행 스크립트
├── requirements.txt        # Python 의존성
└── config.json             # 사용자 설정 파일
```

---

## Pipeline

```
input/*.mp4  (파일명 오름차순 정렬)
     │
     ▼
[Step 1] 각 영상별 무음 구간 감지
         ffmpeg -af "silencedetect=noise=-35dB:d=0.5"
     │
     ▼
[Step 2] 무음 제거 클립 추출
         유효 구간(start, end) 목록 → ffmpeg trim+concat filter
         말 시작/끝 전후 0.1초 padding 유지
     │
     ▼
[Step 3] 전체 클립 순서대로 연결
         ffmpeg concat demuxer (무손실 스트림 복사)
     │
     ▼
[Step 4] 한국어 자막 생성
         연결된 영상에서 오디오 추출 → Whisper(medium 모델) 전사
         language="ko" 지정 → .srt 파일 생성
     │
     ▼
[Step 5] 자막 영상에 burn-in
         ffmpeg subtitles filter + 한국어 지원 폰트
     │
     ▼
output/output.mp4
```

---

## Configuration (config.json)

```json
{
  "silence_threshold": "-35dB",
  "min_silence_duration": 0.5,
  "silence_padding": 0.1,
  "whisper_model": "medium",
  "output_filename": "output.mp4",
  "subtitle_font": "Malgun Gothic",
  "subtitle_font_size": 24
}
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `silence_threshold` | `-35dB` | 이 이하 음량을 무음으로 판단 |
| `min_silence_duration` | `0.5` | 무음이 최소 이 시간(초) 이상이어야 잘림 |
| `silence_padding` | `0.1` | 말 시작/끝 전후 남길 여유(초) |
| `whisper_model` | `medium` | 한국어 인식 품질/속도 균형점 |
| `subtitle_font` | `Malgun Gothic` | Windows 기본 한국어 폰트 |
| `subtitle_font_size` | `24` | 자막 폰트 크기 |

---

## Components

### `process.py`

단일 스크립트. 다음 함수들로 구성:

- `load_config()` — config.json 읽기, 기본값 병합
- `get_input_files(input_dir)` — 파일명 기준 정렬된 영상 목록 반환
- `detect_voice_segments(video_path, cfg)` — ffmpeg silencedetect로 유효 구간 목록 반환
- `extract_segments(video_path, segments, out_dir)` — 각 유효 구간을 temp 파일로 추출
- `concat_clips(clip_paths, out_path)` — ffmpeg concat demuxer로 연결
- `transcribe_audio(video_path, cfg)` — Whisper로 한국어 전사, SRT 반환
- `burn_subtitles(video_path, srt_path, out_path, cfg)` — 자막 burn-in
- `main()` — 위 함수들을 순서대로 호출, temp 정리

### `requirements.txt`

```
openai-whisper
ffmpeg-python
```

> torch는 openai-whisper 설치 시 자동으로 CPU 버전이 함께 설치됨.

---

## Error Handling

- `input/`에 영상이 없으면 안내 메시지 출력 후 종료
- 지원 확장자: `.mp4`, `.mov`, `.avi`, `.mkv`
- 개별 영상 처리 실패 시 해당 파일 스킵 + 경고 출력, 나머지 계속 처리
- 처리 완료 후 `temp/` 폴더 자동 삭제

---

## Dependencies

| 도구 | 용도 | 설치 상태 |
|------|------|-----------|
| ffmpeg | 무음 감지, 클립 추출, 연결, 자막 burn-in | 설치됨 |
| Python 3.x | 파이프라인 오케스트레이션 | 설치됨 |
| openai-whisper | 한국어 음성 전사 | 미설치 (requirements.txt) |
| ffmpeg-python | ffmpeg Python 바인딩 | 미설치 (requirements.txt) |

---

## Usage

```bash
# 1회: 의존성 설치
pip install -r requirements.txt

# 영상 처리
python process.py
```
