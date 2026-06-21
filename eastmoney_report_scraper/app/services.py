"""Application services used by the local web app and tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import LocalAppConfig
from ..storage import sqlite
from .tasks import TaskManager


@dataclass
class LocalAppServices:
    config: LocalAppConfig
    task_manager: Optional[TaskManager] = None

    @property
    def output_root(self) -> Path:
        return Path(self.config.output_dir).expanduser()

    @property
    def db_path(self) -> Path:
        return Path(self.config.db_path).expanduser()

    def ensure_ready(self) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)
        sqlite.init_db(self.db_path)

    def health(self) -> Dict[str, Any]:
        self.ensure_ready()
        return sqlite.health(self.output_root, self.db_path)

    def import_existing(self) -> Dict[str, Any]:
        self.ensure_ready()
        counts = sqlite.import_existing_outputs(self.output_root, self.db_path)
        return {"ok": True, "output_dir": str(self.output_root), "db_path": str(self.db_path), "imported": counts}

    def reports(self, limit: int = 200, offset: int = 0, search: str = "") -> Dict[str, Any]:
        self.ensure_ready()
        return sqlite.query_reports(self.db_path, limit=limit, offset=offset, search=search)

    def hotspots(self, limit: int = 100) -> Dict[str, Any]:
        self.ensure_ready()
        rows = sqlite.list_hotspots(self.db_path, limit=limit)
        return {"items": rows, "count": len(rows)}

    def dashboard_data(self) -> Dict[str, Any]:
        self.ensure_ready()
        return sqlite.dashboard_data(self.output_root, self.db_path)

    def runs(self, limit: int = 50) -> Dict[str, Any]:
        self.ensure_ready()
        rows = sqlite.list_runs(self.db_path, limit=limit)
        return {"items": rows, "count": len(rows)}

    def start_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_ready()
        manager = self.task_manager or TaskManager(self.output_root, self.db_path)
        self.task_manager = manager
        run_id = manager.start_run(params)
        return {"ok": True, "run_id": run_id}
