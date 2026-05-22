"""Historical coverage exporters."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..constants import (
    DEFAULT_COVERAGE_HISTORY_NAME,
    DEFAULT_COVERAGE_SUMMARY_NAME,
    DEFAULT_INDUSTRY_COVERAGE_SUMMARY_NAME,
)
from ..models import DayRun, FetchResult
from .common import _analysis_for

def _split_theme_tags(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[|,，；;]", value) if part.strip()]
    return []

def _normalize_coverage_entry(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    info_code = str(entry.get("infoCode") or "").strip()
    stock_code = str(entry.get("stockCode") or "").strip()
    stock_name = str(entry.get("stockName") or "").strip()
    industry_name = str(entry.get("industryName") or entry.get("indvInduName") or "").strip()
    if not info_code or not (stock_code or stock_name or industry_name):
        return None

    report_type = str(entry.get("reportType") or "").strip()
    if report_type not in {"stock", "industry"}:
        report_type = "stock" if stock_code or stock_name else "industry"

    return {
        "infoCode": info_code,
        "reportType": report_type,
        "stockCode": stock_code,
        "stockName": stock_name,
        "industryName": industry_name,
        "orgName": str(entry.get("orgName") or entry.get("orgSName") or "").strip(),
        "rating": str(entry.get("rating") or entry.get("emRatingName") or entry.get("sRatingName") or "").strip(),
        "publishDate": str(entry.get("publishDate") or "").strip(),
        "title": str(entry.get("title") or "").strip(),
        "themeTags": _split_theme_tags(entry.get("themeTags")),
        "signalScore": entry.get("signalScore", entry.get("signal_score", "")),
        "priorityBucket": str(entry.get("priorityBucket") or entry.get("priority_bucket") or "").strip(),
    }

def _coverage_entry_from_result(result: FetchResult) -> Optional[Dict[str, Any]]:
    item = result.item
    analysis = _analysis_for(result)
    return _normalize_coverage_entry(
        {
            "infoCode": item.get("infoCode") or "",
            "reportType": "stock" if item.get("stockCode") or item.get("stockName") else "industry",
            "stockCode": item.get("stockCode") or "",
            "stockName": item.get("stockName") or "",
            "industryName": item.get("industryName") or item.get("indvInduName") or "",
            "orgName": item.get("orgSName") or item.get("orgName") or "",
            "rating": item.get("emRatingName") or item.get("sRatingName") or "",
            "publishDate": item.get("publishDate") or "",
            "title": item.get("title") or "",
            "themeTags": analysis.get("theme_tags") or [],
            "signalScore": analysis.get("signal_score", ""),
            "priorityBucket": analysis.get("priority_bucket", ""),
        }
    )

def read_coverage_history(history_path: Path) -> Dict[str, Dict[str, Any]]:
    entries: Dict[str, Dict[str, Any]] = {}
    if not history_path.exists():
        return entries
    with history_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            normalized = _normalize_coverage_entry(entry)
            if normalized:
                entries[normalized["infoCode"]] = normalized
    return entries

def write_coverage_history(history_path: Path, entries: Dict[str, Dict[str, Any]]) -> None:
    ordered = sorted(
        entries.values(),
        key=lambda entry: (
            entry.get("stockCode") or "",
            entry.get("stockName") or "",
            entry.get("industryName") or "",
            entry.get("publishDate") or "",
            entry.get("infoCode") or "",
        ),
    )
    with history_path.open("w", encoding="utf-8") as handle:
        for entry in ordered:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

def write_company_coverage_summary(summary_path: Path, entries: Dict[str, Dict[str, Any]]) -> None:
    grouped: Dict[tuple[str, str, str, str], set[str]] = {}
    for entry in entries.values():
        stock_code = entry.get("stockCode") or ""
        stock_name = entry.get("stockName") or ""
        if not stock_code and not stock_name:
            continue
        key = (
            stock_code,
            stock_name,
            entry.get("orgName") or "",
            entry.get("rating") or "",
        )
        grouped.setdefault(key, set()).add(entry.get("infoCode") or "")

    rows = sorted(
        [
            {
                "stockCode": stock_code,
                "stockName": stock_name,
                "orgName": org_name,
                "rating": rating,
                "coverageCount": len({info_code for info_code in info_codes if info_code}),
            }
            for (stock_code, stock_name, org_name, rating), info_codes in grouped.items()
        ],
        key=lambda row: (-row["coverageCount"], row["stockCode"], row["stockName"], row["orgName"], row["rating"]),
    )

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["stockCode", "stockName", "orgName", "rating", "coverageCount"],
        )
        writer.writeheader()
        writer.writerows(rows)

def write_industry_coverage_summary(summary_path: Path, entries: Dict[str, Dict[str, Any]]) -> None:
    grouped: Dict[tuple[str, str, str], set[str]] = {}
    for entry in entries.values():
        industry_name = entry.get("industryName") or ""
        if not industry_name:
            continue
        key = (
            industry_name,
            entry.get("orgName") or "",
            entry.get("rating") or "",
        )
        grouped.setdefault(key, set()).add(entry.get("infoCode") or "")

    rows = sorted(
        [
            {
                "industryName": industry_name,
                "orgName": org_name,
                "rating": rating,
                "coverageCount": len({info_code for info_code in info_codes if info_code}),
            }
            for (industry_name, org_name, rating), info_codes in grouped.items()
        ],
        key=lambda row: (-row["coverageCount"], row["industryName"], row["orgName"], row["rating"]),
    )

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["industryName", "orgName", "rating", "coverageCount"],
        )
        writer.writeheader()
        writer.writerows(rows)

def update_coverage_history(output_root: Path, day_runs: List[DayRun]) -> tuple[Path, Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    history_path = output_root / DEFAULT_COVERAGE_HISTORY_NAME
    company_summary_path = output_root / DEFAULT_COVERAGE_SUMMARY_NAME
    industry_summary_path = output_root / DEFAULT_INDUSTRY_COVERAGE_SUMMARY_NAME
    entries = read_coverage_history(history_path)
    for run in day_runs:
        for result in run.results:
            entry = _coverage_entry_from_result(result)
            if entry:
                entries[entry["infoCode"]] = entry
    write_coverage_history(history_path, entries)
    write_company_coverage_summary(company_summary_path, entries)
    write_industry_coverage_summary(industry_summary_path, entries)
    return history_path, company_summary_path, industry_summary_path
