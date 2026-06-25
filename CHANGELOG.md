# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Added
- Optional Local App AI settings and analysis endpoints backed by bounded dashboard evidence.
- Local AI config file support with masked UI/API settings and regression tests for token redaction.
- cc-switch import for the current Claude provider plus Anthropic-compatible AI request support.
- Standalone `ai_connector.py` for reusing the AI provider integration in other projects.
- Built-in Local App AI prompt templates for general research, opinion changes, hotspot radar, company deep dives, industry trends, multi-industry comparison, and daily overview.
- Multiple local AI provider profiles with masked token handling, active-profile switching, and cc-switch import into profiles.
- Local App AI scopes for all data, current filters, companies, industries, hotspots, date ranges, and keyword queries.
- AI provider test-connection diagnostics covering request URL, response kind, HTTP status, and suggested fixes.

### Changed
- Local App background fetch tasks now call the shared `core` orchestration layer directly while the CLI remains an entrypoint wrapper.

### Removed
- Removed the legacy Simplified Chinese compatibility redirect file because root `README.md` is now the default Simplified Chinese documentation.

## [0.5.0] - 2026-06-21

### Added
- optional Local App dependencies through `.[app]`
- `eastmoney-report-scraper app` command for a local FastAPI/Uvicorn web workspace
- `eastmoney-report-scraper import-existing` command for importing existing outputs into SQLite
- `--open-browser` for opening the local app URL after startup
- `start_local_app.bat` for one-click Windows startup from a fresh checkout, including optional Python 3.12 installation through `winget`
- local SQLite cache `eastmoney.db` for reports, hotspots, coverage history, manifests, and run status
- `local_app_config.json` for local app defaults
- local app service and task layers with background fetch runs
- tests for config, SQLite import, service payloads, task transitions, and import CLI output
- `--qtype 2` / Local App `全部` mode for fetching stock and industry reports together
- Local App visual analysis panel for company/industry trends, broker diffusion, ratings, priority buckets, target price/EPS timelines, and continuous opinion changes

### Changed
- bumped project version to `0.5.0`
- documented Local App Mode while keeping OpenClaw/CLI as the stable default workflow

## [0.4.0] - 2026-06-20

### Added
- offline static `DASHBOARD.html` with hotspots, report trends, broker diffusion, filters, opinion changes, and data quality views
- `--dashboard-only` CLI mode to rebuild the visual dashboard from existing outputs without network requests
- `--no-dashboard` and `--dashboard-name` CLI options
- dashboard regression tests covering generated data, empty output roots, and CLI short-circuit behavior

### Changed
- normal fetch runs and `--hotspots-only` now refresh the static dashboard by default
- updated README and SKILL guidance for dashboard-first research workflows

## [0.3.0] - 2026-05-21

### Added
- GitHub Actions CI for Python 3.9, 3.10, 3.11, and 3.12
- fixture-based parser and analysis regression tests
- CLI modes:
  - `--doctor`
  - `--dry-run`
  - `--list-only`
  - `--hotspots-only`
- hotspot `reasonCodes` and `coveredCompanyCount30d` CSV fields
- broker name normalization hook for hotspot aggregation

### Changed
- split `eastmoney_report_scraper/exporters.py` into the `eastmoney_report_scraper/exporters/` package
- kept exporter public imports compatible through `exporters/__init__.py`
- improved hotspot dashboard reason rendering
- updated README, DEVELOPMENT, and SKILL guidance for public reliability workflows

## [0.2.0] - 2026-05-13

### Added
- v2 package layout under `eastmoney_report_scraper/`
- compatibility wrapper in `scripts/fetch_reports.py`
- `run_manifest.jsonl` run state tracking
- text quality scoring for HTML/PDF selection
- `scoreReasons`, `scoreBreakdown`, and `qualityScore` exports
- `CONSENSUS_BRIEF.md`
- date-range `RANGE_DASHBOARD.md`
- CLI args:
  - `--refresh-weak`
  - `--resume-errors-only`
  - `--min-text-length`
  - `--jitter`
  - `--manifest-name`
- pytest regression tests
- `beautifulsoup4`, `pytest`, and `ruff` dependencies
- GitHub default Chinese `README.md`
- English documentation in `README.en.md`
- formalized project documentation in `README.md`
- historical coverage detail in `COVERAGE_HISTORY.jsonl`
- company coverage summary in `COMPANY_COVERAGE_SUMMARY.csv`
- industry coverage summary in `INDUSTRY_COVERAGE_SUMMARY.csv`
- hotspot detection module in `eastmoney_report_scraper/hotspots.py`
- `HOTSPOT_DASHBOARD.md`
- `HOTSPOT_SIGNALS.csv`
- hotspot CLI args:
  - `--hotspot-days`
  - `--hotspot-short-days`
  - `--hotspot-silent-days`
  - `--hotspot-broker-threshold`
  - `--hotspot-coverage-threshold`
  - `--no-hotspot`
- `ROADMAP.md` for public milestone planning
- `TODO.md` for task breakdown
- `CONTRIBUTING.md`
- `LICENSE` (MIT)
- `pyproject.toml`
- `requirements.txt`
- `requirements-dev.txt`
- `DEVELOPMENT.md`
- `TRADING_DASHBOARD.md`
- dashboard sector heat and theme heat sections
- controlled concurrent detail fetch via `--concurrency`
- richer CSV export fields:
  - `signalScore`
  - `priorityBucket`
  - `themeTags`
  - `ratingChange`
  - `targetPrice`
  - `epsForecast`
  - `peForecast`

### Changed
- moved scraper internals out of the monolithic script into modules
- upgraded HTML parsing to use BeautifulSoup when available, with regex fallback
- made scoring output more transparent
- improved structured analysis quality
- refined risk extraction logic
- added signal score and priority bucket
- improved core driver extraction
- improved trade hint generation
- improved valuation field extraction
- expanded `COVERAGE_HISTORY.jsonl` schema with report type, industry, title, theme tags, signal score, and priority bucket
- updated the skill guide to read hotspot outputs when judging recent company or industry attention

## [v1.4]

### Added
- `DAILY_BRIEF.md`
- `TOP_SIGNALS.md`
- `SECTOR_BRIEF.md`
- `THEME_BRIEF.md`
- multi-report daily aggregation outputs

## [v1.3]

### Added
- single-report structured analysis fields:
  - one-line conclusion
  - core drivers
  - positive signals
  - negative signals
  - valuation / rating
  - trade hint
  - risks

## [v1.2]

### Added
- filtering by stock / code
- filtering by broker
- filtering by rating
- filtering by industry
- date-range batch fetch
- incremental update / resume
- `report_index.csv`
- optional `report_index.xlsx`
- `SUMMARY.md`
- `ANALYSIS_INPUT.md`
- `ANALYSIS_INPUT.json`

## [v1.1]

### Added
- retry for detail-page fetch failures
- retry for list-page fetch failures
- `run.log.jsonl`
- resume by skipping existing markdown files
- PDF fallback when HTML extraction is weak
