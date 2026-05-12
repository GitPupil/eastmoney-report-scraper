#!/usr/bin/env python3
"""Compatibility entrypoint for the v2 package layout."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eastmoney_report_scraper.cli import main  # noqa: E402


if __name__ == "__main__":
    main()
