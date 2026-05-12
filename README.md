# eastmoney-report-scraper

Batch scrape Eastmoney research reports by date or date range.

## Features

- Fetch stock or industry reports by single date or date range
- Filter by stock, broker, rating, and industry
- Retry on list/detail fetch failures
- Resume from existing markdown outputs
- PDF fallback when HTML extraction is weak
- Export markdown, SUMMARY, ANALYSIS_INPUT, CSV/XLSX index, JSON list, and daily briefs

## Quick Start

```bash
python3 scripts/fetch_reports.py --date 2026-05-12
python3 scripts/fetch_reports.py --start-date 2026-05-09 --end-date 2026-05-12
python3 scripts/fetch_reports.py --date 2026-05-12 --stock 润本股份
python3 scripts/fetch_reports.py --date 2026-05-12 --org 中邮证券
```

## Main Arguments

- `--date` single date in `YYYY-MM-DD`
- `--start-date --end-date` date range
- `--qtype 0|1` stock reports / industry reports
- `--stock` repeatable stock filter
- `--org` repeatable broker filter
- `--rating` repeatable rating filter
- `--industry` repeatable industry filter
- `--limit` limit reports per date
- `--force` force refetch
- `--no-pdf-fallback` disable PDF fallback
- `--no-xlsx` skip xlsx export

## Output

Default output root:

```text
eastmoney_reports/
```

Per run, the scraper can generate:

- report markdown files
- `README.md`
- `SUMMARY.md`
- `ANALYSIS_INPUT.md`
- `ANALYSIS_INPUT.json`
- `DAILY_BRIEF.md`
- `TOP_SIGNALS.md`
- `SECTOR_BRIEF.md`
- `THEME_BRIEF.md`
- `report_list.json`
- `report_index.csv`
- `report_index.xlsx`
- `run.log.jsonl`

## Notes

- This is a page-scraping workflow, not an official stable content API.
- `pdftotext` is needed for PDF fallback.
- `openpyxl` is needed for xlsx export.
