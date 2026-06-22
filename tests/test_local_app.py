import csv
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

import pytest

from eastmoney_report_scraper.app.services import LocalAppServices
from eastmoney_report_scraper.app.server import (
    _APP_DIR,
    _INDEX_HTML,
    _markdown_to_html,
    _preview_html,
    _resolve_file_target,
    create_app,
)
from eastmoney_report_scraper.app.tasks import TaskManager, build_fetch_command
from eastmoney_report_scraper.cli import parse_app_args, run_import_existing_command
from eastmoney_report_scraper.config import (
    LocalAppConfig,
    load_local_app_config,
    save_local_app_config,
)
from eastmoney_report_scraper.constants import (
    DEFAULT_COVERAGE_HISTORY_NAME,
    DEFAULT_HOTSPOT_SIGNALS_NAME,
    DEFAULT_INDEX_NAME,
    DEFAULT_MANIFEST_NAME,
)
from eastmoney_report_scraper.hotspots import SIGNAL_FIELDS
from eastmoney_report_scraper.storage.sqlite import health, import_existing_outputs, list_hotspots, list_reports, list_runs


def _write_index(output_dir: Path, rows=None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "stockName",
        "stockCode",
        "industryName",
        "title",
        "orgName",
        "publishDate",
        "rating",
        "infoCode",
        "status",
        "source",
        "chars",
        "summary",
        "signalScore",
        "priorityBucket",
        "themeTags",
        "ratingChange",
        "targetPrice",
        "epsForecast",
        "peForecast",
        "file",
        "scoreReasons",
        "scoreBreakdown",
        "qualityScore",
    ]
    with (output_dir / DEFAULT_INDEX_NAME).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            rows
            or [
                {
                    "stockName": "本地样本",
                    "stockCode": "300001",
                    "industryName": "人工智能",
                    "title": "本地版测试",
                    "orgName": "测试证券",
                    "publishDate": "2026-05-12",
                    "rating": "买入",
                    "infoCode": "LOCAL001",
                    "status": "ok",
                    "source": "html",
                    "chars": "1200",
                    "summary": "订单增长 | 景气改善",
                    "signalScore": "80",
                    "priorityBucket": "A",
                    "themeTags": "AI | 景气",
                    "ratingChange": "",
                    "targetPrice": "30",
                    "epsForecast": "1.00",
                    "peForecast": "20",
                    "file": "001.md",
                    "scoreReasons": "景气改善",
                    "scoreBreakdown": "{}",
                    "qualityScore": "90",
                }
            ]
        )


def _write_hotspots(output_root: Path) -> None:
    with (output_root / DEFAULT_HOTSPOT_SIGNALS_NAME).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SIGNAL_FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "entityType": "company",
                "entityName": "本地样本",
                "stockCode": "300001",
                "industryName": "人工智能",
                "hotspotLevel": "STRONG",
                "isFirstCoverage": "true",
                "isReactivatedCoverage": "false",
                "coverage7d": "1",
                "coverage30d": "1",
                "previous30dCoverage": "0",
                "coverageAcceleration": "1",
                "brokerCount30d": "1",
                "newBrokerCount30d": "1",
                "ratingDistribution": "{}",
                "buyRatio": "1.0000",
                "latestPublishDate": "2026-05-12",
                "reasons": "近期首次被覆盖",
                "reasonCodes": "FIRST_COVERAGE",
                "coveredCompanyCount30d": "1",
            }
        )


