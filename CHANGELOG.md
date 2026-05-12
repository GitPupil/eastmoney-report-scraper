# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Formalized project documentation in `README.md`
- Added standalone Chinese documentation in `README.zh-CN.md`
- Added `ROADMAP.md` for v1.5 planning
- Added `TODO.md` for task breakdown
- Added `CONTRIBUTING.md`
- Added `LICENSE` (MIT)

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
