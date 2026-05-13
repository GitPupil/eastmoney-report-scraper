# TODO

## 0.2.0 Current Status

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
- [x] Pytest regression tests and ruff checks

## Remaining Work

### Extraction
- [ ] Improve PDF text cleanup
- [ ] Add a small checked-in regression fixture set
- [ ] Further reduce noisy summary bullets

### Analysis
- [ ] Improve headline quality
- [ ] Compress core drivers into cleaner research-style bullets
- [ ] Improve theme tag precision
- [ ] Continue calibrating score thresholds

### Research Outputs
- [ ] Deepen consensus and divergence summaries
- [ ] Add richer range-level synthesis for repeated multi-day runs
- [ ] Add more explicit hotspot reason categories for downstream agents

### Engineering
- [ ] Add GitHub Actions for pytest and ruff
- [ ] Add smoke-test fixtures that do not require network access
- [ ] Document release tagging workflow
