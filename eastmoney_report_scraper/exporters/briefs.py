"""Daily report brief and dashboard exporters."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from ..constants import QTYPE_NAMES
from ..models import FetchResult
from .common import _analysis_for
from .indexes import write_csv_index, write_xlsx_index

def write_day_summary(output_dir: Path, target_date: str, qtype: int, raw_list: List[Dict[str, Any]], results: Iterable[FetchResult], log_path: Path) -> None:
    results = list(results)
    (output_dir / "report_list.json").write_text(json.dumps(raw_list, ensure_ascii=False, indent=2), encoding="utf-8")

    qtype_name = QTYPE_NAMES.get(qtype, str(qtype))
    lines = [
        f"# 东方财富研报采集汇总（{target_date}）",
        "",
        f"- 类型：`{qtype_name}`",
        f"- 列表总数：`{len(raw_list)}`",
        f"- 抓取篇数：`{len(results)}`",
        f"- 成功：`{sum(r.status == 'ok' for r in results)}`",
        f"- 弱提取：`{sum(r.status == 'weak' for r in results)}`",
        f"- 失败：`{sum(r.status == 'error' for r in results)}`",
        f"- resume 跳过：`{sum(r.skipped for r in results)}`",
        "",
        "## 明细",
        "",
        "| 序号 | 标的 | 标题 | 机构 | 状态 | 来源 | 质量 | 字符数 | 摘要 | 文件 |",
        "|---|---|---|---|---|---|---:|---:|---|---|",
    ]
    for idx, result in enumerate(results, 1):
        item = result.item
        stock_label = item.get("stockName") or item.get("industryName") or "-"
        file_name = result.output_path.name if result.output_path else "-"
        summary_text = "；".join(result.summary[:2]) if result.summary else "-"
        lines.append(
            "| {idx} | {stock} | {title} | {org} | {status} | {source} | {quality} | {chars} | {summary} | {file} |".format(
                idx=idx,
                stock=stock_label.replace("|", "/"),
                title=(item.get("title") or "-").replace("|", "/"),
                org=(item.get("orgSName") or item.get("orgName") or "-").replace("|", "/"),
                status=result.status,
                source=result.source,
                quality=result.quality_score,
                chars=len(result.text),
                summary=summary_text.replace("|", "/"),
                file=file_name.replace("|", "/"),
            )
        )
        if result.error:
            lines.append(f"\n> error[{idx}]: `{result.error}`")
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    analysis_input = _write_summary_and_analysis(output_dir, target_date, results)
    (output_dir / "DAILY_BRIEF.md").write_text(build_daily_brief(target_date, analysis_input), encoding="utf-8")
    (output_dir / "TOP_SIGNALS.md").write_text(build_top_signals(target_date, analysis_input), encoding="utf-8")
    (output_dir / "SECTOR_BRIEF.md").write_text(build_sector_brief(target_date, analysis_input), encoding="utf-8")
    (output_dir / "THEME_BRIEF.md").write_text(build_theme_brief(target_date, analysis_input), encoding="utf-8")
    (output_dir / "TRADING_DASHBOARD.md").write_text(build_trading_dashboard(target_date, analysis_input), encoding="utf-8")
    (output_dir / "CONSENSUS_BRIEF.md").write_text(build_consensus_brief(target_date, analysis_input), encoding="utf-8")

    csv_index_path = write_csv_index(output_dir, results)
    write_xlsx_index(output_dir, csv_index_path, log_path)

def _write_summary_and_analysis(output_dir: Path, target_date: str, results: List[FetchResult]) -> List[Dict[str, Any]]:
    summary_lines = [
        f"# 自动摘要（{target_date}）",
        "",
        f"- 研报数：`{len(results)}`",
        "",
    ]
    analysis_input = []
    for idx, result in enumerate(results, 1):
        item = result.item
        stock_label = item.get("stockName") or item.get("industryName") or "未知标的"
        summary_lines.append(f"## {idx:03d}. {stock_label}｜{item.get('title', '')}")
        summary_lines.append("")
        if result.summary:
            summary_lines.extend([f"- {bullet}" for bullet in result.summary])
        else:
            summary_lines.append("- [未提取到有效摘要]")
        summary_lines.append("")

        structured_analysis = _analysis_for(result)
        analysis_input.append(
            {
                "index": idx,
                "stockName": item.get("stockName"),
                "stockCode": item.get("stockCode"),
                "industryName": item.get("industryName") or item.get("indvInduName"),
                "title": item.get("title"),
                "orgName": item.get("orgSName") or item.get("orgName"),
                "publishDate": item.get("publishDate"),
                "rating": item.get("emRatingName") or item.get("sRatingName"),
                "infoCode": item.get("infoCode"),
                "status": result.status,
                "source": result.source,
                "qualityScore": result.quality_score,
                "summary": result.summary,
                "structured_analysis": structured_analysis,
                "textPreview": result.text[:1200],
                "file": result.output_path.name if result.output_path else None,
            }
        )
    (output_dir / "SUMMARY.md").write_text("\n".join(summary_lines), encoding="utf-8")
    (output_dir / "ANALYSIS_INPUT.json").write_text(json.dumps(analysis_input, ensure_ascii=False, indent=2), encoding="utf-8")

    analysis_prompt_lines = [
        f"# AI 分析输入（{target_date}）",
        "",
        "这个文件给后续 AI/分析代理使用：先读取下方每篇研报的摘要，再做归纳分析。",
        "建议输出结构：`headline -> 共识主线 -> 分歧点 -> 业绩/估值/评级变化 -> 可交易线索 -> 风险`。",
        "",
    ]
    for entry in analysis_input:
        name = entry.get("stockName") or entry.get("industryName") or "未知标的"
        analysis = entry["structured_analysis"]
        analysis_prompt_lines.append(f"## {entry['index']:03d}. {name}｜{entry.get('title') or ''}")
        analysis_prompt_lines.append("")
        analysis_prompt_lines.append(f"- 机构：`{entry.get('orgName') or ''}`")
        analysis_prompt_lines.append(f"- 日期：`{entry.get('publishDate') or ''}`")
        analysis_prompt_lines.append(f"- 评级：`{entry.get('rating') or ''}`")
        analysis_prompt_lines.append(f"- 状态：`{entry.get('status') or ''}` | 来源：`{entry.get('source') or ''}` | 质量：`{entry.get('qualityScore')}`")
        analysis_prompt_lines.append(f"- 文件：`{entry.get('file') or ''}`")
        analysis_prompt_lines.append("- 摘要：")
        if entry["summary"]:
            analysis_prompt_lines.extend([f"  - {bullet}" for bullet in entry["summary"]])
        else:
            analysis_prompt_lines.append("  - [未提取到有效摘要]")
        analysis_prompt_lines.append("- 结构化分析：")
        analysis_prompt_lines.append(f"  - 一句话结论：{analysis['headline']}")
        analysis_prompt_lines.append(f"  - 核心驱动：{'；'.join(analysis['core_drivers']) if analysis['core_drivers'] else '[无]'}")
        analysis_prompt_lines.append(f"  - 正向信号：{'；'.join(analysis['positive_signals']) if analysis['positive_signals'] else '[无]'}")
        analysis_prompt_lines.append(f"  - 负向信号：{'；'.join(analysis['negative_signals']) if analysis['negative_signals'] else '[无]'}")
        analysis_prompt_lines.append(f"  - 估值/评级：{'；'.join(analysis['valuation_and_rating']) if analysis['valuation_and_rating'] else '[无]'}")
        analysis_prompt_lines.append(f"  - 交易含义：{'；'.join(analysis['trade_hint']) if analysis['trade_hint'] else '[无]'}")
        analysis_prompt_lines.append(f"  - 风险：{'；'.join(analysis['risks']) if analysis['risks'] else '[无]'}")
        analysis_prompt_lines.append(f"  - 信号评分：{analysis.get('signal_score', '[无]')} / 100（优先级：{analysis.get('priority_bucket', '[无]')}）")
        analysis_prompt_lines.append(f"  - 评分原因：{'；'.join(analysis.get('score_reasons', [])) if analysis.get('score_reasons') else '[无]'}")
        analysis_prompt_lines.append(f"  - 评分拆解：`{json.dumps(analysis.get('score_breakdown', {}), ensure_ascii=False)}`")
        analysis_prompt_lines.append(f"  - 主题标签：{'；'.join(analysis.get('theme_tags', [])) if analysis.get('theme_tags') else '[无]'}")
        analysis_prompt_lines.append("")
    (output_dir / "ANALYSIS_INPUT.md").write_text("\n".join(analysis_prompt_lines), encoding="utf-8")
    return analysis_input

def build_daily_brief(target_date: str, analysis_input: List[Dict[str, Any]]) -> str:
    positive_count = 0
    negative_count = 0
    industry_counter: Dict[str, int] = {}
    org_counter: Dict[str, int] = {}
    headlines: List[str] = []
    signals: List[str] = []

    for entry in analysis_input:
        analysis = entry["structured_analysis"]
        if analysis["positive_signals"]:
            positive_count += 1
        if analysis["negative_signals"]:
            negative_count += 1
        industry = entry.get("industryName") or "未标注行业"
        org = entry.get("orgName") or "未知机构"
        industry_counter[industry] = industry_counter.get(industry, 0) + 1
        org_counter[org] = org_counter.get(org, 0) + 1
        headlines.append(f"- `{entry.get('stockName') or industry}`：{analysis['headline']}")
        if analysis["trade_hint"]:
            signals.append(f"- `{entry.get('stockName') or industry}`（score={analysis.get('signal_score', 0)} / {analysis.get('priority_bucket', 'C')}）：{analysis['trade_hint'][0]}")

    top_industries = sorted(industry_counter.items(), key=lambda item: item[1], reverse=True)[:5]
    top_orgs = sorted(org_counter.items(), key=lambda item: item[1], reverse=True)[:5]

    lines = [
        f"# DAILY_BRIEF（{target_date}）",
        "",
        f"- 样本数：`{len(analysis_input)}`",
        f"- 正向信号篇数：`{positive_count}`",
        f"- 负向信号篇数：`{negative_count}`",
        "",
        "## Headline",
        "",
        f"- 当天研报整体更偏 {'业绩/景气改善' if positive_count >= negative_count else '分化/谨慎'}。",
        "",
        "## 主线",
        "",
    ]
    lines.extend([f"- `{name}`：出现 `{count}` 次" for name, count in top_industries] if top_industries else ["- [样本不足]"])
    lines.extend(["", "## 重点个股", ""])
    lines.extend(headlines[:10] if headlines else ["- [样本不足]"])
    lines.extend(["", "## 机构活跃度", ""])
    lines.extend([f"- `{name}`：覆盖 `{count}` 篇" for name, count in top_orgs] if top_orgs else ["- [样本不足]"])
    lines.extend(["", "## 可交易线索", ""])
    lines.extend(signals[:10] if signals else ["- [样本不足]"])
    return "\n".join(lines) + "\n"

def build_top_signals(target_date: str, analysis_input: List[Dict[str, Any]]) -> str:
    positive_names = []
    risk_names = []
    valuation_names = []
    ranked = sorted(analysis_input, key=lambda entry: entry["structured_analysis"].get("signal_score", 0), reverse=True)
    for entry in analysis_input:
        analysis = entry["structured_analysis"]
        name = entry.get("stockName") or entry.get("industryName") or "未知标的"
        if analysis["positive_signals"]:
            positive_names.append(f"- `{name}`（score={analysis.get('signal_score', 0)}）：{'；'.join(analysis['positive_signals'])}")
        if analysis["risks"]:
            risk_names.append(f"- `{name}`：{'；'.join(analysis['risks'])}")
        if analysis["valuation_and_rating"]:
            valuation_names.append(f"- `{name}`：{'；'.join(analysis['valuation_and_rating'])}")

    lines = [f"# TOP_SIGNALS（{target_date}）", "", "## 综合优先级", ""]
    lines.extend(
        [
            f"- `{(entry.get('stockName') or entry.get('industryName') or '未知标的')}`：score={entry['structured_analysis'].get('signal_score', 0)}，优先级={entry['structured_analysis'].get('priority_bucket', 'C')}"
            for entry in ranked[:10]
        ]
        if ranked
        else ["- [无样本]"]
    )
    lines.extend(["", "## 正向信号", ""])
    lines.extend(positive_names[:10] if positive_names else ["- [无明显集中正向信号]"])
    lines.extend(["", "## 估值 / 评级信号", ""])
    lines.extend(valuation_names[:10] if valuation_names else ["- [无显式估值/评级提取]"])
    lines.extend(["", "## 风险信号", ""])
    lines.extend(risk_names[:10] if risk_names else ["- [无显式风险提取]"])
    return "\n".join(lines) + "\n"

def build_sector_brief(target_date: str, analysis_input: List[Dict[str, Any]]) -> str:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for entry in analysis_input:
        industry = entry.get("industryName") or "未标注行业"
        grouped.setdefault(industry, []).append(entry)

    lines = [f"# SECTOR_BRIEF（{target_date}）", "", f"- 覆盖行业数：`{len(grouped)}`", ""]
    for industry, entries in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        lines.append(f"## {industry}")
        lines.append("")
        lines.append(f"- 篇数：`{len(entries)}`")
        positive = sum(1 for entry in entries if entry["structured_analysis"]["positive_signals"])
        negative = sum(1 for entry in entries if entry["structured_analysis"]["negative_signals"])
        lines.append(f"- 正向信号：`{positive}` | 负向信号：`{negative}`")
        lines.append("- 代表个股：")
        for entry in entries[:5]:
            name = entry.get("stockName") or entry.get("industryName") or "未知标的"
            lines.append(f"  - `{name}`：{entry['structured_analysis']['headline']}")
        valuation_tags = []
        for entry in entries:
            valuation_tags.extend(entry["structured_analysis"]["valuation_and_rating"])
        if valuation_tags:
            lines.append(f"- 估值/评级标签：{'；'.join(valuation_tags[:4])}")
        lines.append("")
    return "\n".join(lines) + "\n"

def build_theme_brief(target_date: str, analysis_input: List[Dict[str, Any]]) -> str:
    theme_keywords = {
        "业绩增长": r"增长|高增|加速|改善|修复|扭亏",
        "估值评级": r"PE|PB|EPS|目标价|评级|首次覆盖|维持评级",
        "风险提示": r"风险|承压|波动|竞争加剧|需求变动|不及预期",
        "景气/周期": r"价格上涨|景气|回暖|周期|供给|需求",
    }
    grouped: Dict[str, List[str]] = {key: [] for key in theme_keywords}
    for entry in analysis_input:
        joined = " ".join(entry.get("summary") or []) + " " + (entry.get("title") or "") + " " + " ".join(entry["structured_analysis"].get("theme_tags") or [])
        name = entry.get("stockName") or entry.get("industryName") or "未知标的"
        for theme, pattern in theme_keywords.items():
            if re.search(pattern, joined):
                grouped[theme].append(name)

    lines = [f"# THEME_BRIEF（{target_date}）", ""]
    for theme, names in grouped.items():
        unique_names = []
        seen = set()
        for name in names:
            if name not in seen:
                seen.add(name)
                unique_names.append(name)
        lines.append(f"## {theme}")
        lines.append("")
        if unique_names:
            lines.append(f"- 涉及标的数：`{len(unique_names)}`")
            lines.extend([f"- `{name}`" for name in unique_names[:10]])
        else:
            lines.append("- [无明显样本]")
        lines.append("")
    return "\n".join(lines) + "\n"

def build_trading_dashboard(target_date: str, analysis_input: List[Dict[str, Any]]) -> str:
    ranked = sorted(analysis_input, key=lambda entry: entry["structured_analysis"].get("signal_score", 0), reverse=True)
    high_priority = [entry for entry in ranked if entry["structured_analysis"].get("priority_bucket") in {"A", "B"}]
    risky = sorted(
        analysis_input,
        key=lambda entry: (len(entry["structured_analysis"].get("risks") or []), -entry["structured_analysis"].get("signal_score", 0)),
        reverse=True,
    )
    broker_counter: Dict[str, int] = {}
    industry_counter: Dict[str, int] = {}
    theme_counter: Dict[str, int] = {}
    for entry in analysis_input:
        broker = entry.get("orgName") or "未知机构"
        broker_counter[broker] = broker_counter.get(broker, 0) + 1
        industry = entry.get("industryName") or "未标注行业"
        industry_counter[industry] = industry_counter.get(industry, 0) + 1
        for tag in entry["structured_analysis"].get("theme_tags") or []:
            theme_counter[tag] = theme_counter.get(tag, 0) + 1
    active_brokers = sorted(broker_counter.items(), key=lambda item: item[1], reverse=True)[:5]
    hot_industries = sorted(industry_counter.items(), key=lambda item: item[1], reverse=True)[:5]
    hot_themes = sorted(theme_counter.items(), key=lambda item: item[1], reverse=True)[:6]

    lines = [f"# TRADING_DASHBOARD（{target_date}）", "", f"- 样本数：`{len(analysis_input)}`", f"- A/B 优先级样本：`{len(high_priority)}`", "", "## Headline", ""]
    lines.append(f"- 今日更值得先看的方向偏向：`{ranked[0]['structured_analysis'].get('headline', '无')}`" if ranked else "- [无样本]")
    lines.extend(["", "## Strongest Longs", ""])
    lines.extend(
        [
            f"- `{entry.get('stockName') or entry.get('industryName')}`：score={entry['structured_analysis'].get('signal_score', 0)}，{'；'.join(entry['structured_analysis'].get('trade_hint') or [])}"
            for entry in ranked[:5]
        ]
        if ranked
        else ["- [无样本]"]
    )
    lines.extend(["", "## Biggest Risks", ""])
    lines.extend(
        [
            f"- `{entry.get('stockName') or entry.get('industryName')}`：{'；'.join(entry['structured_analysis'].get('risks') or ['[无]'])}"
            for entry in risky[:5]
        ]
        if risky
        else ["- [无样本]"]
    )
    lines.extend(["", "## Rating / Forecast Changes", ""])
    change_lines = []
    for entry in ranked:
        fields = entry["structured_analysis"].get("valuation_fields") or {}
        parts = []
        if fields.get("rating_change"):
            parts.append(fields["rating_change"])
        if fields.get("target_price"):
            parts.append(f"目标价={'/'.join(fields['target_price'])}元")
        if fields.get("eps"):
            parts.append(f"EPS={'/'.join(fields['eps'])}元")
        if fields.get("pe"):
            parts.append(f"PE={'/'.join(fields['pe'])}倍")
        if parts:
            change_lines.append(f"- `{entry.get('stockName') or entry.get('industryName')}`：{'；'.join(parts)}")
    lines.extend(change_lines[:8] if change_lines else ["- [无显式变化提取]"])
    lines.extend(["", "## Sector Heat", ""])
    lines.extend([f"- `{name}`：{count} 篇" for name, count in hot_industries] if hot_industries else ["- [无样本]"])
    lines.extend(["", "## Theme Heat", ""])
    lines.extend([f"- `{name}`：命中 `{count}` 次" for name, count in hot_themes] if hot_themes else ["- [无明显主题]"])
    lines.extend(["", "## Active Brokers", ""])
    lines.extend([f"- `{name}`：覆盖 `{count}` 篇" for name, count in active_brokers] if active_brokers else ["- [无样本]"])
    return "\n".join(lines) + "\n"

def build_consensus_brief(target_date: str, analysis_input: List[Dict[str, Any]]) -> str:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for entry in analysis_input:
        key = entry.get("stockCode") or entry.get("stockName") or entry.get("industryName") or "未知标的"
        grouped.setdefault(key, []).append(entry)

    lines = [f"# CONSENSUS_BRIEF（{target_date}）", ""]
    repeated = [(key, entries) for key, entries in grouped.items() if len(entries) >= 2]
    if not repeated:
        lines.append("- [暂无同一标的多机构覆盖样本]")
        return "\n".join(lines) + "\n"

    for key, entries in sorted(repeated, key=lambda item: len(item[1]), reverse=True):
        name = entries[0].get("stockName") or entries[0].get("industryName") or key
        orgs = [entry.get("orgName") or "未知机构" for entry in entries]
        ratings = [entry.get("rating") for entry in entries if entry.get("rating")]
        target_prices = []
        eps_values = []
        scores = []
        for entry in entries:
            analysis = entry["structured_analysis"]
            fields = analysis.get("valuation_fields") or {}
            target_prices.extend(fields.get("target_price") or [])
            eps_values.extend(fields.get("eps") or [])
            scores.append(analysis.get("signal_score", 0))
        lines.append(f"## {name}")
        lines.append("")
        lines.append(f"- 覆盖机构：{'；'.join(orgs)}")
        lines.append(f"- 评级分布：{'；'.join(ratings) if ratings else '[无显式评级]'}")
        lines.append(f"- 目标价：{'；'.join(target_prices) if target_prices else '[无显式目标价]'}")
        lines.append(f"- EPS：{'；'.join(eps_values) if eps_values else '[无显式 EPS]'}")
        lines.append(f"- 平均信号分：`{round(sum(scores) / max(1, len(scores)), 1)}`")
        lines.append("")
    return "\n".join(lines) + "\n"
