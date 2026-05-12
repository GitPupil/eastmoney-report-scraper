# TODO

## v1.5 Current Status

### Landed
- [x] financial signal extraction
- [x] refined risk extraction
- [x] valuation field extraction (`ratingChange`, `targetPrice`, `epsForecast`, `peForecast`)
- [x] signal score
- [x] priority bucket classification
- [x] `TRADING_DASHBOARD.md`
- [x] sector / theme heat in dashboard
- [x] `--concurrency`
- [x] richer CSV export schema
- [x] v2 package layout
- [x] `run_manifest.jsonl`
- [x] text quality score
- [x] score breakdown export
- [x] `CONSENSUS_BRIEF.md`
- [x] `RANGE_DASHBOARD.md`
- [x] pytest regression tests

## Remaining Work

### Parsing
- [x] improve HTML section detection stability
- [ ] add PDF text cleaning improvements
- [x] add HTML vs PDF quality selection / merge strategy
- [ ] further reduce noisy summary bullets

### Analysis
- [ ] keep refining headline quality
- [ ] compress core drivers into cleaner research-style expressions
- [ ] improve theme tag precision
- [ ] improve consistency between signals, risks, and score
- [x] add same-stock multi-broker aggregation

### Scoring
- [ ] continue calibrating score thresholds
- [x] add more explicit score breakdown export
- [ ] distinguish recovery-driven vs quality-growth-driven ideas better

### Resume / Batch
- [x] add `--refresh-weak`
- [x] add `--resume-errors-only`
- [x] add `--min-text-length`
- [x] add optional request jitter / throttling

### Engineering
- [x] split monolithic script into internal modules
- [x] add parser tests
- [x] add analysis tests
- [x] add scoring tests
- [ ] prepare regression sample set
- [ ] add CI / smoke checks
