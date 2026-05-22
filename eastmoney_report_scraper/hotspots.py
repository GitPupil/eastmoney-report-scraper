"""Hotspot detection from historical broker coverage records."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .constants import DEFAULT_HOTSPOT_DASHBOARD_NAME, DEFAULT_HOTSPOT_SIGNALS_NAME

SIGNAL_FIELDS = [
    "entityType",
    "entityName",
    "stockCode",
    "industryName",
    "hotspotLevel",
    "isFirstCoverage",
    "isReactivatedCoverage",
    "coverage7d",
    "coverage30d",
    "previous30dCoverage",
    "coverageAcceleration",
    "brokerCount30d",
    "newBrokerCount30d",
    "ratingDistribution",
    "buyRatio",
    "latestPublishDate",
    "reasons",
    "reasonCodes",
    "coveredCompanyCount30d",
]

FIRST_COVERAGE = "FIRST_COVERAGE"
REACTIVATED_COVERAGE = "REACTIVATED_COVERAGE"
MULTI_BROKER = "MULTI_BROKER"
COVERAGE_ACCELERATION = "COVERAGE_ACCELERATION"
INDUSTRY_RESONANCE = "INDUSTRY_RESONANCE"
HIGH_BUY_RATIO = "HIGH_BUY_RATIO"


@dataclass(frozen=True)
class HotspotConfig:
    recent_days: int = 30
    short_days: int = 7
    silent_days: int = 90
    multi_broker_threshold: int = 3
    hot_coverage_threshold: int = 3


def parse_publish_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text[:10].replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _split_tags(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        separators = ["|", "；", ";", "，", ","]
        tags = [value]
        for separator in separators:
            tags = [part for tag in tags for part in tag.split(separator)]
        return [tag.strip() for tag in tags if tag.strip()]
    return []


def normalize_broker_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", "", text).strip()


def _entry_values(entries: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(entries, dict):
        return entries.values()
    return entries


def normalize_coverage_entries(entries: Any) -> List[Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    for raw in _entry_values(entries):
        info_code = str(raw.get("infoCode") or "").strip()
        stock_code = str(raw.get("stockCode") or "").strip()
        stock_name = str(raw.get("stockName") or "").strip()
        industry_name = str(raw.get("industryName") or raw.get("indvInduName") or "").strip()
        if not info_code or not (stock_code or stock_name or industry_name):
            continue
        report_type = str(raw.get("reportType") or "").strip()
        if report_type not in {"stock", "industry"}:
            report_type = "stock" if stock_code or stock_name else "industry"
        normalized[info_code] = {
            "infoCode": info_code,
            "reportType": report_type,
            "stockCode": stock_code,
            "stockName": stock_name,
            "industryName": industry_name,
            "orgName": normalize_broker_name(raw.get("orgName") or raw.get("orgSName") or ""),
            "rating": str(raw.get("rating") or raw.get("emRatingName") or raw.get("sRatingName") or "").strip(),
            "publishDate": str(raw.get("publishDate") or "").strip(),
            "title": str(raw.get("title") or "").strip(),
            "themeTags": _split_tags(raw.get("themeTags")),
            "signalScore": raw.get("signalScore", raw.get("signal_score", "")),
            "priorityBucket": str(raw.get("priorityBucket") or raw.get("priority_bucket") or "").strip(),
        }
    return list(normalized.values())


def _dated_entries(entries: Sequence[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], date]]:
    dated = []
    for entry in entries:
        publish_date = parse_publish_date(entry.get("publishDate"))
        if publish_date:
            dated.append((entry, publish_date))
    return dated


def _reference_date(dated: Sequence[Tuple[Dict[str, Any], date]], as_of: Optional[date]) -> date:
    if as_of:
        return as_of
    if dated:
        return max(publish_date for _, publish_date in dated)
    return date.today()


def _in_window(publish_date: date, start: date, end: date) -> bool:
    return start <= publish_date <= end


def _distinct_count(entries: Sequence[Dict[str, Any]], field: str) -> int:
    return len({str(entry.get(field) or "").strip() for entry in entries if str(entry.get(field) or "").strip()})


def _rating_distribution(entries: Sequence[Dict[str, Any]]) -> str:
    counter = Counter(str(entry.get("rating") or "").strip() or "未标注" for entry in entries)
    if not counter:
        return ""
    return json.dumps(dict(sorted(counter.items())), ensure_ascii=False)


def _buy_ratio(entries: Sequence[Dict[str, Any]]) -> float:
    ratings = [str(entry.get("rating") or "").strip() for entry in entries if str(entry.get("rating") or "").strip()]
    if not ratings:
        return 0.0
    buy_count = sum(1 for rating in ratings if any(token in rating for token in ("买入", "推荐", "强烈推荐")))
    return round(buy_count / len(ratings), 4)


def _dominant_value(entries: Sequence[Dict[str, Any]], field: str) -> str:
    counter = Counter(str(entry.get(field) or "").strip() for entry in entries if str(entry.get(field) or "").strip())
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def _recent_metrics(
    dated_entries: Sequence[Tuple[Dict[str, Any], date]],
    config: HotspotConfig,
    as_of: date,
) -> Dict[str, Any]:
    recent_start = as_of - timedelta(days=max(config.recent_days, 1) - 1)
    short_start = as_of - timedelta(days=max(config.short_days, 1) - 1)
    previous_start = recent_start - timedelta(days=max(config.recent_days, 1))

    recent = [entry for entry, publish_date in dated_entries if _in_window(publish_date, recent_start, as_of)]
    short = [entry for entry, publish_date in dated_entries if _in_window(publish_date, short_start, as_of)]
    previous = [entry for entry, publish_date in dated_entries if previous_start <= publish_date < recent_start]
    before_recent = [entry for entry, publish_date in dated_entries if publish_date < recent_start]

    recent_dates = [publish_date for _, publish_date in dated_entries if _in_window(publish_date, recent_start, as_of)]
    first_recent_date = min(recent_dates) if recent_dates else None
    is_first = False
    is_reactivated = False
    if first_recent_date:
        is_first = not any(publish_date < first_recent_date for _, publish_date in dated_entries)
        silent_start = first_recent_date - timedelta(days=max(config.silent_days, 1))
        has_older_coverage = any(publish_date < silent_start for _, publish_date in dated_entries)
        has_silent_window_coverage = any(silent_start <= publish_date < first_recent_date for _, publish_date in dated_entries)
        is_reactivated = has_older_coverage and not has_silent_window_coverage

    broker_count = _distinct_count(recent, "orgName")
    previous_brokers = {entry.get("orgName") for entry in before_recent if entry.get("orgName")}
    recent_brokers = {entry.get("orgName") for entry in recent if entry.get("orgName")}
    latest_date = max(recent_dates).isoformat() if recent_dates else ""
    coverage_30d = len(recent)
    previous_30d = len(previous)

    return {
        "recent": recent,
        "short": short,
        "previous": previous,
        "coverage7d": len(short),
        "coverage30d": coverage_30d,
        "previous30dCoverage": previous_30d,
        "coverageAcceleration": coverage_30d - previous_30d,
        "brokerCount30d": broker_count,
        "newBrokerCount30d": len(recent_brokers - previous_brokers),
        "ratingDistribution": _rating_distribution(recent),
        "buyRatio": _buy_ratio(recent),
        "latestPublishDate": latest_date,
        "isFirstCoverage": is_first,
        "isReactivatedCoverage": is_reactivated,
    }


def _level_from_reasons(reasons: List[str], active: bool, hot: bool, strong: bool) -> str:
    if strong:
        return "STRONG"
    if hot:
        return "HOT"
    if active or reasons:
        return "WATCH"
    return "NONE"


def _industry_signal(
    industry_name: str,
    dated_entries: Sequence[Tuple[Dict[str, Any], date]],
    config: HotspotConfig,
    as_of: date,
) -> Dict[str, Any]:
    metrics = _recent_metrics(dated_entries, config, as_of)
    recent = metrics["recent"]
    covered_companies = {
        entry.get("stockCode") or entry.get("stockName")
        for entry in recent
        if entry.get("stockCode") or entry.get("stockName")
    }
    hot = (
        metrics["coverage30d"] >= config.hot_coverage_threshold
        or metrics["brokerCount30d"] >= config.multi_broker_threshold
        or metrics["coverageAcceleration"] >= 2
    )
    strong = hot and metrics["brokerCount30d"] >= config.multi_broker_threshold and len(covered_companies) >= config.hot_coverage_threshold

    reasons: List[str] = []
    reason_codes: List[str] = []
    if metrics["isFirstCoverage"]:
        reasons.append("近期首次覆盖行业")
        reason_codes.append(FIRST_COVERAGE)
    if metrics["isReactivatedCoverage"]:
        reasons.append(f"{config.silent_days}日沉寂后再覆盖")
        reason_codes.append(REACTIVATED_COVERAGE)
    if metrics["coverage30d"] >= config.hot_coverage_threshold:
        reasons.append(f"{config.recent_days}日覆盖{metrics['coverage30d']}篇")
    if metrics["brokerCount30d"] >= config.multi_broker_threshold:
        reasons.append(f"{config.recent_days}日{metrics['brokerCount30d']}家券商覆盖")
        reason_codes.append(MULTI_BROKER)
    if metrics["coverageAcceleration"] >= 2:
        reasons.append(f"覆盖加速+{metrics['coverageAcceleration']}")
        reason_codes.append(COVERAGE_ACCELERATION)
    if metrics["buyRatio"] >= 0.6 and metrics["coverage30d"] >= 2:
        reasons.append(f"买入类评级占比{metrics['buyRatio']:.0%}")
        reason_codes.append(HIGH_BUY_RATIO)
    if covered_companies:
        reasons.append(f"覆盖{len(covered_companies)}家公司")

    return {
        "entityType": "industry",
        "entityName": industry_name,
        "stockCode": "",
        "industryName": industry_name,
        "hotspotLevel": _level_from_reasons(reasons, bool(recent), hot, strong),
        "coveredCompanyCount30d": len(covered_companies),
        "reasons": reasons,
        "reasonCodes": reason_codes,
        **{key: value for key, value in metrics.items() if key not in {"recent", "short", "previous"}},
    }


def _company_signal(
    stock_key: str,
    dated_entries: Sequence[Tuple[Dict[str, Any], date]],
    industry_levels: Dict[str, str],
    config: HotspotConfig,
    as_of: date,
) -> Dict[str, Any]:
    metrics = _recent_metrics(dated_entries, config, as_of)
    recent = metrics["recent"]
    all_entries = [entry for entry, _ in dated_entries]
    source_entries = recent or all_entries
    stock_name = _dominant_value(source_entries, "stockName") or stock_key
    stock_code = _dominant_value(source_entries, "stockCode")
    industry_name = _dominant_value(source_entries, "industryName")
    industry_level = industry_levels.get(industry_name, "NONE")
    industry_hot = industry_level in {"HOT", "STRONG"}

    hot = (
        metrics["coverage30d"] >= config.hot_coverage_threshold
        or metrics["brokerCount30d"] >= config.multi_broker_threshold
        or metrics["coverageAcceleration"] >= 2
    )
    strong = (
        (metrics["isFirstCoverage"] or metrics["isReactivatedCoverage"]) and metrics["brokerCount30d"] >= config.multi_broker_threshold
    ) or (hot and industry_hot)

    reasons: List[str] = []
    reason_codes: List[str] = []
    if metrics["isFirstCoverage"]:
        reasons.append("近期首次被覆盖")
        reason_codes.append(FIRST_COVERAGE)
    if metrics["isReactivatedCoverage"]:
        reasons.append(f"{config.silent_days}日沉寂后再覆盖")
        reason_codes.append(REACTIVATED_COVERAGE)
    if metrics["coverage30d"] >= config.hot_coverage_threshold:
        reasons.append(f"{config.recent_days}日覆盖{metrics['coverage30d']}篇")
    if metrics["brokerCount30d"] >= config.multi_broker_threshold:
        reasons.append(f"{config.recent_days}日{metrics['brokerCount30d']}家券商覆盖")
        reason_codes.append(MULTI_BROKER)
    if metrics["newBrokerCount30d"] > 0:
        reasons.append(f"新增{metrics['newBrokerCount30d']}家券商")
    if metrics["coverageAcceleration"] >= 2:
        reasons.append(f"覆盖加速+{metrics['coverageAcceleration']}")
        reason_codes.append(COVERAGE_ACCELERATION)
    if industry_hot:
        reasons.append(f"个股与行业同时升温（行业={industry_level}）")
        reason_codes.append(INDUSTRY_RESONANCE)
    if metrics["buyRatio"] >= 0.6 and metrics["coverage30d"] >= 2:
        reasons.append(f"买入类评级占比{metrics['buyRatio']:.0%}")
        reason_codes.append(HIGH_BUY_RATIO)

    return {
        "entityType": "company",
        "entityName": stock_name,
        "stockCode": stock_code,
        "industryName": industry_name,
        "industryHotspotLevel": industry_level,
        "hotspotLevel": _level_from_reasons(reasons, bool(recent), hot, strong),
        "reasons": reasons,
        "reasonCodes": reason_codes,
        **{key: value for key, value in metrics.items() if key not in {"recent", "short", "previous"}},
    }


def calculate_hotspot_signals(
    entries: Any,
    config: Optional[HotspotConfig] = None,
    as_of: Optional[date] = None,
) -> List[Dict[str, Any]]:
    config = config or HotspotConfig()
    normalized = normalize_coverage_entries(entries)
    dated = _dated_entries(normalized)
    reference = _reference_date(dated, as_of)

    industry_groups: Dict[str, List[Tuple[Dict[str, Any], date]]] = {}
    company_groups: Dict[str, List[Tuple[Dict[str, Any], date]]] = {}
    for entry, publish_date in dated:
        industry_name = entry.get("industryName") or ""
        if industry_name:
            industry_groups.setdefault(industry_name, []).append((entry, publish_date))
        stock_key = entry.get("stockCode") or entry.get("stockName") or ""
        if stock_key:
            company_groups.setdefault(stock_key, []).append((entry, publish_date))

    industry_signals = [
        _industry_signal(industry_name, industry_entries, config, reference)
        for industry_name, industry_entries in industry_groups.items()
    ]
    industry_levels = {signal["industryName"]: signal["hotspotLevel"] for signal in industry_signals}
    company_signals = [
        _company_signal(stock_key, company_entries, industry_levels, config, reference)
        for stock_key, company_entries in company_groups.items()
    ]
    signals = [signal for signal in company_signals + industry_signals if signal["hotspotLevel"] != "NONE"]
    return sorted(
        signals,
        key=lambda signal: (
            {"STRONG": 0, "HOT": 1, "WATCH": 2, "NONE": 3}.get(signal["hotspotLevel"], 4),
            -int(signal.get("coverage30d") or 0),
            -int(signal.get("brokerCount30d") or 0),
            signal.get("entityType") or "",
            signal.get("entityName") or "",
        ),
    )


def _csv_row(signal: Dict[str, Any]) -> Dict[str, Any]:
    row = {field: signal.get(field, "") for field in SIGNAL_FIELDS}
    row["isFirstCoverage"] = "true" if signal.get("isFirstCoverage") else "false"
    row["isReactivatedCoverage"] = "true" if signal.get("isReactivatedCoverage") else "false"
    row["buyRatio"] = f"{float(signal.get('buyRatio') or 0):.4f}"
    row["reasons"] = "；".join(signal.get("reasons") or [])
    row["reasonCodes"] = "|".join(signal.get("reasonCodes") or [])
    return row


def write_hotspot_signals_csv(path: Path, signals: Sequence[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SIGNAL_FIELDS)
        writer.writeheader()
        for signal in signals:
            writer.writerow(_csv_row(signal))


def _top(signals: Sequence[Dict[str, Any]], predicate: Any, key: Any, limit: int = 10) -> List[Dict[str, Any]]:
    return sorted([signal for signal in signals if predicate(signal)], key=key, reverse=True)[:limit]


def _format_signal_line(signal: Dict[str, Any]) -> str:
    code = f" `{signal.get('stockCode')}`" if signal.get("stockCode") else ""
    industry = f"，行业={signal.get('industryName')}" if signal.get("entityType") == "company" and signal.get("industryName") else ""
    industry_level = f"/{signal.get('industryHotspotLevel')}" if signal.get("industryHotspotLevel") else ""
    new_brokers = f"，新增券商={signal.get('newBrokerCount30d')}" if int(signal.get("newBrokerCount30d") or 0) else ""
    reasons = "；".join(signal.get("reasons") or []) or "近期有覆盖"
    return (
        f"- `{signal.get('entityName')}`{code}：{signal.get('hotspotLevel')}，"
        f"{signal.get('coverage30d')}篇/{signal.get('brokerCount30d')}家{new_brokers}{industry}{industry_level}，{reasons}"
    )


def _append_section(lines: List[str], title: str, signals: Sequence[Dict[str, Any]]) -> None:
    lines.extend(["", f"## {title}", ""])
    if signals:
        lines.extend(_format_signal_line(signal) for signal in signals)
    else:
        lines.append("- [暂无样本]")


def build_hotspot_dashboard(signals: Sequence[Dict[str, Any]], config: HotspotConfig, as_of: Optional[date] = None) -> str:
    signal_list = list(signals)
    reference = as_of or parse_publish_date(max((signal.get("latestPublishDate") or "" for signal in signal_list), default="")) or date.today()
    companies = [signal for signal in signal_list if signal.get("entityType") == "company"]
    industries = [signal for signal in signal_list if signal.get("entityType") == "industry"]

    new_companies = _top(
        companies,
        lambda signal: bool(signal.get("isFirstCoverage")),
        lambda signal: (int(signal.get("brokerCount30d") or 0), int(signal.get("coverage30d") or 0)),
    )
    reactivated = _top(
        companies,
        lambda signal: bool(signal.get("isReactivatedCoverage")),
        lambda signal: (int(signal.get("brokerCount30d") or 0), int(signal.get("coverage30d") or 0)),
    )
    multi_broker = _top(
        companies,
        lambda signal: int(signal.get("brokerCount30d") or 0) >= config.multi_broker_threshold,
        lambda signal: (int(signal.get("brokerCount30d") or 0), int(signal.get("coverage30d") or 0)),
    )
    industry_heat = _top(
        industries,
        lambda signal: int(signal.get("coverage30d") or 0) > 0,
        lambda signal: (
            int(signal.get("coverage30d") or 0),
            int(signal.get("brokerCount30d") or 0),
            int(signal.get("coveredCompanyCount30d") or 0),
        ),
    )
    resonance = _top(
        companies,
        lambda signal: INDUSTRY_RESONANCE in (signal.get("reasonCodes") or []),
        lambda signal: (int(signal.get("coverage30d") or 0), int(signal.get("brokerCount30d") or 0)),
    )
    buy_concentration = _top(
        companies,
        lambda signal: float(signal.get("buyRatio") or 0) >= 0.6 and int(signal.get("coverage30d") or 0) >= 2,
        lambda signal: (float(signal.get("buyRatio") or 0), int(signal.get("coverage30d") or 0)),
    )
    acceleration = _top(
        companies + industries,
        lambda signal: int(signal.get("coverageAcceleration") or 0) > 0,
        lambda signal: (int(signal.get("coverageAcceleration") or 0), int(signal.get("coverage7d") or 0)),
    )

    lines = [
        "# HOTSPOT_DASHBOARD",
        "",
        f"- 观察截止日：`{reference.isoformat()}`",
        f"- 短窗口：`{config.short_days}` 日 | 主窗口：`{config.recent_days}` 日 | 沉寂窗口：`{config.silent_days}` 日",
        f"- 多券商阈值：`{config.multi_broker_threshold}` | 覆盖热度阈值：`{config.hot_coverage_threshold}`",
        f"- 热点信号数：`{len(signal_list)}` | 公司：`{len(companies)}` | 行业：`{len(industries)}`",
    ]
    _append_section(lines, "新增覆盖公司", new_companies)
    _append_section(lines, "沉寂后再覆盖", reactivated)
    _append_section(lines, "多券商集中覆盖", multi_broker)
    _append_section(lines, "行业热度排名", industry_heat)
    _append_section(lines, "个股-行业共振", resonance)
    _append_section(lines, "高买入评级集中", buy_concentration)
    _append_section(lines, "近7日加速排名", acceleration)
    return "\n".join(lines) + "\n"


def write_hotspot_outputs(
    output_root: Path,
    entries: Any,
    config: Optional[HotspotConfig] = None,
    as_of: Optional[date] = None,
) -> Tuple[Path, Path]:
    config = config or HotspotConfig()
    signals = calculate_hotspot_signals(entries, config=config, as_of=as_of)
    signals_path = output_root / DEFAULT_HOTSPOT_SIGNALS_NAME
    dashboard_path = output_root / DEFAULT_HOTSPOT_DASHBOARD_NAME
    output_root.mkdir(parents=True, exist_ok=True)
    write_hotspot_signals_csv(signals_path, signals)
    dashboard_path.write_text(build_hotspot_dashboard(signals, config, as_of=as_of), encoding="utf-8")
    return signals_path, dashboard_path
