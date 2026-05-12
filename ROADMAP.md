# eastmoney-report-scraper Roadmap

## v1.5 Goal

Upgrade the scraper from a basic collection tool into a more reliable research workflow tool:

- more accurate structured analysis
- better risk extraction
- transaction-oriented ranking and summaries
- stronger resume / batch handling

---

## P0 (Must Have)

### 1. Structured analysis refactor
- replace coarse full-text keyword tagging
- split output into clearer fields:
  - headline
  - core drivers
  - revenue / profit / margin view
  - valuation / rating
  - trade hint
  - risks
- reduce contradictory positive/negative labeling

### 2. Risk extraction fix
- extract only from explicit risk sections
- reduce cross-company / cross-industry contamination
- mark missing risk sections clearly

### 3. Signal score
- add rule-based signal scoring
- rank reports by trading relevance
- generate top ideas / top risks / top deep-dive candidates

### 4. Rating / target price / forecast extraction
- extract rating
- detect rating change
- detect first coverage
- extract target price / EPS / PE

### 5. Richer exports
- extend CSV / JSON fields with:
  - signal score
  - rating change
  - target price
  - EPS / PE forecasts
  - theme tags
  - risk tags

---

## P1 (Should Have)

### 6. Controlled concurrency
- add `--concurrency`
- concurrent detail fetch with retry / jitter / fallback

### 7. Stronger resume
- re-fetch weak outputs
- support `--resume-errors-only`
- support minimum text length threshold

### 8. Trading dashboard
- add `TRADING_DASHBOARD.md`
- summarize:
  - headline
  - strongest longs
  - biggest risks
  - sector heat
  - broker activity

### 9. Better HTML/PDF selection
- compare HTML and PDF text quality
- choose best source or merge
- clean PDF noise better

---

## P2 (Nice to Have)

### 10. Watchlist / theme mode
- watch specific stocks / sectors / brokers
- generate watchlist-focused daily outputs

### 11. Multi-day consensus analysis
- cross-day sector heat
- repeated broker coverage
- rising keywords / themes

### 12. Request-side filtering research
- see whether Eastmoney list API supports better upstream filters

---

## Suggested Milestones

### Milestone A: Correctness
- structured analysis refactor
- risk extraction fix
- valuation / rating field extraction

### Milestone B: Research usability
- signal scoring
- richer CSV / JSON
- trading dashboard

### Milestone C: Engineering
- concurrency
- stronger resume
- better PDF handling
