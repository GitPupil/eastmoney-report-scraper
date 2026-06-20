"""CLI orchestration for the Eastmoney report scraper."""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .analysis import build_structured_analysis, extract_summary
from .client import fetch_report_list, http_get_with_retry
from .constants import (
    DEFAULT_COVERAGE_HISTORY_NAME,
    DEFAULT_DASHBOARD_NAME,
    DEFAULT_MANIFEST_NAME,
    DEFAULT_OUTPUT_ROOT,
    DETAIL_URL_TEMPLATE,
)
from .dashboard import write_dashboard
from .exporters import build_markdown, read_coverage_history, update_coverage_history, write_day_summary, write_range_summary
from .hotspots import HotspotConfig, write_hotspot_outputs
from .models import DayRun, FetchResult
from .parser import extract_pdf_text, extract_pdf_url, extract_report_text, text_quality
from .utils import log_event, sanitize_filename


def emit_result_progress(target_date: str, idx: int, item: Dict[str, Any], result: FetchResult) -> None:
    print(
        json.dumps(
            {
                "date": target_date,
                "idx": idx,
                "stockName": item.get("stockName") or item.get("industryName"),
                "title": item.get("title"),
                "infoCode": item.get("infoCode"),
                "status": result.status,
                "source": result.source,
                "skipped": result.skipped,
                "chars": len(result.text),
                "qualityScore": result.quality_score,
                "summary": result.summary[:2],
                "file": str(result.output_path) if result.output_path else None,
                "error": result.error,
            },
            ensure_ascii=False,
        )
    )


def daterange(start_date: date, end_date: date) -> List[str]:
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")
    days = (end_date - start_date).days
    return [(start_date + timedelta(days=offset)).isoformat() for offset in range(days + 1)]


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def resolve_dates(args: argparse.Namespace) -> List[str]:
    if args.date:
        return [args.date]
    if args.start_date and args.end_date:
        return daterange(parse_date(args.start_date), parse_date(args.end_date))
    raise ValueError("Provide either --date or both --start-date and --end-date")


def matches_filter(value: str, patterns: Sequence[str]) -> bool:
    if not patterns:
        return True
    haystack = (value or "").lower()
    return any(pattern.lower() in haystack for pattern in patterns)


