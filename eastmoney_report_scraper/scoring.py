"""Signal scoring and priority bucketing."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def score_report(analysis: Dict[str, Any]) -> Tuple[int, str, List[str], Dict[str, int]]:
    score = 50
    reasons: List[str] = []
    breakdown: Dict[str, int] = {"base": 50}

    positive_count = len(analysis.get("positive_signals") or [])
    negative_count = len(analysis.get("negative_signals") or [])
    if positive_count:
        delta = min(positive_count * 8, 20)
        score += delta
        breakdown["positive_signals"] = delta
        reasons.append("存在正向经营/景气信号")
    if negative_count:
        delta = -min(negative_count * 6, 18)
        score += delta
        breakdown["negative_signals"] = delta
        reasons.append("存在负向经营/景气信号")

    financial_signals = analysis.get("financial_signals") or {}
    if financial_signals.get("profit") == "利润承压":
        score -= 8
        breakdown["profit_pressure"] = -8
        reasons.append("利润端仍承压")
    elif financial_signals.get("profit") == "利润改善":
        score += 6
        breakdown["profit_improvement"] = 6
        reasons.append("利润改善较明确")

    if financial_signals.get("revenue") == "收入承压":
        score -= 4
        breakdown["revenue_pressure"] = -4
        reasons.append("收入端承压")
    elif financial_signals.get("revenue") == "收入增长":
        score += 4
        breakdown["revenue_growth"] = 4
        reasons.append("收入保持增长")

    valuation_text = "；".join(analysis.get("valuation_and_rating") or [])
    valuation_fields = analysis.get("valuation_fields") or {}
    if "评级：买入" in valuation_text:
        score += 8
        breakdown["buy_rating"] = 8
        reasons.append("卖方评级积极")
    elif "评级：增持" in valuation_text:
        score += 4
        breakdown["outperform_rating"] = 4
        reasons.append("卖方评级偏积极")

    if valuation_fields.get("target_price") or valuation_fields.get("eps"):
        score += 4
        breakdown["valuation_anchor"] = 4
        reasons.append("存在明确估值/盈利预测锚")
    if valuation_fields.get("rating_change") == "首次覆盖":
        score += 3
        breakdown["first_coverage"] = 3
        reasons.append("存在首次覆盖催化")

    if any(tag in (analysis.get("theme_tags") or []) for tag in ("业绩增长", "利润修复", "景气改善")):
        score += 6
        breakdown["tradable_theme"] = 6
        reasons.append("具备可交易主题标签")

    risk_count = len(analysis.get("risks") or [])
    if risk_count >= 3:
        score -= 6
        breakdown["many_risks"] = -6
        reasons.append("风险提示较多")
    if financial_signals.get("profit") == "利润承压" and risk_count >= 2:
        score -= 4
        breakdown["profit_risk_overlap"] = -4
        reasons.append("利润与风险共振偏负面")

    score = max(0, min(100, score))
    if score >= 74:
        bucket = "A"
    elif score >= 62:
        bucket = "B"
    elif score >= 45:
        bucket = "C"
    else:
        bucket = "D"
    breakdown["final"] = score
    return score, bucket, reasons[:4], breakdown

