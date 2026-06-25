import json
import sqlite3
from pathlib import Path
from urllib import error

from eastmoney_report_scraper.ai import (
    AIConfig,
    _anthropic_request_url,
    _openai_request_url,
    ai_http_error_hint,
    analyze_with_ai,
    build_ai_payload,
    build_ai_citations,
    build_ai_evidence,
    build_ai_evidence_quality,
    build_ai_messages,
    build_ai_record,
    delete_ai_profile,
    detect_ai_response_kind,
    export_ai_analysis_markdown,
    list_ai_prompt_templates,
    list_ai_analysis_history,
    load_ai_config,
    load_ai_profiles,
    load_cc_switch_current_ai_config,
    messages_to_prompt,
    messages_to_anthropic,
    messages_to_responses,
    parse_ai_response_body,
    probe_ai_connection,
    public_ai_profile_settings,
    public_ai_settings,
    redact_secrets,
    resolve_ai_prompt_template,
    save_ai_analysis_record,
    set_active_ai_profile,
    structure_ai_analysis,
    update_ai_config,
)
from eastmoney_report_scraper.ai_connector import AIConfig as StandaloneAIConfig
from eastmoney_report_scraper.app.services import LocalAppServices
from eastmoney_report_scraper.config import LocalAppConfig


def test_ai_config_round_trip_masks_token(tmp_path: Path):
    token = "sk-test-secret-123456"
    config = update_ai_config(
        tmp_path,
        {
            "baseUrl": "https://example.test/v1/chat/completions",
            "model": "demo-model",
            "apiToken": token,
            "apiFormat": "completions",
            "timeout": 30,
        },
    )
    loaded = load_ai_config(tmp_path)
    public = public_ai_settings(config, tmp_path)

    assert loaded.api_token == token
    assert loaded.base_url == "https://example.test/v1/chat/completions"
    assert loaded.api_format == "completions"
    assert public["hasToken"] is True
    assert public["apiFormat"] == "completions"
    assert public["maskedToken"] == "sk-...3456"
    assert token not in json.dumps(public, ensure_ascii=False)


def test_standalone_ai_connector_can_be_imported_directly():
    config = StandaloneAIConfig(base_url="https://example.test/v1", model="demo")

    assert config.provider == "openai-compatible"
    assert config.base_url == "https://example.test/v1"


def test_ai_config_update_preserves_token_when_password_field_is_blank(tmp_path: Path):
    token = "secret-token-abcdef"
    update_ai_config(tmp_path, {"apiToken": token, "model": "first"})
    config = update_ai_config(tmp_path, {"apiToken": "", "model": "second"})

    assert config.model == "second"
    assert config.api_token == token


def test_ai_config_update_can_clear_saved_token(tmp_path: Path):
    update_ai_config(tmp_path, {"apiToken": "secret-token-abcdef", "model": "first"})
    config = update_ai_config(tmp_path, {"clearToken": True})

    assert config.model == "first"
    assert config.api_token == ""
    assert public_ai_profile_settings(tmp_path)["hasToken"] is False


