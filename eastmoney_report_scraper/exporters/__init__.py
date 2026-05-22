"""Exporter package public API."""

from .briefs import (
    build_consensus_brief,
    build_daily_brief,
    build_sector_brief,
    build_theme_brief,
    build_top_signals,
    build_trading_dashboard,
    write_day_summary,
)
from .coverage import (
    read_coverage_history,
    update_coverage_history,
    write_company_coverage_summary,
    write_coverage_history,
    write_industry_coverage_summary,
)
from .indexes import write_csv_index, write_xlsx_index
from .markdown import build_markdown
from .range import build_range_dashboard, write_range_summary

__all__ = [
    "build_consensus_brief",
    "build_daily_brief",
    "build_markdown",
    "build_range_dashboard",
    "build_sector_brief",
    "build_theme_brief",
    "build_top_signals",
    "build_trading_dashboard",
    "read_coverage_history",
    "update_coverage_history",
    "write_company_coverage_summary",
    "write_coverage_history",
    "write_csv_index",
    "write_day_summary",
    "write_industry_coverage_summary",
    "write_range_summary",
    "write_xlsx_index",
]
