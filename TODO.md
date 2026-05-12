# TODO

## v1.5 Task Breakdown

### Models
- [ ] add internal report models for meta / content / structured analysis / scoring

### Parsing
- [ ] refactor HTML extraction
- [ ] add PDF text cleaning
- [ ] add HTML vs PDF quality selection
- [ ] rebuild summary extraction by section
- [ ] add dedicated risk-section extraction

### Analysis
- [ ] split `build_structured_analysis` into smaller functions
- [ ] add revenue / profit / margin signal extraction
- [ ] add rating change detection
- [ ] add target price / EPS / PE extraction
- [ ] add theme tag inference

### Scoring
- [ ] add signal score
- [ ] add score breakdown
- [ ] add priority bucket classification

### Export
- [ ] upgrade single-report markdown layout
- [ ] add `TRADING_DASHBOARD.md`
- [ ] enrich `TOP_SIGNALS.md`
- [ ] enrich `SECTOR_BRIEF.md`
- [ ] enrich `THEME_BRIEF.md`
- [ ] extend CSV / JSON export schema

### Resume / Batch
- [ ] add `--refresh-weak`
- [ ] add `--resume-errors-only`
- [ ] add `--min-text-length`
- [ ] add `--concurrency`
- [ ] add optional request jitter

### Validation
- [ ] prepare regression sample set
- [ ] add parser tests
- [ ] add analysis tests
- [ ] add scoring tests
- [ ] create manual QA checklist
