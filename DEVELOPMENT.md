# Development

## Environment

Recommended:

- Python 3.9+
- `pdftotext` available in PATH if you want PDF fallback coverage

## Setup

### Minimal setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Local app setup

```bash
pip install -e ".[app]"
```

## Local Run

```bash
python3 scripts/fetch_reports.py --help
python3 scripts/fetch_reports.py --date 2026-05-12
python3 scripts/fetch_reports.py --date 2026-05-12 --concurrency 2
python3 scripts/fetch_reports.py --dashboard-only --output-dir ./eastmoney_reports
eastmoney-report-scraper import-existing --output-dir ./eastmoney_reports
eastmoney-report-scraper app --output-dir ./eastmoney_reports --port 8765 --open-browser
start_local_app.bat
```

## Smoke Validation

Recommended minimum validation after changes:

```bash
python -B -m pytest -q -p no:cacheprovider
python -m ruff check . --no-cache
python scripts/fetch_reports.py --help
python -m py_compile scripts/fetch_reports.py
python scripts/fetch_reports.py --doctor
python scripts/fetch_reports.py import-existing --output-dir ./tests_tmp
```

Check that at least these outputs exist:

- report markdown files
- `SUMMARY.md`
- `TOP_SIGNALS.md`
- `TRADING_DASHBOARD.md`
- `report_index.csv`
- `run_manifest.jsonl`
- `CONSENSUS_BRIEF.md`
- root-level `DASHBOARD.html`

Optional real-network smoke test:

```bash
python scripts/fetch_reports.py --date 2026-05-12 --limit 2 --output-dir /tmp/eastmoney_check
```

## Current Codebase Shape

A `pyproject.toml` is included so the repository has a standard Python project shape.
The implementation keeps `scripts/fetch_reports.py` as a compatibility entrypoint and moves core logic into:

- `eastmoney_report_scraper/client.py`
- `eastmoney_report_scraper/parser.py`
- `eastmoney_report_scraper/analysis.py`
- `eastmoney_report_scraper/scoring.py`
- `eastmoney_report_scraper/exporters/`
- `eastmoney_report_scraper/hotspots.py`
- `eastmoney_report_scraper/dashboard.py`
- `eastmoney_report_scraper/storage/`
- `eastmoney_report_scraper/app/`
- `eastmoney_report_scraper/config.py`
- `eastmoney_report_scraper/cli.py`

The Local App is developed on `codex/local-app-mvp` before being merged back to `main`. Keep CLI/OpenClaw behavior compatible while adding local app features.

## Fixtures

Regression fixtures live in `tests/fixtures/`.

- Keep fixtures small and artificial.
- Do not commit long real report bodies.
- Prefer one focused sample per behavior: standard stock HTML, industry HTML, weak HTML, malformed HTML, and PDF text.
- When parser behavior changes, update tests first so the expected extraction semantics are clear.

## CI

GitHub Actions runs the same local checks on Python 3.9, 3.10, 3.11, and 3.12:

```bash
python -B -m pytest -q -p no:cacheprovider
python -m ruff check . --no-cache
python scripts/fetch_reports.py --help
python -m py_compile scripts/fetch_reports.py
```

## Release Checklist

Before tagging a release:

- Update `pyproject.toml` and `eastmoney_report_scraper/__init__.py`.
- Update README badges and version status.
- Add a dated section to `CHANGELOG.md`.
- Run the smoke validation commands.
- Push to `main` and confirm CI is green.

## Recommended Next Engineering Steps

- expand fixture coverage for parser edge cases
- keep calibrating quality scoring and signal scoring on small samples
- improve PDF text cleanup
- deepen range-level synthesis
- keep local app APIs thin wrappers around existing output files and dashboard aggregation