def test_legacy_single_ai_config_loads_as_default_profile(tmp_path: Path):
    config_path = tmp_path / "local_ai_config.json"
    config_path.write_text(
        json.dumps(
            {
                "baseUrl": "https://example.test/v1/chat/completions",
                "model": "legacy-model",
                "apiToken": "legacy-token-abcdef",
                "apiFormat": "chat",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    store = load_ai_profiles(tmp_path)
    public = public_ai_profile_settings(tmp_path)
    loaded = load_ai_config(tmp_path)

    assert store["activeProfileId"] == "default"
    assert store["profiles"][0]["id"] == "default"
    assert loaded.model == "legacy-model"
    assert loaded.api_token == "legacy-token-abcdef"
    assert public["profiles"][0]["maskedToken"] == "leg...cdef"
    assert "legacy-token-abcdef" not in json.dumps(public, ensure_ascii=False)


def test_ai_profiles_save_switch_delete_and_preserve_token(tmp_path: Path):
    token = "secret-token-abcdef"
    update_ai_config(
        tmp_path,
        {"profileId": "default", "profileName": "Default", "apiToken": token, "model": "default-model"},
    )
    update_ai_config(
        tmp_path,
        {
            "profileId": "third-party",
            "profileName": "Third Party",
            "provider": "openai-compatible",
            "baseUrl": "https://example.test/v1",
            "model": "third-model",
            "apiFormat": "responses",
            "apiToken": "third-token-abcdef",
        },
    )
    switched = set_active_ai_profile(tmp_path, "default")
    preserved = update_ai_config(tmp_path, {"profileId": "default", "apiToken": "", "model": "default-model-2"})
    deleted = delete_ai_profile(tmp_path, "third-party")

    assert switched["activeProfileId"] == "default"
    assert preserved.api_token == token
    assert preserved.model == "default-model-2"
    assert deleted["activeProfileId"] == "default"
    assert [profile["id"] for profile in deleted["profiles"]] == ["default"]
    assert "third-token-abcdef" not in json.dumps(deleted, ensure_ascii=False)


def test_redact_secrets_replaces_raw_token():
    text = redact_secrets("request failed: secret-token-abcdef", ["secret-token-abcdef"])

    assert "secret-token-abcdef" not in text
    assert "sec...cdef" in text


def test_ai_http_error_hint_explains_cloudflare_1010():
    hint = ai_http_error_hint(403, "error code: 1010")

    assert "403/1010" in hint
    assert "Chat Completions" in hint
    assert "/v1/chat/completions" in hint


def test_ai_payload_formats_support_messages_prompt_and_input():
    config = AIConfig(model="mock-model")
    messages = [{"role": "system", "content": "系统"}, {"role": "user", "content": "用户"}]

    chat_payload = build_ai_payload(config, messages, "chat")
    completions_payload = build_ai_payload(config, messages, "completions")
    responses_payload = build_ai_payload(config, messages, "responses")
    prompt = messages_to_prompt(messages)

    assert "messages" in chat_payload
    assert "prompt" not in chat_payload
    assert completions_payload["prompt"] == prompt
    assert "messages" not in completions_payload
    assert responses_payload["instructions"] == "系统"
    assert responses_payload["input"] == [{"role": "user", "content": "用户"}]
    assert "messages" not in responses_payload


def test_prompt_template_registry_falls_back_to_general_research():
    templates = list_ai_prompt_templates()
    template_ids = {template["id"] for template in templates}
    fallback = resolve_ai_prompt_template("missing-template")
    messages = build_ai_messages({"reports": []}, template_id="opinion_change")

    assert "general_research" in template_ids
    assert "opinion_change" in template_ids
    assert fallback["id"] == "general_research"
    assert "观点变化趋势" in messages[1]["content"]
    assert "支持证据" in messages[1]["content"]


def test_build_ai_messages_accepts_custom_template_prompt():
    messages = build_ai_messages(
        {"reports": []},
        template_id="opinion_change",
        template_prompt="只输出三条最重要的观点变化。",
    )
    content = messages[1]["content"]

    assert "只输出三条最重要的观点变化。" in content
    assert "区分覆盖增加与看多加强" not in content


def test_responses_messages_are_list_for_strict_third_party_apis():
    messages = [{"role": "system", "content": "系统"}, {"role": "user", "content": "用户"}]
    instructions, input_items = messages_to_responses(messages)
    payload = build_ai_payload(AIConfig(model="mock-model"), messages, "responses")

    assert instructions == "系统"
    assert input_items == [{"role": "user", "content": "用户"}]
    assert isinstance(payload["input"], list)


def test_anthropic_payload_matches_cc_switch_style():
    config = AIConfig(provider="anthropic-compatible", base_url="https://api.example.com/anthropic", model="mock-model", api_format="anthropic")
    messages = [{"role": "system", "content": "系统"}, {"role": "user", "content": "用户"}]
    system, anthropic_messages = messages_to_anthropic(messages)
    payload = build_ai_payload(config, messages, "anthropic")

    assert system == "系统"
    assert anthropic_messages == [{"role": "user", "content": "用户"}]
    assert payload["system"] == "系统"
    assert payload["messages"] == [{"role": "user", "content": "用户"}]
    assert payload["max_tokens"] == 1200
    assert _anthropic_request_url(config.base_url) == "https://api.example.com/anthropic/v1/messages"


def test_openai_compatible_base_url_appends_selected_endpoint():
    assert _openai_request_url("https://right.codes/codex/v1", "responses") == "https://right.codes/codex/v1/responses"
    assert _openai_request_url("https://right.codes/codex/v1/", "chat") == "https://right.codes/codex/v1/chat/completions"
    assert _openai_request_url("https://right.codes/codex", "completions") == "https://right.codes/codex/v1/completions"
    assert (
        _openai_request_url("https://right.codes/codex/v1/responses", "responses")
        == "https://right.codes/codex/v1/responses"
    )


def test_parse_ai_response_body_handles_empty_sse_and_plain_text():
    assert parse_ai_response_body('{"output_text":"完成"}')["output_text"] == "完成"
    assert parse_ai_response_body('data: {"delta":"你"}\n\ndata: {"delta":"好"}\n\ndata: [DONE]')["output_text"] == "你好"
    assert parse_ai_response_body("plain text result")["output_text"] == "plain text result"


def test_parse_ai_response_body_reports_empty_or_html_response():
    try:
        parse_ai_response_body("")
    except RuntimeError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("empty response should raise")

    try:
        parse_ai_response_body("<html><body>login</body></html>")
    except RuntimeError as exc:
        assert "HTML" in str(exc)
    else:
        raise AssertionError("HTML response should raise")


def test_detect_ai_response_kind_classifies_provider_responses():
    assert detect_ai_response_kind('{"ok":true}') == "json"
    assert detect_ai_response_kind('data: {"delta":"ok"}') == "sse"
    assert detect_ai_response_kind("plain text") == "plain_text"
    assert detect_ai_response_kind("<html></html>") == "html"
    assert detect_ai_response_kind("") == "empty"


def test_probe_ai_connection_returns_diagnostics_for_success(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "pong"}}]}).encode()

    def fake_urlopen(http_request, timeout):
        captured["url"] = http_request.full_url
        captured["body"] = json.loads(http_request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("eastmoney_report_scraper.ai_connector.request.urlopen", fake_urlopen)
    config = AIConfig(base_url="https://example.test/v1", model="mock", api_token="secret-token-abcdef")
    result = probe_ai_connection(config)

    assert result["ok"] is True
    assert result["apiFormat"] == "chat"
    assert result["requestUrl"] == "https://example.test/v1/chat/completions"
    assert result["responseKind"] == "json"
    assert captured["body"]["messages"][0]["content"] == "ping"
    assert captured["timeout"] == 60


def test_probe_ai_connection_returns_structured_http_error(monkeypatch):
    class FakeHTTPError(error.HTTPError):
        def read(self):
            return b'{"detail":"Input must be a list"}'

    def fake_urlopen_with_body(_http_request, timeout):
        assert timeout == 60
        raise FakeHTTPError(
            url="https://example.test/v1/responses",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("eastmoney_report_scraper.ai_connector.request.urlopen", fake_urlopen_with_body)
    config = AIConfig(
        base_url="https://example.test/v1",
        model="mock",
        api_token="secret-token-abcdef",
        api_format="responses",
    )
    result = probe_ai_connection(config)

    assert result["ok"] is False
    assert result["statusCode"] == 400
    assert result["responseKind"] == "json"
    assert "Input must be a list" in result["message"]
    assert "Responses" in result["suggestedFix"]
    assert "secret-token-abcdef" not in json.dumps(result, ensure_ascii=False)


def test_load_cc_switch_current_ai_config_reads_current_claude_provider(tmp_path: Path):
    cc_switch = tmp_path / ".cc-switch"
    cc_switch.mkdir()
    settings_path = cc_switch / "settings.json"
    db_path = cc_switch / "cc-switch.db"
    provider_id = "provider-1"
    settings_path.write_text(json.dumps({"currentProviderClaude": provider_id}), encoding="utf-8")

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "create table providers (id text, app_type text, name text, settings_config text)"
        )
        connection.execute(
            "create table provider_endpoints (provider_id text, app_type text, url text)"
        )
        connection.execute(
            "insert into providers values (?,?,?,?)",
            (
                provider_id,
                "claude",
                "DeepSeek",
                json.dumps(
                    {
                        "env": {
                            "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
                            "ANTHROPIC_AUTH_TOKEN": "secret-token-abcdef",
                            "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]",
                        }
                    }
                ),
            ),
        )
        connection.execute(
            "insert into provider_endpoints values (?,?,?)",
            (provider_id, "claude", "https://api.deepseek.com/anthropic"),
        )

    config, metadata = load_cc_switch_current_ai_config(settings_path=settings_path, db_path=db_path)
    public = public_ai_settings(config, tmp_path)

    assert config.provider == "anthropic-compatible"
    assert config.api_format == "anthropic"
    assert config.base_url == "https://api.deepseek.com/anthropic"
    assert config.model == "deepseek-v4-pro[1m]"
    assert config.api_token == "secret-token-abcdef"
    assert metadata["providerName"] == "DeepSeek"
    assert "secret-token-abcdef" not in json.dumps(public, ensure_ascii=False)


def test_build_ai_evidence_uses_entity_filters_and_caps_reports():
    dashboard_data = {
        "entityDrilldowns": [
            {
                "entityKey": "company:300001",
                "entityType": "company",
                "label": "样本公司",
                "stockCode": "300001",
                "industryName": "人工智能",
                "reportCount": 2,
                "brokerCount": 2,
                "hotspotLevel": "HOT",
                "reasonCodes": ["MULTI_BROKER"],
            }
        ],
        "reports": [
            {
                "date": "2026-05-12",
                "stockName": "样本公司",
                "stockCode": "300001",
                "industryName": "人工智能",
                "orgName": "测试证券",
                "rating": "买入",
                "summary": "景气改善，订单增长。",
                "signalScore": 86,
            },
            {
                "date": "2026-05-13",
                "stockName": "其他公司",
                "stockCode": "300002",
                "industryName": "机器人",
                "orgName": "测试证券",
                "rating": "增持",
                "summary": "其他样本。",
                "signalScore": 60,
            },
        ],
        "hotspots": [
            {
                "entityType": "company",
                "entityName": "样本公司",
                "stockCode": "300001",
                "industryName": "人工智能",
                "hotspotLevel": "HOT",
                "coverage30d": 2,
                "reasonCodes": ["MULTI_BROKER"],
            }
        ],
        "opinionTrends": [
            {
                "stockName": "样本公司",
                "stockCode": "300001",
                "industryName": "人工智能",
                "orgName": "测试证券",
                "latestDate": "2026-05-12",
                "targetDirection": "up",
            }
        ],
    }

    evidence = build_ai_evidence(
        dashboard_data,
        scope="selected",
        entity_key="company:300001",
        filters={"startDate": "2026-05-01", "endDate": "2026-05-31"},
        max_reports=1,
    )

    assert evidence["entity"]["label"] == "样本公司"
    assert evidence["sampleCounts"]["reports"] == 1
    assert evidence["sampleCounts"]["hotspots"] == 1
    assert evidence["sampleCounts"]["opinionTrends"] == 1
    assert len(evidence["reports"]) == 1
    assert evidence["reports"][0]["stockName"] == "样本公司"


def test_build_ai_evidence_supports_multi_entities_date_range_and_scope_summary():
    dashboard_data = {
        "entityDrilldowns": [
            {"entityKey": "company:300001", "entityType": "company", "label": "甲公司", "stockCode": "300001"},
            {"entityKey": "company:300002", "entityType": "company", "label": "乙公司", "stockCode": "300002"},
            {"entityKey": "industry:ai", "entityType": "industry", "label": "人工智能"},
        ],
        "reports": [
            {
                "date": "2026-05-10",
                "stockName": "甲公司",
                "stockCode": "300001",
                "industryName": "人工智能",
                "orgName": "A证券",
                "summary": "AI 订单增长",
            },
            {
                "date": "2026-05-11",
                "stockName": "乙公司",
                "stockCode": "300002",
                "industryName": "人工智能",
                "orgName": "B证券",
                "summary": "国产替代",
            },
            {
                "date": "2026-04-01",
                "stockName": "丙公司",
                "stockCode": "300003",
                "industryName": "机器人",
                "orgName": "C证券",
                "summary": "旧数据",
            },
        ],
        "hotspots": [
            {"entityType": "company", "entityName": "甲公司", "stockCode": "300001", "hotspotLevel": "HOT"},
            {"entityType": "company", "entityName": "乙公司", "stockCode": "300002", "hotspotLevel": "WATCH"},
        ],
        "opinionTrends": [],
    }

    companies = build_ai_evidence(
        dashboard_data,
        scope="companies",
        entity_keys=["company:300001", "company:300002"],
        max_reports=8,
    )
    date_range = build_ai_evidence(
        dashboard_data,
        scope="date_range",
        start_date="2026-05-01",
        end_date="2026-05-31",
        max_reports=8,
    )
    current_filters = build_ai_evidence(
        dashboard_data,
        scope="current_filters",
        filters={"industry": "人工智能"},
        max_reports=8,
    )

    assert companies["selectedScopeSummary"]["reportCount"] == 2
    assert companies["selectedScopeSummary"]["companyCount"] == 2
    assert date_range["selectedScopeSummary"]["reportCount"] == 2
    assert current_filters["selectedScopeSummary"]["industryCount"] == 1
    assert [row["stockName"] for row in current_filters["reports"]] == ["乙公司", "甲公司"]


def test_ai_p1_quality_citations_structure_history_and_markdown(tmp_path: Path):
    evidence = {
        "selectedScopeSummary": {
            "scope": "company",
            "query": "样本公司",
            "reportCount": 2,
            "companyCount": 1,
            "industryCount": 1,
            "brokerCount": 2,
        },
        "sampleCounts": {"reports": 2, "hotspots": 1, "opinionTrends": 1},
        "reports": [
            {
                "sourceId": "R1",
                "date": "2026-05-12",
                "stockName": "样本公司",
                "stockCode": "300001",
                "industryName": "人工智能",
                "orgName": "测试证券",
                "rating": "买入",
                "targetPrice": "30",
                "epsForecast": "1.00",
                "signalScore": "88",
                "title": "样本公司深度",
                "fileHref": "研报_2026-05-12/001.md",
            }
        ],
        "hotspots": [
            {
                "sourceId": "H1",
                "entityName": "样本公司",
                "stockCode": "300001",
                "industryName": "人工智能",
                "hotspotLevel": "HOT",
                "reasonCodes": ["MULTI_BROKER"],
            }
        ],
        "opinionTrends": [
            {
                "sourceId": "O1",
                "stockName": "样本公司",
                "stockCode": "300001",
                "orgName": "测试证券",
                "previousDate": "2026-05-01",
                "latestDate": "2026-05-12",
                "scoreDirection": "up",
            }
        ],
    }
    analysis = (
        "## 核心结论\n样本公司信号增强 [R1]。\n"
        "## 支持证据\n多券商共振 [H1]。\n"
        "## 观点变化\n评分上行 [O1]。\n"
        "## 后续观察\n继续观察订单。"
    )

    structured = structure_ai_analysis(analysis, evidence)
    citations = build_ai_citations(evidence)
    quality = build_ai_evidence_quality(evidence)
    record = build_ai_record(
        {
            "ok": True,
            "provider": "openai-compatible",
            "model": "mock-model",
            "analysis": analysis,
            "template": {"id": "company_deep_dive", "name": "单公司深挖"},
            "usage": {"total_tokens": 12},
            "evidence": evidence,
        },
        {"scope": "company", "query": "样本公司", "templateId": "company_deep_dive"},
    )
    saved = save_ai_analysis_record(tmp_path, record)
    history = list_ai_analysis_history(tmp_path)
    markdown_path = export_ai_analysis_markdown(tmp_path, saved)

    assert structured["coreConclusion"] == "样本公司信号增强 [R1]。"
    assert structured["sourceReportIds"] == ["R1"]
    assert citations[0]["sourceId"] == "R1"
    assert citations[0]["fileHref"] == "研报_2026-05-12/001.md"
    assert quality["level"] == "warn"
    assert "只发送最近 1 篇" in "；".join(quality["warnings"])
    assert saved["markdownHref"].startswith("AI_ANALYSES/")
    assert history["count"] == 1
    assert history["items"][0]["analysis"] == analysis
    assert markdown_path.exists()
    assert "## 引用来源" in markdown_path.read_text(encoding="utf-8")


def test_analyze_with_ai_uses_injected_http_post_without_network():
    config = AIConfig(api_token="secret-token-abcdef", model="mock-model")
    evidence = {"reports": [{"stockName": "样本公司"}]}

    def fake_post(received_config, messages):
        assert received_config.api_token == "secret-token-abcdef"
        assert "secret-token-abcdef" not in json.dumps(messages, ensure_ascii=False)
        return {"choices": [{"message": {"content": "核心结论：样本分析。"}}], "usage": {"total_tokens": 12}}

    result = analyze_with_ai(config, evidence, http_post=fake_post)

    assert result["ok"] is True
    assert result["analysis"] == "核心结论：样本分析。"
    assert result["usage"]["total_tokens"] == 12


def test_analyze_with_anthropic_compatible_provider_uses_messages_endpoint(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def read(self):
            return json.dumps({"content": [{"type": "text", "text": "核心结论：Anthropic 样本。"}]}).encode()

    def fake_urlopen(http_request, timeout):
        captured["url"] = http_request.full_url
        captured["headers"] = dict(http_request.header_items())
        captured["body"] = json.loads(http_request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("eastmoney_report_scraper.ai_connector.request.urlopen", fake_urlopen)

    config = AIConfig(
        provider="anthropic-compatible",
        base_url="https://api.deepseek.com/anthropic",
        model="deepseek-v4-pro[1m]",
        api_token="secret-token-abcdef",
        api_format="anthropic",
    )
    result = analyze_with_ai(config, {"reports": [{"stockName": "样本公司"}]})

    assert result["ok"] is True
    assert result["analysis"] == "核心结论：Anthropic 样本。"
    assert captured["url"] == "https://api.deepseek.com/anthropic/v1/messages"
    assert captured["headers"]["X-api-key"] == "secret-token-abcdef"
    assert captured["headers"]["Anthropic-version"] == "2023-06-01"
    assert captured["body"]["model"] == "deepseek-v4-pro[1m]"
    assert captured["body"]["messages"][0]["role"] == "user"


def test_analyze_with_provider_plain_text_response(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def read(self):
            return "纯文本分析结果".encode("utf-8")

    monkeypatch.setattr("eastmoney_report_scraper.ai_connector.request.urlopen", lambda _request, timeout: FakeResponse())

    config = AIConfig(
        base_url="https://right.codes/codex/v1",
        model="gpt-5.4",
        api_token="secret-token-abcdef",
        api_format="responses",
    )
    result = analyze_with_ai(config, {"reports": [{"stockName": "样本公司"}]})

    assert result["ok"] is True
    assert result["analysis"] == "纯文本分析结果"


def test_local_app_ai_service_never_returns_raw_token(tmp_path: Path):
    token = "secret-token-abcdef"

    def fake_post(received_config, _messages):
        assert received_config.api_token == token
        return {"choices": [{"message": {"content": "AI 分析结果"}}]}

    services = LocalAppServices(
        LocalAppConfig(output_dir=str(tmp_path / "reports"), db_path=str(tmp_path / "eastmoney.db")),
        ai_http_post=fake_post,
    )
    saved = services.update_ai_settings({"apiToken": token, "model": "mock-model"})
    settings = services.ai_settings()
    result = services.ai_analyze({"scope": "global"})
    history = services.ai_history()

    assert saved["ok"] is True
    assert result["ok"] is True
    assert result["historyRecord"]["markdownHref"].startswith("AI_ANALYSES/")
    assert (tmp_path / "reports" / result["historyRecord"]["markdownHref"]).exists()
    assert history["count"] == 1
    payload = json.dumps({"saved": saved, "settings": settings, "result": result}, ensure_ascii=False)
    assert token not in payload
    assert settings["maskedToken"] == "sec...cdef"


def test_local_app_ai_service_redacts_token_from_errors(tmp_path: Path):
    token = "secret-token-abcdef"

    def fake_post(received_config, _messages):
        raise RuntimeError(f"bad token {received_config.api_token}")

    services = LocalAppServices(
        LocalAppConfig(output_dir=str(tmp_path / "reports"), db_path=str(tmp_path / "eastmoney.db")),
        ai_http_post=fake_post,
    )
    services.update_ai_settings({"apiToken": token, "model": "mock-model"})
    result = services.ai_analyze({"scope": "global"})

    assert result["ok"] is False
    assert token not in result["error"]
    assert "sec...cdef" in result["error"]
