import argparse
import csv
import json
from pathlib import Path

from eastmoney_report_scraper.analysis import (
    build_structured_analysis,
    extract_risk_items,
    extract_summary,
    extract_valuation_fields,
)
from eastmoney_report_scraper.client import build_list_url
from eastmoney_report_scraper.cli import (
    append_manifest_entry,
    daterange,
    existing_markdown_map,
    fetch_detail,
    filter_items,
    parse_date,
    read_manifest,
    select_resume_error_items,
)
from eastmoney_report_scraper.exporters import build_markdown, write_csv_index, write_day_summary
from eastmoney_report_scraper.models import FetchResult
from eastmoney_report_scraper.parser import extract_report_text, text_quality
from eastmoney_report_scraper.scoring import score_report
from eastmoney_report_scraper.utils import sanitize_filename


SAMPLE_ITEM = {
    "stockName": "样本股份",
    "stockCode": "000001",
    "industryName": "计算机",
    "title": "业绩增长超预期，维持买入评级",
    "orgSName": "测试证券",
    "publishDate": "2026-05-12",
    "emRatingName": "买入",
    "infoCode": "ABC123",
}


SAMPLE_TEXT = """事件
公司发布年报，营收同比增长25%，净利润同比增长32%，毛利率提升。
投资要点
核心产品放量，景气回暖，费用控制改善。
盈利预测与投资建议
预计EPS为1.20/1.55/1.90元，对应PE为20/16/13倍，目标价为35元，维持买入评级。
风险提示
需求不及预期；竞争加剧；价格波动。"""


def test_date_and_url_helpers():
    assert parse_date("2026-05-12").isoformat() == "2026-05-12"
    assert daterange(parse_date("2026-05-10"), parse_date("2026-05-12")) == [
        "2026-05-10",
        "2026-05-11",
        "2026-05-12",
    ]
    url = build_list_url("2026-05-12", 2, 50, 1)
    assert "beginTime=2026-05-12" in url
    assert "pageNo=2" in url
    assert "qType=1" in url


def test_filters_and_filename():
    args = argparse.Namespace(
        stock_filters=["000001"],
        org_filters=["测试"],
        rating_filters=["买入"],
        industry_filters=["计算机"],
    )
    assert filter_items([SAMPLE_ITEM], args) == [SAMPLE_ITEM]
    assert sanitize_filename('a/b:c*d?"e<f>g|') == "a_b_c_d__e_f_g_"


def test_html_parser_and_quality():
    html = f"""
    <html><body><div class="report-infos"><div class="ctx-content">
    <p>{SAMPLE_TEXT.splitlines()[0]}</p><p>{SAMPLE_TEXT.splitlines()[1]}</p>
    <p>{SAMPLE_TEXT.splitlines()[2]}</p><p>{SAMPLE_TEXT.splitlines()[3]}</p>
    </div><div class="c-foot"></div></div></body></html>
    """
    text = extract_report_text(html)
    quality = text_quality(text)
    assert "营收同比增长25%" in text
    assert quality.score > 40
    assert quality.section_hits >= 2


def test_analysis_and_scoring():
    summary = extract_summary(SAMPLE_TEXT)
    risks = extract_risk_items(SAMPLE_TEXT, "计算机")
    valuation = extract_valuation_fields(SAMPLE_TEXT, "买入")
    analysis = build_structured_analysis(SAMPLE_ITEM, SAMPLE_TEXT, summary)
    score, bucket, reasons, breakdown = score_report(analysis)
    assert summary
    assert "需求不及预期" in risks
    assert valuation["eps"] == ["1.20/1.55/1.90"]
    assert analysis["priority_bucket"] in {"A", "B", "C", "D"}
    assert score == analysis["signal_score"]
    assert bucket == analysis["priority_bucket"]
    assert reasons
    assert breakdown["final"] == score


def test_markdown_manifest_and_existing_map(tmp_path: Path):
    summary = extract_summary(SAMPLE_TEXT)
    markdown = build_markdown(SAMPLE_ITEM, SAMPLE_TEXT, summary, "html", 88)
    report_path = tmp_path / "001——样本股份——报告.md"
    report_path.write_text(markdown, encoding="utf-8")
    mapping = existing_markdown_map(tmp_path)
    assert mapping["ABC123"] == report_path

    result = FetchResult(SAMPLE_ITEM, "ok", SAMPLE_TEXT, summary, report_path, "html", quality_score=88)
    manifest = tmp_path / "run_manifest.jsonl"
    append_manifest_entry(manifest, "2026-05-12", 1, result)
    loaded = read_manifest(manifest)
    assert loaded["ABC123"]["qualityScore"] == 88


def test_resume_errors_only_selection():
    items = [
        {**SAMPLE_ITEM, "infoCode": "OK"},
        {**SAMPLE_ITEM, "infoCode": "WEAK"},
        {**SAMPLE_ITEM, "infoCode": "ERR"},
    ]
    selected = select_resume_error_items(
        items,
        {
            "OK": {"status": "ok"},
            "WEAK": {"status": "weak"},
            "ERR": {"status": "error"},
        },
    )
    assert [item["infoCode"] for item in selected] == ["ERR"]


def test_csv_and_day_outputs(tmp_path: Path):
    summary = extract_summary(SAMPLE_TEXT)
    result = FetchResult(
        item=SAMPLE_ITEM,
        status="ok",
        text=SAMPLE_TEXT,
        summary=summary,
        output_path=tmp_path / "001.md",
        source="html",
        quality_score=90,
        structured_analysis=build_structured_analysis(SAMPLE_ITEM, SAMPLE_TEXT, summary),
    )
    csv_path = write_csv_index(tmp_path, [result])
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert "scoreReasons" in rows[0]
    assert "scoreBreakdown" in rows[0]
    assert rows[0]["qualityScore"] == "90"

    log_path = tmp_path / "run.log.jsonl"
    write_day_summary(tmp_path, "2026-05-12", 0, [SAMPLE_ITEM], [result], log_path)
    assert (tmp_path / "TRADING_DASHBOARD.md").exists()
    assert (tmp_path / "CONSENSUS_BRIEF.md").exists()
    data = json.loads((tmp_path / "ANALYSIS_INPUT.json").read_text(encoding="utf-8"))
    assert data[0]["structured_analysis"]["score_breakdown"]["final"]


def test_refresh_weak_refetches_existing(monkeypatch, tmp_path: Path):
    report_path = tmp_path / "001.md"
    report_path.write_text(build_markdown(SAMPLE_ITEM, "短", [], "html", 10), encoding="utf-8")
    log_path = tmp_path / "run.log.jsonl"

    def fake_http(*args, **kwargs):
        return '<div class="ctx-content"><p>' + SAMPLE_TEXT + "</p></div>"

    monkeypatch.setattr("eastmoney_report_scraper.cli.http_get_with_retry", fake_http)
    monkeypatch.setattr("eastmoney_report_scraper.cli.extract_pdf_text", lambda *args, **kwargs: "")
    result = fetch_detail(
        item=SAMPLE_ITEM,
        output_dir=tmp_path,
        index=1,
        timeout=1,
        retries=0,
        retry_delay=0,
        log_path=log_path,
        resume_map={"ABC123": report_path},
        manifest_map={"ABC123": {"status": "weak"}},
        force=False,
        use_pdf_fallback=True,
        min_text_length=80,
        refresh_weak=True,
        resume_errors_only=False,
    )
    assert result.status == "ok"
    assert not result.skipped
