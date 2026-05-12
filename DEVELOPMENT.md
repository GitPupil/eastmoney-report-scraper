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
python3 -m pytest -q
python3 scripts/fetch_reports.py --date 2026-05-12 --limit 2 --output-dir /tmp/eastmoney_check
```

Check that at least these outputs exist:

- report markdown files
- `SUMMARY.md`
- `TOP_SIGNALS.md`
- `TRADING_DASHBOARD.md`
- `report_index.csv`
- `run_manifest.jsonl`
- `CONSENSUS_BRIEF.md`

## Current Codebase Shape

A `pyproject.toml` is included so the repository has a standard Python project shape.
The v2 implementation keeps `scripts/fetch_reports.py` as a compatibility entrypoint and moves core logic into:

- `eastmoney_report_scraper/client.py`
- `eastmoney_report_scraper/parser.py`
- `eastmoney_report_scraper/analysis.py`
- `eastmoney_report_scraper/scoring.py`
- `eastmoney_report_scraper/exporters.py`
- `eastmoney_report_scraper/cli.py`

## Recommended Next Engineering Steps

- add more regression fixtures for parsing and analysis
- add lint / format tooling
- add CI for syntax / smoke validation
- calibrate quality scoring and signal scoring on real report samples
