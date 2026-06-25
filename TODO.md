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
- [x] Local App optional AI settings and analysis API
- [x] Token masking helpers and regression tests for local AI config
- [x] cc-switch current Claude provider import for Anthropic-compatible AI analysis
- [x] Standalone `ai_connector.py` for reusing AI provider integration in other projects
- [x] AI P0: prompt templates, richer scopes, provider profiles, compatibility diagnostics, and test connection
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
- [x] Add token redaction helpers and regression tests before enabling any token-based integration.
- [x] Add optional Local App AI explanation workflow grounded in structured evidence, not raw unbounded report dumps.
- [x] Add local model API token config for Local App; tokens are masked in UI/API diagnostics and excluded from exported research artifacts.
- [x] Add built-in prompt templates for common research tasks so users can choose a prepared analysis style instead of writing prompts every time.
- [x] Add multiple AI token/provider profiles with quick switching in the Local App.
- [x] Expand AI analysis scopes to all fetched data, one company, multiple companies, one industry, multiple industries, selected hotspots, and selected date ranges.
- [x] Add prompt templates for company, industry, multi-industry, date-range, hotspot, and opinion-change explanations.
- [x] Add a provider diagnostic / test connection button that probes endpoint, payload shape, auth, unsupported parameters, empty responses, and streaming/plain-text behavior.
- [ ] Add CLI AI analysis command using the same evidence builder.
- [ ] Add richer Local App actions to explain selected hotspot and date range presets when an AI token is configured.
- [ ] Further formalize provider adapters beyond the current OpenAI Chat, OpenAI Responses, Text Completions, Anthropic-compatible, cc-switch, SSE/plain-text, and error-diagnostic tests.
- [ ] Add evidence preview and evidence quality checks before sending AI requests.
- [ ] Add structured AI output fields such as `coreConclusion`, `bullishEvidence`, `bearishEvidence`, `opinionChange`, `brokerConsensus`, `nextWatch`, `confidence`, and `sourceReportIds`.
- [ ] Add traceable citations from AI conclusions back to report IDs, brokers, dates, ratings, target prices, EPS fields, and hotspot reason codes.
- [ ] Add AI analysis history cache, likely `AI_ANALYSIS_HISTORY.jsonl`, keyed by scope, evidence hash, prompt template, provider, and model.
- [ ] Add batch AI analysis jobs for daily A/B priority reports, HOT/STRONG hotspots, industry groups, and selected watchlists.
- [ ] Add `AI_DAILY_BRIEF.md` generated from batch AI analysis.
- [ ] Add multi-model comparison for the same evidence, including cheap-model screening and stronger-model deep dives.
- [ ] Add token and cost estimation before each AI request.
- [ ] Add rule-vs-AI consistency checks so deterministic signals and AI conclusions can flag conflicts.

### AI Analysis Priority Order
- [x] P0: Prompt templates, richer analysis scopes, provider profiles, provider compatibility tests, and test connection diagnostics.
- [ ] P1: Evidence preview, evidence quality checks, structured AI output, citations/source traceability, and AI analysis history cache.
- [ ] P2: Batch AI analysis jobs, `AI_DAILY_BRIEF.md`, multi-model comparison, token/cost estimation, and rule-vs-AI consistency checks.

### Market Data & Alpha Feedback
- [ ] Add optional real-time market data API integration. Users should provide API tokens locally; tokens must not be written to Git, logs, Markdown/CSV/JSONL/XLSX outputs, SQLite rows, dashboard HTML, or error messages.
- [ ] Compare report coverage heat, first coverage, broker resonance, and opinion-change events with later market performance.
- [ ] Add 3/5/10-day post-event return and excess-return summaries when market data is available.
- [ ] Let AI explanations reference market feedback only after the structured return evidence is available.

### Engineering
- [ ] Document release tagging workflow
- [ ] Add public examples and sample output fixtures
- [ ] Add sample Local App screenshots
