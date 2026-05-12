"""Small shared helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def log_event(log_path: Path, level: str, message: str, **payload: Any) -> None:
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "level": level,
        "message": message,
        "payload": payload,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def sanitize_filename(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]', "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:120] if len(value) > 120 else value


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" ：:；;，,")

