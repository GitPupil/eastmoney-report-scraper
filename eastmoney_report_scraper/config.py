"""Local app configuration helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .constants import DEFAULT_LOCAL_CONFIG_NAME, DEFAULT_LOCAL_DB_NAME, DEFAULT_OUTPUT_ROOT


@dataclass(frozen=True)
class LocalAppConfig:
    output_dir: str
    db_path: str
    host: str = "127.0.0.1"
    port: int = 8765
    concurrency: int = 1
    jitter: float = 0.0
    hotspot_days: int = 30
    hotspot_short_days: int = 7
    hotspot_silent_days: int = 90
    hotspot_broker_threshold: int = 3
    hotspot_coverage_threshold: int = 3


def default_local_app_config(output_dir: Optional[Path] = None, db_path: Optional[Path] = None) -> LocalAppConfig:
    root = (output_dir or DEFAULT_OUTPUT_ROOT).expanduser()
    database = (db_path or (root / DEFAULT_LOCAL_DB_NAME)).expanduser()
    return LocalAppConfig(output_dir=str(root), db_path=str(database))


def local_config_path(output_dir: Path) -> Path:
    return output_dir.expanduser() / DEFAULT_LOCAL_CONFIG_NAME


def load_local_app_config(
    output_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
    config_path: Optional[Path] = None,
) -> LocalAppConfig:
    base = default_local_app_config(output_dir, db_path)
    path = config_path or local_config_path(Path(base.output_dir))
    data: Dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    merged = {**asdict(base), **{key: value for key, value in data.items() if value is not None}}
    if output_dir is not None:
        merged["output_dir"] = str(output_dir.expanduser())
    if db_path is not None:
        merged["db_path"] = str(db_path.expanduser())
    return LocalAppConfig(**merged)


def save_local_app_config(config: LocalAppConfig, config_path: Optional[Path] = None) -> Path:
    output_dir = Path(config.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = config_path or local_config_path(output_dir)
    path.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
