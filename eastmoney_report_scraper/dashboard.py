"""Static HTML dashboard exporter for local research outputs."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote

from .constants import (
    DEFAULT_COVERAGE_HISTORY_NAME,
    DEFAULT_COVERAGE_SUMMARY_NAME,
    DEFAULT_DASHBOARD_NAME,
    DEFAULT_HOTSPOT_SIGNALS_NAME,
    DEFAULT_INDEX_NAME,
    DEFAULT_INDUSTRY_COVERAGE_SUMMARY_NAME,
)


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except Exception:
        return []


def _read_jsonl_rows(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    rows.append(value)
    except Exception:
        return []
    return rows


def _split_tokens(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []
    return [part.strip() for part in re.split(r"[|,，；;]", value) if part.strip()]


def _to_int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _to_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _date_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}", text)
    if match:
        return match.group(0).replace("/", "-")
    match = re.search(r"\d{8}", text)
    if match:
        raw = match.group(0)
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return ""


def _date_from_path(path: Path) -> str:
    for part in reversed(path.parts):
        date_value = _date_text(part)
        if date_value:
            return date_value
    return ""


def _relative_href(output_root: Path, path: Path) -> str:
    try:
        relative = path.relative_to(output_root)
    except ValueError:
        relative = path
    text = str(relative).replace("\\", "/")
    return quote(text, safe="/._-()%")


def _first_number(value: Any) -> Optional[float]:
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _direction(previous: Any, latest: Any) -> str:
    previous_number = _first_number(previous)
    latest_number = _first_number(latest)
    if previous_number is None or latest_number is None:
        return "unknown"
    if latest_number > previous_number:
        return "up"
    if latest_number < previous_number:
        return "down"
    return "flat"


def _score_direction(previous: float, latest: float) -> str:
    if latest > previous:
        return "up"
    if latest < previous:
        return "down"
    return "flat"


def discover_report_indexes(output_root: Path) -> List[Path]:
    """Find generated report indexes below an output root."""
    if not output_root.exists():
        return []
    try:
        return sorted(path for path in output_root.rglob(DEFAULT_INDEX_NAME) if path.is_file())
    except Exception:
        return []


def _normalize_report_row(output_root: Path, index_path: Path, row: Dict[str, str]) -> Dict[str, Any]:
    publish_date = _date_text(row.get("publishDate")) or _date_from_path(index_path.parent)
    report_file = str(row.get("file") or "").strip()
    file_path = index_path.parent / report_file if report_file else None
    return {
        "date": publish_date,
        "stockName": row.get("stockName") or "",
        "stockCode": row.get("stockCode") or "",
        "industryName": row.get("industryName") or "",
        "title": row.get("title") or "",
        "orgName": row.get("orgName") or "",
        "rating": row.get("rating") or "",
        "infoCode": row.get("infoCode") or "",
        "status": row.get("status") or "",
        "source": row.get("source") or "",
        "chars": _to_int(row.get("chars")),
        "summary": row.get("summary") or "",
        "signalScore": _to_float(row.get("signalScore")),
        "priorityBucket": row.get("priorityBucket") or "",
        "themeTags": _split_tokens(row.get("themeTags")),
        "ratingChange": row.get("ratingChange") or "",
        "targetPrice": row.get("targetPrice") or "",
        "epsForecast": row.get("epsForecast") or "",
        "peForecast": row.get("peForecast") or "",
        "scoreReasons": _split_tokens(row.get("scoreReasons")),
        "scoreBreakdown": row.get("scoreBreakdown") or "",
        "qualityScore": _to_int(row.get("qualityScore")),
        "file": report_file,
        "fileHref": _relative_href(output_root, file_path) if file_path else "",
        "indexHref": _relative_href(output_root, index_path),
    }


def _report_rank(row: Dict[str, Any]) -> Tuple[int, int, int, str]:
    status_rank = {"ok": 3, "weak": 2, "error": 1}.get(str(row.get("status") or ""), 0)
    return (
        status_rank,
        _to_int(row.get("qualityScore")),
        _to_int(row.get("chars")),
        str(row.get("date") or ""),
    )


def load_report_rows(output_root: Path) -> List[Dict[str, Any]]:
    deduped: Dict[str, Dict[str, Any]] = {}
    fallback_index = 0
    for index_path in discover_report_indexes(output_root):
        for row in _read_csv_rows(index_path):
            normalized = _normalize_report_row(output_root, index_path, row)
            info_code = str(normalized.get("infoCode") or "").strip()
            key = info_code or f"{index_path}:{fallback_index}"
            fallback_index += 1
            existing = deduped.get(key)
            if existing is None or _report_rank(normalized) >= _report_rank(existing):
                deduped[key] = normalized
    return sorted(deduped.values(), key=lambda row: (row.get("date") or "", row.get("infoCode") or ""))


def load_hotspot_rows(output_root: Path) -> List[Dict[str, Any]]:
    rows = []
    for row in _read_csv_rows(output_root / DEFAULT_HOTSPOT_SIGNALS_NAME):
        rows.append(
            {
                "entityType": row.get("entityType") or "",
                "entityName": row.get("entityName") or "",
                "stockCode": row.get("stockCode") or "",
                "industryName": row.get("industryName") or "",
                "hotspotLevel": row.get("hotspotLevel") or "",
                "isFirstCoverage": _to_bool(row.get("isFirstCoverage")),
                "isReactivatedCoverage": _to_bool(row.get("isReactivatedCoverage")),
                "coverage7d": _to_int(row.get("coverage7d")),
                "coverage30d": _to_int(row.get("coverage30d")),
                "previous30dCoverage": _to_int(row.get("previous30dCoverage")),
                "coverageAcceleration": _to_int(row.get("coverageAcceleration")),
                "brokerCount30d": _to_int(row.get("brokerCount30d")),
                "newBrokerCount30d": _to_int(row.get("newBrokerCount30d")),
                "ratingDistribution": row.get("ratingDistribution") or "",
                "buyRatio": _to_float(row.get("buyRatio")),
                "latestPublishDate": _date_text(row.get("latestPublishDate")),
                "reasons": _split_tokens(row.get("reasons")),
                "reasonCodes": _split_tokens(row.get("reasonCodes")),
                "coveredCompanyCount30d": _to_int(row.get("coveredCompanyCount30d")),
            }
        )
    level_order = {"STRONG": 0, "HOT": 1, "WATCH": 2}
    return sorted(
        rows,
        key=lambda row: (
            level_order.get(row.get("hotspotLevel"), 9),
            -_to_int(row.get("coverage30d")),
            -_to_int(row.get("brokerCount30d")),
            row.get("entityName") or "",
        ),
    )


def _counter_rows(counter: Counter[str], limit: Optional[int] = None) -> List[Dict[str, Any]]:
    rows = [{"name": key, "count": value} for key, value in counter.items() if key]
    rows.sort(key=lambda row: (-row["count"], row["name"]))
    return rows[:limit] if limit else rows


def _daily_count_rows(reports: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counter = Counter(str(row.get("date") or "") for row in reports if row.get("date"))
    return [{"date": key, "count": counter[key]} for key in sorted(counter)]


def _daily_distinct_rows(reports: Sequence[Dict[str, Any]], field: str) -> List[Dict[str, Any]]:
    grouped: Dict[str, set[str]] = defaultdict(set)
    for row in reports:
        date_value = str(row.get("date") or "")
        field_value = str(row.get(field) or "").strip()
        if date_value and field_value:
            grouped[date_value].add(field_value)
    return [{"date": key, "count": len(grouped[key])} for key in sorted(grouped)]


def _daily_token_rows(reports: Sequence[Dict[str, Any]], field: str, top_tokens: Iterable[str]) -> List[Dict[str, Any]]:
    selected = set(top_tokens)
    grouped: Dict[Tuple[str, str], int] = defaultdict(int)
    for row in reports:
        date_value = str(row.get("date") or "")
        if not date_value:
            continue
        for token in row.get(field) or []:
            if token in selected:
                grouped[(date_value, token)] += 1
    return [
        {"date": date_value, "name": token, "count": count}
        for (date_value, token), count in sorted(grouped.items())
    ]


def _daily_value_rows(reports: Sequence[Dict[str, Any]], field: str, top_values: Iterable[str]) -> List[Dict[str, Any]]:
    selected = set(top_values)
    grouped: Dict[Tuple[str, str], int] = defaultdict(int)
    for row in reports:
        date_value = str(row.get("date") or "")
        value = str(row.get(field) or "").strip()
        if date_value and value and value in selected:
            grouped[(date_value, value)] += 1
    return [
        {"date": date_value, "name": value, "count": count}
        for (date_value, value), count in sorted(grouped.items())
    ]


def _hotspot_reason_trend(hotspots: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], int] = defaultdict(int)
    for row in hotspots:
        date_value = str(row.get("latestPublishDate") or "")
        if not date_value:
            continue
        for code in row.get("reasonCodes") or []:
            grouped[(date_value, code)] += 1
    return [
        {"date": date_value, "name": code, "count": count}
        for (date_value, code), count in sorted(grouped.items())
    ]


def build_opinion_trends(reports: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in reports:
        entity_key = str(row.get("stockCode") or row.get("stockName") or row.get("industryName") or "").strip()
        org_name = str(row.get("orgName") or "").strip()
        if entity_key and org_name and row.get("date"):
            grouped[(entity_key, org_name)].append(row)

    trends: List[Dict[str, Any]] = []
    for (_, org_name), rows in grouped.items():
        ordered = sorted(rows, key=lambda row: (row.get("date") or "", row.get("infoCode") or ""))
        if len(ordered) < 2:
            continue
        previous = ordered[-2]
        latest = ordered[-1]
        trends.append(
            {
                "stockName": latest.get("stockName") or latest.get("industryName") or "",
                "stockCode": latest.get("stockCode") or "",
                "industryName": latest.get("industryName") or "",
                "orgName": org_name,
                "count": len(ordered),
                "previousDate": previous.get("date") or "",
                "latestDate": latest.get("date") or "",
                "previousRating": previous.get("rating") or "",
                "latestRating": latest.get("rating") or "",
                "ratingChange": latest.get("ratingChange") or "",
                "previousTargetPrice": previous.get("targetPrice") or "",
                "latestTargetPrice": latest.get("targetPrice") or "",
                "targetDirection": _direction(previous.get("targetPrice"), latest.get("targetPrice")),
                "previousEps": previous.get("epsForecast") or "",
                "latestEps": latest.get("epsForecast") or "",
                "epsDirection": _direction(previous.get("epsForecast"), latest.get("epsForecast")),
                "previousScore": _to_float(previous.get("signalScore")),
                "latestScore": _to_float(latest.get("signalScore")),
                "scoreDirection": _score_direction(
                    _to_float(previous.get("signalScore")),
                    _to_float(latest.get("signalScore")),
                ),
            }
        )
    return sorted(trends, key=lambda row: (row.get("latestDate") or "", row.get("count") or 0), reverse=True)[:120]


def _dominant(rows: Sequence[Dict[str, Any]], field: str) -> str:
    counter = Counter(str(row.get(field) or "").strip() for row in rows if str(row.get(field) or "").strip())
    return counter.most_common(1)[0][0] if counter else ""


def _average_by_day(rows: Sequence[Dict[str, Any]], field: str) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[float]] = defaultdict(list)
    for row in rows:
        date_value = str(row.get("date") or "")
        if date_value:
            grouped[date_value].append(_to_float(row.get(field)))
    return [
        {"name": date_value[5:], "date": date_value, "count": round(sum(values) / max(1, len(values)), 2)}
        for date_value, values in sorted(grouped.items())
        if values
    ]


def _entity_timeline(rows: Sequence[Dict[str, Any]], field: str) -> List[Dict[str, Any]]:
    timeline = []
    for row in sorted(rows, key=lambda item: (item.get("date") or "", item.get("infoCode") or "")):
        value = row.get(field)
        number = _first_number(value)
        if number is None:
            continue
        timeline.append(
            {
                "date": row.get("date") or "",
                "name": (row.get("date") or "")[5:],
                "count": number,
                "value": value,
                "orgName": row.get("orgName") or "",
                "title": row.get("title") or "",
            }
        )
    return timeline[-40:]


def _compact_report(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "date": row.get("date") or "",
        "stockName": row.get("stockName") or "",
        "stockCode": row.get("stockCode") or "",
        "industryName": row.get("industryName") or "",
        "title": row.get("title") or "",
        "orgName": row.get("orgName") or "",
        "rating": row.get("rating") or "",
        "summary": row.get("summary") or "",
        "signalScore": row.get("signalScore") or 0,
        "priorityBucket": row.get("priorityBucket") or "",
        "themeTags": row.get("themeTags") or [],
        "targetPrice": row.get("targetPrice") or "",
        "epsForecast": row.get("epsForecast") or "",
        "file": row.get("file") or "",
        "fileHref": row.get("fileHref") or "",
    }


def _matching_hotspots(
    entity_type: str,
    label: str,
    stock_code: str,
    industry_name: str,
    hotspots: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    matches = []
    for hotspot in hotspots:
        if entity_type == "company":
            if hotspot.get("entityType") == "company" and (
                (stock_code and hotspot.get("stockCode") == stock_code) or hotspot.get("entityName") == label
            ):
                matches.append(hotspot)
        elif hotspot.get("entityType") == "industry":
            if hotspot.get("entityName") == label or hotspot.get("industryName") == industry_name:
                matches.append(hotspot)
    return matches


def _matching_opinion_trends(
    entity_type: str,
    label: str,
    stock_code: str,
    industry_name: str,
    opinions: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if entity_type == "company":
        return [
            row
            for row in opinions
            if (stock_code and row.get("stockCode") == stock_code) or row.get("stockName") == label
        ]
    return [row for row in opinions if row.get("industryName") == industry_name or row.get("stockName") == label]


def _direction_counts(opinions: Sequence[Dict[str, Any]], field: str) -> Dict[str, int]:
    counter = Counter(str(row.get(field) or "unknown") for row in opinions)
    return {
        "up": counter.get("up", 0),
        "down": counter.get("down", 0),
        "flat": counter.get("flat", 0),
        "unknown": counter.get("unknown", 0),
    }


def _entity_drilldown(
    entity_type: str,
    key: str,
    rows: Sequence[Dict[str, Any]],
    hotspots: Sequence[Dict[str, Any]],
    opinions: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (row.get("date") or "", row.get("infoCode") or ""))
    label = _dominant(ordered, "stockName") or _dominant(ordered, "industryName") or key
    stock_code = _dominant(ordered, "stockCode")
    industry_name = _dominant(ordered, "industryName")
    entity_hotspots = _matching_hotspots(entity_type, label, stock_code, industry_name, hotspots)
    entity_opinions = _matching_opinion_trends(entity_type, label, stock_code, industry_name, opinions)
    dates = [row.get("date") for row in ordered if row.get("date")]
    broker_count = len({row.get("orgName") for row in ordered if row.get("orgName")})
    score_values = [_to_float(row.get("signalScore")) for row in ordered if row.get("signalScore") not in {"", None}]
    latest_reports = sorted(ordered, key=lambda row: (row.get("date") or "", row.get("signalScore") or 0), reverse=True)[:10]
    coverage_by_day = [{"name": row["date"][5:], "date": row["date"], "count": row["count"]} for row in _daily_count_rows(ordered)]
    return {
        "entityKey": f"{entity_type}::{key}",
        "entityType": entity_type,
        "label": label,
        "stockCode": stock_code,
        "industryName": industry_name,
        "reportCount": len(ordered),
        "brokerCount": broker_count,
        "firstDate": min(dates) if dates else "",
        "latestDate": max(dates) if dates else "",
        "avgScore": round(sum(score_values) / max(1, len(score_values)), 1) if score_values else 0,
        "hotspotLevel": (entity_hotspots[0].get("hotspotLevel") if entity_hotspots else ""),
        "reasonCodes": sorted({code for hotspot in entity_hotspots for code in hotspot.get("reasonCodes", [])}),
        "coverageByDay": coverage_by_day,
        "brokerByDay": _daily_distinct_rows(ordered, "orgName"),
        "scoreByDay": _average_by_day(ordered, "signalScore"),
        "targetTimeline": _entity_timeline(ordered, "targetPrice"),
        "epsTimeline": _entity_timeline(ordered, "epsForecast"),
        "topBrokers": _counter_rows(Counter(row.get("orgName") or "" for row in ordered), limit=10),
        "topThemes": _counter_rows(Counter(tag for row in ordered for tag in row.get("themeTags", [])), limit=10),
        "ratingDistribution": _counter_rows(Counter(row.get("rating") or "" for row in ordered), limit=10),
        "opinionSummary": {
            "trendCount": len(entity_opinions),
            "target": _direction_counts(entity_opinions, "targetDirection"),
            "eps": _direction_counts(entity_opinions, "epsDirection"),
            "score": _direction_counts(entity_opinions, "scoreDirection"),
        },
        "opinionTrends": entity_opinions[:20],
        "hotspots": entity_hotspots[:10],
        "latestReports": [_compact_report(row) for row in latest_reports],
    }


def build_entity_drilldowns(
    reports: Sequence[Dict[str, Any]],
    hotspots: Sequence[Dict[str, Any]],
    opinions: Sequence[Dict[str, Any]],
    limit: int = 300,
) -> List[Dict[str, Any]]:
    entities: List[Dict[str, Any]] = []
    company_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    industry_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in reports:
        company_key = str(row.get("stockCode") or row.get("stockName") or "").strip()
        industry_key = str(row.get("industryName") or "").strip()
        if company_key:
            company_groups[company_key].append(row)
        if industry_key:
            industry_groups[industry_key].append(row)

    for key, rows in company_groups.items():
        entities.append(_entity_drilldown("company", key, rows, hotspots, opinions))
    for key, rows in industry_groups.items():
        entities.append(_entity_drilldown("industry", key, rows, hotspots, opinions))

    return sorted(
        entities,
        key=lambda row: (
            {"STRONG": 0, "HOT": 1, "WATCH": 2, "": 3}.get(str(row.get("hotspotLevel") or ""), 4),
            -_to_int(row.get("reportCount")),
            -_to_int(row.get("brokerCount")),
            row.get("entityType") or "",
            row.get("label") or "",
        ),
    )[:limit]


def build_dashboard_data(output_root: Path) -> Dict[str, Any]:
    reports = load_report_rows(output_root)
    hotspots = load_hotspot_rows(output_root)
    opinion_trends = build_opinion_trends(reports)
    coverage_history = _read_jsonl_rows(output_root / DEFAULT_COVERAGE_HISTORY_NAME)
    company_summary = _read_csv_rows(output_root / DEFAULT_COVERAGE_SUMMARY_NAME)
    industry_summary = _read_csv_rows(output_root / DEFAULT_INDUSTRY_COVERAGE_SUMMARY_NAME)
    dates = sorted({row.get("date") for row in reports if row.get("date")})
    industry_counter = Counter(row.get("industryName") or "" for row in reports)
    theme_counter = Counter(tag for row in reports for tag in row.get("themeTags", []))
    top_industries = [row["name"] for row in _counter_rows(industry_counter, limit=8)]
    top_themes = [row["name"] for row in _counter_rows(theme_counter, limit=12)]

    return {
        "meta": {
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "outputRoot": str(output_root),
            "firstDate": dates[0] if dates else "",
            "latestDate": dates[-1] if dates else "",
            "reportIndexCount": len(discover_report_indexes(output_root)),
            "sourceFiles": {
                "hotspots": DEFAULT_HOTSPOT_SIGNALS_NAME,
                "coverageHistory": DEFAULT_COVERAGE_HISTORY_NAME,
                "companyCoverage": DEFAULT_COVERAGE_SUMMARY_NAME,
                "industryCoverage": DEFAULT_INDUSTRY_COVERAGE_SUMMARY_NAME,
            },
        },
        "reports": reports,
        "hotspots": hotspots,
        "coverageHistoryCount": len(coverage_history),
        "companyCoverageSummary": company_summary[:500],
        "industryCoverageSummary": industry_summary[:500],
        "opinionTrends": opinion_trends,
        "entityDrilldowns": build_entity_drilldowns(reports, hotspots, opinion_trends),
        "aggregates": {
            "reportsByDay": _daily_count_rows(reports),
            "brokersByDay": _daily_distinct_rows(reports, "orgName"),
            "companiesByDay": _daily_distinct_rows(reports, "stockCode"),
            "industries": _counter_rows(industry_counter, limit=20),
            "brokers": _counter_rows(Counter(row.get("orgName") or "" for row in reports), limit=20),
            "ratings": _counter_rows(Counter(row.get("rating") or "" for row in reports), limit=20),
            "priorityBuckets": _counter_rows(Counter(row.get("priorityBucket") or "" for row in reports), limit=10),
            "statuses": _counter_rows(Counter(row.get("status") or "" for row in reports), limit=10),
            "sources": _counter_rows(Counter(row.get("source") or "" for row in reports), limit=10),
            "themes": _counter_rows(theme_counter, limit=30),
            "industryTrend": _daily_value_rows(reports, "industryName", top_industries),
            "themeTrend": _daily_token_rows(reports, "themeTags", top_themes),
            "hotspotLevels": _counter_rows(Counter(row.get("hotspotLevel") or "" for row in hotspots), limit=10),
            "hotspotReasonTrend": _hotspot_reason_trend(hotspots),
            "topIndustries": top_industries,
            "topThemes": top_themes,
        },
    }


def _safe_json(data: Dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def build_dashboard_html(data: Dict[str, Any]) -> str:
    return _HTML_TEMPLATE.replace("__DASHBOARD_DATA__", _safe_json(data))


def write_dashboard(output_root: Path, dashboard_name: str = DEFAULT_DASHBOARD_NAME) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    dashboard_path = output_root / dashboard_name
    data = build_dashboard_data(output_root)
    dashboard_path.write_text(build_dashboard_html(data), encoding="utf-8")
    return dashboard_path


_HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Eastmoney Research Dashboard</title>
  <style>
    :root {
      --bg: #f6f4ef;
      --surface: #ffffff;
      --surface-soft: #fbfaf7;
      --text: #1c2730;
      --muted: #65717d;
      --line: #d9d3c6;
      --teal: #0f766e;
      --amber: #b7791f;
      --rose: #be4b63;
      --blue: #2563a8;
      --green: #2f855a;
      --shadow: 0 16px 40px rgba(34, 32, 28, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", "Microsoft YaHei", sans-serif;
      font-size: 14px;
      line-height: 1.45;
    }
    a { color: var(--blue); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .page { max-width: 1440px; margin: 0 auto; padding: 24px; }
    .topbar {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 20px;
      padding: 12px 0 22px;
      border-bottom: 1px solid var(--line);
    }
    .eyebrow { margin: 0 0 4px; color: var(--teal); font-size: 12px; font-weight: 700; text-transform: uppercase; }
    h1 { margin: 0; font-size: 30px; line-height: 1.1; letter-spacing: 0; }
    h2 { margin: 0 0 14px; font-size: 18px; letter-spacing: 0; }
    h3 { margin: 0 0 10px; font-size: 14px; letter-spacing: 0; }
    .meta { color: var(--muted); text-align: right; font-size: 13px; }
    .filters {
      display: grid;
      grid-template-columns: repeat(6, minmax(150px, 1fr));
      gap: 12px;
      padding: 18px 0;
    }
    .field { display: flex; flex-direction: column; gap: 5px; }
    label { color: var(--muted); font-size: 12px; font-weight: 650; }
    input, select {
      width: 100%;
      height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      color: var(--text);
      padding: 0 10px;
      font: inherit;
    }
    .span-2 { grid-column: span 2; }
    .kpis { display: grid; grid-template-columns: repeat(8, 1fr); gap: 12px; margin-bottom: 18px; }
    .kpi, .card {
      background: var(--surface);
      border: 1px solid rgba(217, 211, 198, 0.9);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    .kpi { padding: 14px; min-height: 88px; }
    .kpi .label { color: var(--muted); font-size: 12px; }
    .kpi .value { margin-top: 8px; font-size: 26px; font-weight: 750; }
    .kpi .sub { margin-top: 3px; color: var(--muted); font-size: 12px; }
    .grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; margin-bottom: 14px; }
    .card { padding: 16px; min-width: 0; }
    .card-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
    .card-head h2 { margin: 0; }
    .entity-select { width: min(420px, 100%); }
    .col-4 { grid-column: span 4; }
    .col-6 { grid-column: span 6; }
    .col-8 { grid-column: span 8; }
    .col-12 { grid-column: span 12; }
    .chart { height: 220px; width: 100%; }
    .mini-chart { height: 170px; width: 100%; }
    .detail-kpis { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin: 8px 0 14px; }
    .detail-kpi { padding: 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-soft); min-height: 70px; }
    .detail-kpi .label { color: var(--muted); font-size: 12px; }
    .detail-kpi .value { margin-top: 5px; font-size: 20px; font-weight: 750; }
    .detail-grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }
    .detail-panel { grid-column: span 4; min-width: 0; padding-top: 12px; border-top: 1px solid var(--line); }
    .detail-panel.wide { grid-column: span 8; }
    .link-button {
      border: 0;
      background: transparent;
      color: var(--blue);
      padding: 0;
      font: inherit;
      cursor: pointer;
    }
    .link-button:hover { text-decoration: underline; }
    .empty { color: var(--muted); padding: 28px 0; text-align: center; border: 1px dashed var(--line); border-radius: 8px; background: var(--surface-soft); }
    .table-wrap { overflow: auto; max-height: 560px; border: 1px solid var(--line); border-radius: 8px; }
    table { width: 100%; border-collapse: collapse; min-width: 920px; background: var(--surface); }
    th, td { padding: 9px 10px; border-bottom: 1px solid #ebe6dc; text-align: left; vertical-align: top; }
    th { position: sticky; top: 0; background: #eee8dc; color: #33404a; z-index: 1; font-size: 12px; }
    tr:hover td { background: #fcfaf4; }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 7px;
      border-radius: 999px;
      background: #eee8dc;
      color: #33404a;
      font-size: 12px;
      font-weight: 650;
      white-space: nowrap;
    }
    .pill.strong { background: #ffe4e6; color: #9f1239; }
    .pill.hot { background: #fef3c7; color: #92400e; }
    .pill.watch { background: #dcfce7; color: #166534; }
    .pill.a { background: #dbeafe; color: #1d4ed8; }
    .pill.b { background: #ccfbf1; color: #0f766e; }
    .pill.up { background: #dcfce7; color: #166534; }
    .pill.down { background: #ffe4e6; color: #9f1239; }
    .pill.flat { background: #e0f2fe; color: #075985; }
    .muted { color: var(--muted); }
    .tags { display: flex; flex-wrap: wrap; gap: 4px; max-width: 260px; }
    .summary { max-width: 360px; min-width: 240px; color: #42505a; }
    .footer { color: var(--muted); padding: 18px 0 4px; font-size: 12px; }
    @media (max-width: 1120px) {
      .filters { grid-template-columns: repeat(3, 1fr); }
      .kpis { grid-template-columns: repeat(4, 1fr); }
      .detail-kpis { grid-template-columns: repeat(3, 1fr); }
      .col-4, .col-6, .col-8, .detail-panel, .detail-panel.wide { grid-column: span 12; }
    }
    @media (max-width: 720px) {
      .page { padding: 14px; }
      .topbar { align-items: flex-start; flex-direction: column; }
      .meta { text-align: left; }
      .filters { grid-template-columns: 1fr; }
      .span-2 { grid-column: span 1; }
      .kpis { grid-template-columns: repeat(2, 1fr); }
      .detail-kpis { grid-template-columns: repeat(2, 1fr); }
      .card-head { align-items: stretch; flex-direction: column; }
      h1 { font-size: 24px; }
    }
  </style>
</head>
<body>
  <main class="page">
    <header class="topbar">
      <div>
        <p class="eyebrow">Eastmoney Report Scraper</p>
        <h1>Research Dashboard</h1>
      </div>
      <div class="meta" id="meta"></div>
    </header>

    <section class="filters" aria-label="filters">
      <div class="field"><label for="startDate">开始日期</label><input id="startDate" type="date"></div>
      <div class="field"><label for="endDate">结束日期</label><input id="endDate" type="date"></div>
      <div class="field span-2"><label for="search">关键词</label><input id="search" type="search" placeholder="公司 / 行业 / 标题 / 摘要"></div>
      <div class="field"><label for="companyFilter">公司</label><select id="companyFilter"></select></div>
      <div class="field"><label for="industryFilter">行业</label><select id="industryFilter"></select></div>
      <div class="field"><label for="brokerFilter">券商</label><select id="brokerFilter"></select></div>
      <div class="field"><label for="ratingFilter">评级</label><select id="ratingFilter"></select></div>
      <div class="field"><label for="priorityFilter">优先级</label><select id="priorityFilter"></select></div>
      <div class="field"><label for="hotspotFilter">热点等级</label><select id="hotspotFilter"></select></div>
      <div class="field"><label for="themeFilter">主题</label><select id="themeFilter"></select></div>
      <div class="field"><label for="reasonFilter">热点原因</label><select id="reasonFilter"></select></div>
      <div class="field"><label for="minScore">最低分</label><input id="minScore" type="number" min="0" max="100" step="1" value="0"></div>
    </section>

    <section class="kpis" id="kpis"></section>

    <section class="grid">
      <article class="card col-6"><h2>研报数量趋势</h2><div class="chart" id="reportTrend"></div></article>
      <article class="card col-6"><h2>券商覆盖扩散</h2><div class="chart" id="brokerTrend"></div></article>
      <article class="card col-4"><h2>行业热度</h2><div class="mini-chart" id="industryChart"></div></article>
      <article class="card col-4"><h2>主题趋势</h2><div class="mini-chart" id="themeChart"></div></article>
      <article class="card col-4"><h2>热点原因</h2><div class="mini-chart" id="reasonChart"></div></article>
    </section>

    <section class="grid">
      <article class="card col-12" id="drilldownCard">
        <div class="card-head">
          <h2>研究对象 Drilldown</h2>
          <div class="field entity-select"><label for="entitySelect">公司 / 行业</label><select id="entitySelect"></select></div>
        </div>
        <div class="detail-kpis" id="entityKpis"></div>
        <div class="detail-grid">
          <div class="detail-panel"><h3>覆盖时间线</h3><div class="mini-chart" id="entityCoverageChart"></div></div>
          <div class="detail-panel"><h3>券商扩散</h3><div class="mini-chart" id="entityBrokerChart"></div></div>
          <div class="detail-panel"><h3>信号分数</h3><div class="mini-chart" id="entityScoreChart"></div></div>
          <div class="detail-panel"><h3>目标价轨迹</h3><div class="mini-chart" id="entityTargetChart"></div></div>
          <div class="detail-panel"><h3>EPS 轨迹</h3><div class="mini-chart" id="entityEpsChart"></div></div>
          <div class="detail-panel"><h3>券商 / 主题</h3><div class="mini-chart" id="entityBrokerMix"></div><div class="mini-chart" id="entityThemeMix"></div></div>
          <div class="detail-panel wide"><h3>连续观点</h3><div class="table-wrap"><table id="entityOpinionTable"></table></div></div>
          <div class="detail-panel"><h3>最新研报</h3><div class="table-wrap"><table id="entityReportTable"></table></div></div>
        </div>
      </article>
    </section>

    <section class="grid">
      <article class="card col-12">
        <h2>近期热点</h2>
        <div class="table-wrap"><table id="hotspotTable"></table></div>
      </article>
      <article class="card col-12">
        <h2>观点变化</h2>
        <div class="table-wrap"><table id="opinionTable"></table></div>
      </article>
      <article class="card col-8">
        <h2>研报明细</h2>
        <div class="table-wrap"><table id="reportTable"></table></div>
      </article>
      <article class="card col-4">
        <h2>数据质量</h2>
        <div class="mini-chart" id="qualityChart"></div>
        <div class="mini-chart" id="sourceChart"></div>
      </article>
    </section>
    <div class="footer" id="footer"></div>
  </main>
  <script id="dashboard-data" type="application/json">__DASHBOARD_DATA__</script>
  <script>
    const DATA = JSON.parse(document.getElementById("dashboard-data").textContent);
    const $ = (id) => document.getElementById(id);
    const state = {};
    const levelRank = { STRONG: 0, HOT: 1, WATCH: 2 };

    function uniq(values) {
      return [...new Set(values.filter(Boolean).map(String))].sort((a, b) => a.localeCompare(b, "zh-CN"));
    }
    function optionList(values, label) {
      return [`<option value="">全部${label}</option>`, ...values.map((v) => `<option value="${escapeAttr(v)}">${escapeHtml(v)}</option>`)].join("");
    }
    function escapeHtml(value) {
      const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
      return String(value ?? "").replace(/[&<>"']/g, (m) => map[m]);
    }
    function escapeAttr(value) { return escapeHtml(value); }
    function includesText(row, text) {
      if (!text) return true;
      const haystack = [
        row.stockName, row.stockCode, row.industryName, row.title, row.orgName,
        row.rating, row.summary, ...(row.themeTags || []), ...(row.scoreReasons || [])
      ].join(" ").toLowerCase();
      return haystack.includes(text.toLowerCase());
    }
    function inDate(date) {
      if (!date) return true;
      if (state.startDate && date < state.startDate) return false;
      if (state.endDate && date > state.endDate) return false;
      return true;
    }
    function reportMatches(row) {
      return inDate(row.date)
        && includesText(row, state.search)
        && (!state.company || row.stockName === state.company || row.stockCode === state.company)
        && (!state.industry || row.industryName === state.industry)
        && (!state.broker || row.orgName === state.broker)
        && (!state.rating || row.rating === state.rating)
        && (!state.priority || row.priorityBucket === state.priority)
        && (!state.theme || (row.themeTags || []).includes(state.theme))
        && Number(row.signalScore || 0) >= Number(state.minScore || 0);
    }
    function hotspotMatches(row) {
      const textMatch = !state.search || [row.entityName, row.stockCode, row.industryName, ...(row.reasons || []), ...(row.reasonCodes || [])].join(" ").toLowerCase().includes(state.search.toLowerCase());
      return inDate(row.latestPublishDate)
        && textMatch
        && (!state.company || row.entityName === state.company || row.stockCode === state.company)
        && (!state.industry || row.industryName === state.industry || row.entityName === state.industry)
        && (!state.hotspot || row.hotspotLevel === state.hotspot)
        && (!state.reason || (row.reasonCodes || []).includes(state.reason));
    }
    function readState() {
      ["startDate", "endDate", "search", "minScore"].forEach((id) => state[id] = $(id).value);
      state.company = $("companyFilter").value;
      state.industry = $("industryFilter").value;
      state.broker = $("brokerFilter").value;
      state.rating = $("ratingFilter").value;
      state.priority = $("priorityFilter").value;
      state.hotspot = $("hotspotFilter").value;
      state.theme = $("themeFilter").value;
      state.reason = $("reasonFilter").value;
      state.entityKey = $("entitySelect").value;
    }
    function initFilters() {
      const reports = DATA.reports || [];
      const hotspots = DATA.hotspots || [];
      const entities = DATA.entityDrilldowns || [];
      const dates = uniq(reports.map((r) => r.date));
      if (dates.length) {
        $("startDate").value = dates[0];
        $("endDate").value = dates[dates.length - 1];
      }
      $("companyFilter").innerHTML = optionList(uniq([...reports.map((r) => r.stockName || r.stockCode), ...hotspots.filter((h) => h.entityType === "company").map((h) => h.entityName)]), "公司");
      $("industryFilter").innerHTML = optionList(uniq([...reports.map((r) => r.industryName), ...hotspots.map((h) => h.industryName || (h.entityType === "industry" ? h.entityName : ""))]), "行业");
      $("brokerFilter").innerHTML = optionList(uniq(reports.map((r) => r.orgName)), "券商");
      $("ratingFilter").innerHTML = optionList(uniq(reports.map((r) => r.rating)), "评级");
      $("priorityFilter").innerHTML = optionList(uniq(reports.map((r) => r.priorityBucket)), "优先级");
      $("hotspotFilter").innerHTML = optionList(uniq(hotspots.map((h) => h.hotspotLevel)), "热点");
      $("themeFilter").innerHTML = optionList(uniq(reports.flatMap((r) => r.themeTags || [])), "主题");
      $("reasonFilter").innerHTML = optionList(uniq(hotspots.flatMap((h) => h.reasonCodes || [])), "原因");
      $("entitySelect").innerHTML = [`<option value="">自动选择研究对象</option>`, ...entities.map((entity) => {
        const type = entity.entityType === "company" ? "公司" : "行业";
        const suffix = `${entity.reportCount}篇 / ${entity.brokerCount}家`;
        return `<option value="${escapeAttr(entity.entityKey)}">${type}｜${escapeHtml(entity.label)}（${suffix}）</option>`;
      })].join("");
      document.querySelectorAll("input, select").forEach((el) => el.addEventListener("input", render));
      $("meta").innerHTML = `${escapeHtml(DATA.meta.firstDate || "-")} 至 ${escapeHtml(DATA.meta.latestDate || "-")}<br>生成于 ${escapeHtml(DATA.meta.generatedAt || "")}`;
    }
    function countUnique(rows, getter) {
      return new Set(rows.map(getter).filter(Boolean)).size;
    }
    function renderKpis(reports, hotspots) {
      const weak = reports.filter((r) => r.status === "weak" || r.status === "error").length;
      const ab = reports.filter((r) => ["A", "B"].includes(r.priorityBucket)).length;
      const strong = hotspots.filter((h) => h.hotspotLevel === "STRONG" || h.hotspotLevel === "HOT").length;
      const cards = [
        ["研报", reports.length, "筛选后样本"],
        ["公司", countUnique(reports, (r) => r.stockCode || r.stockName), "覆盖标的"],
        ["行业", countUnique(reports, (r) => r.industryName), "覆盖行业"],
        ["券商", countUnique(reports, (r) => r.orgName), "参与机构"],
        ["热点", hotspots.length, `HOT/STRONG ${strong}`],
        ["A/B", ab, "优先级样本"],
        ["弱/错", weak, "数据质量"],
        ["历史", DATA.coverageHistoryCount || 0, "coverage rows"],
      ];
      $("kpis").innerHTML = cards.map(([label, value, sub]) => `<div class="kpi"><div class="label">${label}</div><div class="value">${value}</div><div class="sub">${sub}</div></div>`).join("");
    }
    function seriesByDay(rows, getDate, getKey) {
      const grouped = {};
      rows.forEach((row) => {
        const date = getDate(row);
        if (!date) return;
        if (!grouped[date]) grouped[date] = new Set();
        grouped[date].add(getKey ? getKey(row) : `${date}-${grouped[date].size}`);
      });
      return Object.keys(grouped).sort().map((date) => ({ name: date.slice(5), count: grouped[date].size }));
    }
    function countBy(rows, getter, limit = 12) {
      const counter = {};
      rows.forEach((row) => {
        const value = getter(row);
        if (!value) return;
        counter[value] = (counter[value] || 0) + 1;
      });
      return Object.keys(counter).map((name) => ({ name, count: counter[name] })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "zh-CN")).slice(0, limit);
    }
    function countTokens(rows, getter, limit = 12) {
      const counter = {};
      rows.forEach((row) => (getter(row) || []).forEach((value) => {
        if (!value) return;
        counter[value] = (counter[value] || 0) + 1;
      }));
      return Object.keys(counter).map((name) => ({ name, count: counter[name] })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "zh-CN")).slice(0, limit);
    }
    function drawBar(id, rows, color = "var(--teal)") {
      const el = $(id);
      if (!rows.length) { el.innerHTML = `<div class="empty">暂无数据</div>`; return; }
      const max = Math.max(...rows.map((r) => r.count), 1);
      el.innerHTML = `<svg viewBox="0 0 640 220" width="100%" height="100%" role="img">
        ${rows.map((r, i) => {
          const width = Math.max(3, (r.count / max) * 420);
          const y = 18 + i * Math.max(16, 180 / rows.length);
          return `<g><text x="0" y="${y + 10}" font-size="11" fill="#65717d">${escapeHtml(String(r.name).slice(0, 12))}</text><rect x="132" y="${y}" width="${width}" height="12" rx="3" fill="${color}"></rect><text x="${140 + width}" y="${y + 10}" font-size="11" fill="#33404a">${r.count}</text></g>`;
        }).join("")}
      </svg>`;
    }
    function drawLine(id, rows, color = "var(--blue)") {
      const el = $(id);
      if (!rows.length) { el.innerHTML = `<div class="empty">暂无数据</div>`; return; }
      const max = Math.max(...rows.map((r) => r.count), 1);
      const step = rows.length > 1 ? 560 / (rows.length - 1) : 0;
      const points = rows.map((r, i) => `${50 + i * step},${170 - (r.count / max) * 130}`).join(" ");
      el.innerHTML = `<svg viewBox="0 0 640 220" width="100%" height="100%" role="img">
        <line x1="50" y1="180" x2="610" y2="180" stroke="#d9d3c6"></line>
        <line x1="50" y1="30" x2="50" y2="180" stroke="#d9d3c6"></line>
        <polyline points="${points}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></polyline>
        ${rows.map((r, i) => {
          const x = 50 + i * step;
          const y = 170 - (r.count / max) * 130;
          const label = rows.length <= 12 || i % Math.ceil(rows.length / 12) === 0 ? `<text x="${x}" y="202" text-anchor="middle" font-size="10" fill="#65717d">${escapeHtml(r.name)}</text>` : "";
          return `<circle cx="${x}" cy="${y}" r="4" fill="${color}"><title>${escapeHtml(r.name)}: ${r.count}</title></circle><text x="${x}" y="${y - 8}" text-anchor="middle" font-size="10" fill="#33404a">${r.count}</text>${label}`;
        }).join("")}
      </svg>`;
    }
    function rowsWithDateNames(rows) {
      return (rows || []).map((row) => ({ name: row.name || String(row.date || "").slice(5), count: Number(row.count || 0) }));
    }
    function entityMatchesCurrentFilters(entity) {
      const text = [entity.label, entity.stockCode, entity.industryName, ...(entity.reasonCodes || [])].join(" ").toLowerCase();
      return (!state.search || text.includes(state.search.toLowerCase()))
        && (!state.company || entity.label === state.company || entity.stockCode === state.company)
        && (!state.industry || entity.industryName === state.industry || entity.label === state.industry)
        && (!state.hotspot || entity.hotspotLevel === state.hotspot)
        && (!state.reason || (entity.reasonCodes || []).includes(state.reason));
    }
    function entityKeyForReport(row) {
      const entities = DATA.entityDrilldowns || [];
      const company = entities.find((entity) => entity.entityType === "company" && ((row.stockCode && entity.stockCode === row.stockCode) || entity.label === row.stockName));
      if (company) return company.entityKey;
      const industry = entities.find((entity) => entity.entityType === "industry" && entity.label === row.industryName);
      return industry ? industry.entityKey : "";
    }
    function entityKeyForHotspot(row) {
      const entities = DATA.entityDrilldowns || [];
      const company = entities.find((entity) => entity.entityType === "company" && row.entityType === "company" && ((row.stockCode && entity.stockCode === row.stockCode) || entity.label === row.entityName));
      if (company) return company.entityKey;
      const industry = entities.find((entity) => entity.entityType === "industry" && (entity.label === row.entityName || entity.label === row.industryName));
      return industry ? industry.entityKey : "";
    }
    function directionSummary(summary) {
      const safe = summary || {};
      return `↑${safe.up || 0} ↓${safe.down || 0} →${safe.flat || 0}`;
    }
    function renderEntityTable(entity) {
      const reports = entity.latestReports || [];
      if (!reports.length) {
        $("entityReportTable").innerHTML = `<tbody><tr><td><div class="empty">暂无研报</div></td></tr></tbody>`;
        return;
      }
      $("entityReportTable").innerHTML = `<thead><tr><th>日期</th><th>券商</th><th>评级</th><th>分数</th><th>文件</th></tr></thead><tbody>
        ${reports.map((row) => `<tr>
          <td>${escapeHtml(row.date)}</td>
          <td>${escapeHtml(row.orgName)}</td>
          <td>${escapeHtml(row.rating || "-")}</td>
          <td>${pill(row.priorityBucket)} ${row.signalScore}</td>
          <td>${row.fileHref ? `<a href="${escapeAttr(row.fileHref)}">${escapeHtml(row.file || "打开")}</a>` : `<span class="muted">-</span>`}</td>
        </tr>`).join("")}
      </tbody>`;
    }
    function renderEntityOpinion(entity) {
      const trends = entity.opinionTrends || [];
      if (!trends.length) {
        $("entityOpinionTable").innerHTML = `<tbody><tr><td><div class="empty">暂无同一机构连续观点</div></td></tr></tbody>`;
        return;
      }
      $("entityOpinionTable").innerHTML = `<thead><tr><th>券商</th><th>日期</th><th>评级</th><th>目标价</th><th>EPS</th><th>分数</th></tr></thead><tbody>
        ${trends.map((row) => `<tr>
          <td>${escapeHtml(row.orgName)}</td>
          <td>${escapeHtml(row.previousDate)} → ${escapeHtml(row.latestDate)}</td>
          <td>${escapeHtml(row.previousRating || "-")} → ${escapeHtml(row.latestRating || "-")}<div class="muted">${escapeHtml(row.ratingChange || "")}</div></td>
          <td>${escapeHtml(row.previousTargetPrice || "-")} → ${escapeHtml(row.latestTargetPrice || "-")} ${pill(row.targetDirection)}</td>
          <td>${escapeHtml(row.previousEps || "-")} → ${escapeHtml(row.latestEps || "-")} ${pill(row.epsDirection)}</td>
          <td>${row.previousScore} → ${row.latestScore} ${pill(row.scoreDirection)}</td>
        </tr>`).join("")}
      </tbody>`;
    }
    function renderDrilldown() {
      const entities = DATA.entityDrilldowns || [];
      const selected = state.entityKey ? entities.find((entity) => entity.entityKey === state.entityKey) : null;
      const entity = selected || entities.filter(entityMatchesCurrentFilters)[0] || entities[0];
      if (!entity) {
        $("entityKpis").innerHTML = `<div class="empty">暂无研究对象</div>`;
        ["entityCoverageChart", "entityBrokerChart", "entityScoreChart", "entityTargetChart", "entityEpsChart", "entityBrokerMix", "entityThemeMix"].forEach((id) => $(id).innerHTML = `<div class="empty">暂无数据</div>`);
        $("entityOpinionTable").innerHTML = `<tbody><tr><td><div class="empty">暂无连续观点记录</div></td></tr></tbody>`;
        $("entityReportTable").innerHTML = `<tbody><tr><td><div class="empty">暂无研报</div></td></tr></tbody>`;
        return;
      }
      if (!state.entityKey && $("entitySelect").value !== "") $("entitySelect").value = "";
      const summary = entity.opinionSummary || {};
      const kpis = [
        ["对象", entity.label, entity.entityType === "company" ? entity.stockCode || "公司" : "行业"],
        ["覆盖", entity.reportCount, `${entity.firstDate || "-"} → ${entity.latestDate || "-"}`],
        ["券商", entity.brokerCount, "不同机构"],
        ["均分", entity.avgScore, "signalScore"],
        ["热点", entity.hotspotLevel || "-", (entity.reasonCodes || []).join(" | ") || "无"],
        ["观点", summary.trendCount || 0, `目标 ${directionSummary(summary.target)} / EPS ${directionSummary(summary.eps)}`],
      ];
      $("entityKpis").innerHTML = kpis.map(([label, value, sub]) => `<div class="detail-kpi"><div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(value)}</div><div class="sub muted">${escapeHtml(sub)}</div></div>`).join("");
      drawLine("entityCoverageChart", entity.coverageByDay || [], "var(--blue)");
      drawLine("entityBrokerChart", rowsWithDateNames(entity.brokerByDay), "var(--teal)");
      drawLine("entityScoreChart", rowsWithDateNames(entity.scoreByDay), "var(--green)");
      drawLine("entityTargetChart", rowsWithDateNames(entity.targetTimeline), "var(--amber)");
      drawLine("entityEpsChart", rowsWithDateNames(entity.epsTimeline), "var(--rose)");
      drawBar("entityBrokerMix", entity.topBrokers || [], "var(--teal)");
      drawBar("entityThemeMix", entity.topThemes || [], "var(--amber)");
      renderEntityOpinion(entity);
      renderEntityTable(entity);
    }
    function bindEntityButtons() {
      document.querySelectorAll("[data-entity-key]").forEach((button) => {
        button.addEventListener("click", () => {
          $("entitySelect").value = button.dataset.entityKey || "";
          render();
          $("drilldownCard").scrollIntoView({ behavior: "smooth", block: "start" });
        });
      });
    }
    function pill(value) {
      const lower = String(value || "").toLowerCase();
      const cls = lower === "strong" ? "strong" : lower === "hot" ? "hot" : lower === "watch" ? "watch" : lower === "a" ? "a" : lower === "b" ? "b" : lower === "up" ? "up" : lower === "down" ? "down" : lower === "flat" ? "flat" : "";
      return `<span class="pill ${cls}">${escapeHtml(value || "-")}</span>`;
    }
    function renderHotspots(rows) {
      const limited = rows.sort((a, b) => (levelRank[a.hotspotLevel] ?? 9) - (levelRank[b.hotspotLevel] ?? 9) || b.coverage30d - a.coverage30d).slice(0, 120);
      if (!limited.length) { $("hotspotTable").innerHTML = `<tbody><tr><td><div class="empty">暂无热点信号</div></td></tr></tbody>`; return; }
      $("hotspotTable").innerHTML = `<thead><tr><th>标的</th><th>等级</th><th>行业</th><th>30日/7日</th><th>券商</th><th>加速</th><th>买入比</th><th>原因</th><th>操作</th></tr></thead><tbody>
        ${limited.map((row) => {
          const entityKey = entityKeyForHotspot(row);
          return `<tr>
          <td><strong>${escapeHtml(row.entityName)}</strong><div class="muted">${escapeHtml(row.stockCode || row.entityType)}</div></td>
          <td>${pill(row.hotspotLevel)}</td>
          <td>${escapeHtml(row.industryName)}</td>
          <td>${row.coverage30d} / ${row.coverage7d}</td>
          <td>${row.brokerCount30d}<div class="muted">新增 ${row.newBrokerCount30d}</div></td>
          <td>${row.coverageAcceleration}</td>
          <td>${Math.round((row.buyRatio || 0) * 100)}%</td>
          <td><div class="tags">${(row.reasonCodes || []).map((x) => `<span class="pill">${escapeHtml(x)}</span>`).join("")}</div><div class="muted">${escapeHtml((row.reasons || []).join("；"))}</div></td>
          <td>${entityKey ? `<button type="button" class="link-button" data-entity-key="${escapeAttr(entityKey)}">查看</button>` : `<span class="muted">-</span>`}</td>
        </tr>`;
        }).join("")}
      </tbody>`;
    }
    function renderOpinion(rows) {
      const filtered = (DATA.opinionTrends || []).filter((row) => inDate(row.latestDate)
        && (!state.company || row.stockName === state.company || row.stockCode === state.company)
        && (!state.industry || row.industryName === state.industry)
        && (!state.broker || row.orgName === state.broker));
      if (!filtered.length) { $("opinionTable").innerHTML = `<tbody><tr><td><div class="empty">暂无连续观点记录</div></td></tr></tbody>`; return; }
      $("opinionTable").innerHTML = `<thead><tr><th>标的</th><th>券商</th><th>日期</th><th>评级</th><th>目标价</th><th>EPS</th><th>分数</th><th>次数</th><th>操作</th></tr></thead><tbody>
        ${filtered.slice(0, 120).map((row) => {
          const entityKey = entityKeyForReport(row);
          return `<tr>
          <td><strong>${escapeHtml(row.stockName)}</strong><div class="muted">${escapeHtml(row.stockCode || row.industryName)}</div></td>
          <td>${escapeHtml(row.orgName)}</td>
          <td>${escapeHtml(row.previousDate)} → ${escapeHtml(row.latestDate)}</td>
          <td>${escapeHtml(row.previousRating || "-")} → ${escapeHtml(row.latestRating || "-")}<div class="muted">${escapeHtml(row.ratingChange || "")}</div></td>
          <td>${escapeHtml(row.previousTargetPrice || "-")} → ${escapeHtml(row.latestTargetPrice || "-")} ${pill(row.targetDirection)}</td>
          <td>${escapeHtml(row.previousEps || "-")} → ${escapeHtml(row.latestEps || "-")} ${pill(row.epsDirection)}</td>
          <td>${row.previousScore} → ${row.latestScore} ${pill(row.scoreDirection)}</td>
          <td>${row.count}</td>
          <td>${entityKey ? `<button type="button" class="link-button" data-entity-key="${escapeAttr(entityKey)}">查看</button>` : `<span class="muted">-</span>`}</td>
        </tr>`;
        }).join("")}
      </tbody>`;
    }
    function renderReports(rows) {
      const limited = [...rows].sort((a, b) => String(b.date).localeCompare(String(a.date)) || Number(b.signalScore || 0) - Number(a.signalScore || 0)).slice(0, 400);
      if (!limited.length) { $("reportTable").innerHTML = `<tbody><tr><td><div class="empty">暂无研报明细</div></td></tr></tbody>`; return; }
      $("reportTable").innerHTML = `<thead><tr><th>日期</th><th>标的</th><th>券商</th><th>评级</th><th>分数</th><th>主题</th><th>摘要</th><th>文件</th><th>操作</th></tr></thead><tbody>
        ${limited.map((row) => {
          const entityKey = entityKeyForReport(row);
          return `<tr>
          <td>${escapeHtml(row.date)}</td>
          <td><strong>${escapeHtml(row.stockName || row.industryName)}</strong><div class="muted">${escapeHtml(row.stockCode || row.industryName)}</div></td>
          <td>${escapeHtml(row.orgName)}</td>
          <td>${escapeHtml(row.rating || "-")}</td>
          <td>${pill(row.priorityBucket)} <strong>${row.signalScore}</strong><div class="muted">Q ${row.qualityScore}</div></td>
          <td><div class="tags">${(row.themeTags || []).slice(0, 5).map((x) => `<span class="pill">${escapeHtml(x)}</span>`).join("")}</div></td>
          <td class="summary">${escapeHtml(row.summary || row.title || "")}</td>
          <td>${row.fileHref ? `<a href="${escapeAttr(row.fileHref)}">${escapeHtml(row.file || "打开")}</a>` : `<span class="muted">-</span>`}</td>
          <td>${entityKey ? `<button type="button" class="link-button" data-entity-key="${escapeAttr(entityKey)}">查看</button>` : `<span class="muted">-</span>`}</td>
        </tr>`;
        }).join("")}
      </tbody>`;
    }
    function render() {
      readState();
      const reports = (DATA.reports || []).filter(reportMatches);
      const hotspots = (DATA.hotspots || []).filter(hotspotMatches);
      renderKpis(reports, hotspots);
      drawLine("reportTrend", seriesByDay(reports, (r) => r.date), "var(--blue)");
      drawLine("brokerTrend", seriesByDay(reports, (r) => r.date, (r) => r.orgName), "var(--teal)");
      drawBar("industryChart", countBy(reports, (r) => r.industryName, 10), "var(--amber)");
      drawBar("themeChart", countTokens(reports, (r) => r.themeTags, 10), "var(--teal)");
      drawBar("reasonChart", countTokens(hotspots, (r) => r.reasonCodes, 10), "var(--rose)");
      drawBar("qualityChart", countBy(reports, (r) => r.status || "unknown", 8), "var(--green)");
      drawBar("sourceChart", countBy(reports, (r) => r.source || "unknown", 8), "var(--blue)");
      renderDrilldown();
      renderHotspots(hotspots);
      renderOpinion(reports);
      renderReports(reports);
      bindEntityButtons();
      $("footer").textContent = `显示 ${reports.length} 篇研报，${hotspots.length} 条热点信号，索引文件 ${DATA.meta.reportIndexCount || 0} 个`;
    }
    initFilters();
    render();
  </script>
</body>
</html>
"""
