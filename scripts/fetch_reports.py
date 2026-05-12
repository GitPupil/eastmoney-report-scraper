#!/usr/bin/env python3
import argparse
import csv
import json
import math
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib import parse as urlparse
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError

LIST_API = "https://reportapi.eastmoney.com/report/list"
DETAIL_URL_TEMPLATE = "https://data.eastmoney.com/report/info/{info_code}.html"
PDF_URL_TEMPLATE = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
DEFAULT_OUTPUT_ROOT = Path.cwd() / "eastmoney_reports"
DEFAULT_INDEX_NAME = "report_index.csv"
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


@dataclass
class FetchResult:
    item: Dict[str, Any]
    status: str
    text: str
    summary: List[str]
    output_path: Optional[Path]
    source: str
    skipped: bool = False
    error: str = ""


@dataclass
class DayRun:
    date_str: str
    output_dir: Path
    raw_list: List[Dict[str, Any]]
    results: List[FetchResult]


def log_event(log_path: Path, level: str, message: str, **payload: Any) -> None:
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "level": level,
        "message": message,
        "payload": payload,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def http_get(url: str, timeout: int = 20) -> str:
    req = urlrequest.Request(url, headers={"User-Agent": USER_AGENT})
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_get_with_retry(url: str, timeout: int, retries: int, retry_delay: float, log_path: Path, label: str) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 2):
        try:
            return http_get(url, timeout=timeout)
        except (URLError, HTTPError, TimeoutError, ValueError) as exc:
            last_error = exc
            log_event(log_path, "warn", f"{label} failed", attempt=attempt, url=url, error=repr(exc))
            if attempt <= retries:
                time.sleep(retry_delay)
    raise RuntimeError(f"{label} failed after retries: {last_error!r}")


def build_list_url(target_date: str, page_no: int, page_size: int, qtype: int) -> str:
    params = {
        "industryCode": "*",
        "pageSize": str(page_size),
        "industry": "*",
        "rating": "*",
        "ratingChange": "*",
        "beginTime": target_date,
        "endTime": target_date,
        "pageNo": str(page_no),
        "fields": "",
        "qType": str(qtype),
        "orgCode": "",
        "rcode": "",
    }
    return f"{LIST_API}?{urlparse.urlencode(params)}"


def fetch_report_list(target_date: str, page_size: int, qtype: int, timeout: int, retries: int, retry_delay: float, log_path: Path) -> List[Dict[str, Any]]:
    first = json.loads(http_get_with_retry(build_list_url(target_date, 1, page_size, qtype), timeout, retries, retry_delay, log_path, "list_page_1"))
    hits = int(first.get("hits") or 0)
    data = list(first.get("data") or [])
    total_pages = max(1, math.ceil(hits / page_size))
    for page_no in range(2, total_pages + 1):
        page = json.loads(http_get_with_retry(build_list_url(target_date, page_no, page_size, qtype), timeout, retries, retry_delay, log_path, f"list_page_{page_no}"))
        data.extend(page.get("data") or [])
    return data


def extract_report_text(html: str) -> str:
    patterns = [
        r'<div class="report-infos">.*?<div class="ctx-content">(.*?)</div>\s*<div class="c-foot">',
        r'<div class="zw-content">(.*?)<div class="c-foot">',
    ]
    block = html
    for pattern in patterns:
        match = re.search(pattern, html, re.S | re.I)
        if match:
            block = match.group(1)
            break

    paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', block, re.S | re.I)
    cleaned: List[str] = []
    for paragraph in paragraphs:
        text = re.sub(r"<[^>]+>", "", paragraph)
        text = unescape(text).replace("\u3000", " ").replace("&nbsp;", " ")
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            cleaned.append(text)
    return "\n".join(cleaned).strip()


def extract_pdf_url(html: str, info_code: str) -> str:
    match = re.search(r'href="(https://pdf\.dfcfw\.com/pdf/[^"]+)"', html, re.I)
    if match:
        return match.group(1)
    return PDF_URL_TEMPLATE.format(info_code=info_code)


