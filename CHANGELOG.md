# Changelog

All notable changes to this project will be documented in this file.

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
- compatibility redirect in `README.zh-CN.md`
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
