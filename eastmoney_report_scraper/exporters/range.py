"""Date-range summary exporters."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..constants import QTYPE_NAMES
from ..models import DayRun
from .common import _analysis_for

def write_range_summary(root_dir: Path, day_runs: List[DayRun], qtype: int) -> None:
    if len(day_runs) <= 1:
        return
    qtype_name = QTYPE_NAMES.get(qtype, str(qtype))
    total_list = sum(len(run.raw_list) for run in day_runs)
    total_fetched = sum(len(run.results) for run in day_runs)
    total_ok = sum(sum(r.status == "ok" for r in run.results) for run in day_runs)
    total_weak = sum(sum(r.status == "weak" for r in run.results) for run in day_runs)
    total_error = sum(sum(r.status == "error" for r in run.results) for run in day_runs)
    lines = [
        "# 东方财富研报区间汇总",
        "",
        f"- 类型：`{qtype_name}`",
        f"- 日期区间：`{day_runs[0].date_str}` → `{day_runs[-1].date_str}`",
        f"- 列表总数：`{total_list}`",
        f"- 抓取篇数：`{total_fetched}`",
        f"- 成功：`{total_ok}` | 弱提取：`{total_weak}` | 失败：`{total_error}`",
        "",
        "| 日期 | 列表总数 | 抓取篇数 | 成功 | 弱提取 | 失败 | 目录 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for run in day_runs:
        lines.append(
            f"| {run.date_str} | {len(run.raw_list)} | {len(run.results)} | {sum(r.status == 'ok' for r in run.results)} | {sum(r.status == 'weak' for r in run.results)} | {sum(r.status == 'error' for r in run.results)} | {run.output_dir.name} |"
        )
    (root_dir / "RANGE_SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root_dir / "RANGE_DASHBOARD.md").write_text(build_range_dashboard(day_runs), encoding="utf-8")

def build_range_dashboard(day_runs: List[DayRun]) -> str:
    industry_by_day: Dict[str, Dict[str, int]] = {}
    theme_by_day: Dict[str, Dict[str, int]] = {}
    stock_by_day: Dict[str, Dict[str, int]] = {}
    for run in day_runs:
        industry_by_day.setdefault(run.date_str, {})
        theme_by_day.setdefault(run.date_str, {})
        stock_by_day.setdefault(run.date_str, {})
        for result in run.results:
            analysis = _analysis_for(result)
            item = result.item
            industry = item.get("industryName") or item.get("indvInduName") or "未标注行业"
            stock = item.get("stockName") or item.get("industryName") or "未知标的"
            industry_by_day[run.date_str][industry] = industry_by_day[run.date_str].get(industry, 0) + 1
            stock_by_day[run.date_str][stock] = stock_by_day[run.date_str].get(stock, 0) + 1
            for tag in analysis.get("theme_tags") or []:
                theme_by_day[run.date_str][tag] = theme_by_day[run.date_str].get(tag, 0) + 1

    lines = ["# RANGE_DASHBOARD", "", f"- 覆盖日期：`{len(day_runs)}`", ""]
    for title, grouped in (("Industry Heat", industry_by_day), ("Theme Heat", theme_by_day), ("Stock Heat", stock_by_day)):
        lines.append(f"## {title}")
        lines.append("")
        for day, counter in grouped.items():
            top = sorted(counter.items(), key=lambda item: item[1], reverse=True)[:5]
            rendered = "；".join([f"{name}={count}" for name, count in top]) if top else "[无样本]"
            lines.append(f"- `{day}`：{rendered}")
        lines.append("")
    return "\n".join(lines) + "\n"
