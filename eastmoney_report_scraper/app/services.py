"""Application services used by the local web app and tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..ai import (
    AIHttpPost,
    analyze_with_ai,
    build_ai_evidence,
    delete_ai_profile,
    import_cc_switch_ai_config,
    list_ai_prompt_templates,
    load_ai_config,
    probe_ai_connection,
    public_ai_profile_settings,
    redact_secrets,
    set_active_ai_profile,
    update_ai_config,
)
from ..config import LocalAppConfig
from ..storage import sqlite
from .tasks import TaskManager


@dataclass
class LocalAppServices:
    config: LocalAppConfig
    task_manager: Optional[TaskManager] = None
    ai_http_post: Optional[AIHttpPost] = None

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

    def ai_settings(self) -> Dict[str, Any]:
        self.ensure_ready()
        return {**public_ai_profile_settings(self.output_root), "templates": list_ai_prompt_templates()}

    def update_ai_settings(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_ready()
        update_ai_config(self.output_root, payload)
        return {"ok": True, "settings": self.ai_settings()}

    def set_active_ai_profile(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_ready()
        profile_id = str(payload.get("profileId") or payload.get("profile_id") or "")
        return {"ok": True, "settings": {**set_active_ai_profile(self.output_root, profile_id), "templates": list_ai_prompt_templates()}}

    def delete_ai_profile(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_ready()
        profile_id = str(payload.get("profileId") or payload.get("profile_id") or "")
        return {"ok": True, "settings": {**delete_ai_profile(self.output_root, profile_id), "templates": list_ai_prompt_templates()}}

    def import_cc_switch_ai_settings(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.ensure_ready()
        payload = payload or {}
        return import_cc_switch_ai_config(
            self.output_root,
            settings_path=Path(payload["settingsPath"]) if payload.get("settingsPath") else None,
            db_path=Path(payload["dbPath"]) if payload.get("dbPath") else None,
            profile_id=str(payload.get("profileId") or ""),
            profile_name=str(payload.get("profileName") or ""),
            overwrite_profile_id=str(payload.get("overwriteProfileId") or ""),
        )

    def test_ai_connection(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.ensure_ready()
        payload = payload or {}
        if payload:
            config = update_ai_config(self.output_root, payload)
        else:
            config = load_ai_config(self.output_root)
        return probe_ai_connection(config)

    def ai_analyze(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_ready()
        config = load_ai_config(self.output_root)
        evidence = build_ai_evidence(
            self.dashboard_data(),
            scope=str(payload.get("scope") or "selected"),
            query=str(payload.get("query") or ""),
            entity_key=str(payload.get("entityKey") or ""),
            entity_keys=payload.get("entityKeys") or [],
            start_date=str(payload.get("startDate") or ""),
            end_date=str(payload.get("endDate") or ""),
            filters=payload.get("filters") or {},
            max_reports=int(payload.get("maxReports") or 8),
        )
        try:
            return analyze_with_ai(
                config,
                evidence,
                instruction=str(payload.get("instruction") or ""),
                template_id=str(payload.get("templateId") or "general_research"),
                template_prompt=str(payload.get("templatePrompt") or ""),
                http_post=self.ai_http_post,
            )
        except Exception as exc:
            return {
                "ok": False,
                "error": redact_secrets(str(exc), [config.api_token]),
                "settings": self.ai_settings(),
                "evidence": evidence,
            }

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
