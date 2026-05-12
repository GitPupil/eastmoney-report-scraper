"""Rule-based report summary and structured analysis."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from .constants import SUMMARY_SECTION_KEYS
from .parser import is_heading
from .scoring import score_report
from .utils import normalize_line


def split_sentences(text: str) -> List[str]:
    raw_parts = re.split(r"(?<=[。！？；;])\s*", text.replace("\n", " "))
    return [normalize_line(part) for part in raw_parts if normalize_line(part)]


def extract_sections(text: str) -> Dict[str, List[str]]:
    lines = [normalize_line(line) for line in text.splitlines() if normalize_line(line)]
    sections: Dict[str, List[str]] = {}
    current = "正文"
    sections[current] = []
    heading_set = {name for _, name in SUMMARY_SECTION_KEYS}
    for line in lines:
        if line in heading_set:
            current = line
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def extract_risk_items(text: str, industry_name: str = "") -> List[str]:
    sections = extract_sections(text)
    risk_lines: List[str] = []
    for key in ("风险提示", "投资建议", "核心观点", "盈利预测与投资建议"):
        if key in sections:
            for line in sections[key][:6]:
                if "风险" in line or key == "风险提示":
                    risk_lines.append(line)

    joined = " ".join(risk_lines)
    candidates = re.split(r"[；;。]", joined)
    cleaned: List[str] = []
    industry_hint = (industry_name or "").lower()
    banned_by_industry = []
    if industry_hint and all(term not in industry_hint for term in ("医", "药", "医疗")):
        banned_by_industry.extend(["创新药", "临床", "集采"])
    for candidate in candidates:
        item = normalize_line(candidate)
        if not item:
            continue
        item = re.sub(r"^(风险提示|投资风险|特别风险提示)[：:]?", "", item).strip()
        item = re.sub(r"^(包括|主要包括|需关注|关注)", "", item).strip(" ，,")
        if len(item) < 4:
            continue
        if item in {"[无]", "无", "暂无"}:
            continue
        if any(bad in item for bad in banned_by_industry):
            continue
        if item not in cleaned:
            cleaned.append(item)
    return cleaned[:5]


def extract_financial_signals(text: str, summary: List[str]) -> Dict[str, str]:
    joined = " ".join(summary) + " " + text.replace("\n", " ")
    signal_map = {
        "revenue": [(r"营收[^。]{0,20}(增长|提升|高增)", "收入增长"), (r"营收[^。]{0,20}(下降|下滑)", "收入承压")],
        "profit": [(r"净利润[^。]{0,20}(增长|提升|高增|扭亏|超预期)", "利润改善"), (r"净利润[^。]{0,20}(下降|下滑|亏损|承压)", "利润承压")],
        "margin": [(r"毛利率[^。]{0,20}(提升|改善)", "毛利率改善"), (r"毛利率[^。]{0,20}(下降|承压)", "毛利率承压")],
        "demand": [(r"放量|景气|回暖|提价|修复|加速", "景气/需求改善"), (r"竞争加剧|需求不及预期|产能过剩", "需求或竞争压力")],
    }
    signals: Dict[str, str] = {}
    for key, patterns in signal_map.items():
        for pattern, label in patterns:
            if re.search(pattern, joined):
                signals[key] = label
                break
    return signals


def build_headline(item: Dict[str, Any], text: str, summary: List[str], financial_signals: Dict[str, str]) -> str:
    stock_name = item.get("stockName") or item.get("industryName") or "该标的"
    if summary:
        lead = re.sub(r"^(事件|投资要点|核心观点|盈利预测与投资建议|投资建议|风险提示)[：:]?", "", summary[0]).strip()
        if len(lead) <= 90 and "风险提示" not in summary[0]:
            return lead
    signal_parts = []
    for key in ("revenue", "profit", "margin", "demand"):
        if key in financial_signals:
            signal_parts.append(financial_signals[key])
    if signal_parts:
        return f"{stock_name}：{'，'.join(signal_parts[:3])}"
    sentences = split_sentences(text)
    return sentences[0][:90] if sentences else "[无有效结论]"


def extract_core_drivers(summary: List[str], text: str) -> List[str]:
    drivers: List[str] = []
    for bullet in summary:
        if bullet.startswith("风险提示："):
            continue
        cleaned = re.sub(r"^(事件|投资要点|核心观点|盈利预测与投资建议|投资建议)[：:]?", "", bullet).strip()
        if cleaned and cleaned not in drivers:
            drivers.append(cleaned)
    sections = extract_sections(text)
    for key in ("投资要点", "核心观点", "盈利预测与投资建议", "投资建议"):
        for line in sections.get(key, []):
            if "风险" in line:
                continue
            if line and line not in drivers:
                drivers.append(line)
            if len(drivers) >= 3:
                break
        if len(drivers) >= 3:
            break
    return drivers[:3]


def extract_numeric_series(text: str, label: str, unit: str) -> List[str]:
    patterns = [
        rf"{label}[为：:]?\s*([0-9\.]+(?:/[0-9\.]+){{0,4}}){unit}",
        rf"{label}[^\n。；;]*?分别为\s*([0-9\.]+(?:/[0-9\.]+){{0,4}}){unit}",
        rf"对应{label}[^\n。；;]*?([0-9\.]+(?:/[0-9\.]+){{0,4}}){unit}",
    ]
    values: List[str] = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if match not in values:
                values.append(match)
    return values[:2]


def extract_valuation_fields(text: str, rating: str) -> Dict[str, Any]:
    pe_match = extract_numeric_series(text, "PE", "倍")
    pb_match = extract_numeric_series(text, "PB", "倍")
    eps_match = extract_numeric_series(text, "EPS", "元")
    target_price_match = re.findall(r"目标价[为：:]?\s*([0-9\.]+)元", text)
    rating_change = ""
    if re.search(r"首次覆盖", text):
        rating_change = "首次覆盖"
    elif re.search(r"维持[“\"]?(买入|增持|中性|减持|卖出)[”\"]?评级", text):
        rating_change = "维持评级"
    elif re.search(r"上调|下调", text):
        rating_change = "评级或预期存在调整"

    valuation = []
    if pe_match:
        valuation.append(f"PE：{'；'.join(pe_match)}倍")
    if pb_match:
        valuation.append(f"PB：{'；'.join(pb_match)}倍")
    if eps_match:
        valuation.append(f"EPS：{'；'.join(eps_match)}元")
    if target_price_match:
        valuation.append(f"目标价：{'；'.join(target_price_match[:2])}元")
    if rating:
        valuation.append(f"评级：{rating}")
    if rating_change:
        valuation.append(rating_change)

    return {
        "valuation": valuation,
        "pe": pe_match,
        "pb": pb_match,
        "eps": eps_match,
        "target_price": target_price_match[:2],
        "rating_change": rating_change,
    }


def infer_theme_tags(title: str, text: str, summary: List[str]) -> List[str]:
    joined = f"{title} {' '.join(summary)} {text.replace(chr(10), ' ')}"
    theme_patterns = {
        "业绩增长": r"增长|高增|超预期|扭亏",
        "利润修复": r"修复|改善|减亏",
        "景气改善": r"景气|回暖|提价|放量",
        "首次覆盖": r"首次覆盖",
        "评级信号": r"买入|增持|维持评级|目标价|PE|EPS",
        "风险提示": r"风险|承压|不及预期|竞争加剧",
    }
    tags = [name for name, pattern in theme_patterns.items() if re.search(pattern, joined)]
    return tags[:6]


def format_trade_hint_from_signals(financial_signals: Dict[str, str], valuation_fields: Dict[str, Any], risks: List[str]) -> List[str]:
    hints: List[str] = []
    if financial_signals.get("profit") == "利润改善":
        hints.append("利润端改善较明确，若估值未充分反映，短线更容易形成正向反馈")
    elif financial_signals.get("profit") == "利润承压":
        hints.append("利润端仍承压，更适合等待后续盈利验证，而不是只看收入或题材")
    if financial_signals.get("revenue") == "收入增长" and financial_signals.get("profit") == "利润改善":
        hints.append("收入和利润方向一致，属于更标准的基本面改善型线索")
    elif financial_signals.get("revenue") == "收入承压" and financial_signals.get("profit") == "利润改善":
        hints.append("收入承压但利润改善，需重点判断改善是否来自结构优化或费用控制")
    if valuation_fields.get("target_price") or valuation_fields.get("eps") or valuation_fields.get("pe"):
        hints.append("卖方已给出明确估值/盈利预测，可直接对照市场预期判断赔率")
    if len(risks) >= 3:
        hints.append("风险项较多，交易上更适合轻仓跟踪而非激进追价")
    if not hints:
        hints.append("建议结合后续业绩兑现和同业比较再决定交易优先级")
    return hints[:3]


def extract_summary(text: str, max_bullets: int = 5) -> List[str]:
    lines = [normalize_line(line) for line in text.splitlines() if normalize_line(line)]
    if not lines:
        return []

    summary: List[str] = []
    used = set()
    for key, label in SUMMARY_SECTION_KEYS:
        for idx, line in enumerate(lines):
            if line == key:
                for candidate in lines[idx + 1 : idx + 4]:
                    if candidate and not is_heading(candidate):
                        bullet = f"{label}：{candidate}"
                        if bullet not in used:
                            summary.append(bullet)
                            used.add(bullet)
                        break
                break

    if not summary:
        for line in lines[:max_bullets]:
            if not is_heading(line):
                summary.append(line)

    compacted: List[str] = []
    for bullet in summary:
        bullet = bullet[:220] + "…" if len(bullet) > 220 else bullet
        if bullet not in compacted:
            compacted.append(bullet)
        if len(compacted) >= max_bullets:
            break
    return compacted


def build_structured_analysis(item: Dict[str, Any], text: str, summary: List[str]) -> Dict[str, Any]:
    joined_summary = " ".join(summary)
    joined_text = text.replace("\n", " ")
    rating = item.get("emRatingName") or item.get("sRatingName") or ""
    title = item.get("title") or ""

    financial_signals = extract_financial_signals(text, summary)
    statement = build_headline(item, text, summary, financial_signals)
    drivers = extract_core_drivers(summary, text)
    if not drivers and statement:
        drivers = [statement]

    positives: List[str] = []
    negatives: List[str] = []
    for label in financial_signals.values():
        if "增长" in label or "改善" in label or "修复" in label:
            positives.append(label)
        if "承压" in label or "压力" in label:
            negatives.append(label)

    if not positives and re.search(r"增长|改善|提升|加速|修复|超预期|高增|扭亏|回暖", joined_summary):
        positives.append("盈利/经营趋势偏积极")
    if not negatives and re.search(r"承压|下滑|下降|回落|亏损|疲弱", joined_summary):
        negatives.append("短期经营或景气存在压力")

    valuation_fields = extract_valuation_fields(joined_text, rating)
    valuation = valuation_fields["valuation"]

    risks = extract_risk_items(text, item.get("industryName") or item.get("indvInduName") or "")
    if not risks and re.search(r"地缘政治|价格波动|不及预期|竞争加剧|政策变化", joined_text):
        risks = ["需关注外部与经营风险"]

    trade_hint = format_trade_hint_from_signals(financial_signals, valuation_fields, risks)
    if negatives and all("利润端仍承压" not in hint and "收入承压" not in hint for hint in trade_hint):
        trade_hint.append("需要区分是短期承压还是中期逻辑改善，避免只看标题追涨")
    trade_hint = trade_hint[:3]

    theme_tags = infer_theme_tags(title, text, summary)
    score, priority_bucket, score_reasons, score_breakdown = score_report(
        {
            "positive_signals": positives,
            "negative_signals": negatives,
            "valuation_and_rating": valuation,
            "valuation_fields": valuation_fields,
            "risks": risks,
            "theme_tags": theme_tags,
            "financial_signals": financial_signals,
        }
    )

    return {
        "headline": statement,
        "core_drivers": drivers[:3],
        "positive_signals": positives,
        "negative_signals": negatives,
        "valuation_and_rating": valuation,
        "valuation_fields": valuation_fields,
        "trade_hint": trade_hint,
        "risks": risks or ["需结合原文风险提示进一步确认"],
        "title_signal": title,
        "financial_signals": financial_signals,
        "theme_tags": theme_tags,
        "signal_score": score,
        "priority_bucket": priority_bucket,
        "score_reasons": score_reasons,
        "score_breakdown": score_breakdown,
    }

