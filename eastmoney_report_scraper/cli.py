"""Command-line entrypoint for the Eastmoney report scraper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from .config import load_local_app_config, save_local_app_config
from .constants import DEFAULT_DASHBOARD_NAME, DEFAULT_MANIFEST_NAME, DEFAULT_OUTPUT_ROOT, QTYPE_ALL, QTYPE_INDUSTRY, QTYPE_STOCK
from .core.orchestration import (
    append_manifest_entry,
    daterange,
    existing_markdown_map,
    fetch_detail,
    fetch_report_lists_for_date,
    filter_items,
    make_root_dir,
    parse_date,
    qtype_values,
    read_manifest,
    resolve_dates,
    run_dashboard_only,
    run_doctor,
    run_fetch_workflow,
    run_hotspots_only,
    run_list_mode,
    select_resume_error_items,
)
from .storage.sqlite import import_existing_outputs, init_db

__all__ = [
    "append_manifest_entry",
    "daterange",
    "existing_markdown_map",
    "fetch_detail",
    "fetch_report_lists_for_date",
    "filter_items",
    "main",
    "make_root_dir",
    "parse_app_args",
    "parse_args",
    "parse_date",
    "parse_import_args",
    "qtype_values",
    "read_manifest",
    "resolve_dates",
    "run_app_command",
    "run_dashboard_only",
    "run_doctor",
    "run_fetch_workflow",
    "run_hotspots_only",
    "run_import_existing_command",
    "run_list_mode",
    "select_resume_error_items",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch scrape Eastmoney research reports by date or date range.")
    parser.add_argument("--date", help="Single date in YYYY-MM-DD")
    parser.add_argument("--start-date", help="Start date in YYYY-MM-DD")
    parser.add_argument("--end-date", help="End date in YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=None, help="Only fetch first N reports for each date")
    parser.add_argument("--qtype", type=int, default=0, choices=[QTYPE_STOCK, QTYPE_INDUSTRY, QTYPE_ALL], help="0=stock reports, 1=industry reports, 2=all")
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


def parse_app_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local Eastmoney report scraper web app.")
    parser.add_argument("--host", default=None, help="Local app host, default 127.0.0.1")
    parser.add_argument("--port", type=int, default=None, help="Local app port, default 8765")
    parser.add_argument("--output-dir", default=None, help="Output root directory")
    parser.add_argument("--db-path", default=None, help="SQLite database path")
    parser.add_argument("--config-path", default=None, help="Local app config JSON path")
    parser.add_argument("--open-browser", action="store_true", help="Open the local app URL in the default browser")
    return parser.parse_args(argv)


def parse_import_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import existing scraper outputs into the local SQLite database.")
    parser.add_argument("--output-dir", default=None, help="Output root directory")
    parser.add_argument("--db-path", default=None, help="SQLite database path")
    parser.add_argument("--config-path", default=None, help="Local app config JSON path")
    return parser.parse_args(argv)


def run_import_existing_command(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_import_args(argv)
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else None
    db_path = Path(args.db_path).expanduser() if args.db_path else None
    config_path = Path(args.config_path).expanduser() if args.config_path else None
    config = load_local_app_config(output_dir=output_dir, db_path=db_path, config_path=config_path)
    save_local_app_config(config, config_path=config_path)
    counts = import_existing_outputs(Path(config.output_dir), Path(config.db_path))
    print(
        json.dumps(
            {
                "mode": "import-existing",
                "output_dir": config.output_dir,
                "db_path": config.db_path,
                "imported": counts,
            },
            ensure_ascii=False,
        )
    )


def run_app_command(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_app_args(argv)
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else None
    db_path = Path(args.db_path).expanduser() if args.db_path else None
    config_path = Path(args.config_path).expanduser() if args.config_path else None
    config = load_local_app_config(output_dir=output_dir, db_path=db_path, config_path=config_path)
    if args.host:
        config = config.__class__(**{**config.__dict__, "host": args.host})
    if args.port:
        config = config.__class__(**{**config.__dict__, "port": args.port})
    save_local_app_config(config, config_path=config_path)
    init_db(Path(config.db_path))
    try:
        from .app.server import run_app

        print(
            json.dumps(
                {
                    "mode": "app",
                    "ok": True,
                    "url": f"http://{config.host}:{config.port}",
                    "output_dir": config.output_dir,
                    "db_path": config.db_path,
                    "open_browser": args.open_browser,
                },
                ensure_ascii=False,
            )
        )
        run_app(config, open_browser=args.open_browser)
    except RuntimeError as exc:
        print(json.dumps({"mode": "app", "ok": False, "error": str(exc)}, ensure_ascii=False))


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "app":
        run_app_command(sys.argv[2:])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "import-existing":
        run_import_existing_command(sys.argv[2:])
        return

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

    payload = run_fetch_workflow(date_values, output_root, args)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