def extract_pdf_text(pdf_url: str, timeout: int, log_path: Path) -> str:
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", pdf_url, "-"],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return re.sub(r"\n{3,}", "\n\n", proc.stdout).strip()
    except FileNotFoundError:
        log_event(log_path, "warn", "pdftotext not found", pdf_url=pdf_url)
        return ""
    except subprocess.SubprocessError as exc:
        log_event(log_path, "warn", "pdftotext failed", pdf_url=pdf_url, error=repr(exc))
        return ""


def sanitize_filename(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]', "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:120] if len(value) > 120 else value


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" ：:；;，,")


def is_heading(line: str) -> bool:
    line = normalize_line(line)
    if not line:
        return False
    heading_set = {name for _, name in SUMMARY_SECTION_KEYS}
    if line in heading_set:
        return True
    return len(line) <= 14 and not re.search(r"[。；;]", line)


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
    for key in ("风险提示", "投资建议", "核心观点"):
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
        if len(item) < 4:
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
        if len(lead) <= 90:
            return lead
    signal_parts = []
    for key in ("revenue", "profit", "margin", "demand"):
        if key in financial_signals:
            signal_parts.append(financial_signals[key])
    if signal_parts:
        return f"{stock_name}：{'，'.join(signal_parts[:3])}"
    sentences = split_sentences(text)
    return sentences[0][:90] if sentences else "[无有效结论]"


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


def score_report(analysis: Dict[str, Any]) -> Tuple[int, str, List[str]]:
    score = 50
    reasons: List[str] = []
    positive_count = len(analysis.get("positive_signals") or [])
    negative_count = len(analysis.get("negative_signals") or [])
    if positive_count:
        score += min(positive_count * 8, 20)
        reasons.append("存在正向经营/景气信号")
    if negative_count:
        score -= min(negative_count * 6, 18)
        reasons.append("存在负向经营/景气信号")
    valuation_text = "；".join(analysis.get("valuation_and_rating") or [])
    if "评级：买入" in valuation_text:
        score += 8
        reasons.append("卖方评级积极")
    elif "评级：增持" in valuation_text:
        score += 4
        reasons.append("卖方评级偏积极")
    if any(tag in (analysis.get("theme_tags") or []) for tag in ("业绩增长", "利润修复", "景气改善")):
        score += 6
        reasons.append("具备可交易主题标签")
    if len(analysis.get("risks") or []) >= 3:
        score -= 4
        reasons.append("风险提示较多")
    score = max(0, min(100, score))
    if score >= 70:
        bucket = "A"
    elif score >= 58:
        bucket = "B"
    elif score >= 45:
        bucket = "C"
    else:
        bucket = "D"
    return score, bucket, reasons[:4]


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
    drivers = summary[1:3] if len(summary) > 1 else ([] if not summary else [statement])

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

    valuation = []
    pe_match = re.findall(r"PE[为：:]?\s*([0-9\.]+(?:/[0-9\.]+){0,3})倍", joined_text)
    pb_match = re.findall(r"PB[为：:]?\s*([0-9\.]+(?:/[0-9\.]+){0,3})倍", joined_text)
    eps_match = re.findall(r"EPS[为：:]?\s*([0-9\.]+(?:/[0-9\.]+){0,3})元", joined_text)
    aim_price_match = re.findall(r"目标价[为：:]?\s*([0-9\.]+)元", joined_text)
    rating_change = ""
    if re.search(r"首次覆盖", joined_text):
        rating_change = "首次覆盖"
    elif re.search(r"维持[“\"]?(买入|增持|中性|减持|卖出)[”\"]?评级", joined_text):
        rating_change = "维持评级"
    elif re.search(r"上调|下调", joined_text):
        rating_change = "评级或预期存在调整"

    if pe_match:
        valuation.append(f"PE：{'；'.join(pe_match[:2])}倍")
    if pb_match:
        valuation.append(f"PB：{'；'.join(pb_match[:2])}倍")
    if eps_match:
        valuation.append(f"EPS：{'；'.join(eps_match[:2])}元")
    if aim_price_match:
        valuation.append(f"目标价：{'；'.join(aim_price_match[:2])}元")
    if rating:
        valuation.append(f"评级：{rating}")
    if rating_change:
        valuation.append(rating_change)

    risks = extract_risk_items(text, item.get("industryName") or item.get("indvInduName") or "")
    if not risks and re.search(r"地缘政治|价格波动|不及预期|竞争加剧|政策变化", joined_text):
        risks = ["需关注外部与经营风险"]

    trade_hint = []
    if positives:
        trade_hint.append("如果市场风格偏业绩/景气验证，这篇研报更容易提供正向交易线索")
    if valuation:
        trade_hint.append("建议结合估值与评级表述判断卖方是否已在交易中期改善预期")
    if negatives:
        trade_hint.append("需要区分是短期承压还是中期逻辑改善，避免只看标题追涨")
    if not trade_hint:
        trade_hint.append("建议结合后续业绩兑现和同业比较再决定交易优先级")

    theme_tags = infer_theme_tags(title, text, summary)
    score, priority_bucket, score_reasons = score_report(
        {
            "positive_signals": positives,
            "negative_signals": negatives,
            "valuation_and_rating": valuation,
            "risks": risks,
            "theme_tags": theme_tags,
        }
    )

    return {
        "headline": statement,
        "core_drivers": drivers[:3],
        "positive_signals": positives,
        "negative_signals": negatives,
        "valuation_and_rating": valuation,
        "trade_hint": trade_hint,
        "risks": risks or ["需结合原文风险提示进一步确认"],
        "title_signal": title,
        "financial_signals": financial_signals,
        "theme_tags": theme_tags,
        "signal_score": score,
        "priority_bucket": priority_bucket,
        "score_reasons": score_reasons,
    }


