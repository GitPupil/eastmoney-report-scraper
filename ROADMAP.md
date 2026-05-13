# Roadmap

## 0.2.0 Landed

- Modular package layout under `eastmoney_report_scraper/`
- Compatibility script entrypoint in `scripts/fetch_reports.py`
- Parser, analysis, scoring, exporter, CLI, and hotspot modules
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
- Pytest regression tests and ruff development checks

---

## Next Milestones

### 0.3.0: Extraction Reliability
- Add small HTML/PDF regression fixtures
- Improve PDF text cleanup
- Reduce noisy summary bullets
- Add stronger handling for malformed pages

### 0.4.0: Research Depth
- Improve headline and core-driver quality
- Deepen consensus and divergence summaries
- Add richer range-level synthesis
- Refine hotspot reason categories for downstream agents

### 0.5.0: Developer Experience
- Add GitHub Actions for pytest and ruff
- Add network-free smoke fixtures
- Document release tagging and publishing workflow
- Expand public examples and sample output screenshots
