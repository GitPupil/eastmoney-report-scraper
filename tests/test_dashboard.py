import csv
import json
from pathlib import Path

from eastmoney_report_scraper.constants import (
    DEFAULT_COVERAGE_HISTORY_NAME,
    DEFAULT_HOTSPOT_SIGNALS_NAME,
    DEFAULT_INDEX_NAME,
)
from eastmoney_report_scraper.dashboard import build_dashboard_data, write_dashboard
from eastmoney_report_scraper.hotspots import SIGNAL_FIELDS


def _write_index(output_dir: Path, rows):
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / DEFAULT_INDEX_NAME
    fields = [
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
        "ratingChange",
        "targetPrice",
        "epsForecast",
        "peForecast",
        "file",
        "scoreReasons",
        "scoreBreakdown",
        "qualityScore",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_hotspots(output_root: Path):
    path = output_root / DEFAULT_HOTSPOT_SIGNALS_NAME
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SIGNAL_FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "entityType": "company",
                "entityName": "热点样本",
                "stockCode": "300001",
                "industryName": "人工智能",
                "hotspotLevel": "STRONG",
                "isFirstCoverage": "true",
                "isReactivatedCoverage": "false",
                "coverage7d": "2",
                "coverage30d": "3",
                "previous30dCoverage": "0",
                "coverageAcceleration": "3",
                "brokerCount30d": "3",
                "newBrokerCount30d": "3",
                "ratingDistribution": "{}",
                "buyRatio": "0.6667",
                "latestPublishDate": "2026-05-13",
                "reasons": "近期首次被覆盖；30日3家券商覆盖",
                "reasonCodes": "FIRST_COVERAGE|MULTI_BROKER",
                "coveredCompanyCount30d": "1",
            }
        )
    return path


def test_dashboard_data_and_html_generation(tmp_path: Path):
    _write_index(
        tmp_path / "研报_2026-05-12",
        [
            {
                "stockName": "热点样本",
                "stockCode": "300001",
                "industryName": "人工智能",
                "title": "首次覆盖，维持买入",
                "orgName": "测试证券",
                "publishDate": "2026-05-12",
                "rating": "买入",
                "infoCode": "A1",
                "status": "ok",
                "source": "html",
                "chars": "1200",
                "summary": "订单增长 | 景气改善",
                "signalScore": "72",
                "priorityBucket": "B",
                "themeTags": "AI | 景气",
                "ratingChange": "",
                "targetPrice": "30",
                "epsForecast": "1.00",
                "peForecast": "20",
                "file": "001.md",
                "scoreReasons": "景气改善",
                "scoreBreakdown": "{}",
                "qualityScore": "88",
            }
        ],
    )
    _write_index(
        tmp_path / "研报_2026-05-13",
        [
            {
                "stockName": "热点样本",
                "stockCode": "300001",
                "industryName": "人工智能",
                "title": "目标价上修",
                "orgName": "测试证券",
                "publishDate": "2026-05-13",
                "rating": "买入",
                "infoCode": "A2",
                "status": "ok",
                "source": "pdf",
                "chars": "1500",
                "summary": "目标价上修 | EPS 上修",
                "signalScore": "84",
                "priorityBucket": "A",
                "themeTags": "AI | 出海",
                "ratingChange": "维持买入",
                "targetPrice": "35",
                "epsForecast": "1.20",
                "peForecast": "18",
                "file": "002.md",
                "scoreReasons": "目标价上修",
                "scoreBreakdown": "{}",
                "qualityScore": "92",
            }
        ],
    )
    _write_hotspots(tmp_path)
    (tmp_path / DEFAULT_COVERAGE_HISTORY_NAME).write_text(
        json.dumps({"infoCode": "A1", "stockName": "热点样本"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    data = build_dashboard_data(tmp_path)
    assert len(data["reports"]) == 2
    assert data["hotspots"][0]["reasonCodes"] == ["FIRST_COVERAGE", "MULTI_BROKER"]
    assert data["coverageHistoryCount"] == 1
    assert data["opinionTrends"][0]["targetDirection"] == "up"
    assert data["opinionTrends"][0]["epsDirection"] == "up"
    company = next(entity for entity in data["entityDrilldowns"] if entity["entityType"] == "company")
    assert company["label"] == "热点样本"
    assert company["reportCount"] == 2
    assert company["brokerCount"] == 1
    assert company["coverageByDay"] == [
        {"name": "05-12", "date": "2026-05-12", "count": 1},
        {"name": "05-13", "date": "2026-05-13", "count": 1},
    ]
    assert company["targetTimeline"][-1]["count"] == 35.0
    assert company["epsTimeline"][-1]["count"] == 1.2
    assert company["opinionSummary"]["target"]["up"] == 1
    assert company["latestReports"][0]["title"] == "目标价上修"

    dashboard_path = write_dashboard(tmp_path)
    html = dashboard_path.read_text(encoding="utf-8")
    assert dashboard_path.name == "DASHBOARD.html"
    assert "Research Dashboard" in html
    assert "研究对象 Drilldown" in html
    assert "目标价轨迹" in html
    assert "近期热点" in html
    assert "热点样本" in html
    assert "FIRST_COVERAGE" in html


def test_dashboard_handles_empty_output_root(tmp_path: Path):
    dashboard_path = write_dashboard(tmp_path)
    html = dashboard_path.read_text(encoding="utf-8")
    data = build_dashboard_data(tmp_path)
    assert data["reports"] == []
    assert data["hotspots"] == []
    assert data["entityDrilldowns"] == []
    assert "暂无数据" in html
