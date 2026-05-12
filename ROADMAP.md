# eastmoney-report-scraper Roadmap

## v2.0 Landed

- modular package layout
- compatibility script entrypoint
- parser / analysis / scoring / exporter separation
- run manifest for weak/error resume workflows
- text quality scoring for extraction selection
- score reasons and score breakdown exports
- consensus and range dashboards
- pytest regression tests and ruff dev dependency

---

## v1.5 Goal

Upgrade the scraper from a basic collection tool into a more reliable research workflow tool:

- more accurate structured analysis
- better risk extraction
- transaction-oriented ranking and summaries
- stronger resume / batch handling
- more practical engineering ergonomics

---

## Already Landed in v1.5 Alpha

- refined risk extraction
- financial-signal-based structured analysis
- signal score and priority bucket
- richer valuation exports
- `TRADING_DASHBOARD.md`
- dashboard sector/theme heat
- controlled concurrent detail fetch via `--concurrency`

---

## Remaining P0 / P1 Work

### 1. Analysis quality refinement
- continue improving headline quality
- compress core drivers into cleaner research-style bullets
- reduce false-positive theme tags
- improve consistency between risks, score, and trade hints

### 2. Resume / batch improvements
- continue calibrating weak/error resume behavior on real runs
- add richer throttling presets for concurrency

### 3. Extraction robustness
- continue improving section detection quality
- calibrate HTML vs PDF quality selection logic
- reduce noisy summary bullets
- add stronger handling for malformed pages

### 4. Research usability
- deepen same-stock multi-broker coverage summary
- deepen consensus / divergence summary for repeated coverage
- improve cross-day synthesis for date-range runs

### 5. Engineering
- expand tests and regression fixtures
- add CI for syntax / smoke validation

---

## Suggested Next Milestones

### Milestone A: Stabilize v1.5 alpha
- improve score calibration
- tighten summary / driver extraction
- add jitter / better concurrency controls

### Milestone B: Research depth
- multi-broker consensus view
- repeated coverage statistics
- stronger range-level synthesis

### Milestone C: Codebase structure
- expand parser / analysis / exporter fixtures
- add CI
