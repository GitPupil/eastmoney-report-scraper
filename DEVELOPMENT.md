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

## Local Run

```bash
python3 scripts/fetch_reports.py --help
python3 scripts/fetch_reports.py --date 2026-05-12
python3 scripts/fetch_reports.py --date 2026-05-12 --concurrency 2
```

## Smoke Validation

Recommended minimum validation after changes:

```bash
python3 -m py_compile scripts/fetch_reports.py
python3 scripts/fetch_reports.py --help
python3 scripts/fetch_reports.py --date 2026-05-12 --limit 2 --output-dir /tmp/eastmoney_check
```

Check that at least these outputs exist:

- report markdown files
- `SUMMARY.md`
- `TOP_SIGNALS.md`
- `TRADING_DASHBOARD.md`
- `report_index.csv`

## Current Codebase Shape

A `pyproject.toml` is included so the repository has a standard Python project shape.
The implementation is still script-first and centered on:

- `scripts/fetch_reports.py`

The script currently contains logic for:

- HTTP fetch and retry
- HTML / PDF extraction
- summary and risk extraction
- structured analysis and scoring
- export generation
- concurrency orchestration

## Recommended Next Engineering Steps

- split parser / analysis / exporter into internal modules
- add automated tests for parsing and analysis
- add lint / format tooling
- add CI for syntax / smoke validation
- add regression fixtures for representative report samples
