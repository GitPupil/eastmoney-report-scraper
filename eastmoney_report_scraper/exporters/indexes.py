"""CSV and XLSX index exporters."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List, Optional

from ..constants import DEFAULT_INDEX_NAME
from ..models import FetchResult
from .common import _analysis_for

def write_csv_index(output_dir: Path, results: List[FetchResult]) -> Path:
    index_path = output_dir / DEFAULT_INDEX_NAME
    base_fields = [
        "stockName",
        "stockCode",
        "industryName",
        "title",
        "orgName",
        "publishDate",
        "rating",
        "infoCode",
        "status",
        "source",
        "chars",
        "summary",
        "signalScore",
        "priorityBucket",
        "themeTags",
        "ratingChange",
        "targetPrice",
        "epsForecast",
        "peForecast",
        "file",
    ]
    v2_fields = ["scoreReasons", "scoreBreakdown", "qualityScore"]
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=base_fields + v2_fields)
        writer.writeheader()
        for result in results:
            item = result.item
            structured = _analysis_for(result)
            valuation_fields = structured.get("valuation_fields") or {}
            writer.writerow(
                {
                    "stockName": item.get("stockName") or "",
                    "stockCode": item.get("stockCode") or "",
                    "industryName": item.get("industryName") or item.get("indvInduName") or "",
                    "title": item.get("title") or "",
                    "orgName": item.get("orgSName") or item.get("orgName") or "",
                    "publishDate": item.get("publishDate") or "",
                    "rating": item.get("emRatingName") or item.get("sRatingName") or "",
                    "infoCode": item.get("infoCode") or "",
                    "status": result.status,
                    "source": result.source,
                    "chars": len(result.text),
                    "summary": " | ".join(result.summary),
                    "signalScore": structured.get("signal_score", ""),
                    "priorityBucket": structured.get("priority_bucket", ""),
                    "themeTags": " | ".join(structured.get("theme_tags", [])),
                    "ratingChange": valuation_fields.get("rating_change", ""),
                    "targetPrice": " | ".join(valuation_fields.get("target_price", [])),
                    "epsForecast": " | ".join(valuation_fields.get("eps", [])),
                    "peForecast": " | ".join(valuation_fields.get("pe", [])),
                    "file": result.output_path.name if result.output_path else "",
                    "scoreReasons": " | ".join(structured.get("score_reasons", [])),
                    "scoreBreakdown": json.dumps(structured.get("score_breakdown", {}), ensure_ascii=False),
                    "qualityScore": result.quality_score,
                }
            )
    return index_path

def write_xlsx_index(output_dir: Path, csv_index_path: Path, log_path: Path) -> Optional[Path]:
    xlsx_path = output_dir / "report_index.xlsx"
    try:
        import openpyxl
    except ImportError:
        from ..utils import log_event

        log_event(log_path, "warn", "xlsx_export_skipped", reason="openpyxl not installed")
        return None

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    with csv_index_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            sheet.append(row)
    workbook.save(xlsx_path)
    return xlsx_path
