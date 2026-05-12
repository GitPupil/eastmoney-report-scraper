# Development

## Environment

Recommended:

- Python 3.9+
- `pdftotext` available in PATH if you want PDF fallback coverage

## Setup

### Minimal setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Local Run

```bash
python3 scripts/fetch_reports.py --help
python3 scripts/fetch_reports.py --date 2026-05-12
```

## Packaging Note

A `pyproject.toml` is included so the repository has a standard Python project shape.
The current implementation is still a script-first project centered on:

- `scripts/fetch_reports.py`

Future refactors can move parsing, analysis, scoring, and export logic into installable modules.

## Recommended Next Engineering Steps

- add internal package modules under `scripts/` or `src/`
- add automated tests for parsing and analysis
- add lint / format tooling
- add CI for basic validation
