# eastmoney-report-scraper Roadmap

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
- re-fetch weak outputs
- support `--resume-errors-only`
- support minimum text length threshold
- support jitter / throttling controls for concurrency

### 3. Extraction robustness
- improve section detection quality
- improve HTML vs PDF selection logic
- reduce noisy summary bullets
- add stronger handling for malformed pages

### 4. Research usability
- add same-stock multi-broker coverage summary
- add consensus / divergence summary for repeated coverage
- improve cross-day synthesis for date-range runs

### 5. Engineering
- split the script into internal modules
- add tests and regression fixtures
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
- extract parser / analysis / exporter modules
- add tests
- add CI
