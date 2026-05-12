"""HTML/PDF parsing and text-quality scoring."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from html import unescape
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - exercised in environments without optional deps installed
    BeautifulSoup = None  # type: ignore[assignment]

from .constants import PDF_URL_TEMPLATE, SUMMARY_SECTION_KEYS
from .utils import log_event, normalize_line


@dataclass(frozen=True)
class TextQuality:
    score: int
    chars: int
    chinese_ratio: float
    section_hits: int
    noise_ratio: float


def _clean_text(value: str) -> str:
    value = unescape(value).replace("\u3000", " ").replace("&nbsp;", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _paragraphs_from_block(block) -> list[str]:
    paragraphs: list[str] = []
    nodes = block.find_all(["p", "div", "section"], recursive=True)
    for node in nodes:
        text = _clean_text(node.get_text(" ", strip=True))
        if text and len(text) >= 2 and text not in paragraphs:
            paragraphs.append(text)
    if not paragraphs:
        text = _clean_text(block.get_text("\n", strip=True))
        paragraphs = [line for line in text.splitlines() if line.strip()]
    return paragraphs


def extract_report_text(html: str) -> str:
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        selectors = [
            ".report-infos .ctx-content",
            ".zw-content",
            ".ctx-content",
            "article",
            "body",
        ]
        for selector in selectors:
            block = soup.select_one(selector)
            if block:
                paragraphs = _paragraphs_from_block(block)
                cleaned = [line for line in paragraphs if not _looks_like_navigation(line)]
                if cleaned:
                    return "\n".join(cleaned).strip()

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
    cleaned = []
    for paragraph in paragraphs:
        text = re.sub(r"<[^>]+>", "", paragraph)
        text = _clean_text(text)
        if text:
            cleaned.append(text)
    return "\n".join(cleaned).strip()


def _looks_like_navigation(line: str) -> bool:
    if len(line) > 80:
        return False
    nav_terms = ("首页", "登录", "注册", "广告", "免责声明", "东方财富网")
    return sum(1 for term in nav_terms if term in line) >= 2


def text_quality(text: str) -> TextQuality:
    chars = len(text)
    if not text:
        return TextQuality(score=0, chars=0, chinese_ratio=0.0, section_hits=0, noise_ratio=1.0)

    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    chinese_ratio = chinese_chars / max(1, chars)
    section_hits = sum(1 for key, _ in SUMMARY_SECTION_KEYS if key in text)
    replacement_chars = text.count("\ufffd")
    odd_chars = len(re.findall(r"[^\w\s\u4e00-\u9fff，。；：！？、（）《》【】“”‘’%./+-]", text))
    noise_ratio = (replacement_chars + odd_chars) / max(1, chars)

    score = 0
    score += min(40, chars // 25)
    score += min(25, int(chinese_ratio * 35))
    score += min(20, section_hits * 5)
    score -= min(25, int(noise_ratio * 120))
    if section_hits >= 2:
        score += 5
    if chars >= 80:
        score += 10
    if chars >= 500:
        score += 5
    return TextQuality(
        score=max(0, min(100, score)),
        chars=chars,
        chinese_ratio=round(chinese_ratio, 4),
        section_hits=section_hits,
        noise_ratio=round(noise_ratio, 4),
    )


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


def is_heading(line: str) -> bool:
    line = normalize_line(line)
    if not line:
        return False
    heading_set = {name for _, name in SUMMARY_SECTION_KEYS}
    if line in heading_set:
        return True
    return len(line) <= 14 and not re.search(r"[。；;]", line)