def _write_fixture_outputs(output_root: Path) -> None:
    _write_index(output_root / "研报_2026-05-12")
    (output_root / "研报_2026-05-12" / "001.md").write_text("# 本地样本\n", encoding="utf-8")
    _write_hotspots(output_root)
    (output_root / DEFAULT_COVERAGE_HISTORY_NAME).write_text(
        json.dumps(
            {
                "infoCode": "LOCAL001",
                "stockCode": "300001",
                "stockName": "本地样本",
                "industryName": "人工智能",
                "orgName": "测试证券",
                "rating": "买入",
                "publishDate": "2026-05-12",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_dir = output_root / "研报_2026-05-12"
    (manifest_dir / DEFAULT_MANIFEST_NAME).write_text(
        json.dumps({"infoCode": "LOCAL001", "date": "2026-05-12", "status": "ok", "file": "001.md"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )


def test_local_app_config_round_trip_and_overrides(tmp_path: Path):
    config_path = tmp_path / "local_app_config.json"
    config = LocalAppConfig(output_dir=str(tmp_path / "reports"), db_path=str(tmp_path / "eastmoney.db"), port=9000)
    save_local_app_config(config, config_path=config_path)
    loaded = load_local_app_config(config_path=config_path)
    assert loaded.port == 9000

    override_output = tmp_path / "override"
    overridden = load_local_app_config(output_dir=override_output, config_path=config_path)
    assert overridden.output_dir == str(override_output)
    assert overridden.db_path == str(tmp_path / "eastmoney.db")


def test_sqlite_import_existing_outputs_is_idempotent(tmp_path: Path):
    output_root = tmp_path / "reports"
    db_path = tmp_path / "eastmoney.db"
    _write_fixture_outputs(output_root)

    first = import_existing_outputs(output_root, db_path)
    second = import_existing_outputs(output_root, db_path)
    stats = health(output_root, db_path)

    assert first["reports"] == 1
    assert second["reports"] == 1
    assert stats["tables"]["reports"] == 1
    assert stats["tables"]["hotspots"] == 1
    assert stats["tables"]["coverage_history"] == 1
    assert list_reports(db_path)[0]["infoCode"] == "LOCAL001"
    assert list_hotspots(db_path)[0]["entityName"] == "本地样本"


def test_local_app_services_return_api_payloads(tmp_path: Path):
    output_root = tmp_path / "reports"
    db_path = tmp_path / "eastmoney.db"
    _write_fixture_outputs(output_root)
    services = LocalAppServices(LocalAppConfig(output_dir=str(output_root), db_path=str(db_path)))

    imported = services.import_existing()
    reports = services.reports()
    hotspots = services.hotspots()
    dashboard = services.dashboard_data()

    assert imported["ok"] is True
    assert reports["count"] == 1
    assert hotspots["items"][0]["hotspotLevel"] == "STRONG"
    assert dashboard["reports"][0]["stockName"] == "本地样本"


def test_local_app_reports_support_limit_search_and_pagination(tmp_path: Path):
    output_root = tmp_path / "reports"
    db_path = tmp_path / "eastmoney.db"

    def row(info_code: str, stock_name: str, industry_name: str, score: str) -> dict:
        return {
            "stockName": stock_name,
            "stockCode": info_code[-6:],
            "industryName": industry_name,
            "title": f"{stock_name} 深度跟踪",
            "orgName": "测试证券",
            "publishDate": "2026-05-12",
            "rating": "买入",
            "infoCode": info_code,
            "status": "ok",
            "source": "html",
            "chars": "1200",
            "summary": "订单增长",
            "signalScore": score,
            "priorityBucket": "A",
            "themeTags": "AI | 景气",
            "ratingChange": "",
            "targetPrice": "30",
            "epsForecast": "1.00",
            "peForecast": "20",
            "file": f"{info_code}.md",
            "scoreReasons": "景气改善",
            "scoreBreakdown": "{}",
            "qualityScore": "90",
        }

    _write_index(
        output_root / "研报_2026-05-12",
        [
            row("LOCAL001", "甲公司", "人工智能", "90"),
            row("LOCAL002", "乙公司", "机器人", "80"),
            row("LOCAL003", "丙公司", "新能源", "70"),
        ],
    )
    import_existing_outputs(output_root, db_path)
    services = LocalAppServices(LocalAppConfig(output_dir=str(output_root), db_path=str(db_path)))

    first_page = services.reports(limit=2, offset=0)
    second_page = services.reports(limit=2, offset=2)
    searched = services.reports(limit=10, offset=0, search="机器人")
    all_rows = services.reports(limit=0)

    assert first_page["count"] == 2
    assert first_page["total"] == 3
    assert first_page["offset"] == 0
    assert second_page["count"] == 1
    assert second_page["offset"] == 2
    assert searched["total"] == 1
    assert searched["items"][0]["stockName"] == "乙公司"
    assert all_rows["count"] == 3
    assert all_rows["limit"] == 0


def test_task_manager_transitions_to_done_with_fake_runner(tmp_path: Path):
    output_root = tmp_path / "reports"
    db_path = tmp_path / "eastmoney.db"
    commands = []

    def fake_runner(command):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout='{"ok": 1, "weak": 0, "error": 0}\n', stderr="")

    manager = TaskManager(output_root, db_path, runner=fake_runner)
    run_id = manager.start_run({"date": "2026-05-12", "limit": 1, "concurrency": 1})

    for _ in range(50):
        rows = list_runs(db_path)
        if rows and rows[0]["status"] == "done":
            break
        time.sleep(0.02)

    row = list_runs(db_path)[0]
    assert row["run_id"] == run_id
    assert row["status"] == "done"
    assert row["ok_count"] == 1
    assert "--date" in commands[0]


def test_build_fetch_command_keeps_cli_entrypoint(tmp_path: Path):
    command = build_fetch_command(
        {"date": "2026-05-12", "stock": ["样本"], "qtype": 2, "limit": 2, "no_xlsx": True},
        tmp_path,
    )
    assert command[:3] == [command[0], "-m", "eastmoney_report_scraper.cli"]
    assert "--stock" in command
    assert command[command.index("--qtype") + 1] == "2"
    assert "--no-xlsx" in command


def test_build_fetch_command_prefers_date_range_over_single_date(tmp_path: Path):
    command = build_fetch_command(
        {
            "date": "2026-05-12",
            "start_date": "2026-05-12",
            "end_date": "2026-05-14",
            "qtype": 0,
            "no_xlsx": True,
        },
        tmp_path,
    )
    assert "--date" not in command
    assert command[command.index("--start-date") + 1] == "2026-05-12"
    assert command[command.index("--end-date") + 1] == "2026-05-14"


def test_import_existing_cli_outputs_json(capsys, tmp_path: Path):
    output_root = tmp_path / "reports"
    db_path = tmp_path / "eastmoney.db"
    _write_fixture_outputs(output_root)

    run_import_existing_command(["--output-dir", str(output_root), "--db-path", str(db_path)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "import-existing"
    assert payload["imported"]["reports"] == 1
    assert db_path.exists()


def test_app_cli_open_browser_arg():
    args = parse_app_args(["--output-dir", "reports", "--port", "8765", "--open-browser"])
    assert args.output_dir == "reports"
    assert args.port == 8765
    assert args.open_browser is True


def test_local_app_html_has_tooltips_and_markdown_preview_links():
    app_css = (_APP_DIR / "static" / "app.css").read_text(encoding="utf-8")
    app_js = (_APP_DIR / "static" / "app.js").read_text(encoding="utf-8")

    assert "<title>Eastmoney研报分析</title>" in _INDEX_HTML
    assert "<h1>Eastmoney研报分析</h1>" in _INDEX_HTML
    assert 'href="/static/app.css"' in _INDEX_HTML
    assert 'src="/static/app.js"' in _INDEX_HTML
    assert "Eastmoney Local App" not in _INDEX_HTML
    assert 'id="meta" hidden' in _INDEX_HTML
    assert "交易雷达首页 / 研究工作台" in _INDEX_HTML
    assert "近期研报信号" in _INDEX_HTML
    assert 'id="radarMetrics"' in _INDEX_HTML
    assert 'id="radarList"' in _INDEX_HTML
    assert 'id="radarFocus"' in _INDEX_HTML
    assert "function renderRadar" in app_js
    assert "renderRadar(hotspots, reports)" in app_js
    assert 'id="filtersPanel"' in _INDEX_HTML
    assert 'id="globalStartDate"' in _INDEX_HTML
    assert 'id="companyFilter"' in _INDEX_HTML
    assert 'id="industryFilter"' in _INDEX_HTML
    assert 'id="brokerFilter"' in _INDEX_HTML
    assert 'id="ratingFilter"' in _INDEX_HTML
    assert 'id="hotspotFilter"' in _INDEX_HTML
    assert 'id="priorityFilter"' in _INDEX_HTML
    assert 'id="themeFilter"' in _INDEX_HTML
    assert 'id="reasonFilter"' in _INDEX_HTML
    assert 'id="minScoreFilter"' in _INDEX_HTML
    assert 'id="globalSearch"' in _INDEX_HTML
    assert 'id="resetFiltersBtn"' in _INDEX_HTML
    assert 'id="overviewPanel"' in _INDEX_HTML
    assert 'id="reportTrendChart"' in _INDEX_HTML
    assert 'id="brokerTrendChart"' in _INDEX_HTML
    assert 'id="industryHeatChart"' in _INDEX_HTML
    assert 'id="themeHeatChart"' in _INDEX_HTML
    assert 'id="reasonTrendChart"' in _INDEX_HTML
    assert 'id="qualityChart"' in _INDEX_HTML
    assert 'id="sourceChart"' in _INDEX_HTML
    assert 'id="globalOpinionTable"' in _INDEX_HTML
    assert "function filteredDashboardData" in app_js
    assert "function renderDashboardViews" in app_js
    assert "function renderOverviewCharts" in app_js
    assert "function renderGlobalOpinion" in app_js
    assert "api(\"/api/reports" not in app_js
    assert "api(\"/api/hotspots" not in app_js
    assert 'href="#analysisPanel"' in _INDEX_HTML
    assert '<option value="2">全部</option>' in _INDEX_HTML
    assert 'id="status"' in _INDEX_HTML
    assert "正在导入已有输出" in app_js
    assert "导入完成" in app_js
    assert "刷新失败" in app_js
    assert "可视化分析" in _INDEX_HTML
    assert "核心趋势" in _INDEX_HTML
    assert "估值与结构" in _INDEX_HTML
    assert "single-point" in app_css
    assert "grid-template-columns: repeat(2, minmax(300px, 1fr))" in app_css
    assert 'font-size="13"' in app_js
    assert 'id="analysisSearch"' in _INDEX_HTML
    assert 'id="analysisEntity"' in _INDEX_HTML
    assert 'id="analysisRefreshBtn"' in _INDEX_HTML
    assert 'id="analysisCoverageChart"' in _INDEX_HTML
    assert 'id="analysisBrokerChart"' in _INDEX_HTML
    assert 'id="analysisScoreChart"' in _INDEX_HTML
    assert 'id="analysisRatingChart"' in _INDEX_HTML
    assert 'id="analysisPriorityChart"' in _INDEX_HTML
    assert 'id="analysisOpinionTable"' in _INDEX_HTML
    assert 'id="analysisLatestReports"' in _INDEX_HTML
    assert "function loadAnalysis" in app_js
    assert "function filteredAnalysisEntities" in app_js
    assert 'api("/api/dashboard-data")' in app_js
    assert 'data-tip="每个日期最多抓取多少篇研报' in _INDEX_HTML
    assert "选择全部时，会先合并个股和行业列表再应用该限制" in _INDEX_HTML
    assert "let fetchTuningTouched = false;" in app_js
    assert '$("concurrency").value = "2";' in app_js
    assert '$("jitter").value = "0.5";' in app_js
    assert 'data-tip="同时抓取详情页的 worker 数' in _INDEX_HTML
    assert 'data-tip="每次详情请求额外增加 0 到该数值之间的随机等待秒数' in _INDEX_HTML
    assert 'id="reportLimit"' in _INDEX_HTML
    assert '<option value="100">100</option>' in _INDEX_HTML
    assert '<option value="0">全部</option>' in _INDEX_HTML
    assert 'id="reportSearch"' in _INDEX_HTML
    assert 'id="reportPrevBtn"' in _INDEX_HTML
    assert 'id="reportNextBtn"' in _INDEX_HTML
    assert "encodeURI(r.fileHref)" not in app_js
    assert 'href="/preview/${esc(r.fileHref)}"' in app_js


def test_local_app_serves_split_frontend_assets(tmp_path: Path):
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    try:
        from fastapi.testclient import TestClient
    except (ImportError, RuntimeError) as exc:
        pytest.skip(str(exc))

    app = create_app(LocalAppConfig(output_dir=str(tmp_path), db_path=str(tmp_path / "eastmoney.db")))
    client = TestClient(app)

    index_response = client.get("/")
    css_response = client.get("/static/app.css")
    js_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert 'href="/static/app.css"' in index_response.text
    assert 'src="/static/app.js"' in index_response.text
    assert css_response.status_code == 200
    assert ".chart-grid" in css_response.text
    assert js_response.status_code == 200
    assert "function renderDashboardViews" in js_response.text


def test_resolve_file_target_accepts_encoded_chinese_paths(tmp_path: Path):
    report_dir = tmp_path / "研报_2026-05-12"
    report_dir.mkdir()
    markdown_path = report_dir / "001——样本.md"
    markdown_path.write_text("# 样本\n", encoding="utf-8")

    encoded_path = quote("研报_2026-05-12/001——样本.md", safe="/._-()%")

    assert _resolve_file_target(tmp_path, encoded_path) == markdown_path.resolve()
    assert _resolve_file_target(tmp_path, "研报_2026-05-12/001——样本.md") == markdown_path.resolve()
    assert _resolve_file_target(tmp_path, "../outside.md") is None


def test_markdown_preview_renders_safe_html(tmp_path: Path):
    markdown_path = tmp_path / "001——样本.md"
    markdown_path.write_text("# 标题\n\n- `代码`\n\n<script>alert(1)</script>\n", encoding="utf-8")

    rendered = _markdown_to_html(markdown_path.read_text(encoding="utf-8"))
    preview = _preview_html(markdown_path, "研报_2026-05-12/001——样本.md")

    assert "<h1>标题</h1>" in rendered
    assert "<li><code>代码</code></li>" in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "001——样本.md" in preview
    assert 'href="/raw/研报_2026-05-12/001——样本.md"' in preview


def test_files_route_previews_markdown_instead_of_downloading(tmp_path: Path):
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    try:
        from fastapi.testclient import TestClient
    except (ImportError, RuntimeError) as exc:
        pytest.skip(str(exc))
    report_dir = tmp_path / "研报_2026-05-12"
    report_dir.mkdir()
    markdown_path = report_dir / "001——样本.md"
    markdown_path.write_text("# 预览标题\n", encoding="utf-8")
    app = create_app(LocalAppConfig(output_dir=str(tmp_path), db_path=str(tmp_path / "eastmoney.db")))
    client = TestClient(app)
    encoded_path = quote("研报_2026-05-12/001——样本.md", safe="/._-()%")

    preview_response = client.get(f"/files/{encoded_path}")
    raw_response = client.get(f"/raw/{encoded_path}")

    assert preview_response.status_code == 200
    assert "text/html" in preview_response.headers["content-type"]
    assert "预览标题" in preview_response.text
    assert raw_response.status_code == 200
    assert raw_response.text == "# 预览标题\n"
