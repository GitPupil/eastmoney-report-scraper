"""Shared constants for the Eastmoney report scraper."""

from pathlib import Path
from typing import Sequence, Tuple

LIST_API = "https://reportapi.eastmoney.com/report/list"
DETAIL_URL_TEMPLATE = "https://data.eastmoney.com/report/info/{info_code}.html"
PDF_URL_TEMPLATE = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
DEFAULT_OUTPUT_ROOT = Path.cwd() / "eastmoney_reports"
DEFAULT_INDEX_NAME = "report_index.csv"
DEFAULT_MANIFEST_NAME = "run_manifest.jsonl"
DEFAULT_COVERAGE_HISTORY_NAME = "COVERAGE_HISTORY.jsonl"
DEFAULT_COVERAGE_SUMMARY_NAME = "COMPANY_COVERAGE_SUMMARY.csv"
DEFAULT_INDUSTRY_COVERAGE_SUMMARY_NAME = "INDUSTRY_COVERAGE_SUMMARY.csv"
DEFAULT_HOTSPOT_DASHBOARD_NAME = "HOTSPOT_DASHBOARD.md"
DEFAULT_HOTSPOT_SIGNALS_NAME = "HOTSPOT_SIGNALS.csv"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
SUMMARY_SECTION_KEYS: Sequence[Tuple[str, str]] = (
    ("事件", "事件"),
    ("投资要点", "投资要点"),
    ("核心观点", "核心观点"),
    ("盈利预测与投资建议", "盈利预测与投资建议"),
    ("投资建议", "投资建议"),
    ("风险提示", "风险提示"),
)
