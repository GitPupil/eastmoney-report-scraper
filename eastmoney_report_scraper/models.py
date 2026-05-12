"""Data models used across the scraper."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FetchResult:
    item: Dict[str, Any]
    status: str
    text: str
    summary: List[str]
    output_path: Optional[Path]
    source: str
    quality_score: int = 0
    skipped: bool = False
    error: str = ""
    structured_analysis: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DayRun:
    date_str: str
    output_dir: Path
    raw_list: List[Dict[str, Any]]
    results: List[FetchResult]