def build_markdown(item: Dict[str, Any], text: str, summary: List[str], source: str) -> str:
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
    lines.extend([
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
        f"- 主题标签：{'；'.join(analysis['theme_tags']) if analysis['theme_tags'] else '[无]'}",
        "",
        "---",
        "",
        text or "[正文抽取为空]",
        "",
    ])
    return "\n".join(lines)


def daterange(start_date: date, end_date: date) -> List[str]:
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")
    days = (end_date - start_date).days
    return [(start_date + timedelta(days=offset)).isoformat() for offset in range(days + 1)]


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def resolve_dates(args: argparse.Namespace) -> List[str]:
    if args.date:
        return [args.date]
    if args.start_date and args.end_date:
        return daterange(parse_date(args.start_date), parse_date(args.end_date))
    raise ValueError("Provide either --date or both --start-date and --end-date")


def matches_filter(value: str, patterns: Sequence[str]) -> bool:
    if not patterns:
        return True
    haystack = (value or "").lower()
    return any(pattern.lower() in haystack for pattern in patterns)


def filter_items(items: List[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for item in items:
        stock_target = f"{item.get('stockName', '')} {item.get('stockCode', '')}"
        org_target = f"{item.get('orgSName', '')} {item.get('orgName', '')}"
        rating_target = f"{item.get('emRatingName', '')} {item.get('sRatingName', '')}"
        industry_target = f"{item.get('industryName', '')} {item.get('indvInduName', '')}"
        if not matches_filter(stock_target, args.stock_filters):
            continue
        if not matches_filter(org_target, args.org_filters):
            continue
        if not matches_filter(rating_target, args.rating_filters):
            continue
        if not matches_filter(industry_target, args.industry_filters):
            continue
        filtered.append(item)
    return filtered


def existing_markdown_map(output_dir: Path) -> Dict[str, Path]:
    mapping: Dict[str, Path] = {}
    for path in output_dir.glob("*.md"):
        if path.name in {"README.md", "SUMMARY.md", "ANALYSIS_INPUT.md", "RANGE_SUMMARY.md"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        match = re.search(r"- infoCode：`([^`]+)`", content)
        if match:
            mapping[match.group(1)] = path
    return mapping


def fetch_detail(item: Dict[str, Any], output_dir: Path, index: int, timeout: int, retries: int, retry_delay: float, log_path: Path, resume_map: Dict[str, Path], force: bool, use_pdf_fallback: bool) -> FetchResult:
    info_code = item.get("infoCode", "")
    detail_url = DETAIL_URL_TEMPLATE.format(info_code=info_code)

    if not force and info_code in resume_map:
        existing_path = resume_map[info_code]
        try:
            content = existing_path.read_text(encoding="utf-8")
            body = content.split("\n---\n", 1)[-1].strip() if "\n---\n" in content else content
            summary_block = ""
            match = re.search(r"## 自动摘要\n\n(.*?)\n\n---\n", content, re.S)
            if match:
                summary_block = match.group(1)
            summary_lines = [line[2:].strip() for line in summary_block.splitlines() if line.startswith("- ")]
            log_event(log_path, "info", "resume_skip", infoCode=info_code, file=str(existing_path))
            return FetchResult(item=item, status="ok", text=body, summary=summary_lines[:5], output_path=existing_path, source="resume", skipped=True)
        except Exception as exc:
            log_event(log_path, "warn", "resume_read_failed", infoCode=info_code, error=repr(exc))

    try:
        html = http_get_with_retry(detail_url, timeout, retries, retry_delay, log_path, f"detail_{info_code}")
        text = extract_report_text(html)
        source = "html"
        if len(text) < 80 and use_pdf_fallback:
            pdf_url = extract_pdf_url(html, info_code)
            pdf_text = extract_pdf_text(pdf_url, timeout, log_path)
            if len(pdf_text) > len(text):
                text = pdf_text
                source = "pdf"
                log_event(log_path, "info", "pdf_fallback_used", infoCode=info_code, pdf_url=pdf_url)
            else:
                log_event(log_path, "warn", "pdf_fallback_empty", infoCode=info_code, pdf_url=pdf_url)
        summary = extract_summary(text)
        status = "ok" if len(text) >= 80 else "weak"
        stock_label = item.get("stockName") or item.get("industryName") or "未知标的"
        file_name = f"{index:03d}——{sanitize_filename(stock_label)}——{sanitize_filename(item.get('title') or info_code)}.md"
        output_path = output_dir / file_name
        output_path.write_text(build_markdown(item, text, summary, source), encoding="utf-8")
        return FetchResult(item=item, status=status, text=text, summary=summary, output_path=output_path, source=source)
    except Exception as exc:  # noqa: BLE001
        log_event(log_path, "error", "detail_fetch_failed", infoCode=info_code, error=repr(exc), detailUrl=detail_url)
        return FetchResult(item=item, status="error", text="", summary=[], output_path=None, source="none", error=repr(exc))


def write_csv_index(output_dir: Path, results: List[FetchResult]) -> Path:
    index_path = output_dir / DEFAULT_INDEX_NAME
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "stockName",
                "stockCode",
                "industryName",
                "title",
                "orgName",
                "publishDate",
                "rating",
                "infoCode",
                "status",
                "source",
                "chars",
                "summary",
                "signalScore",
                "priorityBucket",
                "themeTags",
                "file",
            ],
        )
        writer.writeheader()
        for result in results:
            item = result.item
            structured = build_structured_analysis(item, result.text, result.summary)
            writer.writerow(
                {
                    "stockName": item.get("stockName") or "",
                    "stockCode": item.get("stockCode") or "",
                    "industryName": item.get("industryName") or item.get("indvInduName") or "",
                    "title": item.get("title") or "",
                    "orgName": item.get("orgSName") or item.get("orgName") or "",
                    "publishDate": item.get("publishDate") or "",
                    "rating": item.get("emRatingName") or item.get("sRatingName") or "",
                    "infoCode": item.get("infoCode") or "",
                    "status": result.status,
                    "source": result.source,
                    "chars": len(result.text),
                    "summary": " | ".join(result.summary),
                    "signalScore": structured.get("signal_score", ""),
                    "priorityBucket": structured.get("priority_bucket", ""),
                    "themeTags": " | ".join(structured.get("theme_tags", [])),
                    "file": result.output_path.name if result.output_path else "",
                }
            )
    return index_path


def write_xlsx_index(output_dir: Path, csv_index_path: Path, log_path: Path) -> Optional[Path]:
    xlsx_path = output_dir / "report_index.xlsx"
    try:
        import openpyxl
    except ImportError:
        log_event(log_path, "warn", "xlsx_export_skipped", reason="openpyxl not installed")
        return None

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    with csv_index_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            sheet.append(row)
    workbook.save(xlsx_path)
    return xlsx_path


def write_day_summary(output_dir: Path, target_date: str, qtype: int, raw_list: List[Dict[str, Any]], results: Iterable[FetchResult], log_path: Path) -> None:
    results = list(results)
    (output_dir / "report_list.json").write_text(json.dumps(raw_list, ensure_ascii=False, indent=2), encoding="utf-8")

    qtype_name = "个股研报" if qtype == 0 else "行业研报"
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
        "| 序号 | 标的 | 标题 | 机构 | 状态 | 来源 | 字符数 | 摘要 | 文件 |",
        "|---|---|---|---|---|---|---:|---|---|",
    ]
    for idx, result in enumerate(results, 1):
        item = result.item
        stock_label = item.get("stockName") or item.get("industryName") or "-"
        file_name = result.output_path.name if result.output_path else "-"
        summary_text = "；".join(result.summary[:2]) if result.summary else "-"
        lines.append(
            "| {idx} | {stock} | {title} | {org} | {status} | {source} | {chars} | {summary} | {file} |".format(
                idx=idx,
                stock=stock_label.replace("|", "/"),
                title=(item.get("title") or "-").replace("|", "/"),
                org=(item.get("orgSName") or item.get("orgName") or "-").replace("|", "/"),
                status=result.status,
                source=result.source,
                chars=len(result.text),
                summary=summary_text.replace("|", "/"),
                file=file_name.replace("|", "/"),
            )
        )
        if result.error:
            lines.append(f"\n> error[{idx}]: `{result.error}`")
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

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

        structured_analysis = build_structured_analysis(item, result.text, result.summary)
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
        analysis_prompt_lines.append(f"## {entry['index']:03d}. {name}｜{entry.get('title') or ''}")
        analysis_prompt_lines.append("")
        analysis_prompt_lines.append(f"- 机构：`{entry.get('orgName') or ''}`")
        analysis_prompt_lines.append(f"- 日期：`{entry.get('publishDate') or ''}`")
        analysis_prompt_lines.append(f"- 评级：`{entry.get('rating') or ''}`")
        analysis_prompt_lines.append(f"- 状态：`{entry.get('status') or ''}` | 来源：`{entry.get('source') or ''}`")
        analysis_prompt_lines.append(f"- 文件：`{entry.get('file') or ''}`")
        analysis_prompt_lines.append("- 摘要：")
        if entry["summary"]:
            analysis_prompt_lines.extend([f"  - {bullet}" for bullet in entry["summary"]])
        else:
            analysis_prompt_lines.append("  - [未提取到有效摘要]")
        analysis_prompt_lines.append("- 结构化分析：")
        analysis_prompt_lines.append(f"  - 一句话结论：{entry['structured_analysis']['headline']}")
        analysis_prompt_lines.append(f"  - 核心驱动：{'；'.join(entry['structured_analysis']['core_drivers']) if entry['structured_analysis']['core_drivers'] else '[无]'}")
        analysis_prompt_lines.append(f"  - 正向信号：{'；'.join(entry['structured_analysis']['positive_signals']) if entry['structured_analysis']['positive_signals'] else '[无]'}")
        analysis_prompt_lines.append(f"  - 负向信号：{'；'.join(entry['structured_analysis']['negative_signals']) if entry['structured_analysis']['negative_signals'] else '[无]'}")
        analysis_prompt_lines.append(f"  - 估值/评级：{'；'.join(entry['structured_analysis']['valuation_and_rating']) if entry['structured_analysis']['valuation_and_rating'] else '[无]'}")
        analysis_prompt_lines.append(f"  - 交易含义：{'；'.join(entry['structured_analysis']['trade_hint']) if entry['structured_analysis']['trade_hint'] else '[无]'}")
        analysis_prompt_lines.append(f"  - 风险：{'；'.join(entry['structured_analysis']['risks']) if entry['structured_analysis']['risks'] else '[无]'}")
        analysis_prompt_lines.append(f"  - 信号评分：{entry['structured_analysis'].get('signal_score', '[无]')} / 100（优先级：{entry['structured_analysis'].get('priority_bucket', '[无]')}）")
        analysis_prompt_lines.append(f"  - 主题标签：{'；'.join(entry['structured_analysis'].get('theme_tags', [])) if entry['structured_analysis'].get('theme_tags') else '[无]'}")
        analysis_prompt_lines.append("")
    (output_dir / "ANALYSIS_INPUT.md").write_text("\n".join(analysis_prompt_lines), encoding="utf-8")

    daily_brief = build_daily_brief(target_date, analysis_input)
    (output_dir / "DAILY_BRIEF.md").write_text(daily_brief, encoding="utf-8")
    top_signals = build_top_signals(target_date, analysis_input)
    (output_dir / "TOP_SIGNALS.md").write_text(top_signals, encoding="utf-8")
    sector_brief = build_sector_brief(target_date, analysis_input)
    (output_dir / "SECTOR_BRIEF.md").write_text(sector_brief, encoding="utf-8")
    theme_brief = build_theme_brief(target_date, analysis_input)
    (output_dir / "THEME_BRIEF.md").write_text(theme_brief, encoding="utf-8")

    csv_index_path = write_csv_index(output_dir, results)
    write_xlsx_index(output_dir, csv_index_path, log_path)


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
    if top_industries:
        lines.extend([f"- `{name}`：出现 `{count}` 次" for name, count in top_industries])
    else:
        lines.append("- [样本不足]")

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

    lines = [
        f"# TOP_SIGNALS（{target_date}）",
        "",
        "## 综合优先级",
        "",
    ]
    lines.extend([
        f"- `{(entry.get('stockName') or entry.get('industryName') or '未知标的')}`：score={entry['structured_analysis'].get('signal_score', 0)}，优先级={entry['structured_analysis'].get('priority_bucket', 'C')}"
        for entry in ranked[:10]
    ] if ranked else ["- [无样本]"])
    lines.extend([
        "",
        "## 正向信号",
        "",
    ])
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

    lines = [
        f"# SECTOR_BRIEF（{target_date}）",
        "",
        f"- 覆盖行业数：`{len(grouped)}`",
        "",
    ]

    for industry, entries in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        lines.append(f"## {industry}")
        lines.append("")
        lines.append(f"- 篇数：`{len(entries)}`")
        positive = sum(1 for entry in entries if entry['structured_analysis']['positive_signals'])
        negative = sum(1 for entry in entries if entry['structured_analysis']['negative_signals'])
        lines.append(f"- 正向信号：`{positive}` | 负向信号：`{negative}`")
        lines.append("- 代表个股：")
        for entry in entries[:5]:
            name = entry.get("stockName") or entry.get("industryName") or "未知标的"
            lines.append(f"  - `{name}`：{entry['structured_analysis']['headline']}")
        valuation_tags = []
        for entry in entries:
            valuation_tags.extend(entry['structured_analysis']['valuation_and_rating'])
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

    lines = [
        f"# THEME_BRIEF（{target_date}）",
        "",
    ]
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


