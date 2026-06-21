"""Background task runner for the local app."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..storage import sqlite

Runner = Callable[[List[str]], subprocess.CompletedProcess[str]]


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


def default_runner(command: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


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
        command = build_fetch_command(params, self.output_root)
        try:
            completed = self.runner(command)
            payload = _parse_final_payload(completed.stdout or "")
            sqlite.import_existing_outputs(self.output_root, self.db_path)
            if completed.returncode == 0:
                sqlite.update_run(
                    self.db_path,
                    run_id,
                    "done",
                    ok_count=int(payload.get("ok") or 0),
                    weak_count=int(payload.get("weak") or 0),
                    error_count=int(payload.get("error") or 0),
                    stdout_tail=completed.stdout or "",
                    stderr_tail=completed.stderr or "",
                )
            else:
                sqlite.update_run(
                    self.db_path,
                    run_id,
                    "failed",
                    error_text=f"exit code {completed.returncode}",
                    stdout_tail=completed.stdout or "",
                    stderr_tail=completed.stderr or "",
                )
        except Exception as exc:  # noqa: BLE001
            sqlite.update_run(self.db_path, run_id, "failed", error_text=repr(exc))
