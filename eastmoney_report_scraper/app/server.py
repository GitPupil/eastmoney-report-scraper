"""FastAPI server for the local app."""

from __future__ import annotations

import webbrowser
from html import escape
from pathlib import Path
from threading import Timer
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

from ..config import LocalAppConfig
from .services import LocalAppServices


def _require_app_dependencies() -> tuple[Any, Any, Any, Any]:
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import FileResponse, HTMLResponse
        import uvicorn
    except ImportError as exc:
        raise RuntimeError('Local app dependencies are missing. Install with: pip install ".[app]"') from exc
    return FastAPI, HTTPException, FileResponse, HTMLResponse, uvicorn


def _resolve_file_target(output_root: Path, relative_path: str) -> Optional[Path]:
    root = output_root.expanduser().resolve()
    candidates = [relative_path]
    decoded = unquote(relative_path)
    if decoded != relative_path:
        candidates.append(decoded)

    for candidate in candidates:
        target = (root / candidate).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            continue
        if target.exists() and target.is_file():
            return target
    return None


def _render_inline_markdown(text: str) -> str:
    escaped = escape(text)
    pieces: List[str] = []
    index = 0
    while index < len(escaped):
        start = escaped.find("`", index)
        if start < 0:
            pieces.append(escaped[index:])
            break
        end = escaped.find("`", start + 1)
        if end < 0:
            pieces.append(escaped[index:])
            break
        pieces.append(escaped[index:start])
        pieces.append(f"<code>{escaped[start + 1:end]}</code>")
        index = end + 1
    return "".join(pieces)


def _markdown_to_html(markdown_text: str) -> str:
    html_parts: List[str] = []
    list_open = False
    code_open = False
    code_lines: List[str] = []

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            html_parts.append("</ul>")
            list_open = False

    def close_code() -> None:
        nonlocal code_open, code_lines
        if code_open:
            html_parts.append(f"<pre><code>{escape(chr(10).join(code_lines))}</code></pre>")
            code_open = False
            code_lines = []

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            if code_open:
                close_code()
            else:
                close_list()
                code_open = True
                code_lines = []
            continue
        if code_open:
            code_lines.append(raw_line)
            continue
        if not stripped:
            close_list()
            continue
        if stripped.startswith("#"):
            close_list()
            level = min(3, len(stripped) - len(stripped.lstrip("#")))
            title = stripped[level:].strip()
            if title:
                html_parts.append(f"<h{level}>{_render_inline_markdown(title)}</h{level}>")
            continue
        if stripped.startswith(("- ", "* ")):
            if not list_open:
                html_parts.append("<ul>")
                list_open = True
            html_parts.append(f"<li>{_render_inline_markdown(stripped[2:].strip())}</li>")
            continue
        if stripped.startswith(">"):
            close_list()
            html_parts.append(f"<blockquote>{_render_inline_markdown(stripped.lstrip('> ').strip())}</blockquote>")
            continue
        if stripped in {"---", "***", "___"}:
            close_list()
            html_parts.append("<hr>")
            continue
        close_list()
        html_parts.append(f"<p>{_render_inline_markdown(stripped)}</p>")

    close_code()
    close_list()
    return "\n".join(html_parts)


