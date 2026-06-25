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


def _require_app_dependencies() -> tuple[Any, Any, Any, Any, Any, Any]:
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import FileResponse, HTMLResponse
        from fastapi.staticfiles import StaticFiles
        import uvicorn
    except ImportError as exc:
        raise RuntimeError('Local app dependencies are missing. Install with: pip install ".[app]"') from exc
    return FastAPI, HTTPException, FileResponse, HTMLResponse, StaticFiles, uvicorn


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
    FastAPI, HTTPException, FileResponse, HTMLResponse, StaticFiles, _ = _require_app_dependencies()
    services = LocalAppServices(config)
    app = FastAPI(title="Eastmoney Report Scraper Local App")
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

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

    @app.get("/api/ai/settings")
    def ai_settings():
        return services.ai_settings()

    @app.post("/api/ai/settings")
    def update_ai_settings(payload: Dict[str, Any]):
        return services.update_ai_settings(payload)

    @app.post("/api/ai/profiles/active")
    def set_active_ai_profile(payload: Dict[str, Any]):
        return services.set_active_ai_profile(payload)

    @app.post("/api/ai/profiles/delete")
    def delete_ai_profile(payload: Dict[str, Any]):
        return services.delete_ai_profile(payload)

    @app.post("/api/ai/import-cc-switch")
    def import_cc_switch_ai_settings(payload: Optional[Dict[str, Any]] = None):
        return services.import_cc_switch_ai_settings(payload)

    @app.post("/api/ai/test-connection")
    def test_ai_connection(payload: Optional[Dict[str, Any]] = None):
        return services.test_ai_connection(payload)

    @app.post("/api/ai/analyze")
    def ai_analyze(payload: Dict[str, Any]):
        return services.ai_analyze(payload)

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
    _, _, _, _, _, uvicorn = _require_app_dependencies()
    app = create_app(config)
    if open_browser:
        Timer(1.0, lambda: webbrowser.open(f"http://{config.host}:{config.port}")).start()
    uvicorn.run(app, host=config.host, port=config.port)


_APP_DIR = Path(__file__).resolve().parent
_TEMPLATE_DIR = _APP_DIR / "templates"
_STATIC_DIR = _APP_DIR / "static"


def _read_app_text(relative_path: str) -> str:
    return (_APP_DIR / relative_path).read_text(encoding="utf-8")


_INDEX_HTML = _read_app_text("templates/index.html")
