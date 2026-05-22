# TODO

## 0.3.0 Current Status

### Landed
- [x] Modular package layout
- [x] Compatibility script entrypoint
- [x] Structured HTML extraction with PDF fallback
- [x] Text quality scoring
- [x] Run manifest for weak/error resume workflows
- [x] Transparent signal score reasons and breakdown
- [x] Daily briefs, trading dashboard, consensus brief, and range dashboard
- [x] Historical company and industry coverage summaries
- [x] Hotspot dashboard and hotspot signal CSV
- [x] Hotspot reason codes and broker normalization hook
- [x] CLI lightweight modes: `--doctor`, `--dry-run`, `--list-only`, `--hotspots-only`
- [x] Exporter package split with compatible public imports
- [x] GitHub Actions CI
- [x] Network-free parser and CLI fixtures
- [x] Pytest regression tests and ruff checks

## Remaining Work

### Extraction
- [ ] Improve PDF text cleanup
- [ ] Further reduce noisy summary bullets

### Analysis
- [ ] Improve headline quality
- [ ] Compress core drivers into cleaner research-style bullets
- [ ] Improve theme tag precision
- [ ] Continue calibrating score thresholds

### Research Outputs
- [ ] Deepen consensus and divergence summaries
- [ ] Add richer range-level synthesis for repeated multi-day runs
- [ ] Calibrate hotspot reason categories on real small samples

### Engineering
- [ ] Document release tagging workflow
- [ ] Add public examples and sample output screenshots