def _preview_html(target: Path, relative_path: str) -> str:
    markdown_text = target.read_text(encoding="utf-8", errors="replace")
    title = target.name
    raw_href = f"/raw/{escape(relative_path, quote=True)}"
    rendered = _markdown_to_html(markdown_text)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} - Preview</title>
  <style>
    :root {{ --bg: #f6f4ef; --surface: #fff; --line: #d9d3c6; --text: #1c2730; --muted: #65717d; --blue: #2563a8; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", "Microsoft YaHei", sans-serif; font-size: 15px; line-height: 1.68; }}
    .page {{ max-width: 980px; margin: 0 auto; padding: 22px; }}
    header {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; padding-bottom: 16px; border-bottom: 1px solid var(--line); }}
    h1 {{ margin: 0; font-size: 23px; line-height: 1.35; letter-spacing: 0; }}
    .muted {{ color: var(--muted); font-size: 13px; word-break: break-all; }}
    .actions {{ display: flex; gap: 10px; flex-wrap: wrap; flex-shrink: 0; }}
    a.button {{ display: inline-flex; align-items: center; min-height: 34px; padding: 0 12px; border: 1px solid var(--line); border-radius: 6px; color: var(--blue); background: #fff; text-decoration: none; font-size: 14px; }}
    article {{ margin-top: 18px; padding: 22px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); }}
    article h1, article h2, article h3 {{ margin: 1.1em 0 0.45em; line-height: 1.35; }}
    article h1:first-child, article h2:first-child, article h3:first-child {{ margin-top: 0; }}
    p {{ margin: 0.65em 0; }}
    ul {{ padding-left: 1.4em; }}
    blockquote {{ margin: 0.8em 0; padding-left: 12px; border-left: 3px solid var(--line); color: #46535f; }}
    code {{ padding: 1px 4px; border-radius: 4px; background: #eee8dc; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 0.92em; }}
    pre {{ overflow: auto; padding: 12px; border-radius: 8px; background: #1c2730; color: #f8fafc; }}
    pre code {{ padding: 0; background: transparent; color: inherit; }}
    @media (max-width: 720px) {{ header {{ flex-direction: column; }} article {{ padding: 16px; }} }}
  </style>
</head>
<body>
  <main class="page">
    <header>
      <div>
        <h1>{escape(title)}</h1>
        <div class="muted">{escape(relative_path)}</div>
      </div>
      <div class="actions">
        <a class="button" href="/">返回 App</a>
        <a class="button" href="{raw_href}">原始文件</a>
      </div>
    </header>
    <article>{rendered}</article>
  </main>
</body>
</html>
"""


def create_app(config: LocalAppConfig):
    FastAPI, HTTPException, FileResponse, HTMLResponse, _ = _require_app_dependencies()
    services = LocalAppServices(config)
    app = FastAPI(title="Eastmoney Report Scraper Local App")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(_INDEX_HTML)

    @app.get("/api/health")
    def health():
        return services.health()

    @app.post("/api/import-existing")
    def import_existing():
        return services.import_existing()

    @app.get("/api/reports")
    def reports(limit: int = 200, offset: int = 0, search: str = ""):
        return services.reports(limit=limit, offset=offset, search=search)

    @app.get("/api/hotspots")
    def hotspots(limit: int = 100):
        return services.hotspots(limit=limit)

    @app.get("/api/dashboard-data")
    def dashboard_data():
        return services.dashboard_data()

    @app.get("/api/runs")
    def runs(limit: int = 50):
        return services.runs(limit=limit)

    @app.post("/api/runs")
    def start_run(payload: Dict[str, Any]):
        return services.start_run(payload)

    @app.get("/files/{relative_path:path}")
    def files(relative_path: str):
        target = _resolve_file_target(Path(config.output_dir), relative_path)
        if target is None:
            raise HTTPException(status_code=404, detail="file not found")
        if target.suffix.lower() == ".md":
            return HTMLResponse(_preview_html(target, relative_path))
        return FileResponse(target)

    @app.get("/raw/{relative_path:path}")
    def raw_file(relative_path: str):
        target = _resolve_file_target(Path(config.output_dir), relative_path)
        if target is None:
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(target)

    @app.get("/preview/{relative_path:path}", response_class=HTMLResponse)
    def preview(relative_path: str):
        target = _resolve_file_target(Path(config.output_dir), relative_path)
        if target is None or target.suffix.lower() != ".md":
            raise HTTPException(status_code=404, detail="file not found")
        return HTMLResponse(_preview_html(target, relative_path))

    return app


def run_app(config: LocalAppConfig, open_browser: bool = False) -> None:
    _, _, _, _, uvicorn = _require_app_dependencies()
    app = create_app(config)
    if open_browser:
        Timer(1.0, lambda: webbrowser.open(f"http://{config.host}:{config.port}")).start()
    uvicorn.run(app, host=config.host, port=config.port)


_INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Eastmoney研报分析</title>
  <style>
    :root {
      --bg: #eef1f4;
      --surface: #fff;
      --line: #d6dde5;
      --text: #1c2730;
      --muted: #65717d;
      --teal: #0f766e;
      --blue: #2563a8;
      --rose: #be4b63;
      --amber: #b7791f;
      --shadow: 0 12px 30px rgba(34, 32, 28, 0.08);
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", "Microsoft YaHei", sans-serif; font-size: 14px; }
    .page { max-width: 1320px; margin: 0 auto; padding: 22px; }
    header { display: flex; justify-content: space-between; align-items: flex-end; gap: 18px; padding-bottom: 18px; border-bottom: 1px solid var(--line); }
    h1 { margin: 0; font-size: 28px; letter-spacing: 0; }
    h2 { margin: 0 0 12px; font-size: 17px; }
    .muted { color: var(--muted); }
    .eyebrow { color: var(--teal); font-size: 12px; font-weight: 750; letter-spacing: 0; margin-bottom: 5px; }
    .radar-home { display: grid; grid-template-columns: minmax(0, 2fr) minmax(300px, 0.9fr); gap: 14px; margin-top: 16px; }
    .radar-main, .radar-side { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow); min-width: 0; }
    .radar-main { padding: 18px; }
    .radar-side { padding: 16px; display: flex; flex-direction: column; gap: 14px; }
    .radar-title-row { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; border-bottom: 1px solid var(--line); padding-bottom: 12px; }
    .radar-title-row h2 { margin-bottom: 3px; font-size: 22px; }
    .radar-stamp { color: var(--muted); font-size: 12px; font-weight: 650; white-space: nowrap; }
    .radar-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }
    .radar-metric { border: 1px solid var(--line); border-radius: 8px; padding: 11px 12px; background: #fbfcfd; min-height: 76px; }
    .radar-metric .label { color: var(--muted); font-size: 12px; font-weight: 650; }
    .radar-metric .value { margin-top: 6px; font-size: 26px; font-weight: 800; }
    .radar-metric .sub { margin-top: 3px; color: var(--muted); font-size: 12px; }
    .radar-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }
    .radar-item { border: 1px solid var(--line); border-left: 4px solid var(--blue); border-radius: 8px; background: #fff; padding: 11px 12px; min-height: 116px; }
    .radar-item.strong { border-left-color: var(--rose); }
    .radar-item.watch { border-left-color: var(--amber); }
    .radar-item-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
    .radar-name { font-size: 16px; font-weight: 800; }
    .radar-meta { margin-top: 4px; color: var(--muted); font-size: 12px; }
    .radar-stats { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 9px; color: var(--muted); font-size: 12px; font-weight: 650; }
    .reason-list { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
    .reason-list .pill { background: #edf7f4; color: var(--teal); }
    .radar-focus { border-top: 1px solid var(--line); padding-top: 12px; }
    .radar-focus .name { font-size: 18px; font-weight: 800; }
    .quick-links { display: grid; gap: 8px; }
    .quick-links a { display: flex; justify-content: space-between; align-items: center; min-height: 34px; padding: 0 10px; border: 1px solid var(--line); border-radius: 6px; background: #fbfcfd; color: var(--text); text-decoration: none; font-weight: 700; }
    .quick-links a span { color: var(--muted); font-weight: 650; }
    .workspace-title { grid-column: span 12; display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-top: 4px; }
    .workspace-title h2 { margin: 0; font-size: 20px; }
    .grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; margin-top: 16px; }
    .panel { grid-column: span 6; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 16px; box-shadow: var(--shadow); min-width: 0; }
    .wide { grid-column: span 12; }
    .kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }
    .kpi { background: #fbfaf7; border: 1px solid var(--line); border-radius: 8px; padding: 12px; min-height: 74px; }
    .kpi .label { color: var(--muted); font-size: 12px; font-weight: 700; }
    .kpi .value { margin-top: 6px; font-size: 24px; font-weight: 750; }
    .kpi .sub { margin-top: 3px; color: var(--muted); font-size: 12px; }
    .form { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 10px; }
    .global-filters { display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 10px; align-items: end; }
    .filter-actions { display: flex; gap: 8px; align-items: end; }
    label { display: flex; flex-direction: column; gap: 5px; color: var(--muted); font-size: 12px; font-weight: 650; }
    input, select, button { height: 36px; border: 1px solid var(--line); border-radius: 6px; font: inherit; }
    input, select { padding: 0 10px; background: #fff; color: var(--text); }
    button { padding: 0 12px; background: var(--teal); color: #fff; cursor: pointer; }
    button:disabled { opacity: 0.45; cursor: not-allowed; }
    button.secondary { background: var(--blue); }
    button.ghost { background: #fff; color: var(--blue); }
    .field-title { display: inline-flex; align-items: center; gap: 5px; min-height: 16px; }
    .help { position: relative; display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; border: 1px solid var(--line); border-radius: 999px; color: var(--blue); background: #fbfaf7; font-size: 11px; line-height: 1; cursor: help; }
    .help:hover::after, .help:focus::after { content: attr(data-tip); position: absolute; z-index: 5; left: 50%; bottom: calc(100% + 7px); transform: translateX(-50%); width: max-content; max-width: 260px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 6px; background: #1c2730; color: #fff; box-shadow: var(--shadow); font-size: 12px; font-weight: 500; line-height: 1.45; white-space: normal; }
    .help:hover::before, .help:focus::before { content: ""; position: absolute; left: 50%; bottom: calc(100% + 2px); transform: translateX(-50%); border: 5px solid transparent; border-top-color: #1c2730; }
    table { width: 100%; border-collapse: collapse; min-width: 780px; }
    th, td { padding: 9px 10px; border-bottom: 1px solid #ebe6dc; text-align: left; vertical-align: top; }
    th { background: #eee8dc; color: #33404a; font-size: 12px; position: sticky; top: 0; }
    .table-wrap { overflow: auto; max-height: 420px; border: 1px solid var(--line); border-radius: 8px; }
    .pill { display: inline-flex; padding: 2px 7px; border-radius: 999px; background: #eee8dc; font-size: 12px; font-weight: 650; }
    .pill.good { background: #dcfce7; color: #166534; }
    .pill.bad { background: #ffe4e6; color: #9f1239; }
    .pill.strong, .pill.hot { background: #ffe4e6; color: #9f1239; }
    .pill.watch { background: #fef3c7; color: #92400e; }
    .pill.a, .pill.up { background: #dcfce7; color: #166534; }
    .pill.b, .pill.flat { background: #e0f2fe; color: #075985; }
    .pill.down { background: #fee2e2; color: #991b1b; }
    .tags { display: flex; flex-wrap: wrap; gap: 5px; }
    .summary { max-width: 320px; color: #33404a; line-height: 1.45; }
    .link-button { height: 28px; padding: 0 9px; border-color: var(--line); background: #fff; color: var(--blue); }
    .actions { display: flex; gap: 10px; flex-wrap: wrap; }
    .status { margin-top: 8px; min-height: 18px; color: var(--muted); font-size: 12px; }
    .status.error { color: var(--rose); }
    .status.good { color: var(--teal); }
    .section-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
    .report-tools { display: flex; align-items: flex-end; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
    .report-tools label { min-width: 112px; }
    .report-tools .search { min-width: 230px; }
    .pager { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 12px; font-weight: 650; }
    .analysis-tools { display: flex; align-items: flex-end; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
    .analysis-tools label { min-width: 220px; }
    .analysis-kpis { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
    .analysis-kpi { background: #fbfaf7; border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; min-height: 68px; }
    .analysis-kpi .label { color: var(--muted); font-size: 13px; font-weight: 650; }
    .analysis-kpi .value { margin-top: 4px; font-size: 19px; font-weight: 750; word-break: break-word; }
    .analysis-kpi .sub { margin-top: 3px; color: var(--muted); font-size: 13px; }
    .analysis-section-title { margin: 14px 0 10px; color: #33404a; font-size: 15px; font-weight: 750; }
    .chart-grid { display: grid; grid-template-columns: repeat(2, minmax(300px, 1fr)); gap: 12px; margin-top: 0; }
    .chart-grid.secondary { grid-template-columns: repeat(2, minmax(300px, 1fr)); }
    .chart-card { border: 1px solid var(--line); border-radius: 8px; background: #fbfaf7; padding: 12px; min-width: 0; min-height: 260px; }
    .chart-grid.secondary .chart-card { min-height: 238px; }
    .chart-card h3 { margin: 0 0 8px; font-size: 15px; color: #33404a; }
    .chart { height: 205px; overflow: hidden; }
    .chart-grid.secondary .chart { height: 182px; }
    .single-point { height: 100%; display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 4px; color: #33404a; }
    .single-point .value { font-size: 36px; font-weight: 800; line-height: 1; }
    .single-point .label { color: var(--muted); font-size: 14px; font-weight: 650; }
    .single-point .dot { width: 10px; height: 10px; border-radius: 999px; margin-top: 5px; }
    .empty { display: flex; align-items: center; justify-content: center; min-height: 80px; color: var(--muted); }
    .mini-table { margin-top: 12px; }
    .mini-table .table-wrap { max-height: 260px; }
    @media (max-width: 1100px) { .global-filters { grid-template-columns: repeat(3, minmax(120px, 1fr)); } }
    @media (max-width: 900px) { .panel { grid-column: span 12; } .form, .kpis, .radar-metrics { grid-template-columns: repeat(2, 1fr); } .global-filters { grid-template-columns: repeat(2, minmax(120px, 1fr)); } .radar-home, .radar-list { grid-template-columns: 1fr; } header, .radar-title-row, .workspace-title { align-items: flex-start; flex-direction: column; } }
    @media (max-width: 900px) { .section-head { flex-direction: column; } .report-tools, .analysis-tools { justify-content: flex-start; width: 100%; } .report-tools label, .analysis-tools label { flex: 1 1 160px; } .report-tools .search { flex-basis: 100%; } .analysis-kpis { grid-template-columns: repeat(2, 1fr); } .chart-grid, .chart-grid.secondary { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main class="page">
    <header>
      <div>
        <div class="eyebrow">交易雷达首页 / 研究工作台</div>
        <h1>Eastmoney研报分析</h1>
        <div class="muted" id="meta" hidden></div>
        <div class="status" id="status">准备就绪</div>
      </div>
      <div class="actions">
        <button class="secondary" id="importBtn">导入已有输出</button>
        <button class="ghost" id="refreshBtn">刷新</button>
      </div>
    </header>

    <section class="radar-home" aria-label="交易雷达首页">
      <article class="radar-main">
        <div class="radar-title-row">
          <div>
            <div class="eyebrow">交易雷达</div>
            <h2>近期研报信号</h2>
            <div class="muted">优先扫首次覆盖、多券商共振、覆盖加速和强热点。</div>
          </div>
          <div class="radar-stamp" id="radarUpdated">等待刷新</div>
        </div>
        <div class="radar-metrics" id="radarMetrics"></div>
        <div class="radar-list" id="radarList"></div>
      </article>
      <aside class="radar-side">
        <div>
          <div class="eyebrow">工作台入口</div>
          <h2>下一步</h2>
          <div class="quick-links">
            <a href="#fetchPanel">发起抓取 <span>参数 / 范围</span></a>
            <a href="#filtersPanel">全局筛选 <span>日期 / 主题</span></a>
            <a href="#overviewPanel">趋势总览 <span>热点 / 质量</span></a>
            <a href="#analysisPanel">研究分析 <span>趋势 / 观点</span></a>
            <a href="#reportsPanel">研报明细 <span>搜索 / 预览</span></a>
          </div>
        </div>
        <div class="radar-focus" id="radarFocus">
          <div class="muted">导入或刷新后显示当前最值得关注的信号。</div>
        </div>
      </aside>
    </section>

    <section class="grid">
      <div class="workspace-title">
        <div>
          <div class="eyebrow">研究工作台</div>
          <h2>数据、抓取与深挖</h2>
        </div>
        <div class="muted">从雷达信号进入公司、行业、券商和研报原文。</div>
      </div>
      <article class="panel wide" id="filtersPanel">
        <div class="section-head">
          <div>
            <h2>全局筛选</h2>
            <div class="muted">筛选会同步影响 KPI、热点、趋势、观点变化、研究对象和研报明细。</div>
          </div>
          <div class="filter-actions">
            <button class="ghost" id="resetFiltersBtn">重置筛选</button>
          </div>
        </div>
        <div class="global-filters">
          <label>开始日期<input id="globalStartDate" type="date"></label>
          <label>结束日期<input id="globalEndDate" type="date"></label>
          <label>公司<select id="companyFilter"><option value="">全部公司</option></select></label>
          <label>行业<select id="industryFilter"><option value="">全部行业</option></select></label>
          <label>券商<select id="brokerFilter"><option value="">全部券商</option></select></label>
          <label>评级<select id="ratingFilter"><option value="">全部评级</option></select></label>
          <label>热点等级<select id="hotspotFilter"><option value="">全部热点</option></select></label>
          <label>优先级<select id="priorityFilter"><option value="">全部优先级</option></select></label>
          <label>主题<select id="themeFilter"><option value="">全部主题</option></select></label>
          <label>原因<select id="reasonFilter"><option value="">全部原因</option></select></label>
          <label>最低分<input id="minScoreFilter" type="number" min="0" max="100" placeholder="signal score"></label>
          <label>关键词<input id="globalSearch" placeholder="标题 / 摘要 / 主题 / 原因"></label>
        </div>
      </article>
      <article class="panel wide"><div class="kpis" id="kpis"></div></article>
      <article class="panel wide" id="overviewPanel">
        <div class="section-head">
          <div>
            <h2>趋势总览</h2>
            <div class="muted">把静态 Dashboard 的高频观察点放到本地 App 首页。</div>
          </div>
          <div class="muted" id="dashboardFooter">等待分析数据</div>
        </div>
        <div class="chart-grid secondary">
          <div class="chart-card"><h3>研报数量趋势</h3><div class="chart" id="reportTrendChart"></div></div>
          <div class="chart-card"><h3>券商扩散趋势</h3><div class="chart" id="brokerTrendChart"></div></div>
          <div class="chart-card"><h3>行业热度</h3><div class="chart" id="industryHeatChart"></div></div>
          <div class="chart-card"><h3>主题热度</h3><div class="chart" id="themeHeatChart"></div></div>
          <div class="chart-card"><h3>热点原因</h3><div class="chart" id="reasonTrendChart"></div></div>
          <div class="chart-card"><h3>数据质量</h3><div class="chart" id="qualityChart"></div></div>
          <div class="chart-card"><h3>抽取来源</h3><div class="chart" id="sourceChart"></div></div>
        </div>
      </article>
      <article class="panel wide" id="hotspotsPanel"><h2>近期热点</h2><div class="table-wrap"><table id="hotspots"></table></div></article>
      <article class="panel wide" id="opinionPanel"><h2>全局观点变化</h2><div class="table-wrap"><table id="globalOpinionTable"></table></div></article>
      <article class="panel wide" id="analysisPanel">
        <div class="section-head">
          <h2>可视化分析</h2>
          <div class="analysis-tools">
            <label>对象搜索<input id="analysisSearch" placeholder="公司 / 代码 / 行业"></label>
            <label>研究对象<select id="analysisEntity"><option value="">加载中</option></select></label>
            <button class="secondary" id="analysisRefreshBtn">刷新分析</button>
          </div>
        </div>
        <div class="analysis-kpis" id="analysisKpis"></div>
        <div class="analysis-section-title">核心趋势</div>
        <div class="chart-grid primary">
          <div class="chart-card"><h3>覆盖次数趋势</h3><div class="chart" id="analysisCoverageChart"></div></div>
          <div class="chart-card"><h3>券商扩散趋势</h3><div class="chart" id="analysisBrokerChart"></div></div>
          <div class="chart-card"><h3>信号评分趋势</h3><div class="chart" id="analysisScoreChart"></div></div>
        </div>
        <div class="analysis-section-title">估值与结构</div>
        <div class="chart-grid secondary">
          <div class="chart-card"><h3>目标价轨迹</h3><div class="chart" id="analysisTargetChart"></div></div>
          <div class="chart-card"><h3>EPS 轨迹</h3><div class="chart" id="analysisEpsChart"></div></div>
          <div class="chart-card"><h3>评级分布</h3><div class="chart" id="analysisRatingChart"></div></div>
          <div class="chart-card"><h3>等级分布</h3><div class="chart" id="analysisPriorityChart"></div></div>
          <div class="chart-card"><h3>活跃券商</h3><div class="chart" id="analysisBrokerMix"></div></div>
          <div class="chart-card"><h3>主题分布</h3><div class="chart" id="analysisThemeMix"></div></div>
        </div>
        <div class="mini-table">
          <h2>评级 / 目标价 / EPS / 等级变化</h2>
          <div class="table-wrap"><table id="analysisOpinionTable"></table></div>
        </div>
        <div class="mini-table">
          <h2>最新研报</h2>
          <div class="table-wrap"><table id="analysisLatestReports"></table></div>
        </div>
      </article>
      <article class="panel wide" id="reportsPanel">
        <div class="section-head">
          <h2>研报明细</h2>
          <div class="report-tools">
            <label>显示数量<select id="reportLimit"><option value="100">100</option><option value="300">300</option><option value="1000">1000</option><option value="0">全部</option></select></label>
            <label class="search">搜索<input id="reportSearch" placeholder="公司 / 行业 / 券商 / 评级 / 关键词"></label>
            <button class="secondary" id="reportSearchBtn">搜索</button>
            <button class="ghost" id="reportClearBtn">清空</button>
            <div class="pager">
              <button class="ghost" id="reportPrevBtn">上一页</button>
              <span id="reportPageInfo">-</span>
              <button class="ghost" id="reportNextBtn">下一页</button>
            </div>
          </div>
        </div>
        <div class="table-wrap"><table id="reports"></table></div>
      </article>
      <article class="panel wide" id="fetchPanel">
        <h2>发起抓取</h2>
        <div class="form">
          <label>单日日期<input id="date" type="date"></label>
          <label>区间开始<input id="startDate" type="date"></label>
          <label>区间结束<input id="endDate" type="date"></label>
          <label>类型<select id="qtype"><option value="2">全部</option><option value="0">个股研报</option><option value="1">行业研报</option></select></label>
          <label>股票/代码<input id="stock" placeholder="可逗号分隔"></label>
          <label>行业<input id="industry" placeholder="可逗号分隔"></label>
          <label>券商<input id="org" placeholder="可逗号分隔"></label>
          <label>评级<input id="rating" placeholder="可逗号分隔"></label>
          <label><span class="field-title">limit<span class="help" tabindex="0" data-tip="每个日期最多抓取多少篇研报；留空表示不限制。选择全部时，会先合并个股和行业列表再应用该限制。">?</span></span><input id="limit" type="number" min="1"></label>
          <label><span class="field-title">并发<span class="help" tabindex="0" data-tip="同时抓取详情页的 worker 数；数值越大越快，但请求压力也更高。">?</span></span><input id="concurrency" type="number" min="1" value="1"></label>
          <label><span class="field-title">jitter<span class="help" tabindex="0" data-tip="每次详情请求额外增加 0 到该数值之间的随机等待秒数，适合批量抓取时放缓节奏。">?</span></span><input id="jitter" type="number" min="0" step="0.1" value="0"></label>
          <label>&nbsp;<button id="runBtn">开始</button></label>
        </div>
      </article>
      <article class="panel wide" id="tasksPanel"><h2>近期抓取</h2><div class="table-wrap"><table id="runs"></table></div></article>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const levelRank = { STRONG: 0, HOT: 1, WATCH: 2 };
    const filterIds = [
      "globalStartDate", "globalEndDate", "companyFilter", "industryFilter", "brokerFilter",
      "ratingFilter", "hotspotFilter", "priorityFilter", "themeFilter", "reasonFilter",
      "minScoreFilter", "globalSearch"
    ];
    let reportPage = 1;
    let fetchTuningTouched = false;
    let analysisData = { reports: [], hotspots: [], entityDrilldowns: [], opinionTrends: [], meta: {} };
    let latestHealth = null;
    let latestRuns = { items: [] };
    let filtersInitialized = false;
    const api = async (path, options = {}) => {
      const response = await fetch(path, options);
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    };
    const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
    const split = (value) => String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
    function setStatus(message, kind = "") {
      const el = $("status");
      el.className = `status ${kind}`.trim();
      el.textContent = message;
    }
    function setTopBusy(busy) {
      $("importBtn").disabled = busy;
      $("refreshBtn").disabled = busy;
    }
    function formatImported(imported) {
      const safe = imported || {};
      return `研报 ${safe.reports || 0}，热点 ${safe.hotspots || 0}，覆盖历史 ${safe.coverage_history || 0}，manifest ${safe.manifests || 0}`;
    }
    function pill(value) {
      const lower = String(value || "").toLowerCase();
      const cls = lower === "done" || lower === "ok" ? "good"
        : lower === "failed" || lower === "error" ? "bad"
        : lower === "strong" ? "strong"
        : lower === "hot" ? "hot"
        : lower === "watch" ? "watch"
        : lower === "a" ? "a"
        : lower === "b" ? "b"
        : lower === "up" ? "up"
        : lower === "down" ? "down"
        : lower === "flat" ? "flat"
        : "";
      return `<span class="pill ${cls}">${esc(value || "-")}</span>`;
    }
    function numberField(row, names) {
      for (const name of names) {
        const raw = row && row[name];
        if (raw === undefined || raw === null || raw === "") continue;
        const value = Number(raw);
        if (Number.isFinite(value)) return value;
      }
      return 0;
    }
    function reasonCodes(row) {
      const raw = row ? row.reasonCodes || row.reason_codes || "" : "";
      if (Array.isArray(raw)) return raw.filter(Boolean);
      return String(raw).split(/[|,;，、]/).map((item) => item.trim()).filter(Boolean);
    }
    function reasonLabel(code) {
      const labels = {
        FIRST_COVERAGE: "首次覆盖",
        REACTIVATED_COVERAGE: "重新覆盖",
        MULTI_BROKER: "多券商",
        COVERAGE_ACCELERATION: "覆盖加速",
        INDUSTRY_RESONANCE: "行业共振",
        HIGH_BUY_RATIO: "高买入率",
      };
      return labels[code] || code;
    }
    function uniq(values) {
      return [...new Set((values || []).filter(Boolean).map(String))].sort((a, b) => a.localeCompare(b, "zh-CN"));
    }
    function optionList(values, label) {
      return [`<option value="">全部${label}</option>`, ...values.map((value) => `<option value="${esc(value)}">${esc(value)}</option>`)].join("");
    }
    function setSelectOptions(id, values, label) {
      const el = $(id);
      const current = el.value;
      const options = uniq(values);
      el.innerHTML = optionList(options, label);
      if (current && options.includes(current)) el.value = current;
    }
    function allReports() {
      return (analysisData && analysisData.reports) || [];
    }
    function allHotspots() {
      return (analysisData && analysisData.hotspots) || [];
    }
    function allEntities() {
      return (analysisData && analysisData.entityDrilldowns) || [];
    }
    function dashboardDates() {
      return uniq(allReports().map((row) => row.date));
    }
    function populateGlobalFilters() {
      const reports = allReports();
      const hotspots = allHotspots();
      const dates = dashboardDates();
      if (dates.length && (!filtersInitialized || (!$("globalStartDate").value && !$("globalEndDate").value))) {
        $("globalStartDate").value = dates[0];
        $("globalEndDate").value = dates[dates.length - 1];
      }
      setSelectOptions("companyFilter", [
        ...reports.map((row) => row.stockName || row.stockCode),
        ...hotspots.filter((row) => row.entityType === "company").map((row) => row.entityName),
      ], "公司");
      setSelectOptions("industryFilter", [
        ...reports.map((row) => row.industryName),
        ...hotspots.map((row) => row.industryName || (row.entityType === "industry" ? row.entityName : "")),
      ], "行业");
      setSelectOptions("brokerFilter", reports.map((row) => row.orgName), "券商");
      setSelectOptions("ratingFilter", reports.map((row) => row.rating), "评级");
      setSelectOptions("hotspotFilter", hotspots.map((row) => row.hotspotLevel), "热点");
      setSelectOptions("priorityFilter", reports.map((row) => row.priorityBucket), "优先级");
      setSelectOptions("themeFilter", reports.flatMap((row) => row.themeTags || []), "主题");
      setSelectOptions("reasonFilter", hotspots.flatMap((row) => reasonCodes(row)), "原因");
      filtersInitialized = true;
    }
    function readFilters() {
      return {
        startDate: $("globalStartDate").value,
        endDate: $("globalEndDate").value,
        company: $("companyFilter").value,
        industry: $("industryFilter").value,
        broker: $("brokerFilter").value,
        rating: $("ratingFilter").value,
        hotspot: $("hotspotFilter").value,
        priority: $("priorityFilter").value,
        theme: $("themeFilter").value,
        reason: $("reasonFilter").value,
        minScore: Number($("minScoreFilter").value || 0),
        search: $("globalSearch").value.trim().toLowerCase(),
      };
    }
    function inDate(date, filters) {
      if (!date) return true;
      if (filters.startDate && date < filters.startDate) return false;
      if (filters.endDate && date > filters.endDate) return false;
      return true;
    }
    function includesText(row, text) {
      if (!text) return true;
      const haystack = [
        row.stockName, row.stockCode, row.industryName, row.title, row.orgName, row.rating, row.summary,
        ...(row.themeTags || []), ...(row.scoreReasons || []), ...(row.reasonCodes || []), ...(row.reasons || [])
      ].join(" ").toLowerCase();
      return haystack.includes(text);
    }
    function entityKeyForReport(row) {
      const entities = allEntities();
      const company = entities.find((entity) => entity.entityType === "company" && ((row.stockCode && entity.stockCode === row.stockCode) || entity.label === row.stockName));
      if (company) return company.entityKey;
      const industry = entities.find((entity) => entity.entityType === "industry" && entity.label === row.industryName);
      return industry ? industry.entityKey : "";
    }
    function entityKeysForReport(row) {
      const entities = allEntities();
      const keys = [];
      const company = entities.find((entity) => entity.entityType === "company" && ((row.stockCode && entity.stockCode === row.stockCode) || entity.label === row.stockName));
      const industry = entities.find((entity) => entity.entityType === "industry" && entity.label === row.industryName);
      if (company) keys.push(company.entityKey);
      if (industry) keys.push(industry.entityKey);
      return keys;
    }
    function entityKeyForHotspot(row) {
      const entities = allEntities();
      const company = entities.find((entity) => entity.entityType === "company" && row.entityType === "company" && ((row.stockCode && entity.stockCode === row.stockCode) || entity.label === row.entityName));
      if (company) return company.entityKey;
      const industry = entities.find((entity) => entity.entityType === "industry" && (entity.label === row.entityName || entity.label === row.industryName));
      return industry ? industry.entityKey : "";
    }
    function entityKeyForOpinion(row) {
      const entities = allEntities();
      const company = entities.find((entity) => entity.entityType === "company" && ((row.stockCode && entity.stockCode === row.stockCode) || entity.label === row.stockName));
      if (company) return company.entityKey;
      const industry = entities.find((entity) => entity.entityType === "industry" && (entity.label === row.industryName || entity.label === row.stockName));
      return industry ? industry.entityKey : "";
    }
    function reportMatches(row, filters) {
      if (!inDate(row.date, filters)) return false;
      if (!includesText(row, filters.search)) return false;
      if (filters.company && row.stockName !== filters.company && row.stockCode !== filters.company) return false;
      if (filters.industry && row.industryName !== filters.industry) return false;
      if (filters.broker && row.orgName !== filters.broker) return false;
      if (filters.rating && row.rating !== filters.rating) return false;
      if (filters.priority && row.priorityBucket !== filters.priority) return false;
      if (filters.theme && !(row.themeTags || []).includes(filters.theme)) return false;
      if (Number(row.signalScore || 0) < filters.minScore) return false;
      if (filters.hotspot || filters.reason) {
        const keys = new Set(entityKeysForReport(row));
        const matchedHotspot = allHotspots().some((hotspot) => {
          const key = entityKeyForHotspot(hotspot);
          return key && keys.has(key)
            && (!filters.hotspot || hotspot.hotspotLevel === filters.hotspot)
            && (!filters.reason || reasonCodes(hotspot).includes(filters.reason));
        });
        if (!matchedHotspot) return false;
      }
      return true;
    }
    function hotspotMatches(row, filters, reportKeys) {
      const directText = !filters.search || includesText(row, filters.search);
      if (!inDate(row.latestPublishDate || row.latestDate, filters)) return false;
      if (!directText) return false;
      if (filters.company && row.entityName !== filters.company && row.stockCode !== filters.company) return false;
      if (filters.industry && row.industryName !== filters.industry && row.entityName !== filters.industry) return false;
      if (filters.hotspot && row.hotspotLevel !== filters.hotspot) return false;
      if (filters.reason && !reasonCodes(row).includes(filters.reason)) return false;
      const needsReportContext = Boolean(filters.broker || filters.rating || filters.priority || filters.theme || filters.minScore);
      if (needsReportContext) {
        const key = entityKeyForHotspot(row);
        if (!key || !reportKeys.has(key)) return false;
      }
      return true;
    }
    function opinionMatches(row, filters, reportKeys) {
      const haystack = [row.stockName, row.stockCode, row.industryName, row.orgName, row.ratingChange, row.latestRating, row.previousRating].join(" ").toLowerCase();
      if (!inDate(row.latestDate, filters)) return false;
      if (filters.search && !haystack.includes(filters.search)) return false;
      if (filters.company && row.stockName !== filters.company && row.stockCode !== filters.company) return false;
      if (filters.industry && row.industryName !== filters.industry) return false;
      if (filters.broker && row.orgName !== filters.broker) return false;
      const needsReportContext = Boolean(filters.rating || filters.priority || filters.theme || filters.hotspot || filters.reason || filters.minScore);
      if (needsReportContext) {
        const key = entityKeyForOpinion(row);
        if (!key || !reportKeys.has(key)) return false;
      }
      return true;
    }
    function filteredDashboardData() {
      const filters = readFilters();
      const reports = allReports().filter((row) => reportMatches(row, filters));
      const reportKeys = new Set(reports.flatMap((row) => entityKeysForReport(row)));
      const hotspots = allHotspots().filter((row) => hotspotMatches(row, filters, reportKeys));
      const opinions = ((analysisData && analysisData.opinionTrends) || []).filter((row) => opinionMatches(row, filters, reportKeys));
      return { filters, reports, hotspots, opinions, reportKeys };
    }
    function countUnique(rows, getter) {
      return new Set((rows || []).map(getter).filter(Boolean)).size;
    }
    function countBy(rows, getter, limit = 12) {
      const counter = {};
      (rows || []).forEach((row) => {
        const value = getter(row);
        if (!value) return;
        counter[value] = (counter[value] || 0) + 1;
      });
      return Object.keys(counter).map((name) => ({ name, count: counter[name] })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "zh-CN")).slice(0, limit);
    }
    function countTokens(rows, getter, limit = 12) {
      const counter = {};
      (rows || []).forEach((row) => (getter(row) || []).forEach((value) => {
        if (!value) return;
        counter[value] = (counter[value] || 0) + 1;
      }));
      return Object.keys(counter).map((name) => ({ name, count: counter[name] })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "zh-CN")).slice(0, limit);
    }
    function seriesByDay(rows, getDate, getKey) {
      const grouped = {};
      (rows || []).forEach((row) => {
        const date = getDate(row);
        if (!date) return;
        if (!grouped[date]) grouped[date] = new Set();
        grouped[date].add(getKey ? getKey(row) : `${date}-${grouped[date].size}`);
      });
      return Object.keys(grouped).sort().map((date) => ({ name: date.slice(5), date, count: grouped[date].size }));
    }
    function renderKpis(reports, hotspots) {
      const weak = reports.filter((row) => row.status === "weak" || row.status === "error").length;
      const ab = reports.filter((row) => ["A", "B"].includes(row.priorityBucket)).length;
      const strong = hotspots.filter((row) => row.hotspotLevel === "STRONG" || row.hotspotLevel === "HOT").length;
      $("kpis").innerHTML = [
        ["研报", reports.length, "筛选后样本"],
        ["公司", countUnique(reports, (row) => row.stockCode || row.stockName), "覆盖标的"],
        ["行业", countUnique(reports, (row) => row.industryName), "覆盖行业"],
        ["券商", countUnique(reports, (row) => row.orgName), "参与机构"],
        ["热点", hotspots.length, `HOT/STRONG ${strong}`],
        ["A/B", ab, "优先级样本"],
        ["弱/错", weak, "数据质量"],
        ["历史", analysisData.coverageHistoryCount || 0, "coverage rows"],
      ].map(([label, value, sub]) => `<div class="kpi"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="sub">${esc(sub)}</div></div>`).join("");
    }
    function renderRadar(hotspots, reports) {
      const items = [...(hotspots || [])].sort((a, b) => (levelRank[a.hotspotLevel] ?? 9) - (levelRank[b.hotspotLevel] ?? 9) || Number(b.coverage30d || 0) - Number(a.coverage30d || 0));
      const strongCount = items.filter((item) => String(item.hotspotLevel || "").toUpperCase() === "STRONG").length;
      const multiBroker = items.filter((item) => numberField(item, ["brokerCount30d", "brokerCount", "orgCount30d"]) >= 2).length;
      const firstCoverage = items.filter((item) => reasonCodes(item).includes("FIRST_COVERAGE")).length;
      const coverageTotal = items.reduce((sum, item) => sum + numberField(item, ["coverage30d", "reportCount30d", "coverageCount30d"]), 0);
      $("radarUpdated").textContent = `刷新 ${new Date().toLocaleTimeString()}`;
      $("radarMetrics").innerHTML = [
        ["热点信号", items.length, "当前列表"],
        ["强热点", strongCount, "STRONG"],
        ["多券商共振", multiBroker, "30日内 >= 2家"],
        ["首次覆盖", firstCoverage, `覆盖合计 ${coverageTotal} / 研报 ${reports.length}`],
      ].map(([label, value, sub]) => `<div class="radar-metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="sub">${esc(sub)}</div></div>`).join("");
      if (!items.length) {
        $("radarList").innerHTML = `<div class="radar-item"><div class="muted">暂无热点信号。可先导入已有输出，或完成一次抓取。</div></div>`;
        $("radarFocus").innerHTML = `<div class="muted">导入或刷新后显示当前最值得关注的信号。</div>`;
        return;
      }
      $("radarList").innerHTML = items.slice(0, 6).map((item) => {
        const level = String(item.hotspotLevel || "").toUpperCase();
        const codes = reasonCodes(item).slice(0, 4);
        const cls = level === "STRONG" ? "strong" : numberField(item, ["brokerCount30d", "brokerCount"]) >= 2 ? "watch" : "";
        const entityKey = entityKeyForHotspot(item);
        return `<div class="radar-item ${cls}">
          <div class="radar-item-head">
            <div>
              <div class="radar-name">${esc(item.entityName || item.stockName || "-")}</div>
              <div class="radar-meta">${esc(item.industryName || item.entityType || "-")} · ${esc(item.latestPublishDate || item.latestDate || "")}</div>
            </div>
            ${pill(item.hotspotLevel || "-")}
          </div>
          <div class="radar-stats">
            <span>覆盖 ${numberField(item, ["coverage30d", "reportCount30d", "coverageCount30d"])}</span>
            <span>券商 ${numberField(item, ["brokerCount30d", "brokerCount", "orgCount30d"])}</span>
            <span>公司 ${numberField(item, ["coveredCompanyCount30d", "coveredCompanyCount"])}</span>
          </div>
          <div class="reason-list">${codes.map((code) => `<span class="pill">${esc(reasonLabel(code))}</span>`).join("") || '<span class="pill">关注</span>'}</div>
          ${entityKey ? `<button type="button" class="link-button" data-entity-key="${esc(entityKey)}">查看</button>` : ""}
        </div>`;
      }).join("");
      const top = items[0];
      $("radarFocus").innerHTML = `<div class="eyebrow">当前焦点</div>
        <div class="name">${esc(top.entityName || top.stockName || "-")}</div>
        <div class="radar-meta">${esc(top.industryName || "-")} · ${esc(top.latestPublishDate || top.latestDate || "")}</div>
        <div class="radar-stats">
          <span>30日覆盖 ${numberField(top, ["coverage30d", "reportCount30d", "coverageCount30d"])}</span>
          <span>券商 ${numberField(top, ["brokerCount30d", "brokerCount", "orgCount30d"])}</span>
        </div>
        <div class="reason-list">${reasonCodes(top).slice(0, 5).map((code) => `<span class="pill">${esc(reasonLabel(code))}</span>`).join("") || '<span class="pill">关注</span>'}</div>`;
    }
    function rowsWithDateNames(rows) {
      return (rows || []).map((row) => ({ name: row.name || String(row.date || "").slice(5), count: Number(row.count || 0) }));
    }
    function emptyChart(id, text = "暂无数据") {
      $(id).innerHTML = `<div class="empty">${esc(text)}</div>`;
    }
    function formatChartNumber(value) {
      const number = Number(value);
      if (!Number.isFinite(number)) return String(value || "-");
      if (Number.isInteger(number)) return String(number);
      return String(Math.round(number * 100) / 100);
    }
    function singlePointChart(id, row, color) {
      $(id).innerHTML = `<div class="single-point">
        <div class="value">${esc(formatChartNumber(row.count))}</div>
        <div class="label">${esc(row.name || "单点记录")}</div>
        <span class="dot" style="background:${color}"></span>
      </div>`;
    }
    function drawLine(id, rows, color = "var(--blue)") {
      const el = $(id);
      const data = rowsWithDateNames(rows).filter((row) => Number.isFinite(row.count));
      if (!data.length) { emptyChart(id); return; }
      if (data.length === 1) { singlePointChart(id, data[0], color); return; }
      const max = Math.max(...data.map((row) => row.count), 1);
      const min = Math.min(...data.map((row) => row.count), 0);
      const spread = Math.max(max - min, 1);
      const step = data.length > 1 ? 560 / (data.length - 1) : 0;
      const points = data.map((row, index) => `${50 + index * step},${168 - ((row.count - min) / spread) * 116}`).join(" ");
      el.innerHTML = `<svg viewBox="0 0 640 220" width="100%" height="100%" role="img">
        <line x1="50" y1="180" x2="610" y2="180" stroke="#d9d3c6"></line>
        <line x1="50" y1="38" x2="50" y2="180" stroke="#d9d3c6"></line>
        <polyline points="${points}" fill="none" stroke="${color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></polyline>
        ${data.map((row, index) => {
          const x = 50 + index * step;
          const y = 168 - ((row.count - min) / spread) * 116;
          const label = data.length <= 8 || index % Math.ceil(data.length / 8) === 0 ? `<text x="${x}" y="207" text-anchor="middle" font-size="13" fill="#65717d">${esc(row.name)}</text>` : "";
          const value = data.length <= 12 || index % Math.ceil(data.length / 12) === 0 ? `<text x="${x}" y="${y - 11}" text-anchor="middle" font-size="13" fill="#33404a">${esc(formatChartNumber(row.count))}</text>` : "";
          return `<circle cx="${x}" cy="${y}" r="5" fill="${color}"><title>${esc(row.name)}: ${esc(formatChartNumber(row.count))}</title></circle>${value}${label}`;
        }).join("")}
      </svg>`;
    }
    function drawBar(id, rows, color = "var(--teal)") {
      const data = (rows || []).filter((row) => row.name && Number(row.count || 0) > 0).slice(0, 10);
      if (!data.length) { emptyChart(id); return; }
      const max = Math.max(...data.map((row) => Number(row.count || 0)), 1);
      $(id).innerHTML = `<svg viewBox="0 0 640 210" width="100%" height="100%" role="img">
        ${data.map((row, index) => {
          const width = Math.max(4, (Number(row.count || 0) / max) * 410);
          const y = 14 + index * Math.max(18, 180 / data.length);
          return `<g><text x="0" y="${y + 12}" font-size="13" fill="#65717d">${esc(String(row.name).slice(0, 12))}</text><rect x="142" y="${y}" width="${width}" height="14" rx="4" fill="${color}"></rect><text x="${152 + width}" y="${y + 12}" font-size="13" fill="#33404a">${esc(formatChartNumber(row.count))}</text></g>`;
        }).join("")}
      </svg>`;
    }
    function reportMatchesEntity(row, entity) {
      if (!entity) return false;
      if (entity.entityType === "company") {
        return (entity.stockCode && row.stockCode === entity.stockCode) || row.stockName === entity.label;
      }
      return row.industryName === entity.label || row.industryName === entity.industryName;
    }
    function directionSummary(summary) {
      const safe = summary || {};
      return `上修 ${safe.up || 0} / 下修 ${safe.down || 0} / 持平 ${safe.flat || 0}`;
    }
    function selectedAnalysisEntity() {
      const entities = filteredAnalysisEntities();
      const selectedKey = $("analysisEntity").value;
      return entities.find((entity) => entity.entityKey === selectedKey) || entities[0] || null;
    }
    function entityMatchesFilters(entity, filters) {
      const text = [entity.label, entity.stockCode, entity.industryName, entity.entityType, ...(entity.reasonCodes || [])].join(" ").toLowerCase();
      return (!filters.search || text.includes(filters.search))
        && (!filters.company || entity.label === filters.company || entity.stockCode === filters.company)
        && (!filters.industry || entity.industryName === filters.industry || entity.label === filters.industry)
        && (!filters.hotspot || entity.hotspotLevel === filters.hotspot)
        && (!filters.reason || (entity.reasonCodes || []).includes(filters.reason));
    }
    function filteredAnalysisEntities() {
      const entities = allEntities();
      const filters = readFilters();
      const query = $("analysisSearch").value.trim().toLowerCase();
      return entities.filter((entity) => {
        const text = [entity.label, entity.stockCode, entity.industryName, entity.entityType, ...(entity.reasonCodes || [])].join(" ").toLowerCase();
        return entityMatchesFilters(entity, filters) && (!query || text.includes(query));
      });
    }
    function renderAnalysisOptions() {
      const allEntities = (analysisData && analysisData.entityDrilldowns) || [];
      const entities = filteredAnalysisEntities();
      const current = $("analysisEntity").value;
      if (!allEntities.length) {
        $("analysisEntity").innerHTML = `<option value="">暂无可分析对象</option>`;
        return;
      }
      if (!entities.length) {
        $("analysisEntity").innerHTML = `<option value="">无匹配对象</option>`;
        return;
      }
      $("analysisEntity").innerHTML = entities.map((entity) => {
        const type = entity.entityType === "company" ? "公司" : "行业";
        return `<option value="${esc(entity.entityKey)}">${type}｜${esc(entity.label)}（${entity.reportCount || 0}篇 / ${entity.brokerCount || 0}家）</option>`;
      }).join("");
      if (current && entities.some((entity) => entity.entityKey === current)) {
        $("analysisEntity").value = current;
      }
    }
    function renderAnalysisLatestReports(entity) {
      const reports = (entity.latestReports || []).slice(0, 12);
      if (!reports.length) {
        $("analysisLatestReports").innerHTML = `<tbody><tr><td><div class="empty">暂无最新研报</div></td></tr></tbody>`;
        return;
      }
      $("analysisLatestReports").innerHTML = `<thead><tr><th>日期</th><th>券商</th><th>评级</th><th>分数</th><th>主题</th><th>摘要</th><th>文件</th></tr></thead><tbody>${reports.map((row) => `<tr>
        <td>${esc(row.date)}</td>
        <td>${esc(row.orgName)}</td>
        <td>${esc(row.rating || "-")}</td>
        <td>${pill(row.priorityBucket)} ${esc(row.signalScore)}</td>
        <td><div class="tags">${(row.themeTags || []).slice(0, 4).map((tag) => `<span class="pill">${esc(tag)}</span>`).join("")}</div></td>
        <td class="summary">${esc(row.summary || row.title || "")}</td>
        <td>${row.fileHref ? `<a href="/preview/${esc(row.fileHref)}">${esc(row.file || "预览")}</a>` : `<span class="muted">-</span>`}</td>
      </tr>`).join("")}</tbody>`;
    }
    function renderAnalysis() {
      const entity = selectedAnalysisEntity();
      if (!entity) {
        $("analysisKpis").innerHTML = `<div class="empty">暂无分析数据。请先导入已有输出，或完成一次抓取。</div>`;
        ["analysisCoverageChart", "analysisBrokerChart", "analysisScoreChart", "analysisTargetChart", "analysisEpsChart", "analysisRatingChart", "analysisPriorityChart", "analysisBrokerMix", "analysisThemeMix"].forEach((id) => emptyChart(id));
        $("analysisOpinionTable").innerHTML = `<tbody><tr><td><div class="empty">暂无变化记录</div></td></tr></tbody>`;
        $("analysisLatestReports").innerHTML = `<tbody><tr><td><div class="empty">暂无最新研报</div></td></tr></tbody>`;
        return;
      }
      const entityReports = ((analysisData && analysisData.reports) || []).filter((row) => reportMatchesEntity(row, entity));
      const summary = entity.opinionSummary || {};
      const kpis = [
        ["对象", entity.label, entity.entityType === "company" ? entity.stockCode || "公司" : "行业"],
        ["覆盖", entity.reportCount || 0, `${entity.firstDate || "-"} → ${entity.latestDate || "-"}`],
        ["券商", entity.brokerCount || 0, "不同机构"],
        ["均分", entity.avgScore || 0, "signalScore"],
        ["热点", entity.hotspotLevel || "-", (entity.reasonCodes || []).join(" | ") || "无"],
        ["观点变化", summary.trendCount || 0, `目标价 ${directionSummary(summary.target)}；EPS ${directionSummary(summary.eps)}`],
      ];
      $("analysisKpis").innerHTML = kpis.map(([label, value, sub]) => `<div class="analysis-kpi"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="sub">${esc(sub)}</div></div>`).join("");
      drawLine("analysisCoverageChart", entity.coverageByDay || [], "var(--blue)");
      drawLine("analysisBrokerChart", entity.brokerByDay || [], "var(--teal)");
      drawLine("analysisScoreChart", entity.scoreByDay || [], "#15803d");
      drawLine("analysisTargetChart", entity.targetTimeline || [], "#b45309");
      drawLine("analysisEpsChart", entity.epsTimeline || [], "var(--rose)");
      drawBar("analysisRatingChart", entity.ratingDistribution || [], "var(--blue)");
      drawBar("analysisPriorityChart", countBy(entityReports, (row) => row.priorityBucket || "未评级"), "#15803d");
      drawBar("analysisBrokerMix", entity.topBrokers || [], "var(--teal)");
      drawBar("analysisThemeMix", entity.topThemes || [], "#b45309");

      const trends = entity.opinionTrends || [];
      if (!trends.length) {
        $("analysisOpinionTable").innerHTML = `<tbody><tr><td><div class="empty">暂无同一机构连续观点，评级/目标价/EPS 变化暂不可判断。</div></td></tr></tbody>`;
        renderAnalysisLatestReports(entity);
        return;
      }
      $("analysisOpinionTable").innerHTML = `<thead><tr><th>券商</th><th>日期</th><th>评级变化</th><th>目标价变化</th><th>EPS 变化</th><th>评分变化</th></tr></thead><tbody>${trends.map((row) => `<tr>
        <td>${esc(row.orgName)}</td>
        <td>${esc(row.previousDate)} → ${esc(row.latestDate)}</td>
        <td>${esc(row.previousRating || "-")} → ${esc(row.latestRating || "-")}<div class="muted">${esc(row.ratingChange || "")}</div></td>
        <td>${esc(row.previousTargetPrice || "-")} → ${esc(row.latestTargetPrice || "-")} ${pill(row.targetDirection)}</td>
        <td>${esc(row.previousEps || "-")} → ${esc(row.latestEps || "-")} ${pill(row.epsDirection)}</td>
        <td>${row.previousScore} → ${row.latestScore} ${pill(row.scoreDirection)}</td>
      </tr>`).join("")}</tbody>`;
      renderAnalysisLatestReports(entity);
    }
    function renderRuns(runs) {
      const rows = (runs && runs.items) || [];
      if (!rows.length) {
        $("runs").innerHTML = `<tbody><tr><td><div class="empty">暂无任务</div></td></tr></tbody>`;
        return;
      }
      $("runs").innerHTML = `<thead><tr><th>ID</th><th>状态</th><th>开始</th><th>结束</th><th>OK/W/E</th><th>错误</th></tr></thead><tbody>${rows.map((r) => `<tr><td>${esc(String(r.run_id).slice(0, 8))}</td><td>${pill(r.status)}</td><td>${esc(r.started_at)}</td><td>${esc(r.ended_at || "")}</td><td>${r.ok_count}/${r.weak_count}/${r.error_count}</td><td>${esc(r.error_text || "")}</td></tr>`).join("")}</tbody>`;
    }
    function renderOverviewCharts(reports, hotspots) {
      drawLine("reportTrendChart", seriesByDay(reports, (row) => row.date), "var(--blue)");
      drawLine("brokerTrendChart", seriesByDay(reports, (row) => row.date, (row) => row.orgName), "var(--teal)");
      drawBar("industryHeatChart", countBy(reports, (row) => row.industryName, 10), "var(--amber)");
      drawBar("themeHeatChart", countTokens(reports, (row) => row.themeTags, 10), "var(--teal)");
      drawBar("reasonTrendChart", countTokens(hotspots, (row) => reasonCodes(row), 10), "var(--rose)");
      drawBar("qualityChart", countBy(reports, (row) => row.status || "unknown", 8), "#15803d");
      drawBar("sourceChart", countBy(reports, (row) => row.source || "unknown", 8), "var(--blue)");
    }
    function renderHotspotsTable(rows) {
      const limited = [...(rows || [])].sort((a, b) => (levelRank[a.hotspotLevel] ?? 9) - (levelRank[b.hotspotLevel] ?? 9) || Number(b.coverage30d || 0) - Number(a.coverage30d || 0)).slice(0, 120);
      if (!limited.length) {
        $("hotspots").innerHTML = `<tbody><tr><td><div class="empty">暂无热点信号</div></td></tr></tbody>`;
        return;
      }
      $("hotspots").innerHTML = `<thead><tr><th>标的</th><th>等级</th><th>行业</th><th>30日/7日</th><th>券商</th><th>加速</th><th>买入比</th><th>原因</th><th>操作</th></tr></thead><tbody>${limited.map((row) => {
        const entityKey = entityKeyForHotspot(row);
        return `<tr>
          <td><strong>${esc(row.entityName)}</strong><div class="muted">${esc(row.stockCode || row.entityType)}</div></td>
          <td>${pill(row.hotspotLevel)}</td>
          <td>${esc(row.industryName)}</td>
          <td>${numberField(row, ["coverage30d"])} / ${numberField(row, ["coverage7d"])}</td>
          <td>${numberField(row, ["brokerCount30d"])}<div class="muted">新增 ${numberField(row, ["newBrokerCount30d"])}</div></td>
          <td>${numberField(row, ["coverageAcceleration"])}</td>
          <td>${Math.round(Number(row.buyRatio || 0) * 100)}%</td>
          <td><div class="tags">${reasonCodes(row).map((code) => `<span class="pill">${esc(reasonLabel(code))}</span>`).join("")}</div><div class="muted">${esc((row.reasons || []).join("；"))}</div></td>
          <td>${entityKey ? `<button type="button" class="link-button" data-entity-key="${esc(entityKey)}">查看</button>` : `<span class="muted">-</span>`}</td>
        </tr>`;
      }).join("")}</tbody>`;
    }
    function renderGlobalOpinion(rows) {
      const limited = (rows || []).slice(0, 120);
      if (!limited.length) {
        $("globalOpinionTable").innerHTML = `<tbody><tr><td><div class="empty">暂无连续观点记录</div></td></tr></tbody>`;
        return;
      }
      $("globalOpinionTable").innerHTML = `<thead><tr><th>标的</th><th>券商</th><th>日期</th><th>评级</th><th>目标价</th><th>EPS</th><th>分数</th><th>次数</th><th>操作</th></tr></thead><tbody>${limited.map((row) => {
        const entityKey = entityKeyForOpinion(row);
        return `<tr>
          <td><strong>${esc(row.stockName)}</strong><div class="muted">${esc(row.stockCode || row.industryName)}</div></td>
          <td>${esc(row.orgName)}</td>
          <td>${esc(row.previousDate)} → ${esc(row.latestDate)}</td>
          <td>${esc(row.previousRating || "-")} → ${esc(row.latestRating || "-")}<div class="muted">${esc(row.ratingChange || "")}</div></td>
          <td>${esc(row.previousTargetPrice || "-")} → ${esc(row.latestTargetPrice || "-")} ${pill(row.targetDirection)}</td>
          <td>${esc(row.previousEps || "-")} → ${esc(row.latestEps || "-")} ${pill(row.epsDirection)}</td>
          <td>${esc(row.previousScore)} → ${esc(row.latestScore)} ${pill(row.scoreDirection)}</td>
          <td>${esc(row.count)}</td>
          <td>${entityKey ? `<button type="button" class="link-button" data-entity-key="${esc(entityKey)}">查看</button>` : `<span class="muted">-</span>`}</td>
        </tr>`;
      }).join("")}</tbody>`;
    }
    function reportLimit() {
      return Number($("reportLimit").value || 100);
    }
    function reportSearchMatches(row) {
      const text = $("reportSearch").value.trim().toLowerCase();
      return includesText(row, text);
    }
    function renderReportPager(total, shown, offset) {
      const limit = reportLimit();
      if (limit > 0 && total > 0 && shown === 0 && offset >= total) {
        reportPage = Math.max(1, Math.ceil(total / limit));
        renderDashboardViews();
        return;
      }
      if (limit <= 0) {
        $("reportPageInfo").textContent = `全部 ${total} 条`;
        $("reportPrevBtn").disabled = true;
        $("reportNextBtn").disabled = true;
        return;
      }
      const totalPages = Math.max(1, Math.ceil(total / limit));
      const currentPage = Math.min(totalPages, Math.max(1, reportPage));
      const first = total === 0 ? 0 : offset + 1;
      const last = Math.min(total, offset + shown);
      $("reportPageInfo").textContent = `${first}-${last} / ${total} · 第 ${currentPage}/${totalPages} 页`;
      $("reportPrevBtn").disabled = currentPage <= 1;
      $("reportNextBtn").disabled = currentPage >= totalPages;
    }
    function renderReports(rows) {
      const searched = [...(rows || [])].filter(reportSearchMatches).sort((a, b) => String(b.date).localeCompare(String(a.date)) || Number(b.signalScore || 0) - Number(a.signalScore || 0));
      const limit = reportLimit();
      const offset = limit > 0 ? Math.max(0, reportPage - 1) * limit : 0;
      const pageRows = limit > 0 ? searched.slice(offset, offset + limit) : searched;
      renderReportPager(searched.length, pageRows.length, offset);
      if (!pageRows.length) {
        $("reports").innerHTML = `<tbody><tr><td><div class="muted">暂无匹配研报</div></td></tr></tbody>`;
        return;
      }
      $("reports").innerHTML = `<thead><tr><th>日期</th><th>标的</th><th>行业</th><th>券商</th><th>评级</th><th>分数</th><th>主题</th><th>摘要</th><th>质量</th><th>文件</th><th>操作</th></tr></thead><tbody>${pageRows.map((r) => {
        const entityKey = entityKeyForReport(r);
        return `<tr>
          <td>${esc(r.date)}</td>
          <td><strong>${esc(r.stockName || r.industryName)}</strong><div class="muted">${esc(r.stockCode || "")}</div></td>
          <td>${esc(r.industryName)}</td>
          <td>${esc(r.orgName)}</td>
          <td>${esc(r.rating || "-")}</td>
          <td>${pill(r.priorityBucket)} <strong>${esc(r.signalScore || 0)}</strong></td>
          <td><div class="tags">${(r.themeTags || []).slice(0, 5).map((tag) => `<span class="pill">${esc(tag)}</span>`).join("")}</div></td>
          <td class="summary">${esc(r.summary || r.title || "")}</td>
          <td>${esc(r.status || "-")}<div class="muted">${esc(r.source || "-")} / Q ${esc(r.qualityScore || 0)}</div></td>
          <td>${r.fileHref ? `<a href="/preview/${esc(r.fileHref)}">${esc(r.file || "预览")}</a>` : `<span class="muted">-</span>`}</td>
          <td>${entityKey ? `<button type="button" class="link-button" data-entity-key="${esc(entityKey)}">查看</button>` : `<span class="muted">-</span>`}</td>
        </tr>`;
      }).join("")}</tbody>`;
    }
    function bindEntityButtons() {
      document.querySelectorAll("[data-entity-key]").forEach((button) => {
        button.addEventListener("click", () => {
          const key = button.dataset.entityKey || "";
          renderAnalysisOptions();
          $("analysisEntity").value = key;
          renderAnalysis();
          $("analysisPanel").scrollIntoView({ behavior: "smooth", block: "start" });
        });
      });
    }
    function renderDashboardViews() {
      const { reports, hotspots, opinions } = filteredDashboardData();
      renderRadar(hotspots, reports);
      renderKpis(reports, hotspots);
      renderOverviewCharts(reports, hotspots);
      renderHotspotsTable(hotspots);
      renderGlobalOpinion(opinions);
      renderAnalysisOptions();
      renderAnalysis();
      renderReports(reports);
      bindEntityButtons();
      const meta = (analysisData && analysisData.meta) || {};
      $("dashboardFooter").textContent = `显示 ${reports.length} 篇研报，${hotspots.length} 条热点信号，索引文件 ${meta.reportIndexCount || 0} 个`;
    }
    async function loadAnalysis(options = {}) {
      const silent = Boolean(options.silent);
      if (!silent) setStatus("分析数据刷新中...");
      try {
        analysisData = await api("/api/dashboard-data");
        populateGlobalFilters();
        renderDashboardViews();
        if (!silent) setStatus(`分析已刷新：${new Date().toLocaleTimeString()}`, "good");
        return true;
      } catch (error) {
        if (!silent) setStatus(`分析刷新失败：${error.message}`, "error");
        return false;
      }
    }
    async function refresh(options = {}) {
      const silent = Boolean(options.silent);
      if (!silent) setStatus("刷新中...");
      const [health, runs, dashboard] = await Promise.all([
        api("/api/health"), api("/api/runs"), api("/api/dashboard-data")
      ]);
      latestHealth = health;
      latestRuns = runs;
      analysisData = dashboard;
      $("meta").textContent = "";
      populateGlobalFilters();
      renderRuns(latestRuns);
      renderDashboardViews();
      if (!silent) setStatus(`已刷新：${new Date().toLocaleTimeString()}`, "good");
    }
    async function safeRefresh(options = {}) {
      try {
        await refresh(options);
      } catch (error) {
        setStatus(`刷新失败：${error.message}`, "error");
      }
    }
    async function importExisting() {
      setTopBusy(true);
      setStatus("正在导入已有输出...");
      try {
        const payload = await api("/api/import-existing", { method: "POST" });
        reportPage = 1;
        await refresh({ silent: true });
        setStatus(`导入完成：${formatImported(payload.imported)}`, "good");
      } catch (error) {
        setStatus(`导入失败：${error.message}`, "error");
      } finally {
        setTopBusy(false);
      }
    }
    async function refreshAll() {
      await safeRefresh();
    }
    function resetGlobalFilters() {
      const dates = dashboardDates();
      filterIds.forEach((id) => {
        const el = $(id);
        if (!el) return;
        el.value = "";
      });
      if (dates.length) {
        $("globalStartDate").value = dates[0];
        $("globalEndDate").value = dates[dates.length - 1];
      }
      reportPage = 1;
      renderDashboardViews();
    }
    $("importBtn").addEventListener("click", importExisting);
    $("refreshBtn").addEventListener("click", refreshAll);
    $("analysisRefreshBtn").addEventListener("click", () => loadAnalysis());
    $("analysisEntity").addEventListener("change", renderAnalysis);
    $("analysisSearch").addEventListener("input", () => { renderAnalysisOptions(); renderAnalysis(); });
    filterIds.forEach((id) => $(id).addEventListener("input", () => { reportPage = 1; renderDashboardViews(); }));
    $("resetFiltersBtn").addEventListener("click", resetGlobalFilters);
    $("reportLimit").addEventListener("change", () => { reportPage = 1; renderDashboardViews(); });
    $("reportSearchBtn").addEventListener("click", () => { reportPage = 1; renderDashboardViews(); });
    $("reportClearBtn").addEventListener("click", () => { $("reportSearch").value = ""; reportPage = 1; renderDashboardViews(); });
    $("reportSearch").addEventListener("keydown", (event) => { if (event.key === "Enter") { reportPage = 1; renderDashboardViews(); } });
    $("reportPrevBtn").addEventListener("click", () => { reportPage = Math.max(1, reportPage - 1); renderDashboardViews(); });
    $("reportNextBtn").addEventListener("click", () => { reportPage += 1; renderDashboardViews(); });
    $("concurrency").addEventListener("input", () => { fetchTuningTouched = true; });
    $("jitter").addEventListener("input", () => { fetchTuningTouched = true; });
    $("qtype").addEventListener("change", () => {
      if (fetchTuningTouched) return;
      if ($("qtype").value === "2") {
        $("concurrency").value = "2";
        $("jitter").value = "0.5";
      } else {
        $("concurrency").value = "1";
        $("jitter").value = "0";
      }
    });
    $("runBtn").addEventListener("click", async () => {
      const payload = {
        date: $("date").value,
        start_date: $("startDate").value,
        end_date: $("endDate").value,
        qtype: Number($("qtype").value),
        stock: split($("stock").value),
        industry: split($("industry").value),
        org: split($("org").value),
        rating: split($("rating").value),
        limit: $("limit").value ? Number($("limit").value) : null,
        concurrency: Number($("concurrency").value || 1),
        jitter: Number($("jitter").value || 0),
        no_xlsx: true
      };
      $("runBtn").disabled = true;
      setStatus("任务已提交，正在启动...");
      try {
        const run = await api("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        await safeRefresh({ silent: true });
        setStatus(`任务已启动：${String(run.run_id || "").slice(0, 8)}`, "good");
      } catch (error) {
        setStatus(`任务启动失败：${error.message}`, "error");
      } finally {
        $("runBtn").disabled = false;
      }
    });
    if ($("qtype").value === "2") {
      $("concurrency").value = "2";
      $("jitter").value = "0.5";
    }
    safeRefresh({ silent: true });
    setInterval(() => safeRefresh({ silent: true }), 5000);
  </script>
</body>
</html>
"""
