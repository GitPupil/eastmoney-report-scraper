"""SQLite storage for the local app cache."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..constants import (
    DEFAULT_COVERAGE_HISTORY_NAME,
    DEFAULT_HOTSPOT_SIGNALS_NAME,
    DEFAULT_MANIFEST_NAME,
)
from ..dashboard import build_dashboard_data, load_hotspot_rows, load_report_rows


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.expanduser().parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path.expanduser()))
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: Path) -> None:
    with connect(db_path) as connection:
        connection.executescript(
            """
            create table if not exists reports (
                info_code text primary key,
                publish_date text,
                stock_code text,
                stock_name text,
                industry_name text,
                org_name text,
                rating text,
                status text,
                source text,
                signal_score real,
                priority_bucket text,
                file_href text,
                data_json text not null
            );
            create table if not exists hotspots (
                signal_key text primary key,
                entity_type text,
                entity_name text,
                stock_code text,
                industry_name text,
                hotspot_level text,
                latest_publish_date text,
                data_json text not null
            );
            create table if not exists coverage_history (
                info_code text primary key,
                publish_date text,
                stock_code text,
                stock_name text,
                industry_name text,
                org_name text,
                rating text,
                data_json text not null
            );
            create table if not exists manifests (
                manifest_key text primary key,
                info_code text,
                publish_date text,
                status text,
                file text,
                data_json text not null
            );
            create table if not exists runs (
                run_id text primary key,
                status text not null,
                params_json text not null,
                output_dir text,
                started_at text,
                ended_at text,
                ok_count integer default 0,
                weak_count integer default 0,
                error_count integer default 0,
                error_text text default "",
                stdout_tail text default "",
                stderr_tail text default ""
            );
            create index if not exists idx_reports_date on reports(publish_date);
            create index if not exists idx_reports_stock on reports(stock_code, stock_name);
            create index if not exists idx_hotspots_level on hotspots(hotspot_level);
            create index if not exists idx_runs_status on runs(status);
            """
        )


def _json_dumps(value: Dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
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
    return rows


def _upsert_reports(connection: sqlite3.Connection, reports: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for idx, report in enumerate(reports):
        info_code = str(report.get("infoCode") or f"missing-{idx}")
        connection.execute(
            """
            insert into reports (
                info_code, publish_date, stock_code, stock_name, industry_name,
                org_name, rating, status, source, signal_score, priority_bucket,
                file_href, data_json
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(info_code) do update set
                publish_date=excluded.publish_date,
                stock_code=excluded.stock_code,
                stock_name=excluded.stock_name,
                industry_name=excluded.industry_name,
                org_name=excluded.org_name,
                rating=excluded.rating,
                status=excluded.status,
                source=excluded.source,
                signal_score=excluded.signal_score,
                priority_bucket=excluded.priority_bucket,
                file_href=excluded.file_href,
                data_json=excluded.data_json
            """,
            (
                info_code,
                report.get("date") or "",
                report.get("stockCode") or "",
                report.get("stockName") or "",
                report.get("industryName") or "",
                report.get("orgName") or "",
                report.get("rating") or "",
                report.get("status") or "",
                report.get("source") or "",
                float(report.get("signalScore") or 0),
                report.get("priorityBucket") or "",
                report.get("fileHref") or "",
                _json_dumps(report),
            ),
        )
        count += 1
    return count


def _hotspot_key(row: Dict[str, Any], idx: int) -> str:
    return "|".join(
        [
            str(row.get("entityType") or ""),
            str(row.get("entityName") or ""),
            str(row.get("stockCode") or ""),
            str(row.get("industryName") or ""),
        ]
    ) or f"missing-{idx}"


def _upsert_hotspots(connection: sqlite3.Connection, hotspots: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for idx, hotspot in enumerate(hotspots):
        key = _hotspot_key(hotspot, idx)
        connection.execute(
            """
            insert into hotspots (
                signal_key, entity_type, entity_name, stock_code, industry_name,
                hotspot_level, latest_publish_date, data_json
            )
            values (?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(signal_key) do update set
                entity_type=excluded.entity_type,
                entity_name=excluded.entity_name,
                stock_code=excluded.stock_code,
                industry_name=excluded.industry_name,
                hotspot_level=excluded.hotspot_level,
                latest_publish_date=excluded.latest_publish_date,
                data_json=excluded.data_json
            """,
            (
                key,
                hotspot.get("entityType") or "",
                hotspot.get("entityName") or "",
                hotspot.get("stockCode") or "",
                hotspot.get("industryName") or "",
                hotspot.get("hotspotLevel") or "",
                hotspot.get("latestPublishDate") or "",
                _json_dumps(hotspot),
            ),
        )
        count += 1
    return count


def _upsert_jsonl_table(connection: sqlite3.Connection, table: str, rows: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for idx, row in enumerate(rows):
        info_code = str(row.get("infoCode") or "")
        if table == "coverage_history":
            if not info_code:
                continue
            connection.execute(
                """
                insert into coverage_history (
                    info_code, publish_date, stock_code, stock_name, industry_name,
                    org_name, rating, data_json
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(info_code) do update set
                    publish_date=excluded.publish_date,
                    stock_code=excluded.stock_code,
                    stock_name=excluded.stock_name,
                    industry_name=excluded.industry_name,
                    org_name=excluded.org_name,
                    rating=excluded.rating,
                    data_json=excluded.data_json
                """,
                (
                    info_code,
                    row.get("publishDate") or row.get("date") or "",
                    row.get("stockCode") or "",
                    row.get("stockName") or "",
                    row.get("industryName") or row.get("indvInduName") or "",
                    row.get("orgName") or row.get("orgSName") or "",
                    row.get("rating") or row.get("emRatingName") or row.get("sRatingName") or "",
                    _json_dumps(row),
                ),
            )
        else:
            key = "|".join([str(row.get("date") or row.get("publishDate") or ""), info_code, str(idx)])
            connection.execute(
                """
                insert into manifests (manifest_key, info_code, publish_date, status, file, data_json)
                values (?, ?, ?, ?, ?, ?)
                on conflict(manifest_key) do update set
                    info_code=excluded.info_code,
                    publish_date=excluded.publish_date,
                    status=excluded.status,
                    file=excluded.file,
                    data_json=excluded.data_json
                """,
                (
                    key,
                    info_code,
                    row.get("date") or row.get("publishDate") or "",
                    row.get("status") or "",
                    row.get("file") or "",
                    _json_dumps(row),
                ),
            )
        count += 1
    return count


def import_existing_outputs(output_root: Path, db_path: Path) -> Dict[str, int]:
    init_db(db_path)
    reports = load_report_rows(output_root)
    hotspots = load_hotspot_rows(output_root)
    coverage_rows = _read_jsonl(output_root / DEFAULT_COVERAGE_HISTORY_NAME)
    manifest_rows: List[Dict[str, Any]] = []
    for manifest_path in output_root.rglob(DEFAULT_MANIFEST_NAME):
        manifest_rows.extend(_read_jsonl(manifest_path))

    with connect(db_path) as connection:
        imported_reports = _upsert_reports(connection, reports)
        imported_hotspots = _upsert_hotspots(connection, hotspots)
        imported_coverage = _upsert_jsonl_table(connection, "coverage_history", coverage_rows)
        imported_manifests = _upsert_jsonl_table(connection, "manifests", manifest_rows)
    return {
        "reports": imported_reports,
        "hotspots": imported_hotspots,
        "coverage_history": imported_coverage,
        "manifests": imported_manifests,
    }


def create_run(db_path: Path, run_id: str, params: Dict[str, Any], output_dir: Path) -> None:
    init_db(db_path)
    with connect(db_path) as connection:
        connection.execute(
            """
            insert into runs (run_id, status, params_json, output_dir, started_at)
            values (?, ?, ?, ?, ?)
            on conflict(run_id) do update set
                status=excluded.status,
                params_json=excluded.params_json,
                output_dir=excluded.output_dir,
                started_at=excluded.started_at
            """,
            (run_id, "pending", _json_dumps(params), str(output_dir), datetime.now().isoformat(timespec="seconds")),
        )


def update_run(
    db_path: Path,
    run_id: str,
    status: str,
    *,
    ok_count: int = 0,
    weak_count: int = 0,
    error_count: int = 0,
    error_text: str = "",
    stdout_tail: str = "",
    stderr_tail: str = "",
) -> None:
    init_db(db_path)
    ended_at = datetime.now().isoformat(timespec="seconds") if status in {"done", "failed"} else None
    with connect(db_path) as connection:
        connection.execute(
            """
            update runs set
                status=?,
                ended_at=coalesce(?, ended_at),
                ok_count=?,
                weak_count=?,
                error_count=?,
                error_text=?,
                stdout_tail=?,
                stderr_tail=?
            where run_id=?
            """,
            (status, ended_at, ok_count, weak_count, error_count, error_text, stdout_tail[-4000:], stderr_tail[-4000:], run_id),
        )


def _rows_from_query(db_path: Path, sql: str, params: tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
    init_db(db_path)
    with connect(db_path) as connection:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


def list_runs(db_path: Path, limit: int = 50) -> List[Dict[str, Any]]:
    return _rows_from_query(
        db_path,
        "select * from runs order by started_at desc limit ?",
        (limit,),
    )


def _report_search_clause(search: str) -> Tuple[str, Tuple[Any, ...]]:
    terms = [part.strip() for part in search.split() if part.strip()]
    if not terms:
        return "", ()

    searchable_columns = [
        "stock_code",
        "stock_name",
        "industry_name",
        "org_name",
        "rating",
        "priority_bucket",
        "data_json",
    ]
    clauses = []
    params: List[Any] = []
    for term in terms:
        like_value = f"%{term}%"
        clauses.append("(" + " or ".join(f"{column} like ?" for column in searchable_columns) + ")")
        params.extend([like_value] * len(searchable_columns))
    return " where " + " and ".join(clauses), tuple(params)


def query_reports(
    db_path: Path,
    *,
    limit: Optional[int] = 200,
    offset: int = 0,
    search: str = "",
) -> Dict[str, Any]:
    init_db(db_path)
    normalized_limit = max(0, int(limit or 0))
    normalized_offset = max(0, int(offset or 0))
    where_clause, params = _report_search_clause(search)
    base_sql = f" from reports{where_clause}"
    order_sql = " order by publish_date desc, signal_score desc, info_code desc"
    query_sql = "select data_json" + base_sql + order_sql
    query_params: Tuple[Any, ...] = params
    if normalized_limit > 0:
        query_sql += " limit ? offset ?"
        query_params = params + (normalized_limit, normalized_offset)

    with connect(db_path) as connection:
        total = int(connection.execute("select count(*)" + base_sql, params).fetchone()[0])
        rows = [dict(row) for row in connection.execute(query_sql, query_params).fetchall()]

    items = [json.loads(row["data_json"]) for row in rows]
    return {
        "items": items,
        "count": len(items),
        "total": total,
        "limit": normalized_limit,
        "offset": normalized_offset if normalized_limit > 0 else 0,
        "search": search,
    }


def list_reports(db_path: Path, limit: int = 200) -> List[Dict[str, Any]]:
    rows = _rows_from_query(
        db_path,
        "select data_json from reports order by publish_date desc, signal_score desc limit ?",
        (limit,),
    )
    return [json.loads(row["data_json"]) for row in rows]


def list_hotspots(db_path: Path, limit: int = 100) -> List[Dict[str, Any]]:
    rows = _rows_from_query(
        db_path,
        "select data_json from hotspots order by hotspot_level asc, latest_publish_date desc limit ?",
        (limit,),
    )
    return [json.loads(row["data_json"]) for row in rows]


def dashboard_data(output_root: Path, db_path: Path) -> Dict[str, Any]:
    init_db(db_path)
    return build_dashboard_data(output_root)


def health(output_root: Path, db_path: Path) -> Dict[str, Any]:
    init_db(db_path)
    table_counts = {}
    with connect(db_path) as connection:
        for table in ("reports", "hotspots", "coverage_history", "manifests", "runs"):
            table_counts[table] = int(connection.execute(f"select count(*) from {table}").fetchone()[0])
    return {
        "ok": True,
        "output_dir": str(output_root),
        "db_path": str(db_path),
        "has_hotspot_signals": (output_root / DEFAULT_HOTSPOT_SIGNALS_NAME).exists(),
        "tables": table_counts,
    }
