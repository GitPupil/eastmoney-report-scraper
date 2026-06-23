"""Background task runner for the local app."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..constants import DEFAULT_DASHBOARD_NAME, DEFAULT_MANIFEST_NAME
from ..core.orchestration import resolve_dates, run_fetch_workflow
from ..storage import sqlite

Runner = Callable[..., Any]


def _append_option(args: List[str], flag: str, value: Any) -> None:
    if value in (None, "", False):
        return
    args.extend([flag, str(value)])


def build_fetch_command(params: Dict[str, Any], output_root: Path) -> List[str]:
    command = [sys.executable, "-m", "eastmoney_report_scraper.cli"]
    start_date = params.get("start_date")
    end_date = params.get("end_date")
    if start_date and end_date:
        _append_option(command, "--start-date", start_date)
        _append_option(command, "--end-date", end_date)
    else:
        _append_option(command, "--date", params.get("date"))
    _append_option(command, "--limit", params.get("limit"))
    _append_option(command, "--qtype", params.get("qtype", 0))
    _append_option(command, "--concurrency", params.get("concurrency"))
    _append_option(command, "--jitter", params.get("jitter"))
    _append_option(command, "--output-dir", output_root)
    for flag, key in (("--stock", "stock"), ("--org", "org"), ("--rating", "rating"), ("--industry", "industry")):
        values = params.get(key) or []
        if isinstance(values, str):
            values = [item.strip() for item in values.split(",") if item.strip()]
        for value in values:
            _append_option(command, flag, value)
    if params.get("no_xlsx", True):
        command.append("--no-xlsx")
    return command


def build_fetch_namespace(params: Dict[str, Any], output_root: Path) -> argparse.Namespace:
    def _list_value(key: str) -> List[str]:
        values = params.get(key) or []
        if isinstance(values, str):
            return [item.strip() for item in values.split(",") if item.strip()]
        return [str(item).strip() for item in values if str(item).strip()]

    return argparse.Namespace(
        date=params.get("date"),
        start_date=params.get("start_date"),
        end_date=params.get("end_date"),
        limit=params.get("limit"),
        qtype=int(params.get("qtype", 0) or 0),
        page_size=int(params.get("page_size", 100) or 100),
        delay=float(params.get("delay", 0.3) or 0.0),
        timeout=int(params.get("timeout", 20) or 20),
        retries=int(params.get("retries", 2) or 0),
        retry_delay=float(params.get("retry_delay", 1.0) or 0.0),
        concurrency=int(params.get("concurrency", 1) or 1),
        output_dir=str(output_root),
        stock_filters=_list_value("stock"),
        org_filters=_list_value("org"),
        rating_filters=_list_value("rating"),
        industry_filters=_list_value("industry"),
        force=bool(params.get("force", False)),
        no_pdf_fallback=bool(params.get("no_pdf_fallback", False)),
        no_xlsx=bool(params.get("no_xlsx", True)),
        refresh_weak=bool(params.get("refresh_weak", False)),
        resume_errors_only=bool(params.get("resume_errors_only", False)),
        min_text_length=int(params.get("min_text_length", 80) or 80),
        jitter=float(params.get("jitter", 0.0) or 0.0),
        manifest_name=params.get("manifest_name") or DEFAULT_MANIFEST_NAME,
        hotspot_days=int(params.get("hotspot_days", 30) or 30),
        hotspot_short_days=int(params.get("hotspot_short_days", 7) or 7),
        hotspot_silent_days=int(params.get("hotspot_silent_days", 90) or 90),
        hotspot_broker_threshold=int(params.get("hotspot_broker_threshold", 3) or 3),
        hotspot_coverage_threshold=int(params.get("hotspot_coverage_threshold", 3) or 3),
        no_hotspot=bool(params.get("no_hotspot", False)),
        doctor=False,
        dry_run=False,
        list_only=False,
        hotspots_only=False,
        dashboard_only=False,
        no_dashboard=bool(params.get("no_dashboard", False)),
        dashboard_name=params.get("dashboard_name") or DEFAULT_DASHBOARD_NAME,
    )


def default_runner(params: Dict[str, Any], output_root: Path) -> Dict[str, Any]:
    args = build_fetch_namespace(params, output_root)
    date_values = resolve_dates(args)
    return run_fetch_workflow(date_values, output_root, args)


def _parse_final_payload(stdout: str) -> Dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def _run_with_compatible_runner(runner: Runner, params: Dict[str, Any], output_root: Path) -> tuple[int, Dict[str, Any], str, str]:
    try:
        result = runner(params, output_root)
    except TypeError:
        command = build_fetch_command(params, output_root)
        result = runner(command)

    if isinstance(result, subprocess.CompletedProcess):
        payload = _parse_final_payload(result.stdout or "")
        return result.returncode, payload, result.stdout or "", result.stderr or ""

    payload = result if isinstance(result, dict) else {}
    return 0, payload, json.dumps(payload, ensure_ascii=False), ""


class TaskManager:
    def __init__(self, output_root: Path, db_path: Path, runner: Optional[Runner] = None) -> None:
        self.output_root = output_root.expanduser()
        self.db_path = db_path.expanduser()
        self.runner = runner or default_runner

    def start_run(self, params: Dict[str, Any]) -> str:
        run_id = uuid.uuid4().hex
        sqlite.create_run(self.db_path, run_id, params, self.output_root)
        thread = threading.Thread(target=self._run, args=(run_id, params), daemon=True)
        thread.start()
        return run_id

    def _run(self, run_id: str, params: Dict[str, Any]) -> None:
        sqlite.update_run(self.db_path, run_id, "running")
        try:
            returncode, payload, stdout_tail, stderr_tail = _run_with_compatible_runner(self.runner, params, self.output_root)
            sqlite.import_existing_outputs(self.output_root, self.db_path)
            if returncode == 0:
                sqlite.update_run(
                    self.db_path,
                    run_id,
                    "done",
                    ok_count=int(payload.get("ok") or 0),
                    weak_count=int(payload.get("weak") or 0),
                    error_count=int(payload.get("error") or 0),
                    stdout_tail=stdout_tail,
                    stderr_tail=stderr_tail,
                )
            else:
                sqlite.update_run(
                    self.db_path,
                    run_id,
                    "failed",
                    error_text=f"exit code {returncode}",
                    stdout_tail=stdout_tail,
                    stderr_tail=stderr_tail,
                )
        except Exception as exc:  # noqa: BLE001
            sqlite.update_run(self.db_path, run_id, "failed", error_text=repr(exc))
