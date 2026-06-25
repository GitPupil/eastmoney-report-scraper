# Roadmap

## 0.5.0 Landed

- Modular package layout under `eastmoney_report_scraper/`
- Compatibility script entrypoint in `scripts/fetch_reports.py`
- Parser, analysis, scoring, exporter package, CLI, and hotspot modules
- Run manifest for weak/error resume workflows
- Text quality scoring for HTML/PDF selection
- Score reasons and score breakdown exports
- Daily briefs, trading dashboard, consensus brief, and range dashboard
- Historical coverage files:
  - `COVERAGE_HISTORY.jsonl`
  - `COMPANY_COVERAGE_SUMMARY.csv`
  - `INDUSTRY_COVERAGE_SUMMARY.csv`
- Hotspot files:
  - `HOTSPOT_DASHBOARD.md`
  - `HOTSPOT_SIGNALS.csv`
- Hotspot reason codes and broker normalization hook
- CLI lightweight modes: `--doctor`, `--dry-run`, `--list-only`, `--hotspots-only`
- Offline static `DASHBOARD.html`
- Dashboard CLI modes: `--dashboard-only`, `--no-dashboard`, `--dashboard-name`
- Optional Local App dependencies through `.[app]`
- Local App commands: `app` and `import-existing`
- SQLite local cache for reports, hotspots, coverage history, manifests, and run status
- Local browser workspace for tasks, hotspots, reports, and dashboard data
- Optional Local App AI settings and analysis API using bounded structured evidence
- Token masking helpers and regression tests for local AI config
- cc-switch current Claude provider import for Anthropic-compatible local AI analysis
- Standalone `ai_connector.py` for cross-project AI provider integration reuse
- AI P0 usability: built-in prompt templates, richer Local App scopes, multiple provider profiles, and test-connection diagnostics
- GitHub Actions CI
- Pytest fixtures and ruff development checks

---

## Next Milestones

### 0.6.0: Extraction Reliability
- Improve PDF text cleanup
- Reduce noisy summary bullets
- Add stronger handling for malformed pages

### 0.7.0: Research Narrative & AI Explanation
- Improve headline and core-driver quality
- Build structured opinion-change evidence for ratings, target prices, EPS, signal score, and same-broker continuity
- Track company and industry narrative trends through keywords, theme tags, broker diffusion, and hotspot reason codes
- Deepen consensus, divergence, and range-level synthesis using structured evidence
- Add a CLI AI analysis command that reuses the Local App evidence builder

AI priority sequence:
- P0 usability: completed in the Local App with built-in prompt templates, richer scopes for all/company/industry/hotspot/date-range analysis, multiple provider profiles, provider compatibility tests, and a test-connection diagnostic.
- P1 trust: completed in the Local App with evidence preview, evidence quality checks, structured AI output, source citations, `AI_ANALYSIS_HISTORY.jsonl` caching, and `AI_ANALYSES/*.md` exports.
- P2 automation: batch AI analysis jobs, `AI_DAILY_BRIEF.md`, multi-model comparison, token/cost estimation, and rule-vs-AI consistency checks.

### 0.8.0: Market Data & Alpha Feedback
- Add optional real-time market data API integration with user-provided local tokens
- Compare report coverage heat, first coverage, broker resonance, and opinion-change events with later market performance
- Add 3/5/10-day post-event return and excess-return summaries
- Let AI explanations distinguish alpha, lagging confirmation, and narrative follow-through when market evidence is available
- Keep tokens out of Git, logs, exports, dashboards, SQLite rows, and exceptions

### 0.9.0: Developer Experience
- Document release tagging and publishing workflow
- Expand public examples and sample output screenshots
- Add richer contribution examples