def write_range_summary(root_dir: Path, day_runs: List[DayRun], qtype: int) -> None:
    if len(day_runs) <= 1:
        return
    qtype_name = "个股研报" if qtype == 0 else "行业研报"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch scrape Eastmoney research reports by date or date range.")
    parser.add_argument("--date", help="Single date in YYYY-MM-DD")
    parser.add_argument("--start-date", help="Start date in YYYY-MM-DD")
    parser.add_argument("--end-date", help="End date in YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=None, help="Only fetch first N reports for each date")
    parser.add_argument("--qtype", type=int, default=0, choices=[0, 1], help="0=stock reports, 1=industry reports")
    parser.add_argument("--page-size", type=int, default=100, help="List API page size")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay seconds between detail requests")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=int, default=2, help="Retry times for list/detail fetch")
    parser.add_argument("--retry-delay", type=float, default=1.0, help="Retry delay seconds")
    parser.add_argument("--output-dir", default=None, help="Output root directory")
    parser.add_argument("--stock", action="append", dest="stock_filters", default=[], help="Filter by stock code or name, repeatable")
    parser.add_argument("--org", action="append", dest="org_filters", default=[], help="Filter by broker / organization, repeatable")
    parser.add_argument("--rating", action="append", dest="rating_filters", default=[], help="Filter by rating keyword, repeatable")
    parser.add_argument("--industry", action="append", dest="industry_filters", default=[], help="Filter by industry keyword, repeatable")
    parser.add_argument("--force", action="store_true", help="Force re-fetch even if markdown already exists")
    parser.add_argument("--no-pdf-fallback", action="store_true", help="Disable PDF fallback when HTML text is weak")
    parser.add_argument("--no-xlsx", action="store_true", help="Skip xlsx export")
    return parser.parse_args()


def make_root_dir(output_root: Path, date_values: List[str]) -> Path:
    if len(date_values) == 1:
        return output_root / f"研报_{date_values[0]}"
    return output_root / f"研报_{date_values[0]}_to_{date_values[-1]}"


def run_for_date(target_date: str, root_dir: Path, args: argparse.Namespace) -> DayRun:
    output_dir = root_dir if args.date else root_dir / f"研报_{target_date}"
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run.log.jsonl"
    raw_list = fetch_report_list(target_date, args.page_size, args.qtype, args.timeout, args.retries, args.retry_delay, log_path)
    filtered_list = filter_items(raw_list, args)
    items = filtered_list[: args.limit] if args.limit else filtered_list
    resume_map = existing_markdown_map(output_dir)

    log_event(log_path, "info", "day_start", date=target_date, raw=len(raw_list), filtered=len(filtered_list), selected=len(items))

    results: List[FetchResult] = []
    for idx, item in enumerate(items, 1):
        result = fetch_detail(
            item=item,
            output_dir=output_dir,
            index=idx,
            timeout=args.timeout,
            retries=args.retries,
            retry_delay=args.retry_delay,
            log_path=log_path,
            resume_map=resume_map,
            force=args.force,
            use_pdf_fallback=not args.no_pdf_fallback,
        )
        results.append(result)
        print(
            json.dumps(
                {
                    "date": target_date,
                    "idx": idx,
                    "stockName": item.get("stockName") or item.get("industryName"),
                    "title": item.get("title"),
                    "infoCode": item.get("infoCode"),
                    "status": result.status,
                    "source": result.source,
                    "skipped": result.skipped,
                    "chars": len(result.text),
                    "summary": result.summary[:2],
                    "file": str(result.output_path) if result.output_path else None,
                    "error": result.error,
                },
                ensure_ascii=False,
            )
        )
        if idx < len(items):
            time.sleep(max(0.0, args.delay))

    write_day_summary(output_dir, target_date, args.qtype, filtered_list, results, log_path)
    if args.no_xlsx:
        xlsx_path = output_dir / "report_index.xlsx"
        if xlsx_path.exists():
            xlsx_path.unlink()
    log_event(log_path, "info", "day_complete", date=target_date, selected=len(items), ok=sum(r.status == 'ok' for r in results), weak=sum(r.status == 'weak' for r in results), error=sum(r.status == 'error' for r in results))
    return DayRun(date_str=target_date, output_dir=output_dir, raw_list=filtered_list, results=results)


def main() -> None:
    args = parse_args()
    date_values = resolve_dates(args)
    output_root = Path(args.output_dir).expanduser() if args.output_dir else DEFAULT_OUTPUT_ROOT
    root_dir = make_root_dir(output_root, date_values)
    root_dir.mkdir(parents=True, exist_ok=True)

    day_runs: List[DayRun] = []
    for target_date in date_values:
        day_runs.append(run_for_date(target_date, root_dir, args))

    write_range_summary(root_dir, day_runs, args.qtype)

    print(
        json.dumps(
            {
                "root_dir": str(root_dir),
                "dates": date_values,
                "days": len(day_runs),
                "list_count": sum(len(run.raw_list) for run in day_runs),
                "fetched": sum(len(run.results) for run in day_runs),
                "ok": sum(sum(r.status == "ok" for r in run.results) for run in day_runs),
                "weak": sum(sum(r.status == "weak" for r in run.results) for run in day_runs),
                "error": sum(sum(r.status == "error" for r in run.results) for run in day_runs),
                "range_summary": str(root_dir / "RANGE_SUMMARY.md") if len(day_runs) > 1 else None,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
