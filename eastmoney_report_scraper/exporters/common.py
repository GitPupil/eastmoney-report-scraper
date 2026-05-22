"""Shared helpers for exporter modules."""

from __future__ import annotations

from typing import Any, Dict

from ..analysis import build_structured_analysis
from ..models import FetchResult

def _analysis_for(result: FetchResult) -> Dict[str, Any]:
    if not result.structured_analysis:
        result.structured_analysis = build_structured_analysis(result.item, result.text, result.summary)
    return result.structured_analysis
