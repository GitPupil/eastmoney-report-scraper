import json
from pathlib import Path

from eastmoney_report_scraper.analysis import build_structured_analysis, extract_risk_items, extract_summary
from eastmoney_report_scraper.parser import extract_report_text, text_quality

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_stock_html_fixture_extracts_text_and_analysis():
    text = extract_report_text(read_fixture("stock_report.html"))
    quality = text_quality(text)
    summary = extract_summary(text)
    analysis = build_structured_analysis(
        {
            "stockName": "样本公司",
            "stockCode": "000001",
            "industryName": "计算机",
            "title": "业绩预告增长，维持买入评级",
            "emRatingName": "买入",
        },
        text,
        summary,
    )
    assert "净利润同比增长35%" in text
    assert quality.score >= 60
    assert summary
    assert "业绩增长" in analysis["theme_tags"]
    assert extract_risk_items(text, "计算机")


def test_industry_html_fixture_extracts_stable_text():
    text = extract_report_text(read_fixture("industry_report.html"))
    quality = text_quality(text)
    assert "人工智能行业" in text
    assert "资本开支不及预期" in text
    assert quality.section_hits >= 2
    assert quality.score >= 45


def test_weak_and_malformed_html_fixtures_do_not_crash():
    weak_text = extract_report_text(read_fixture("weak_html.html"))
    malformed_text = extract_report_text(read_fixture("malformed_page.html"))
    assert text_quality(weak_text).score < 40
    assert "页面结构异常" in malformed_text


def test_pdf_text_fixture_enters_summary_and_scoring_flow():
    text = read_fixture("pdf_text_sample.txt")
    summary = extract_summary(text)
    analysis = build_structured_analysis(
        {"stockName": "PDF样本", "industryName": "制造", "title": "首次覆盖并给予买入评级", "emRatingName": "买入"},
        text,
        summary,
    )
    assert summary
    assert analysis["signal_score"] >= 50
    assert json.dumps(analysis["score_breakdown"], ensure_ascii=False)
