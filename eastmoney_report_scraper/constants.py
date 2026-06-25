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
DEFAULT_DASHBOARD_NAME = "DASHBOARD.html"
DEFAULT_LOCAL_DB_NAME = "eastmoney.db"
DEFAULT_LOCAL_CONFIG_NAME = "local_app_config.json"
DEFAULT_AI_CONFIG_NAME = "local_ai_config.json"
QTYPE_STOCK = 0
QTYPE_INDUSTRY = 1
QTYPE_ALL = 2
QTYPE_NAMES = {
    QTYPE_STOCK: "个股研报",
    QTYPE_INDUSTRY: "行业研报",
    QTYPE_ALL: "全部",
}
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
