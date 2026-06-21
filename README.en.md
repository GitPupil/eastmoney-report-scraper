# eastmoney-report-scraper

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Status](https://img.shields.io/badge/Status-v0.5.0-orange)](./CHANGELOG.md)
[![CI](https://github.com/GitPupil/eastmoney-report-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/GitPupil/eastmoney-report-scraper/actions/workflows/ci.yml)
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
- Maintain historical coverage in `COVERAGE_HISTORY.jsonl` and company/industry coverage summaries.
- Generate `HOTSPOT_DASHBOARD.md` and `HOTSPOT_SIGNALS.csv` for first coverage, reactivated coverage, multi-broker attention, and company-industry resonance.
- Generate offline static `DASHBOARD.html` for recent hotspots, trends, report counts, filters, opinion changes, and data quality.
- Optional local Web App with SQLite import, local APIs, run status, hotspot and report views.
- Lightweight modes: `--doctor`, `--dry-run`, `--list-only`, `--hotspots-only`, and `--dashboard-only`.
- 0.5.0 adds the Local App MVP; 0.4.0 added the visual dashboard.

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

Optional local app:

```bash
pip install ".[app]"
eastmoney-report-scraper import-existing --output-dir ./eastmoney_reports
eastmoney-report-scraper app --output-dir ./eastmoney_reports --open-browser
```

On Windows, double-click `start_local_app.bat` from the project folder. If Python is missing, the script tries to install Python 3.12 with `winget`; if `winget` is unavailable, it prints the manual download link.

The local app can start fetch runs, import existing outputs, browse report details, and visualize company or industry trends including coverage, broker diffusion, signal scores, target price/EPS timelines, rating distribution, priority-bucket distribution, and continuous opinion changes from the same broker.

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

# Stock and industry reports
python scripts/fetch_reports.py --date 2026-05-12 --qtype 2

# Concurrent detail fetch
python scripts/fetch_reports.py --date 2026-05-12 --concurrency 2 --jitter 0.5

# Re-fetch weak outputs
python scripts/fetch_reports.py --date 2026-05-12 --refresh-weak

# Diagnose local environment
python scripts/fetch_reports.py --doctor

# Rebuild hotspot files from existing coverage history
python scripts/fetch_reports.py --hotspots-only --output-dir ./eastmoney_reports

# Rebuild the visual dashboard from existing outputs
python scripts/fetch_reports.py --dashboard-only --output-dir ./eastmoney_reports

# Fetch only the filtered list, not detail pages
python scripts/fetch_reports.py --date 2026-05-12 --list-only --stock 润本股份

# Import existing outputs into local SQLite
eastmoney-report-scraper import-existing --output-dir ./eastmoney_reports

# Start local web app
eastmoney-report-scraper app --output-dir ./eastmoney_reports --port 8765 --open-browser
```

## Outputs

```text
eastmoney_reports/
├── COVERAGE_HISTORY.jsonl
├── COMPANY_COVERAGE_SUMMARY.csv
├── INDUSTRY_COVERAGE_SUMMARY.csv
├── DASHBOARD.html
├── eastmoney.db
├── local_app_config.json
├── HOTSPOT_DASHBOARD.md
├── HOTSPOT_SIGNALS.csv
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

`DASHBOARD.html` is a single offline HTML dashboard that reads generated CSV/JSONL outputs. `COVERAGE_HISTORY.jsonl` stores de-duplicated historical coverage records by `infoCode`. `COMPANY_COVERAGE_SUMMARY.csv` and `INDUSTRY_COVERAGE_SUMMARY.csv` summarize historical coverage counts. `HOTSPOT_DASHBOARD.md` and `HOTSPOT_SIGNALS.csv` highlight recent first coverage, reactivated names, multi-broker coverage, industry heat, and company-industry resonance.

| File | Purpose |
|---|---|
| `DASHBOARD.html` | Offline visual dashboard for hotspots, trends, filters, opinion changes, and quality |
| `HOTSPOT_DASHBOARD.md` | Recent first coverage, reactivation, multi-broker attention, industry resonance |
| `HOTSPOT_SIGNALS.csv` | Programmatic hotspot metrics, reasons, and reason codes |
| `TRADING_DASHBOARD.md` | Trading priority, risk, sector and theme heat |
| `CONSENSUS_BRIEF.md` | Multi-broker coverage and divergence for the same entity |
| `COVERAGE_HISTORY.jsonl` | De-duplicated historical coverage detail |
| `report_index.csv/xlsx` | Daily report index and structured fields |
| `eastmoney.db` | Local App SQLite query cache |
| `local_app_config.json` | Local App output directory, port, and defaults |

## Local App Mode

The Local App is an optional browser workspace. It keeps the CLI/OpenClaw workflow intact, imports existing CSV/JSONL outputs into `eastmoney.db`, and exposes local API endpoints for reports, hotspots, runs, and dashboard data.

```bash
pip install ".[app]"
eastmoney-report-scraper import-existing --output-dir ./eastmoney_reports
eastmoney-report-scraper app --output-dir ./eastmoney_reports --host 127.0.0.1 --port 8765 --open-browser
```

Open:

```text
http://127.0.0.1:8765
```

## Planned Integrations

The following items are planned and are not released as current features yet:

- Real-time data API: allow users to provide local market-data tokens for price, index, sector-performance, and post-signal feedback analysis. Tokens should stay in the local runtime or a git-ignored local config file, and must not be written to logs, Markdown/CSV/JSONL/XLSX outputs, SQLite rows, dashboard HTML, or exception messages.
- AI analysis: allow users to provide model API tokens for deeper summaries, comparisons, and opinion-change explanations across selected reports, companies, industries, or date ranges. Tokens must be masked in UI/CLI diagnostics and excluded from exported research artifacts.
- Before enabling token-based integrations, add token-redaction helpers, config-loading rules, and regression tests to prevent accidental leakage through debug output or generated files.

## CLI Arguments

| Argument | Description |
|---|---|
| `--date` | Single date in `YYYY-MM-DD` |
| `--start-date` | Start date for a range job |
| `--end-date` | End date for a range job |
| `--limit` | Only fetch the first N reports for each date |
| `--qtype` | `0=stock reports`, `1=industry reports`, `2=all` |
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
| `--hotspot-days` | Main hotspot window in days, default `30` |
| `--hotspot-short-days` | Short hotspot window in days, default `7` |
| `--hotspot-silent-days` | Silent window for reactivated coverage, default `90` |
| `--hotspot-broker-threshold` | Distinct broker threshold, default `3` |
| `--hotspot-coverage-threshold` | Coverage-count threshold, default `3` |
| `--no-hotspot` | Skip hotspot dashboard and signal CSV |
| `--doctor` | Print JSON environment diagnostics and exit |
| `--dry-run` | Fetch list pages and print counts, skip details |
| `--list-only` | Fetch list pages and print selected JSON, skip details |
| `--hotspots-only` | Rebuild hotspot outputs from coverage history without network requests |
| `--dashboard-only` | Rebuild `DASHBOARD.html` from existing outputs without network requests |
| `--no-dashboard` | Skip static HTML dashboard generation |
| `--dashboard-name` | Customize dashboard file name, default `DASHBOARD.html` |
| `--no-pdf-fallback` | Disable PDF fallback |
| `--no-xlsx` | Skip XLSX export |

### Local App Commands

| Command | Description |
|---|---|
| `eastmoney-report-scraper import-existing` | Import existing outputs into local SQLite |
| `eastmoney-report-scraper app` | Start the local Web App |
| `--host` | Local app host, default `127.0.0.1` |
| `--port` | Local app port, default `8765` |
| `--db-path` | Custom SQLite path |
| `--open-browser` | Open the local app URL in the default browser |

## Project Layout

```text
eastmoney_report_scraper/
├── client.py
├── parser.py
├── analysis.py
├── scoring.py
├── exporters/
├── hotspots.py
├── dashboard.py
├── storage/
├── app/
├── config.py
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
