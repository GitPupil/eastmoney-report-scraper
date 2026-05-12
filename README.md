# eastmoney-report-scraper

English | [简体中文](./README.zh-CN.md)

A research-oriented scraper for Eastmoney research reports.

It collects stock and industry reports by date or date range, extracts report content from Eastmoney pages, falls back to PDF when needed, and exports structured local research artifacts including markdown reports, summaries, dashboards, and index files.

## Highlights

- Fetch **stock reports** and **industry reports** from Eastmoney
- Support **single-date** and **date-range** batch jobs
- Filter by **stock**, **broker**, **rating**, and **industry**
- Retry list/detail requests automatically
- Resume from existing markdown outputs
- Use **PDF fallback** when HTML extraction is weak
- Support **concurrent detail fetch** with `--concurrency`
- Generate research artifacts for reading, AI analysis, and trading-style review

## Project Status

Current implemented line:

- **v1.1** stability improvements
- **v1.2** research workflow outputs
- **v1.3** single-report structured analysis
- **v1.4** multi-report daily aggregation
- **v1.5 alpha** analysis/scoring/dashboard/concurrency foundation has landed

Current v1.5 alpha additions include:

- refined risk extraction
- financial-signal-based structured analysis
- signal score and priority bucket
- richer valuation exports (`ratingChange`, `targetPrice`, `epsForecast`, `peForecast`)
- `TRADING_DASHBOARD.md`
- sector/theme heat sections
- controlled concurrent detail fetch via `--concurrency`

See also:

- [ROADMAP.md](./ROADMAP.md)
- [TODO.md](./TODO.md)
- [CHANGELOG.md](./CHANGELOG.md)
- [DEVELOPMENT.md](./DEVELOPMENT.md)

## Repository Structure

```text
.
├── SKILL.md
├── README.md
├── README.zh-CN.md
├── CHANGELOG.md
├── ROADMAP.md
├── TODO.md
├── DEVELOPMENT.md
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── scripts/
    ├── __init__.py
    └── fetch_reports.py
```

## How It Works

The scraper follows this workflow:

1. Query Eastmoney report list pages and collect `infoCode`
2. Fetch the HTML detail page for each report
3. Extract main text content from the HTML page
4. If HTML extraction is too weak, try **PDF fallback**
5. Build structured summary / signals / risks / valuation fields
6. Export local outputs including report markdown, summaries, indexes, and trading dashboards

This project is a **page-scraping workflow**, not an official stable content API.

## Features

### Data Collection

- Single-date fetch
- Date-range batch fetch
- Stock reports (`--qtype 0`)
- Industry reports (`--qtype 1`)

### Filtering

- Filter by stock name or code
- Filter by broker / organization
- Filter by rating keyword
- Filter by industry keyword
- Limit fetched reports per date

### Reliability

- Retry for list-page failures
- Retry for detail-page failures
- Structured run log in `run.log.jsonl`
- Resume from existing markdown outputs
- Optional force re-fetch
- PDF fallback for weak HTML extraction
- Controlled concurrent detail fetch with `--concurrency`

### Research Outputs

- One markdown file per report
- `README.md` run summary
- `SUMMARY.md`
- `ANALYSIS_INPUT.md`
- `ANALYSIS_INPUT.json`
- `DAILY_BRIEF.md`
- `TOP_SIGNALS.md`
- `SECTOR_BRIEF.md`
- `THEME_BRIEF.md`
- `TRADING_DASHBOARD.md`
- `report_list.json`
- `report_index.csv`
- `report_index.xlsx` (optional)

### Structured Analysis Fields

Current structured output includes:

- headline
- core drivers
- positive signals
- negative signals
- valuation / rating fields
- risk items
- theme tags
- signal score
- priority bucket

## Requirements

### Runtime

- Python 3.9+

### Optional Dependencies

- `pdftotext` for PDF fallback
- `openpyxl` for XLSX export

Install runtime dependency:

```bash
pip install -r requirements.txt
```

Or install the optional XLSX dependency directly:

```bash
pip install openpyxl
```

## Installation

### Option 1: Run directly from the repository

