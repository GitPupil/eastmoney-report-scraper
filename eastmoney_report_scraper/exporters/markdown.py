"""Single-report markdown rendering."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from ..analysis import build_structured_analysis
from ..constants import DETAIL_URL_TEMPLATE

def build_markdown(item: Dict[str, Any], text: str, summary: List[str], source: str, quality_score: int = 0) -> str:
    info_code = item.get("infoCode", "")
    detail_url = DETAIL_URL_TEMPLATE.format(info_code=info_code)
    analysis = build_structured_analysis(item, text, summary)
    lines = [
        f"# {item.get('title', '')}",
        "",
        f"- 股票名称：`{item.get('stockName', '')}`",
        f"- 股票代码：`{item.get('stockCode', '')}`",
        f"- 行业：`{item.get('industryName') or item.get('indvInduName') or ''}`",
        f"- 机构：`{item.get('orgSName') or item.get('orgName') or ''}`",
        f"- 日期：`{item.get('publishDate', '')}`",
        f"- 评级：`{item.get('emRatingName') or item.get('sRatingName') or ''}`",
        f"- 来源：`{source}`",
        f"- 文本质量：`{quality_score}`",
        f"- infoCode：`{info_code}`",
        f"- 链接：`{detail_url}`",
        "",
        "## 自动摘要",
        "",
    ]
    if summary:
        lines.extend([f"- {bullet}" for bullet in summary])
    else:
        lines.append("- [未提取到有效摘要]")
    lines.extend(
        [
            "",
            "## 结构化分析",
            "",
            f"- 一句话结论：{analysis['headline']}",
            f"- 核心驱动：{'；'.join(analysis['core_drivers']) if analysis['core_drivers'] else '[无]'}",
            f"- 正向信号：{'；'.join(analysis['positive_signals']) if analysis['positive_signals'] else '[无明显正向标签]'}",
            f"- 负向信号：{'；'.join(analysis['negative_signals']) if analysis['negative_signals'] else '[无明显负向标签]'}",
            f"- 估值/评级：{'；'.join(analysis['valuation_and_rating']) if analysis['valuation_and_rating'] else '[原文未显式提取]'}",
            f"- 交易含义：{'；'.join(analysis['trade_hint']) if analysis['trade_hint'] else '[无]'}",
            f"- 风险：{'；'.join(analysis['risks']) if analysis['risks'] else '[无]'}",
            f"- 信号评分：`{analysis['signal_score']}` / `100`（优先级：`{analysis['priority_bucket']}`）",
            f"- 评分原因：{'；'.join(analysis['score_reasons']) if analysis['score_reasons'] else '[无]'}",
            f"- 评分拆解：`{json.dumps(analysis['score_breakdown'], ensure_ascii=False)}`",
            f"- 主题标签：{'；'.join(analysis['theme_tags']) if analysis['theme_tags'] else '[无]'}",
            "",
            "---",
            "",
            text or "[正文抽取为空]",
            "",
        ]
    )
    return "\n".join(lines)
