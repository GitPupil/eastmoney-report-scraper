# eastmoney-report-scraper

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Status](https://img.shields.io/badge/Status-v2.0-orange)](./CHANGELOG.md)
[![Tests](https://img.shields.io/badge/Tests-pytest-informational)](./tests)

[简体中文](./README.md) | English

A research-oriented Eastmoney report scraper. It collects stock and industry research reports by date or date range, extracts report text, falls back to PDF when needed, and exports local research artifacts for reading, AI analysis, and programmatic processing.

> This is a page-scraping workflow, not an official stable Eastmoney content API. Please make sure your usage complies with the target site's terms, policies, and applicable laws.

## Highlights

- Fetch Eastmoney stock reports and industry reports.
- Run single-date or date-range jobs.
- Filter by stock/code, broker, rating, and industry.
- Retry list/detail requests automatically.
- Resume from existing Markdown outputs and `run_manifest.jsonl`.
- Use text quality scoring to choose HTML or PDF extraction results.
- Export Markdown reports, summaries, daily briefs, dashboards, CSV/XLSX indexes, and JSON inputs.
- Export transparent `scoreReasons`, `scoreBreakdown`, and `qualityScore` fields.
- v2 modular package layout with pytest regression tests.

## Quick Start

```bash
git clone https://github.com/GitPupil/eastmoney-report-scraper.git
cd eastmoney-report-scraper
pip install -r requirements.txt
python scripts/fetch_reports.py --date 2026-05-12 --limit 5
```

Package entrypoint:

```bash
pip install .
eastmoney-report-scraper --date 2026-05-12 --limit 5
```

## Common Commands

```bash
# Single day
python scripts/fetch_reports.py --date 2026-05-12

# Date range
python scripts/fetch_reports.py --start-date 2026-05-09 --end-date 2026-05-12

# Filter by stock
python scripts/fetch_reports.py --date 2026-05-12 --stock 润本股份

# Industry reports
python scripts/fetch_reports.py --date 2026-05-12 --qtype 1 --industry 化学制药

# Concurrent detail fetch
python scripts/fetch_reports.py --date 2026-05-12 --concurrency 2 --jitter 0.5

# Re-fetch weak outputs
python scripts/fetch_reports.py --date 2026-05-12 --refresh-weak
```

## Outputs

```text
eastmoney_reports/
└── 研报_2026-05-12/
    ├── 001——Some Company——Some Title.md
    ├── README.md
    ├── SUMMARY.md
    ├── ANALYSIS_INPUT.md
    ├── ANALYSIS_INPUT.json
    ├── DAILY_BRIEF.md
    ├── TOP_SIGNALS.md
    ├── SECTOR_BRIEF.md
    ├── THEME_BRIEF.md
    ├── TRADING_DASHBOARD.md
    ├── CONSENSUS_BRIEF.md
    ├── report_list.json
    ├── run_manifest.jsonl
    ├── report_index.csv
    ├── report_index.xlsx
    └── run.log.jsonl
```

For date-range jobs, the scraper also writes `RANGE_SUMMARY.md` and `RANGE_DASHBOARD.md`.

## CLI Arguments

| Argument | Description |
|---|---|
| `--date` | Single date in `YYYY-MM-DD` |
| `--start-date` | Start date for a range job |
| `--end-date` | End date for a range job |
| `--limit` | Only fetch the first N reports for each date |
| `--qtype` | `0=stock reports`, `1=industry reports` |
| `--concurrency` | Concurrent detail fetch workers |
| `--jitter` | Add random extra delay to detail requests |
| `--stock` | Filter by stock code or name, repeatable |
| `--org` | Filter by broker / organization, repeatable |
| `--rating` | Filter by rating keyword, repeatable |
| `--industry` | Filter by industry keyword, repeatable |
| `--force` | Force re-fetch even if Markdown already exists |
| `--refresh-weak` | Re-fetch previously weak outputs |
| `--resume-errors-only` | Retry only previous errors |
| `--min-text-length` | Mark extracted text below this length as `weak` |
| `--manifest-name` | Customize run manifest file name |
| `--no-pdf-fallback` | Disable PDF fallback |
| `--no-xlsx` | Skip XLSX export |

## Project Layout

```text
eastmoney_report_scraper/
├── client.py
├── parser.py
├── analysis.py
├── scoring.py
├── exporters.py
└── cli.py
```

`scripts/fetch_reports.py` is kept as a compatibility entrypoint. Both it and the installed `eastmoney-report-scraper` command call the same `eastmoney_report_scraper.cli:main`.

## Development

```bash
pip install -r requirements-dev.txt
python scripts/fetch_reports.py --help
python -B -m pytest -q -p no:cacheprovider
python -m ruff check . --no-cache
```

## License

[MIT](./LICENSE)