def filter_items(items: List[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for item in items:
        stock_target = f"{item.get('stockName', '')} {item.get('stockCode', '')}"
        org_target = f"{item.get('orgSName', '')} {item.get('orgName', '')}"
        rating_target = f"{item.get('emRatingName', '')} {item.get('sRatingName', '')}"
        industry_target = f"{item.get('industryName', '')} {item.get('indvInduName', '')}"
        if not matches_filter(stock_target, args.stock_filters):
            continue
        if not matches_filter(org_target, args.org_filters):
            continue
        if not matches_filter(rating_target, args.rating_filters):
            continue
        if not matches_filter(industry_target, args.industry_filters):
            continue
        filtered.append(item)
    return filtered


def existing_markdown_map(output_dir: Path) -> Dict[str, Path]:
    mapping: Dict[str, Path] = {}
    ignored = {
        "README.md",
        "SUMMARY.md",
        "ANALYSIS_INPUT.md",
        "RANGE_SUMMARY.md",
        "DAILY_BRIEF.md",
        "TOP_SIGNALS.md",
        "SECTOR_BRIEF.md",
        "THEME_BRIEF.md",
        "TRADING_DASHBOARD.md",
        "CONSENSUS_BRIEF.md",
    }
    for path in output_dir.glob("*.md"):
        if path.name in ignored:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        match = re.search(r"- infoCode：`([^`]+)`", content)
        if match:
            mapping[match.group(1)] = path
    return mapping


def read_manifest(manifest_path: Path) -> Dict[str, Dict[str, Any]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    if not manifest_path.exists():
        return mapping
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            info_code = entry.get("infoCode")
            if info_code:
                mapping[info_code] = entry
    return mapping


def select_resume_error_items(items: List[Dict[str, Any]], manifest_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        item
        for item in items
        if (manifest_map.get(item.get("infoCode", "")) or {}).get("status") == "error"
    ]


def append_manifest_entry(manifest_path: Path, target_date: str, idx: int, result: FetchResult) -> None:
    item = result.item
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "date": target_date,
        "idx": idx,
        "infoCode": item.get("infoCode"),
        "stockName": item.get("stockName"),
        "stockCode": item.get("stockCode"),
        "industryName": item.get("industryName") or item.get("indvInduName"),
        "title": item.get("title"),
        "orgName": item.get("orgSName") or item.get("orgName"),
        "status": result.status,
        "source": result.source,
        "chars": len(result.text),
        "qualityScore": result.quality_score,
        "skipped": result.skipped,
        "file": result.output_path.name if result.output_path else None,
        "error": result.error,
    }
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_existing_result(item: Dict[str, Any], existing_path: Path, log_path: Path) -> FetchResult:
    info_code = item.get("infoCode", "")
    content = existing_path.read_text(encoding="utf-8")
    body = content.split("\n---\n", 1)[-1].strip() if "\n---\n" in content else content
    summary_block = ""
    match = re.search(r"## 自动摘要\n\n(.*?)\n\n## 结构化分析", content, re.S)
    if not match:
        match = re.search(r"## 自动摘要\n\n(.*?)\n\n---\n", content, re.S)
    if match:
        summary_block = match.group(1)
    summary_lines = [line[2:].strip() for line in summary_block.splitlines() if line.startswith("- ")]
    quality_score = text_quality(body).score
    log_event(log_path, "info", "resume_skip", infoCode=info_code, file=str(existing_path))
    return FetchResult(
        item=item,
        status="ok" if len(body) >= 80 else "weak",
        text=body,
        summary=summary_lines[:5],
        output_path=existing_path,
        source="resume",
        quality_score=quality_score,
        skipped=True,
        structured_analysis=build_structured_analysis(item, body, summary_lines[:5]),
    )


def _should_try_pdf(html_text: str, html_score: int, min_text_length: int) -> bool:
    return len(html_text) < min_text_length or html_score < 70


def fetch_detail(
    item: Dict[str, Any],
    output_dir: Path,
    index: int,
    timeout: int,
    retries: int,
    retry_delay: float,
    log_path: Path,
    resume_map: Dict[str, Path],
    manifest_map: Dict[str, Dict[str, Any]],
    force: bool,
    use_pdf_fallback: bool,
    min_text_length: int,
    refresh_weak: bool,
    resume_errors_only: bool,
) -> FetchResult:
    info_code = item.get("infoCode", "")
    detail_url = DETAIL_URL_TEMPLATE.format(info_code=info_code)
    manifest_entry = manifest_map.get(info_code) or {}

    if not force and info_code in resume_map:
        manifest_status = manifest_entry.get("status")
        should_refetch = False
        if refresh_weak and manifest_status == "weak":
            should_refetch = True
        if resume_errors_only and manifest_status == "error":
            should_refetch = True
        if not should_refetch:
            try:
                return _read_existing_result(item, resume_map[info_code], log_path)
            except Exception as exc:
                log_event(log_path, "warn", "resume_read_failed", infoCode=info_code, error=repr(exc))

    if resume_errors_only and manifest_entry and manifest_entry.get("status") != "error" and info_code not in resume_map:
        return FetchResult(item=item, status="ok", text="", summary=[], output_path=None, source="manifest", skipped=True)

    try:
        html = http_get_with_retry(detail_url, timeout, retries, retry_delay, log_path, f"detail_{info_code}")
        html_text = extract_report_text(html)
        html_quality = text_quality(html_text)
        text = html_text
        source = "html"
        quality_score = html_quality.score

        if use_pdf_fallback and _should_try_pdf(html_text, html_quality.score, min_text_length):
            pdf_url = extract_pdf_url(html, info_code)
            pdf_text = extract_pdf_text(pdf_url, timeout, log_path)
            pdf_quality = text_quality(pdf_text)
            if pdf_quality.score > html_quality.score:
                text = pdf_text
                source = "pdf"
                quality_score = pdf_quality.score
                log_event(log_path, "info", "pdf_fallback_used", infoCode=info_code, pdf_url=pdf_url, htmlQuality=html_quality.score, pdfQuality=pdf_quality.score)
            else:
                log_event(log_path, "warn", "pdf_fallback_weaker", infoCode=info_code, pdf_url=pdf_url, htmlQuality=html_quality.score, pdfQuality=pdf_quality.score)

        summary = extract_summary(text)
        status = "ok" if len(text) >= min_text_length and quality_score >= 40 else "weak"
        stock_label = item.get("stockName") or item.get("industryName") or "未知标的"
        file_name = f"{index:03d}——{sanitize_filename(stock_label)}——{sanitize_filename(item.get('title') or info_code)}.md"
        output_path = output_dir / file_name
        structured_analysis = build_structured_analysis(item, text, summary)
        output_path.write_text(build_markdown(item, text, summary, source, quality_score), encoding="utf-8")
        return FetchResult(
            item=item,
            status=status,
            text=text,
            summary=summary,
            output_path=output_path,
            source=source,
            quality_score=quality_score,
            structured_analysis=structured_analysis,
        )
    except Exception as exc:  # noqa: BLE001
        log_event(log_path, "error", "detail_fetch_failed", infoCode=info_code, error=repr(exc), detailUrl=detail_url)
        return FetchResult(item=item, status="error", text="", summary=[], output_path=None, source="none", quality_score=0, error=repr(exc))


def _sleep_with_jitter(delay: float, jitter: float) -> None:
    total = max(0.0, delay)
    if jitter > 0:
        total += random.uniform(0, jitter)
    if total > 0:
        time.sleep(total)


def fetch_details_for_day(
    items: List[Dict[str, Any]],
    target_date: str,
    output_dir: Path,
    args: argparse.Namespace,
    log_path: Path,
    resume_map: Dict[str, Path],
    manifest_map: Dict[str, Dict[str, Any]],
    manifest_path: Path,
) -> List[FetchResult]:
    indexed_items = list(enumerate(items, 1))
    results: List[Optional[FetchResult]] = [None] * len(indexed_items)

    def _run_one(index: int, item: Dict[str, Any]) -> Tuple[int, Dict[str, Any], FetchResult]:
        if getattr(args, "jitter", 0.0) > 0 and getattr(args, "concurrency", 1) > 1:
            _sleep_with_jitter(0.0, args.jitter)
        result = fetch_detail(
            item=item,
            output_dir=output_dir,
            index=index,
            timeout=args.timeout,
            retries=args.retries,
            retry_delay=args.retry_delay,
            log_path=log_path,
            resume_map=resume_map,
            manifest_map=manifest_map,
            force=args.force,
            use_pdf_fallback=not args.no_pdf_fallback,
            min_text_length=args.min_text_length,
            refresh_weak=args.refresh_weak,
            resume_errors_only=args.resume_errors_only,
        )
        return index, item, result

    concurrency = max(1, getattr(args, "concurrency", 1))
    if concurrency == 1 or len(indexed_items) <= 1:
        for index, item in indexed_items:
            _, item_ref, result = _run_one(index, item)
            results[index - 1] = result
            emit_result_progress(target_date, index, item_ref, result)
            append_manifest_entry(manifest_path, target_date, index, result)
            if index < len(indexed_items):
                _sleep_with_jitter(args.delay, args.jitter)
        return [result for result in results if result is not None]

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {executor.submit(_run_one, index, item): (index, item) for index, item in indexed_items}
        for future in as_completed(future_map):
            index, item, result = future.result()
            results[index - 1] = result
            emit_result_progress(target_date, index, item, result)
            append_manifest_entry(manifest_path, target_date, index, result)
    return [result for result in results if result is not None]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch scrape Eastmoney research reports by date or date range.")
    parser.add_argument("--date", help="Single date in YYYY-MM-DD")
    parser.add_argument("--start-date", help="Start date in YYYY-MM-DD")
    parser.add_argument("--end-date", help="End date in YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=None, help="Only fetch first N reports for each date")
    parser.add_argument("--qtype", type=int, default=0, choices=[0, 1], help="0=stock reports, 1=industry reports")
    parser.add_argument("--page-size", type=int, default=100, help="List API page size")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay seconds between detail requests")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=int, default=2, help="Retry times for list/detail fetch")
    parser.add_argument("--retry-delay", type=float, default=1.0, help="Retry delay seconds")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrent detail fetch workers")
    parser.add_argument("--output-dir", default=None, help="Output root directory")
    parser.add_argument("--stock", action="append", dest="stock_filters", default=[], help="Filter by stock code or name, repeatable")
    parser.add_argument("--org", action="append", dest="org_filters", default=[], help="Filter by broker / organization, repeatable")
    parser.add_argument("--rating", action="append", dest="rating_filters", default=[], help="Filter by rating keyword, repeatable")
    parser.add_argument("--industry", action="append", dest="industry_filters", default=[], help="Filter by industry keyword, repeatable")
    parser.add_argument("--force", action="store_true", help="Force re-fetch even if markdown already exists")
    parser.add_argument("--no-pdf-fallback", action="store_true", help="Disable PDF fallback when HTML text is weak")
    parser.add_argument("--no-xlsx", action="store_true", help="Skip xlsx export")
    parser.add_argument("--refresh-weak", action="store_true", help="Re-fetch reports that were previously marked weak")
    parser.add_argument("--resume-errors-only", action="store_true", help="Only retry reports that were previously marked error")
    parser.add_argument("--min-text-length", type=int, default=80, help="Minimum extracted text length before a report is marked weak")
    parser.add_argument("--jitter", type=float, default=0.0, help="Random extra delay seconds added to detail requests")
    parser.add_argument("--manifest-name", default=DEFAULT_MANIFEST_NAME, help="Run manifest jsonl file name")
    parser.add_argument("--hotspot-days", type=int, default=30, help="Recent-day window for hotspot detection")
    parser.add_argument("--hotspot-short-days", type=int, default=7, help="Short-day window for hotspot acceleration")
    parser.add_argument("--hotspot-silent-days", type=int, default=90, help="Silent window before reactivated coverage")
    parser.add_argument("--hotspot-broker-threshold", type=int, default=3, help="Distinct broker threshold for hotspot detection")
    parser.add_argument("--hotspot-coverage-threshold", type=int, default=3, help="Coverage count threshold for hotspot detection")
    parser.add_argument("--no-hotspot", action="store_true", help="Skip HOTSPOT_DASHBOARD.md and HOTSPOT_SIGNALS.csv outputs")
    parser.add_argument("--doctor", action="store_true", help="Print JSON environment diagnostics and exit")
    parser.add_argument("--dry-run", action="store_true", help="Fetch list pages and show selected counts without fetching report details")
    parser.add_argument("--list-only", action="store_true", help="Fetch list pages, print selected list JSON, and skip report details")
    parser.add_argument("--hotspots-only", action="store_true", help="Rebuild hotspot files from existing coverage history without network requests")
    parser.add_argument("--dashboard-only", action="store_true", help="Rebuild the static HTML dashboard from existing outputs without network requests")
    parser.add_argument("--no-dashboard", action="store_true", help="Skip static HTML dashboard generation")
    parser.add_argument("--dashboard-name", default=DEFAULT_DASHBOARD_NAME, help="Static HTML dashboard file name")
    return parser.parse_args()


def make_root_dir(output_root: Path, date_values: List[str]) -> Path:
    if len(date_values) == 1:
        return output_root / f"研报_{date_values[0]}"
    return output_root / f"研报_{date_values[0]}_to_{date_values[-1]}"


def build_hotspot_config(args: argparse.Namespace) -> HotspotConfig:
    return HotspotConfig(
        recent_days=args.hotspot_days,
        short_days=args.hotspot_short_days,
        silent_days=args.hotspot_silent_days,
        multi_broker_threshold=args.hotspot_broker_threshold,
        hot_coverage_threshold=args.hotspot_coverage_threshold,
    )


def _check_output_writable(output_root: Path) -> Dict[str, Any]:
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        check_path = output_root / ".doctor_write_check"
        check_path.write_text("ok", encoding="utf-8")
        cleanup_error = ""
        try:
            check_path.unlink()
        except Exception as exc:  # noqa: BLE001
            cleanup_error = repr(exc)
        return {"ok": True, "error": "", "checkFile": str(check_path), "cleanupError": cleanup_error}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": repr(exc), "checkFile": "", "cleanupError": ""}


def run_doctor(output_root: Path) -> None:
    writable = _check_output_writable(output_root)
    checks = {
        "pythonVersion": sys.version.split()[0],
        "beautifulsoup4": importlib.util.find_spec("bs4") is not None,
        "openpyxl": importlib.util.find_spec("openpyxl") is not None,
        "pdftotext": shutil.which("pdftotext") is not None,
        "outputDirWritable": writable["ok"],
    }
    print(
        json.dumps(
            {
                "mode": "doctor",
                "ok": bool(checks["beautifulsoup4"] and checks["outputDirWritable"]),
                "output_dir": str(output_root),
                "checks": checks,
                "check_file": writable["checkFile"],
                "errors": {"outputDirWritable": writable["error"]} if writable["error"] else {},
                "warnings": {"doctorCheckCleanup": writable["cleanupError"]} if writable["cleanupError"] else {},
            },
            ensure_ascii=False,
        )
    )


def run_hotspots_only(output_root: Path, args: argparse.Namespace) -> None:
    coverage_history_path = output_root / DEFAULT_COVERAGE_HISTORY_NAME
    coverage_entries = read_coverage_history(coverage_history_path)
    hotspot_signals_path, hotspot_dashboard_path = write_hotspot_outputs(output_root, coverage_entries, build_hotspot_config(args))
    dashboard_path = None
    if not getattr(args, "no_dashboard", False):
        dashboard_path = write_dashboard(output_root, getattr(args, "dashboard_name", DEFAULT_DASHBOARD_NAME))
    print(
        json.dumps(
            {
                "mode": "hotspots-only",
                "coverage_history": str(coverage_history_path),
                "coverage_entries": len(coverage_entries),
                "hotspot_signals": str(hotspot_signals_path),
                "hotspot_dashboard": str(hotspot_dashboard_path),
                "dashboard": str(dashboard_path) if dashboard_path else None,
            },
            ensure_ascii=False,
        )
    )


def run_dashboard_only(output_root: Path, dashboard_name: str = DEFAULT_DASHBOARD_NAME) -> None:
    dashboard_path = write_dashboard(output_root, dashboard_name)
    print(
        json.dumps(
            {
                "mode": "dashboard-only",
                "output_dir": str(output_root),
                "dashboard": str(dashboard_path),
            },
            ensure_ascii=False,
        )
    )


def run_list_mode(date_values: List[str], root_dir: Path, args: argparse.Namespace, include_items: bool) -> None:
    root_dir.mkdir(parents=True, exist_ok=True)
    days = []
    for target_date in date_values:
        output_dir = root_dir if args.date else root_dir / f"研报_{target_date}"
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / "run.log.jsonl"
        raw_list = fetch_report_list(target_date, args.page_size, args.qtype, args.timeout, args.retries, args.retry_delay, log_path)
        filtered_list = filter_items(raw_list, args)
        selected = filtered_list[: args.limit] if args.limit else filtered_list
        day_entry = {
            "date": target_date,
            "raw_count": len(raw_list),
            "filtered_count": len(filtered_list),
            "selected_count": len(selected),
        }
        if include_items:
            day_entry["items"] = selected
        days.append(day_entry)
    print(
        json.dumps(
            {
                "mode": "list-only" if include_items else "dry-run",
                "root_dir": str(root_dir),
                "dates": date_values,
                "days": days,
                "list_count": sum(day["raw_count"] for day in days),
                "selected_count": sum(day["selected_count"] for day in days),
            },
            ensure_ascii=False,
        )
    )


def run_for_date(target_date: str, root_dir: Path, args: argparse.Namespace) -> DayRun:
    output_dir = root_dir if args.date else root_dir / f"研报_{target_date}"
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run.log.jsonl"
    manifest_path = output_dir / args.manifest_name
    raw_list = fetch_report_list(target_date, args.page_size, args.qtype, args.timeout, args.retries, args.retry_delay, log_path)
    filtered_list = filter_items(raw_list, args)
    items = filtered_list[: args.limit] if args.limit else filtered_list
    resume_map = existing_markdown_map(output_dir)
    manifest_map = read_manifest(manifest_path)
    if args.resume_errors_only:
        items = select_resume_error_items(items, manifest_map)

    log_event(log_path, "info", "day_start", date=target_date, raw=len(raw_list), filtered=len(filtered_list), selected=len(items))

    results = fetch_details_for_day(items, target_date, output_dir, args, log_path, resume_map, manifest_map, manifest_path)

    write_day_summary(output_dir, target_date, args.qtype, filtered_list, results, log_path)
    if args.no_xlsx:
        xlsx_path = output_dir / "report_index.xlsx"
        if xlsx_path.exists():
            xlsx_path.unlink()
    log_event(
        log_path,
        "info",
        "day_complete",
        date=target_date,
        selected=len(items),
        ok=sum(r.status == "ok" for r in results),
        weak=sum(r.status == "weak" for r in results),
        error=sum(r.status == "error" for r in results),
    )
    return DayRun(date_str=target_date, output_dir=output_dir, raw_list=filtered_list, results=results)


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_dir).expanduser() if args.output_dir else DEFAULT_OUTPUT_ROOT
    if args.doctor:
        run_doctor(output_root)
        return
    if args.dashboard_only:
        run_dashboard_only(output_root, args.dashboard_name)
        return
    if args.hotspots_only:
        run_hotspots_only(output_root, args)
        return

    date_values = resolve_dates(args)
    root_dir = make_root_dir(output_root, date_values)
    root_dir.mkdir(parents=True, exist_ok=True)
    if args.dry_run or args.list_only:
        run_list_mode(date_values, root_dir, args, include_items=args.list_only)
        return

    day_runs: List[DayRun] = []
    for target_date in date_values:
        day_runs.append(run_for_date(target_date, root_dir, args))

    write_range_summary(root_dir, day_runs, args.qtype)
    coverage_history_path, coverage_summary_path, industry_coverage_summary_path = update_coverage_history(output_root, day_runs)
    hotspot_signals_path = None
    hotspot_dashboard_path = None
    if not args.no_hotspot:
        coverage_entries = read_coverage_history(coverage_history_path)
        hotspot_signals_path, hotspot_dashboard_path = write_hotspot_outputs(output_root, coverage_entries, build_hotspot_config(args))
    dashboard_path = None
    if not args.no_dashboard:
        dashboard_path = write_dashboard(output_root, args.dashboard_name)

    print(
        json.dumps(
            {
                "root_dir": str(root_dir),
                "dates": date_values,
                "days": len(day_runs),
                "list_count": sum(len(run.raw_list) for run in day_runs),
                "fetched": sum(len(run.results) for run in day_runs),
                "ok": sum(sum(r.status == "ok" for r in run.results) for run in day_runs),
                "weak": sum(sum(r.status == "weak" for r in run.results) for run in day_runs),
                "error": sum(sum(r.status == "error" for r in run.results) for run in day_runs),
                "range_summary": str(root_dir / "RANGE_SUMMARY.md") if len(day_runs) > 1 else None,
                "range_dashboard": str(root_dir / "RANGE_DASHBOARD.md") if len(day_runs) > 1 else None,
                "coverage_history": str(coverage_history_path),
                "coverage_summary": str(coverage_summary_path),
                "industry_coverage_summary": str(industry_coverage_summary_path),
                "hotspot_signals": str(hotspot_signals_path) if hotspot_signals_path else None,
                "hotspot_dashboard": str(hotspot_dashboard_path) if hotspot_dashboard_path else None,
                "dashboard": str(dashboard_path) if dashboard_path else None,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
