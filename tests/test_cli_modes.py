import argparse
import json
from pathlib import Path

from eastmoney_report_scraper.cli import run_doctor, run_hotspots_only, run_list_mode
from eastmoney_report_scraper.constants import DEFAULT_COVERAGE_HISTORY_NAME


def hotspot_args() -> argparse.Namespace:
    return argparse.Namespace(
        hotspot_days=30,
        hotspot_short_days=7,
        hotspot_silent_days=90,
        hotspot_broker_threshold=3,
        hotspot_coverage_threshold=3,
    )


def test_doctor_outputs_json(capsys, tmp_path: Path):
    run_doctor(tmp_path)
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "doctor"
    assert payload["checks"]["outputDirWritable"] is True
    assert "pythonVersion" in payload["checks"]


def test_hotspots_only_rebuilds_without_network(capsys, tmp_path: Path):
    history = tmp_path / DEFAULT_COVERAGE_HISTORY_NAME
    history.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "infoCode": "A1",
                        "reportType": "stock",
                        "stockCode": "300001",
                        "stockName": "热点样本",
                        "industryName": "人工智能",
                        "orgName": "华泰证券",
                        "rating": "买入",
                        "publishDate": "2026-05-12",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "infoCode": "A2",
                        "reportType": "stock",
                        "stockCode": "300001",
                        "stockName": "热点样本",
                        "industryName": "人工智能",
                        "orgName": "中信证券",
                        "rating": "买入",
                        "publishDate": "2026-05-13",
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_hotspots_only(tmp_path, hotspot_args())
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "hotspots-only"
    assert payload["coverage_entries"] == 2
    assert Path(payload["hotspot_signals"]).exists()
    assert Path(payload["hotspot_dashboard"]).exists()


def test_list_mode_outputs_selected_items_without_details(monkeypatch, capsys, tmp_path: Path):
    def fake_fetch_report_list(*args, **kwargs):
        return [
            {
                "stockName": "样本股份",
                "stockCode": "000001",
                "industryName": "计算机",
                "orgSName": "测试证券",
                "emRatingName": "买入",
                "infoCode": "ABC123",
            },
            {
                "stockName": "其他股份",
                "stockCode": "000002",
                "industryName": "医药",
                "orgSName": "测试证券",
                "emRatingName": "增持",
                "infoCode": "DEF456",
            },
        ]

    monkeypatch.setattr("eastmoney_report_scraper.cli.fetch_report_list", fake_fetch_report_list)
    args = argparse.Namespace(
        date="2026-05-12",
        page_size=100,
        qtype=0,
        timeout=1,
        retries=0,
        retry_delay=0,
        limit=None,
        stock_filters=["000001"],
        org_filters=[],
        rating_filters=[],
        industry_filters=[],
    )
    run_list_mode(["2026-05-12"], tmp_path / "root", args, include_items=True)
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "list-only"
    assert payload["selected_count"] == 1
    assert payload["days"][0]["items"][0]["infoCode"] == "ABC123"
