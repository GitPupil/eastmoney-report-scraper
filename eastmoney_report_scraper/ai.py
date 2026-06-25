"""Eastmoney-specific AI analysis helpers.

Generic provider wiring lives in :mod:`eastmoney_report_scraper.ai_connector`.
Keep this file focused on report evidence selection and research prompts.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
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
    load_ai_config_for_profile,
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
from .constants import (
    DEFAULT_AI_ANALYSIS_DIR_NAME,
    DEFAULT_AI_BATCH_HISTORY_NAME,
    DEFAULT_AI_DAILY_BRIEF_NAME,
    DEFAULT_AI_HISTORY_NAME,
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
    "ai_history_path",
    "build_ai_evidence",
    "build_ai_evidence_quality",
    "build_ai_messages",
    "build_ai_payload",
    "build_ai_citations",
    "build_ai_record",
    "default_cc_switch_paths",
    "delete_ai_profile",
    "detect_ai_response_kind",
    "enrich_ai_result",
    "export_ai_analysis_markdown",
    "extract_ai_message_content",
    "history_record_markdown_path",
    "import_cc_switch_ai_config",
    "build_ai_batch_jobs",
    "build_ai_daily_brief",
    "build_rule_ai_consistency",
    "estimate_ai_request",
    "load_ai_config_for_profile",
    "run_ai_batch",
    "run_ai_comparison",
    "save_ai_batch_record",
    "list_ai_analysis_history",
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
    "save_ai_analysis_record",
    "set_active_ai_profile",
    "structure_ai_analysis",
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
    "引用具体证据时优先使用 sourceId，例如 [R1]、[H1]、[O1]。"
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
        "infoCode": row.get("infoCode", ""),
        "date": _first_present(row, ("date", "publishDate")),
        "title": row.get("title", ""),
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
        "file": row.get("file", ""),
        "fileHref": row.get("fileHref", ""),
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
        "previousScore": row.get("previousScore", ""),
        "latestScore": row.get("latestScore", ""),
    }


def _with_source_id(row: Dict[str, Any], prefix: str, index: int) -> Dict[str, Any]:
    return {"sourceId": f"{prefix}{index}", **row}


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
    compact_reports = [_with_source_id(_compact_report(row), "R", index) for index, row in enumerate(reports[:max_reports], start=1)]
    compact_hotspots = [_with_source_id(_compact_hotspot(row), "H", index) for index, row in enumerate(hotspots[:10], start=1)]
    compact_opinions = [_with_source_id(_compact_opinion(row), "O", index) for index, row in enumerate(opinions[:12], start=1)]

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
        "reports": compact_reports,
        "hotspots": compact_hotspots,
        "opinionTrends": compact_opinions,
        "aggregateHints": dashboard_data.get("aggregates", {}),
    }


SECTION_KEYS = {
    "coreConclusion": ("核心结论", "结论", "核心观点"),
    "bullishEvidence": ("支持证据", "正向证据", "看多证据", "利好证据"),
    "bearishEvidence": ("反向证据", "风险", "看空证据", "负面证据"),
    "opinionChange": ("观点变化", "评级变化", "目标价", "eps", "signal score"),
    "brokerConsensus": ("分歧", "券商共识", "机构共识", "一致预期"),
    "nextWatch": ("后续观察", "后续跟踪", "跟踪项", "观察清单"),
    "confidence": ("置信度", "信心", "可信度"),
}


def _section_key(line: str) -> str:
    text = re.sub(r"^[#\s>*\-0-9.、一二三四五六七八九十]+", "", str(line or "").strip())
    text = text.strip("：:[]【】 ")
    lowered = text.lower()
    for key, names in SECTION_KEYS.items():
        if any(name.lower() in lowered for name in names):
            return key
    return ""


def structure_ai_analysis(analysis_text: str, evidence: Mapping[str, Any]) -> Dict[str, Any]:
    structured: Dict[str, Any] = {
        "coreConclusion": "",
        "bullishEvidence": "",
        "bearishEvidence": "",
        "opinionChange": "",
        "brokerConsensus": "",
        "nextWatch": "",
        "confidence": "",
        "sourceIds": sorted(set(re.findall(r"\b[HRO]\d+\b", analysis_text or ""))),
        "sourceReportIds": sorted(set(re.findall(r"\bR\d+\b", analysis_text or ""))),
    }
    current_key = ""
    buffers: Dict[str, list[str]] = {key: [] for key in structured if key not in {"sourceIds", "sourceReportIds"}}
    for line in str(analysis_text or "").splitlines():
        key = _section_key(line)
        if key:
            current_key = key
            remainder = re.split(r"[:：]", line, maxsplit=1)
            if len(remainder) == 2 and remainder[1].strip():
                buffers[current_key].append(remainder[1].strip())
            continue
        if current_key and line.strip():
            buffers[current_key].append(line.rstrip())
    for key, lines in buffers.items():
        structured[key] = "\n".join(lines).strip()
    if not structured["coreConclusion"]:
        compact = " ".join(str(analysis_text or "").split())
        structured["coreConclusion"] = compact[:420]
    if not structured["sourceIds"]:
        structured["sourceIds"] = [citation["sourceId"] for citation in build_ai_citations(evidence)[:5]]
        structured["sourceReportIds"] = [source_id for source_id in structured["sourceIds"] if source_id.startswith("R")]
    return structured


def _citation_label(parts: Sequence[Any]) -> str:
    return " / ".join(str(part) for part in parts if part not in (None, ""))


def build_ai_citations(evidence: Mapping[str, Any]) -> list[Dict[str, Any]]:
    citations: list[Dict[str, Any]] = []
    for row in evidence.get("reports") or []:
        source_id = str(row.get("sourceId") or "")
        if not source_id:
            continue
        citations.append(
            {
                "sourceId": source_id,
                "sourceType": "report",
                "label": _citation_label(
                    [
                        row.get("date"),
                        row.get("stockName") or row.get("stockCode"),
                        row.get("orgName"),
                        row.get("title") or row.get("summary"),
                    ]
                ),
                "date": row.get("date", ""),
                "stockName": row.get("stockName", ""),
                "stockCode": row.get("stockCode", ""),
                "industryName": row.get("industryName", ""),
                "orgName": row.get("orgName", ""),
                "rating": row.get("rating", ""),
                "targetPrice": row.get("targetPrice", ""),
                "epsForecast": row.get("epsForecast", ""),
                "signalScore": row.get("signalScore", ""),
                "fileHref": row.get("fileHref", ""),
            }
        )
    for row in evidence.get("hotspots") or []:
        source_id = str(row.get("sourceId") or "")
        if not source_id:
            continue
        citations.append(
            {
                "sourceId": source_id,
                "sourceType": "hotspot",
                "label": _citation_label(
                    [
                        row.get("entityName") or row.get("stockCode"),
                        row.get("industryName"),
                        row.get("hotspotLevel"),
                        ", ".join(row.get("reasonCodes") or []),
                    ]
                ),
                "entityName": row.get("entityName", ""),
                "stockCode": row.get("stockCode", ""),
                "industryName": row.get("industryName", ""),
                "hotspotLevel": row.get("hotspotLevel", ""),
                "reasonCodes": row.get("reasonCodes", []),
            }
        )
    for row in evidence.get("opinionTrends") or []:
        source_id = str(row.get("sourceId") or "")
        if not source_id:
            continue
        citations.append(
            {
                "sourceId": source_id,
                "sourceType": "opinion",
                "label": _citation_label(
                    [
                        row.get("stockName") or row.get("stockCode"),
                        row.get("orgName"),
                        f"{row.get('previousDate', '')}->{row.get('latestDate', '')}",
                        row.get("ratingChange") or row.get("scoreDirection"),
                    ]
                ),
                "stockName": row.get("stockName", ""),
                "stockCode": row.get("stockCode", ""),
                "industryName": row.get("industryName", ""),
                "orgName": row.get("orgName", ""),
                "previousDate": row.get("previousDate", ""),
                "latestDate": row.get("latestDate", ""),
                "ratingChange": row.get("ratingChange", ""),
                "targetDirection": row.get("targetDirection", ""),
                "epsDirection": row.get("epsDirection", ""),
                "scoreDirection": row.get("scoreDirection", ""),
            }
        )
    return citations


def build_ai_evidence_quality(evidence: Mapping[str, Any]) -> Dict[str, Any]:
    counts = evidence.get("sampleCounts") or {}
    summary = evidence.get("selectedScopeSummary") or {}
    sampled_reports = len(evidence.get("reports") or [])
    full_reports = int(counts.get("reports") or 0)
    warnings: list[str] = []
    if full_reports <= 0:
        warnings.append("当前范围没有命中研报，AI 结论只能基于空样本。")
    if full_reports > sampled_reports:
        warnings.append(f"当前范围命中 {full_reports} 篇研报，本次只发送最近 {sampled_reports} 篇作为 evidence 样本。")
    if full_reports > 0 and int(counts.get("opinionTrends") or 0) <= 0:
        warnings.append("当前范围没有连续观点变化记录，评级/目标价/EPS 趋势判断会偏弱。")
    if full_reports > 0 and int(counts.get("hotspots") or 0) <= 0:
        warnings.append("当前范围没有热点信号记录，热点解释主要依赖研报明细。")
    broker_count = int(summary.get("brokerCount") or 0)
    if full_reports > 1 and broker_count <= 1:
        warnings.append("当前范围券商覆盖较少，机构共识和分歧判断的可靠性有限。")
    level = "empty" if full_reports <= 0 else "warn" if warnings else "good"
    return {
        "ok": full_reports > 0,
        "level": level,
        "warnings": warnings,
        "checks": {
            "reportCount": full_reports,
            "sampledReportCount": sampled_reports,
            "hotspotCount": int(counts.get("hotspots") or 0),
            "opinionTrendCount": int(counts.get("opinionTrends") or 0),
            "companyCount": int(summary.get("companyCount") or 0),
            "industryCount": int(summary.get("industryCount") or 0),
            "brokerCount": broker_count,
        },
    }


def _stable_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_payload(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ai_history_path(output_dir: Path, history_name: str = DEFAULT_AI_HISTORY_NAME) -> Path:
    return Path(output_dir).expanduser() / history_name


def _safe_slug(value: Any, fallback: str = "ai-analysis") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff_-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return (text or fallback)[:48]


def history_record_markdown_path(output_dir: Path, record: Mapping[str, Any]) -> Path:
    relative = str(record.get("markdownFile") or "")
    return Path(output_dir).expanduser() / relative


def _public_request(payload: Mapping[str, Any]) -> Dict[str, Any]:
    allowed = (
        "scope",
        "templateId",
        "entityKey",
        "entityKeys",
        "startDate",
        "endDate",
        "query",
        "filters",
        "instruction",
        "maxReports",
    )
    data = {key: payload.get(key) for key in allowed if key in payload}
    data["hasCustomPrompt"] = bool(str(payload.get("templatePrompt") or "").strip())
    if payload.get("templatePrompt"):
        data["templatePromptHash"] = hashlib.sha256(str(payload.get("templatePrompt")).encode("utf-8")).hexdigest()
    return data


def enrich_ai_result(result: Mapping[str, Any]) -> Dict[str, Any]:
    enriched = dict(result)
    evidence = enriched.get("evidence") or {}
    analysis = str(enriched.get("analysis") or "")
    enriched["quality"] = build_ai_evidence_quality(evidence)
    enriched["citations"] = build_ai_citations(evidence)
    enriched["structured"] = structure_ai_analysis(analysis, evidence)
    enriched["evidenceHash"] = _hash_payload({"evidence": evidence})
    return enriched


def build_ai_record(result: Mapping[str, Any], request_payload: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    enriched = enrich_ai_result(result)
    request_data = _public_request(request_payload or {})
    hash_input = {
        "evidenceHash": enriched.get("evidenceHash"),
        "template": enriched.get("template", {}),
        "request": request_data,
        "provider": enriched.get("provider", ""),
        "model": enriched.get("model", ""),
    }
    record_hash = _hash_payload(hash_input)
    created_at = _utc_now_iso()
    summary = enriched.get("evidence", {}).get("selectedScopeSummary") or {}
    slug_source = summary.get("query") or (summary.get("entities") or [{}])[0].get("label") or summary.get("scope")
    record_id = f"{created_at.replace(':', '').replace('+', 'Z')}-{record_hash[:10]}"
    markdown_file = f"{DEFAULT_AI_ANALYSIS_DIR_NAME}/{record_id}-{_safe_slug(slug_source)}.md"
    return {
        "id": record_id,
        "createdAt": created_at,
        "scope": summary.get("scope", ""),
        "query": summary.get("query", ""),
        "provider": enriched.get("provider", ""),
        "model": enriched.get("model", ""),
        "template": enriched.get("template", {}),
        "request": request_data,
        "usage": enriched.get("usage", {}),
        "evidenceHash": enriched.get("evidenceHash", ""),
        "recordHash": record_hash,
        "sampleCounts": enriched.get("evidence", {}).get("sampleCounts", {}),
        "selectedScopeSummary": summary,
        "quality": enriched.get("quality", {}),
        "citations": enriched.get("citations", []),
        "structured": enriched.get("structured", {}),
        "analysis": enriched.get("analysis", ""),
        "markdownFile": markdown_file,
        "markdownHref": markdown_file.replace("\\", "/"),
    }


def _markdown_escape(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def export_ai_analysis_markdown(output_dir: Path, record: Mapping[str, Any]) -> Path:
    output_root = Path(output_dir).expanduser()
    target = history_record_markdown_path(output_root, record)
    target.parent.mkdir(parents=True, exist_ok=True)
    structured = record.get("structured") or {}
    quality = record.get("quality") or {}
    warnings = quality.get("warnings") or []
    citations = record.get("citations") or []
    summary = record.get("selectedScopeSummary") or {}
    template = record.get("template") or {}
    lines = [
        f"# AI 分析 - {_markdown_escape(summary.get('query') or summary.get('scope') or record.get('id'))}",
        "",
        f"- 时间：{_markdown_escape(record.get('createdAt'))}",
        f"- 模板：{_markdown_escape(template.get('name') or template.get('id'))}",
        f"- 模型：{_markdown_escape(record.get('provider'))} / {_markdown_escape(record.get('model'))}",
        f"- 范围：{_markdown_escape(summary.get('scope'))}",
        (
            f"- 样本：研报 {record.get('sampleCounts', {}).get('reports', 0)}，"
            f"热点 {record.get('sampleCounts', {}).get('hotspots', 0)}，"
            f"观点变化 {record.get('sampleCounts', {}).get('opinionTrends', 0)}"
        ),
        f"- Evidence Hash：`{_markdown_escape(record.get('evidenceHash'))}`",
        "",
    ]
    if warnings:
        lines.extend(["## Evidence 质量提示", "", *[f"- {warning}" for warning in warnings], ""])
    section_titles = [
        ("coreConclusion", "核心结论"),
        ("bullishEvidence", "支持证据"),
        ("bearishEvidence", "反向证据"),
        ("opinionChange", "观点变化"),
        ("brokerConsensus", "分歧"),
        ("nextWatch", "后续观察"),
        ("confidence", "置信度"),
    ]
    for key, title in section_titles:
        value = _markdown_escape(structured.get(key))
        if value:
            lines.extend([f"## {title}", "", value, ""])
    lines.extend(["## 原始输出", "", _markdown_escape(record.get("analysis")), ""])
    if citations:
        lines.extend(["## 引用来源", ""])
        for citation in citations:
            label = _markdown_escape(citation.get("label") or citation.get("sourceId"))
            href = _markdown_escape(citation.get("fileHref"))
            suffix = f" ([原文]({href}))" if href else ""
            lines.append(f"- [{_markdown_escape(citation.get('sourceId'))}] {label}{suffix}")
        lines.append("")
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def save_ai_analysis_record(output_dir: Path, record: Mapping[str, Any]) -> Dict[str, Any]:
    output_root = Path(output_dir).expanduser()
    output_root.mkdir(parents=True, exist_ok=True)
    exported = export_ai_analysis_markdown(output_root, record)
    saved_record = dict(record)
    saved_record["markdownFile"] = str(exported.relative_to(output_root)).replace("\\", "/")
    saved_record["markdownHref"] = saved_record["markdownFile"]
    path = ai_history_path(output_root)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(saved_record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return saved_record


def list_ai_analysis_history(output_dir: Path, limit: int = 50) -> Dict[str, Any]:
    path = ai_history_path(Path(output_dir).expanduser())
    if not path.exists():
        return {"items": [], "count": 0, "historyPath": str(path)}
    rows: list[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            rows.append(dict(payload))
    rows = rows[-max(1, int(limit or 50)) :][::-1]
    return {"items": rows, "count": len(rows), "historyPath": str(path)}


def estimate_ai_request(
    evidence: Mapping[str, Any],
    instruction: str = "",
    template_id: str = "general_research",
    template_prompt: str = "",
    *,
    expected_output_tokens: int = 1200,
    input_price_per_1k: float = 0.0,
    output_price_per_1k: float = 0.0,
) -> Dict[str, Any]:
    messages = build_ai_messages(
        evidence,
        instruction=instruction,
        template_id=template_id,
        template_prompt=template_prompt,
    )
    text = "\n".join(message.get("content", "") for message in messages)
    # A simple local estimate: Chinese-heavy prompts are usually denser than
    # English tokenization, so char/2 is a conservative rough number.
    input_tokens = max(1, int(len(text) / 2))
    output_tokens = max(1, int(expected_output_tokens or 1200))
    total_tokens = input_tokens + output_tokens
    estimated_cost = None
    if input_price_per_1k or output_price_per_1k:
        estimated_cost = round((input_tokens / 1000) * input_price_per_1k + (output_tokens / 1000) * output_price_per_1k, 6)
    return {
        "inputChars": len(text),
        "estimatedInputTokens": input_tokens,
        "estimatedOutputTokens": output_tokens,
        "estimatedTotalTokens": total_tokens,
        "inputPricePer1k": input_price_per_1k,
        "outputPricePer1k": output_price_per_1k,
        "estimatedCost": estimated_cost,
        "currency": "USD" if estimated_cost is not None else "",
        "note": "Token count is a local rough estimate; cost is only calculated when per-1k token prices are supplied.",
    }


def _entity_key_for_hotspot(dashboard_data: Mapping[str, Any], hotspot: Mapping[str, Any]) -> str:
    entities = dashboard_data.get("entityDrilldowns") or []
    for entity in entities:
        if hotspot.get("entityType") == "company" and entity.get("entityType") == "company":
            if (hotspot.get("stockCode") and hotspot.get("stockCode") == entity.get("stockCode")) or (
                hotspot.get("entityName") and hotspot.get("entityName") == entity.get("label")
            ):
                return str(entity.get("entityKey") or "")
        if entity.get("entityType") == "industry" and (
            hotspot.get("entityName") == entity.get("label") or hotspot.get("industryName") == entity.get("label")
        ):
            return str(entity.get("entityKey") or "")
    return ""


def _entity_rank(entity: Mapping[str, Any]) -> tuple[int, int, int]:
    level_rank = {"STRONG": 4, "HOT": 3, "WATCH": 2}
    return (
        level_rank.get(str(entity.get("hotspotLevel") or "").upper(), 0),
        int(entity.get("brokerCount") or entity.get("brokerCount30d") or 0),
        int(entity.get("reportCount") or entity.get("coverage30d") or 0),
    )


def build_ai_batch_jobs(
    dashboard_data: Mapping[str, Any],
    *,
    batch_type: str = "daily_overview",
    limit: int = 5,
    filters: Optional[Mapping[str, Any]] = None,
) -> list[Dict[str, Any]]:
    batch_type = str(batch_type or "daily_overview").strip()
    limit = max(1, min(int(limit or 5), 10))
    filters = dict(filters or {})
    jobs: list[Dict[str, Any]] = []
    if batch_type == "daily_overview":
        return [
            {
                "jobId": "daily-overview",
                "name": "日度总览",
                "payload": {"scope": "current_filters", "filters": filters, "templateId": "daily_overview", "maxReports": 12},
            }
        ]
    if batch_type == "hotspots":
        hotspots = sorted(
            dashboard_data.get("hotspots") or [],
            key=lambda row: (
                {"STRONG": 0, "HOT": 1, "WATCH": 2}.get(str(row.get("hotspotLevel") or "").upper(), 9),
                -int(float(row.get("coverage30d") or row.get("brokerCount30d") or 0)),
            ),
        )
        for index, hotspot in enumerate(hotspots[:limit], start=1):
            entity_key = _entity_key_for_hotspot(dashboard_data, hotspot)
            name = str(hotspot.get("entityName") or hotspot.get("stockCode") or hotspot.get("industryName") or f"热点 {index}")
            jobs.append(
                {
                    "jobId": f"hotspot-{index}",
                    "name": f"热点：{name}",
                    "payload": {
                        "scope": "hotspot",
                        "entityKey": entity_key,
                        "query": name,
                        "filters": filters,
                        "templateId": "hotspot_radar",
                        "maxReports": 8,
                    },
                }
            )
        return jobs
    entity_type = "industry" if batch_type == "industries" else "company"
    template_id = "industry_trend" if entity_type == "industry" else "company_deep_dive"
    scope = "industry" if entity_type == "industry" else "company"
    entities = [
        entity
        for entity in (dashboard_data.get("entityDrilldowns") or [])
        if entity.get("entityType") == entity_type and entity.get("entityKey")
    ]
    for index, entity in enumerate(sorted(entities, key=_entity_rank, reverse=True)[:limit], start=1):
        label = str(entity.get("label") or entity.get("stockCode") or f"{entity_type}-{index}")
        jobs.append(
            {
                "jobId": f"{entity_type}-{index}",
                "name": f"{'行业' if entity_type == 'industry' else '公司'}：{label}",
                "payload": {
                    "scope": scope,
                    "entityKey": entity.get("entityKey", ""),
                    "query": label,
                    "filters": filters,
                    "templateId": template_id,
                    "maxReports": 8,
                },
            }
        )
    return jobs


def build_rule_ai_consistency(record: Mapping[str, Any]) -> Dict[str, Any]:
    structured = record.get("structured") or {}
    evidence = {
        "sampleCounts": record.get("sampleCounts") or {},
        "selectedScopeSummary": record.get("selectedScopeSummary") or {},
    }
    text = " ".join(str(structured.get(key) or "") for key in ("coreConclusion", "bullishEvidence", "bearishEvidence", "opinionChange"))
    text_lower = text.lower()
    source_ids = set(structured.get("sourceIds") or [])
    citation_ids = {citation.get("sourceId") for citation in record.get("citations") or []}
    checks: list[Dict[str, Any]] = []
    if source_ids and not source_ids.issubset(citation_ids):
        checks.append({"level": "warn", "code": "UNKNOWN_SOURCE_ID", "message": "AI 输出引用了 evidence 中不存在的 sourceId。"})
    bearish_words = ("风险", "下调", "转弱", "承压", "下降", "不及预期", "bearish")
    bullish_words = ("上调", "增强", "改善", "共振", "景气", "买入", "bullish")
    sample_counts = evidence.get("sampleCounts") or {}
    if int(sample_counts.get("hotspots") or 0) > 0 and any(word in text_lower for word in bearish_words):
        checks.append({"level": "warn", "code": "HOTSPOT_WITH_BEARISH_TONE", "message": "规则层有热点信号，但 AI 文本出现偏弱或风险表述，建议人工复核。"})
    if int(sample_counts.get("opinionTrends") or 0) <= 0 and any(word in text_lower for word in ("连续", "持续", "上修", "下修")):
        checks.append({"level": "warn", "code": "TREND_WITHOUT_HISTORY", "message": "缺少连续观点记录，但 AI 使用了趋势性表述。"})
    if int(sample_counts.get("reports") or 0) > 0 and not any(word in text_lower for word in bullish_words + bearish_words):
        checks.append({"level": "info", "code": "LOW_DIRECTIONALITY", "message": "AI 文本方向性较弱，可结合 deterministic signalScore 再判断。"})
    return {
        "level": "warn" if any(check["level"] == "warn" for check in checks) else "ok",
        "checks": checks,
    }


def ai_batch_history_path(output_dir: Path, history_name: str = DEFAULT_AI_BATCH_HISTORY_NAME) -> Path:
    return Path(output_dir).expanduser() / history_name


def save_ai_batch_record(output_dir: Path, batch_record: Mapping[str, Any]) -> Dict[str, Any]:
    output_root = Path(output_dir).expanduser()
    output_root.mkdir(parents=True, exist_ok=True)
    path = ai_batch_history_path(output_root)
    saved = dict(batch_record)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(saved, ensure_ascii=False, separators=(",", ":")) + "\n")
    return saved


def build_ai_daily_brief(output_dir: Path, batch_record: Mapping[str, Any], brief_name: str = DEFAULT_AI_DAILY_BRIEF_NAME) -> Path:
    output_root = Path(output_dir).expanduser()
    target = output_root / brief_name
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# AI Daily Brief",
        "",
        f"- Batch ID: `{batch_record.get('id', '')}`",
        f"- Created At: {batch_record.get('createdAt', '')}",
        f"- Batch Type: {batch_record.get('batchType', '')}",
        f"- Jobs: {batch_record.get('okCount', 0)} ok / {batch_record.get('errorCount', 0)} error",
        "",
    ]
    for item in batch_record.get("items") or []:
        record = item.get("record") or {}
        if item.get("ok") and record:
            structured = record.get("structured") or {}
            href = record.get("markdownHref") or record.get("markdownFile") or ""
            title = item.get("name") or record.get("query") or record.get("scope") or item.get("jobId")
            lines.extend(
                [
                    f"## {title}",
                    "",
                    structured.get("coreConclusion") or record.get("analysis", "")[:300],
                    "",
                    f"- Evidence: `{record.get('evidenceHash', '')}`",
                    f"- Markdown: [{href}]({href})" if href else "- Markdown: -",
                    "",
                ]
            )
        else:
            lines.extend([f"## {item.get('name') or item.get('jobId')}", "", f"- Error: {item.get('error', '')}", ""])
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def run_ai_batch(
    config: AIConfig,
    dashboard_data: Mapping[str, Any],
    output_dir: Path,
    *,
    batch_type: str = "daily_overview",
    limit: int = 5,
    filters: Optional[Mapping[str, Any]] = None,
    instruction: str = "",
    http_post: Optional[AIHttpPost] = None,
    write_daily_brief: bool = True,
    input_price_per_1k: float = 0.0,
    output_price_per_1k: float = 0.0,
) -> Dict[str, Any]:
    jobs = build_ai_batch_jobs(dashboard_data, batch_type=batch_type, limit=limit, filters=filters)
    batch_id = f"{_utc_now_iso().replace(':', '').replace('+', 'Z')}-{_hash_payload({'jobs': jobs})[:10]}"
    items: list[Dict[str, Any]] = []
    for job in jobs:
        payload = {**job.get("payload", {}), "instruction": instruction}
        evidence = build_ai_evidence(
            dashboard_data,
            scope=str(payload.get("scope") or "selected"),
            query=str(payload.get("query") or ""),
            entity_key=str(payload.get("entityKey") or ""),
            entity_keys=payload.get("entityKeys") or [],
            filters=payload.get("filters") or {},
            max_reports=int(payload.get("maxReports") or 8),
        )
        estimate = estimate_ai_request(
            evidence,
            instruction=instruction,
            template_id=str(payload.get("templateId") or "general_research"),
            input_price_per_1k=input_price_per_1k,
            output_price_per_1k=output_price_per_1k,
        )
        try:
            result = analyze_with_ai(
                config,
                evidence,
                instruction=instruction,
                template_id=str(payload.get("templateId") or "general_research"),
                http_post=http_post,
            )
            record = build_ai_record(result, payload)
            record["estimate"] = estimate
            record["consistency"] = build_rule_ai_consistency(record)
            saved = save_ai_analysis_record(output_dir, record)
            items.append({"ok": True, "jobId": job.get("jobId"), "name": job.get("name"), "record": saved})
        except Exception as exc:
            items.append({"ok": False, "jobId": job.get("jobId"), "name": job.get("name"), "error": redact_secrets(str(exc), [config.api_token]), "estimate": estimate})
    batch_record = {
        "id": batch_id,
        "createdAt": _utc_now_iso(),
        "batchType": batch_type,
        "jobCount": len(jobs),
        "okCount": sum(1 for item in items if item.get("ok")),
        "errorCount": sum(1 for item in items if not item.get("ok")),
        "items": items,
    }
    if write_daily_brief:
        brief_path = build_ai_daily_brief(output_dir, batch_record)
        batch_record["dailyBriefFile"] = str(brief_path.relative_to(Path(output_dir).expanduser())).replace("\\", "/")
        batch_record["dailyBriefHref"] = batch_record["dailyBriefFile"]
    return save_ai_batch_record(output_dir, batch_record)


def run_ai_comparison(
    configs: Sequence[tuple[str, AIConfig]],
    evidence: Mapping[str, Any],
    output_dir: Path,
    *,
    request_payload: Optional[Mapping[str, Any]] = None,
    instruction: str = "",
    template_id: str = "general_research",
    http_post: Optional[AIHttpPost] = None,
) -> Dict[str, Any]:
    comparison_id = f"{_utc_now_iso().replace(':', '').replace('+', 'Z')}-{_hash_payload({'evidence': evidence, 'template': template_id})[:10]}"
    items: list[Dict[str, Any]] = []
    for profile_id, config in configs:
        estimate = estimate_ai_request(evidence, instruction=instruction, template_id=template_id)
        try:
            result = analyze_with_ai(config, evidence, instruction=instruction, template_id=template_id, http_post=http_post)
            record = build_ai_record(result, request_payload or {"scope": evidence.get("scope"), "templateId": template_id})
            record["comparisonId"] = comparison_id
            record["profileId"] = profile_id
            record["estimate"] = estimate
            record["consistency"] = build_rule_ai_consistency(record)
            saved = save_ai_analysis_record(output_dir, record)
            items.append({"ok": True, "profileId": profile_id, "record": saved})
        except Exception as exc:
            items.append({"ok": False, "profileId": profile_id, "error": redact_secrets(str(exc), [config.api_token]), "estimate": estimate})
    return {
        "ok": any(item.get("ok") for item in items),
        "comparisonId": comparison_id,
        "items": items,
        "evidenceHash": _hash_payload({"evidence": evidence}),
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
    return enrich_ai_result(result)
