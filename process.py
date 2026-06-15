import json
import os
import re
import shutil
import subprocess
from pathlib import Path

DEFAULT_CONFIG = {
    "silence_threshold": "-35dB",
    "min_silence_duration": 0.5,
    "silence_padding": 0.1,
    "whisper_model": "medium",
    "output_filename": "output.mp4",
    "subtitle_font": "Malgun Gothic",
    "subtitle_font_size": 24,
}

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def load_config(config_path="config.json"):
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def get_input_files(input_dir="input"):
    files = [
        f for f in Path(input_dir).iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files, key=lambda f: f.name)
