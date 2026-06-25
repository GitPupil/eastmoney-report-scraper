"""Eastmoney-specific AI analysis helpers.

Generic provider wiring lives in :mod:`eastmoney_report_scraper.ai_connector`.
Keep this file focused on report evidence selection and research prompts.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional, Sequence

from .ai_connector import (
    AIConfig,
    AIHTTPError,
    AIHttpPost,
    _anthropic_request_url,
    _default_http_post,
    _extract_message_content,
    _openai_request_url,
    ai_config_path,
    ai_http_error_hint,
    analyze_messages_with_ai,
    build_ai_payload,
    default_cc_switch_paths,
    delete_ai_profile,
    detect_ai_response_kind,
    extract_ai_message_content,
    import_cc_switch_ai_config,
    load_ai_config,
    load_ai_profiles,
    load_cc_switch_current_ai_config,
    mask_token,
    messages_to_anthropic,
    messages_to_prompt,
    messages_to_responses,
    parse_ai_response_body,
    probe_ai_connection,
    public_ai_profile_settings,
    public_ai_settings,
    redact_secrets,
    save_ai_config,
    save_ai_profiles,
    set_active_ai_profile,
    update_ai_config,
)

__all__ = [
    "AIConfig",
    "AIHTTPError",
    "AIHttpPost",
    "_anthropic_request_url",
    "_default_http_post",
    "_extract_message_content",
    "_openai_request_url",
    "ai_config_path",
    "ai_http_error_hint",
    "analyze_messages_with_ai",
    "analyze_with_ai",
    "build_ai_evidence",
    "build_ai_messages",
    "build_ai_payload",
    "default_cc_switch_paths",
    "delete_ai_profile",
    "detect_ai_response_kind",
    "extract_ai_message_content",
    "import_cc_switch_ai_config",
    "list_ai_prompt_templates",
    "load_ai_config",
    "load_ai_profiles",
    "load_cc_switch_current_ai_config",
    "mask_token",
    "messages_to_anthropic",
    "messages_to_prompt",
    "messages_to_responses",
    "parse_ai_response_body",
    "probe_ai_connection",
    "public_ai_profile_settings",
    "public_ai_settings",
    "redact_secrets",
    "resolve_ai_prompt_template",
    "save_ai_config",
    "save_ai_profiles",
    "set_active_ai_profile",
    "update_ai_config",
]


AI_PROMPT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "general_research": {
        "name": "通用研报解释",
        "instruction": "解释当前 evidence 中的核心研报信号，判断覆盖热度、观点强弱和分歧来源。",
    },
    "opinion_change": {
        "name": "观点变化趋势",
        "instruction": "重点比较评级、目标价、EPS 和 signal score 是否连续变强或转弱，区分覆盖增加与看多加强。",
    },
    "hotspot_radar": {
        "name": "热点雷达",
        "instruction": "重点解释首次覆盖、多券商覆盖、覆盖加速、行业共振和热点 reason codes 的含义。",
    },
    "company_deep_dive": {
        "name": "单公司深挖",
        "instruction": "围绕单公司总结券商覆盖、观点变化、目标价/EPS 方向、主题叙事和后续观察。",
    },
    "industry_trend": {
        "name": "单行业趋势",
        "instruction": "围绕单行业总结热度趋势、覆盖扩散、活跃券商、代表公司和主题词变化。",
    },
    "multi_industry_compare": {
        "name": "多行业比较",
        "instruction": "横向比较多个行业的覆盖热度、券商扩散、买入比例、观点变化和边际变化强弱。",
    },
    "daily_overview": {
        "name": "日度总览",
        "instruction": "对全部抓取数据做日度总览，提炼最值得跟踪的热点、分歧和后续观察清单。",
    },
}

COMMON_OUTPUT_REQUIREMENTS = (
    "输出必须包含以下小节：核心结论、支持证据、反向证据、观点变化、分歧、后续观察。"
    "每个判断都要引用 evidence 中的公司、行业、券商、日期、评分或 reason code。"
)


def list_ai_prompt_templates() -> list[dict[str, str]]:
    return [
        {"id": template_id, "name": template["name"], "instruction": template["instruction"]}
        for template_id, template in AI_PROMPT_TEMPLATES.items()
    ]


def resolve_ai_prompt_template(template_id: str) -> Dict[str, str]:
    key = str(template_id or "general_research").strip()
    template = AI_PROMPT_TEMPLATES.get(key) or AI_PROMPT_TEMPLATES["general_research"]
    resolved_id = key if key in AI_PROMPT_TEMPLATES else "general_research"
    return {"id": resolved_id, **template}


def _first_present(row: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return ""


def _compact_report(row: Mapping[str, Any]) -> Dict[str, Any]:
    summary = str(row.get("summary") or row.get("title") or "")
    return {
        "date": _first_present(row, ("date", "publishDate")),
        "stockName": row.get("stockName", ""),
        "stockCode": row.get("stockCode", ""),
        "industryName": row.get("industryName", ""),
        "orgName": row.get("orgName", ""),
        "rating": row.get("rating", ""),
        "targetPrice": row.get("targetPrice", ""),
        "epsForecast": row.get("epsForecast", ""),
        "signalScore": row.get("signalScore", ""),
        "priorityBucket": row.get("priorityBucket", ""),
        "themeTags": row.get("themeTags", []),
        "scoreReasons": row.get("scoreReasons", []),
        "summary": summary[:260],
    }


def _compact_hotspot(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "entityType": row.get("entityType", ""),
        "entityName": row.get("entityName", ""),
        "stockCode": row.get("stockCode", ""),
        "industryName": row.get("industryName", ""),
        "hotspotLevel": row.get("hotspotLevel", ""),
        "coverage7d": row.get("coverage7d", ""),
        "coverage30d": row.get("coverage30d", ""),
        "brokerCount30d": row.get("brokerCount30d", ""),
        "newBrokerCount30d": row.get("newBrokerCount30d", ""),
        "coverageAcceleration": row.get("coverageAcceleration", ""),
        "buyRatio": row.get("buyRatio", ""),
        "reasonCodes": row.get("reasonCodes", []),
        "reasons": row.get("reasons", []),
    }


def _compact_opinion(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "stockName": row.get("stockName", ""),
        "stockCode": row.get("stockCode", ""),
        "industryName": row.get("industryName", ""),
        "orgName": row.get("orgName", ""),
        "previousDate": row.get("previousDate", ""),
        "latestDate": row.get("latestDate", ""),
        "previousRating": row.get("previousRating", ""),
        "latestRating": row.get("latestRating", ""),
        "ratingChange": row.get("ratingChange", ""),
        "targetDirection": row.get("targetDirection", ""),
        "epsDirection": row.get("epsDirection", ""),
        "scoreDirection": row.get("scoreDirection", ""),
    }


def _matches_text(row: Mapping[str, Any], query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        str(value)
        for value in [
            row.get("stockName"),
            row.get("stockCode"),
            row.get("industryName"),
            row.get("entityName"),
            row.get("orgName"),
            row.get("rating"),
            row.get("title"),
            row.get("summary"),
        ]
        if value
    ).lower()
    return query.lower() in haystack


def _in_date(row: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
    date = str(_first_present(row, ("date", "publishDate", "latestPublishDate", "latestDate")))
    if not date:
        return True
    start = str(filters.get("startDate") or "")
    end = str(filters.get("endDate") or "")
    return (not start or date >= start) and (not end or date <= end)


def _matches_filters(row: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
    if not _in_date(row, filters):
        return False
    checks = (
        ("company", ("stockName", "stockCode", "entityName")),
        ("industry", ("industryName", "entityName")),
        ("broker", ("orgName",)),
        ("rating", ("rating", "latestRating")),
        ("priority", ("priorityBucket",)),
        ("hotspot", ("hotspotLevel",)),
    )
    for filter_name, row_names in checks:
        value = filters.get(filter_name)
        if value and str(value) not in {str(row.get(name, "")) for name in row_names}:
            return False
    search = str(filters.get("search") or "").strip()
    return _matches_text(row, search)


def _entity_for_key(dashboard_data: Mapping[str, Any], entity_key: str, query: str) -> Dict[str, Any]:
    entities = dashboard_data.get("entityDrilldowns") or []
    for entity in entities:
        if entity_key and entity.get("entityKey") == entity_key:
            return dict(entity)
    if query:
        for entity in entities:
            fields = [entity.get("label"), entity.get("stockCode"), entity.get("industryName")]
            if any(str(field or "").lower() == query.lower() for field in fields):
                return dict(entity)
        for entity in entities:
            fields = [entity.get("label"), entity.get("stockCode"), entity.get("industryName")]
            if any(query.lower() in str(field or "").lower() for field in fields):
                return dict(entity)
    return {}


def _matches_entity(row: Mapping[str, Any], entity: Mapping[str, Any]) -> bool:
    if not entity:
        return False
    if entity.get("entityType") == "company":
        return bool(
            (entity.get("stockCode") and row.get("stockCode") == entity.get("stockCode"))
            or (entity.get("label") and row.get("stockName") == entity.get("label"))
            or (entity.get("label") and row.get("entityName") == entity.get("label"))
        )
    label = entity.get("label")
    return bool(label and (row.get("industryName") == label or row.get("entityName") == label))


def _entities_for_keys(
    dashboard_data: Mapping[str, Any],
    entity_keys: Sequence[str],
    query: str = "",
) -> list[Dict[str, Any]]:
    entities: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for key in entity_keys:
        entity = _entity_for_key(dashboard_data, str(key or ""), "")
        entity_key = str(entity.get("entityKey") or "")
        if entity and entity_key not in seen:
            entities.append(entity)
            seen.add(entity_key)
    if not entities and query:
        for part in [item.strip() for item in query.replace("，", ",").split(",") if item.strip()]:
            entity = _entity_for_key(dashboard_data, "", part)
            entity_key = str(entity.get("entityKey") or "")
            if entity and entity_key not in seen:
                entities.append(entity)
                seen.add(entity_key)
    return entities


def _matches_any_entity(row: Mapping[str, Any], entities: Sequence[Mapping[str, Any]]) -> bool:
    return any(_matches_entity(row, entity) for entity in entities)


def _unique_count(rows: Sequence[Mapping[str, Any]], names: Sequence[str]) -> int:
    values = set()
    for row in rows:
        value = _first_present(row, names)
        if value:
            values.add(str(value))
    return len(values)


def build_ai_evidence(
    dashboard_data: Mapping[str, Any],
    *,
    scope: str = "selected",
    query: str = "",
    entity_key: str = "",
    entity_keys: Optional[Sequence[str]] = None,
    start_date: str = "",
    end_date: str = "",
    filters: Optional[Mapping[str, Any]] = None,
    max_reports: int = 8,
) -> Dict[str, Any]:
    scope = str(scope or "selected").strip() or "selected"
    scope_key = "current_filters" if scope == "global" else scope
    filters = dict(filters or {})
    if start_date:
        filters["startDate"] = start_date
    if end_date:
        filters["endDate"] = end_date
    max_reports = max(1, min(int(max_reports or 8), 20))
    selected_keys = [str(key) for key in (entity_keys or []) if str(key or "").strip()]
    if entity_key and entity_key not in selected_keys:
        selected_keys.insert(0, entity_key)
    entities = _entities_for_keys(dashboard_data, selected_keys, query=query)
    entity = entities[0] if entities else _entity_for_key(dashboard_data, entity_key, query)
    if entity and not entities:
        entities = [entity]

    if scope_key == "all":
        effective_filters: Dict[str, Any] = {}
    elif scope_key == "date_range":
        effective_filters = {
            "startDate": filters.get("startDate", ""),
            "endDate": filters.get("endDate", ""),
            "search": filters.get("search", ""),
        }
    else:
        effective_filters = dict(filters)

    reports = [row for row in (dashboard_data.get("reports") or []) if _matches_filters(row, effective_filters)]
    hotspots = [row for row in (dashboard_data.get("hotspots") or []) if _matches_filters(row, effective_filters)]
    opinions = [row for row in (dashboard_data.get("opinionTrends") or []) if _matches_filters(row, effective_filters)]

    entity_scopes = {"selected", "company", "companies", "industry", "industries", "hotspot", "hotspots"}
    if scope_key in entity_scopes and entities:
        reports = [row for row in reports if _matches_any_entity(row, entities)]
        hotspots = [row for row in hotspots if _matches_any_entity(row, entities)]
        opinions = [row for row in opinions if _matches_any_entity(row, entities)]
    elif scope_key == "query" and query:
        reports = [row for row in reports if _matches_text(row, query)]
        hotspots = [row for row in hotspots if _matches_text(row, query)]
        opinions = [row for row in opinions if _matches_text(row, query)]

    reports = sorted(reports, key=lambda row: str(_first_present(row, ("date", "publishDate"))), reverse=True)
    hotspots = sorted(
        hotspots,
        key=lambda row: (str(row.get("hotspotLevel") or ""), str(_first_present(row, ("latestPublishDate", "latestDate")))),
    )
    opinions = sorted(opinions, key=lambda row: str(row.get("latestDate") or ""), reverse=True)

    return {
        "scope": scope_key,
        "query": query,
        "filters": dict(effective_filters),
        "selectedScopeSummary": {
            "scope": scope_key,
            "query": query,
            "entityKeys": [entity.get("entityKey", "") for entity in entities if entity.get("entityKey")],
            "entities": [
                {
                    "entityKey": item.get("entityKey", ""),
                    "entityType": item.get("entityType", ""),
                    "label": item.get("label", ""),
                    "stockCode": item.get("stockCode", ""),
                    "industryName": item.get("industryName", ""),
                }
                for item in entities
            ],
            "reportCount": len(reports),
            "companyCount": _unique_count(reports, ("stockName", "stockCode", "entityName")),
            "industryCount": _unique_count(reports, ("industryName", "entityName")),
            "brokerCount": _unique_count(reports, ("orgName",)),
            "hotspotCount": len(hotspots),
        },
        "entity": {
            "entityKey": entity.get("entityKey", ""),
            "entityType": entity.get("entityType", ""),
            "label": entity.get("label", ""),
            "stockCode": entity.get("stockCode", ""),
            "industryName": entity.get("industryName", ""),
            "reportCount": entity.get("reportCount", ""),
            "brokerCount": entity.get("brokerCount", ""),
            "hotspotLevel": entity.get("hotspotLevel", ""),
            "reasonCodes": entity.get("reasonCodes", []),
            "opinionSummary": entity.get("opinionSummary", {}),
        },
        "sampleCounts": {
            "reports": len(reports),
            "hotspots": len(hotspots),
            "opinionTrends": len(opinions),
        },
        "reports": [_compact_report(row) for row in reports[:max_reports]],
        "hotspots": [_compact_hotspot(row) for row in hotspots[:10]],
        "opinionTrends": [_compact_opinion(row) for row in opinions[:12]],
        "aggregateHints": dashboard_data.get("aggregates", {}),
    }


def build_ai_messages(
    evidence: Mapping[str, Any],
    instruction: str = "",
    template_id: str = "general_research",
    template_prompt: str = "",
) -> list[dict[str, str]]:
    template = resolve_ai_prompt_template(template_id)
    prompt_body = template_prompt.strip() or template["instruction"]
    system = (
        "你是卖方研报研究助手。只基于用户提供的 JSON evidence 分析，"
        "不要编造 evidence 之外的事实。输出使用中文。"
    )
    user_parts = [
        f"分析模板：{template['name']}（{template['id']}）",
        prompt_body,
        COMMON_OUTPUT_REQUIREMENTS,
        "JSON evidence:",
        json.dumps(evidence, ensure_ascii=False, separators=(",", ":")),
    ]
    if instruction.strip():
        user_parts.append(f"用户额外要求：{instruction.strip()}")
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n".join(user_parts)}]


def analyze_with_ai(
    config: AIConfig,
    evidence: Mapping[str, Any],
    instruction: str = "",
    template_id: str = "general_research",
    template_prompt: str = "",
    http_post: Optional[AIHttpPost] = None,
) -> Dict[str, Any]:
    messages = build_ai_messages(
        evidence,
        instruction=instruction,
        template_id=template_id,
        template_prompt=template_prompt,
    )
    result = analyze_messages_with_ai(config, messages, http_post=http_post)
    result["template"] = {**resolve_ai_prompt_template(template_id), "customPrompt": bool(template_prompt.strip())}
    result["evidence"] = evidence
    result.pop("response", None)
    return result
