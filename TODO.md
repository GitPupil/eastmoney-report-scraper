# TODO

## 0.5.0 Current Status

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
- [x] Offline static `DASHBOARD.html`
- [x] Dashboard CLI modes: `--dashboard-only`, `--no-dashboard`, `--dashboard-name`
- [x] Optional Local App dependencies via `.[app]`
- [x] Local App commands: `app` and `import-existing`
- [x] Local App one-click Windows launcher
- [x] SQLite local cache for reports, hotspots, coverage history, manifests, and runs
- [x] Local App service, task, and API layers
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
- [ ] Build structured opinion-change evidence for rating, target price, EPS, signal score, and same-broker continuity
- [ ] Track narrative keyword trends for company and industry entities

### Research Outputs
- [ ] Deepen consensus and divergence summaries
- [ ] Add richer range-level synthesis for repeated multi-day runs
- [ ] Calibrate hotspot reason categories on real small samples
- [ ] Add sample Dashboard screenshots for public docs
- [ ] Add company/industry opinion-change evidence exports for optional AI explanation
- [ ] Add non-AI fallback summaries based on the same structured evidence

### AI Explanation
- [ ] Add token redaction helpers and regression tests before enabling any token-based integration.
- [ ] Add optional AI explanation workflow grounded in structured evidence, not raw unbounded report dumps.
- [ ] Add local model API token config for Local App and CLI use; tokens must be masked in UI/CLI diagnostics and excluded from exported research artifacts.
- [ ] Add prompt templates for company, industry, date-range, hotspot, and opinion-change explanations.
- [ ] Add Local App actions to explain selected company, industry, hotspot, or date range when an AI token is configured.

### Market Data & Alpha Feedback
- [ ] Add optional real-time market data API integration. Users should provide API tokens locally; tokens must not be written to Git, logs, Markdown/CSV/JSONL/XLSX outputs, SQLite rows, dashboard HTML, or error messages.
- [ ] Compare report coverage heat, first coverage, broker resonance, and opinion-change events with later market performance.
- [ ] Add 3/5/10-day post-event return and excess-return summaries when market data is available.
- [ ] Let AI explanations reference market feedback only after the structured return evidence is available.

### Engineering
- [ ] Document release tagging workflow
- [ ] Add public examples and sample output fixtures
- [ ] Add sample Local App screenshots
