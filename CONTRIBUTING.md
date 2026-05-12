# Contributing

Thanks for your interest in contributing to `eastmoney-report-scraper`.

## Scope

This project focuses on:

- Eastmoney research report collection
- robust extraction and fallback handling
- local research artifact generation
- structured analysis and downstream research workflows

## Before You Start

Please read:

- [README.md](./README.md)
- [README.en.md](./README.en.md)
- [ROADMAP.md](./ROADMAP.md)
- [TODO.md](./TODO.md)

## Contribution Guidelines

### 1. Keep changes focused

Prefer small, scoped changes over broad unrelated refactors.

### 2. Preserve output compatibility when possible

Existing outputs such as:

- report markdown files
- `SUMMARY.md`
- `ANALYSIS_INPUT.md`
- `ANALYSIS_INPUT.json`
- `report_index.csv`

should remain stable unless there is a clear versioned reason to change them.

### 3. Prioritize robustness

This project depends on page extraction, so stability matters more than aggressive optimization.

### 4. Document new behavior

If you add or change:

- CLI arguments
- output files
- required dependencies
- workflow behavior

please update the relevant documentation.

## Development Suggestions

### Areas where contributions are especially welcome

- extraction quality improvements
- risk-section parsing improvements
- valuation / rating field extraction
- scoring and prioritization logic
- resume and incremental update improvements
- tests and regression fixtures
- output formatting and dashboards

## Pull Request Checklist

Before submitting a change, please make sure:

- [ ] the change is scoped and explained clearly
- [ ] docs are updated if behavior changed
- [ ] outputs were manually checked on sample reports
- [ ] no unrelated generated output is committed
- [ ] the change aligns with the roadmap direction

## Reporting Issues

When reporting a bug, it is helpful to include:

- target date or date range
- command used
- whether HTML or PDF fallback was used
- example output file or error snippet
- whether the issue is reproducible

## License

By contributing to this repository, you agree that your contributions will be licensed under the [MIT License](./LICENSE).
