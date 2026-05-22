# Roadmap

## 0.3.0 Landed

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
- GitHub Actions CI
- Pytest fixtures and ruff development checks

---

## Next Milestones

### 0.4.0: Extraction Reliability
- Improve PDF text cleanup
- Reduce noisy summary bullets
- Add stronger handling for malformed pages

### 0.5.0: Research Depth
- Improve headline and core-driver quality
- Deepen consensus and divergence summaries
- Add richer range-level synthesis
- Calibrate hotspot reason categories on real small samples

### 0.6.0: Developer Experience
- Document release tagging and publishing workflow
- Expand public examples and sample output screenshots
- Add richer contribution examples