```bash
git clone https://github.com/GitPupil/eastmoney-report-scraper.git
cd eastmoney-report-scraper
pip install -r requirements.txt
```

### Option 2: Use standard Python project metadata

```bash
pip install .
```

## Quick Start

### Fetch all reports for one day

```bash
python3 scripts/fetch_reports.py --date 2026-05-12
```

### Fetch with controlled concurrency

```bash
python3 scripts/fetch_reports.py --date 2026-05-12 --concurrency 2
```

### Fetch reports for a date range

```bash
python3 scripts/fetch_reports.py --start-date 2026-05-09 --end-date 2026-05-12
```

### Filter by stock

```bash
python3 scripts/fetch_reports.py --date 2026-05-12 --stock 润本股份
```

### Filter by broker

```bash
python3 scripts/fetch_reports.py --date 2026-05-12 --org 中邮证券 --org 国泰海通
```

### Filter industry reports

```bash
python3 scripts/fetch_reports.py --date 2026-05-12 --qtype 1 --industry 化学制药
```

## CLI Arguments

| Argument | Description |
|---|---|
| `--date` | Single date in `YYYY-MM-DD` |
| `--start-date` | Start date for a range job |
| `--end-date` | End date for a range job |
| `--limit` | Only fetch the first N reports for each date |
| `--qtype` | `0=stock reports`, `1=industry reports` |
| `--page-size` | List API page size |
| `--delay` | Delay in seconds between detail requests |
| `--timeout` | HTTP timeout in seconds |
| `--retries` | Retry count for list/detail fetches |
| `--retry-delay` | Delay between retries |
| `--concurrency` | Concurrent detail fetch workers |
| `--output-dir` | Output root directory |
| `--stock` | Filter by stock code or name, repeatable |
| `--org` | Filter by broker / organization, repeatable |
| `--rating` | Filter by rating keyword, repeatable |
| `--industry` | Filter by industry keyword, repeatable |
| `--force` | Force re-fetch even if markdown already exists |
| `--no-pdf-fallback` | Disable PDF fallback |
| `--no-xlsx` | Skip XLSX export |

## Output Layout

### Single-day run

```text
eastmoney_reports/
└── 研报_2026-05-12/
    ├── 001——某公司——某标题.md
    ├── README.md
    ├── SUMMARY.md
    ├── ANALYSIS_INPUT.md
    ├── ANALYSIS_INPUT.json
    ├── DAILY_BRIEF.md
    ├── TOP_SIGNALS.md
    ├── SECTOR_BRIEF.md
    ├── THEME_BRIEF.md
    ├── TRADING_DASHBOARD.md
    ├── report_list.json
    ├── report_index.csv
    ├── report_index.xlsx
    └── run.log.jsonl
```

### Date-range run

```text
eastmoney_reports/
└── 研报_2026-05-09_to_2026-05-12/
    ├── RANGE_SUMMARY.md
    ├── 研报_2026-05-09/
    ├── 研报_2026-05-10/
    ├── 研报_2026-05-11/
    └── 研报_2026-05-12/
```

## Suggested Workflow

1. Run the scraper for a target day or date range
2. Review `SUMMARY.md` for a quick scan
3. Review `TRADING_DASHBOARD.md` for trading-style prioritization
4. Read `ANALYSIS_INPUT.md` or `ANALYSIS_INPUT.json` for downstream AI / programmatic analysis
5. Use `DAILY_BRIEF.md`, `TOP_SIGNALS.md`, `SECTOR_BRIEF.md`, and `THEME_BRIEF.md` for cross-report synthesis

## Limitations

- This is not an official content API
- Eastmoney page structure may change
- PDF fallback depends on local `pdftotext`
- XLSX export depends on `openpyxl`
- Current filtering is mostly local post-fetch filtering
- Current concurrency is detail-fetch oriented and progress logs may appear out of order
- Current implementation is still script-first and not yet fully modularized

## Disclaimer

This project is intended for research, workflow automation, and local knowledge organization. Please use it responsibly and ensure your usage complies with the target website's terms, policies, and applicable regulations.
