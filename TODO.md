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

## Remaining Work

### Parsing
- [ ] improve HTML section detection stability
- [ ] add PDF text cleaning improvements
- [ ] add HTML vs PDF quality selection / merge strategy
- [ ] further reduce noisy summary bullets

### Analysis
- [ ] keep refining headline quality
- [ ] compress core drivers into cleaner research-style expressions
- [ ] improve theme tag precision
- [ ] improve consistency between signals, risks, and score
- [ ] add same-stock multi-broker aggregation

### Scoring
- [ ] continue calibrating score thresholds
- [ ] add more explicit score breakdown export
- [ ] distinguish recovery-driven vs quality-growth-driven ideas better

### Resume / Batch
- [ ] add `--refresh-weak`
- [ ] add `--resume-errors-only`
- [ ] add `--min-text-length`
- [ ] add optional request jitter / throttling

### Engineering
- [ ] split monolithic script into internal modules
- [ ] add parser tests
- [ ] add analysis tests
- [ ] add scoring tests
- [ ] prepare regression sample set
- [ ] add CI / smoke checks
