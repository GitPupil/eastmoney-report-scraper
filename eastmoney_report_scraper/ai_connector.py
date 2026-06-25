"""Reusable AI provider connector.

This module is intentionally independent from the Eastmoney report domain. It
only uses the Python standard library, so other local projects can copy this
single file or import it directly.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib import error, request

DEFAULT_AI_CONFIG_NAME = "local_ai_config.json"
DEFAULT_AI_PROFILE_ID = "default"
VALID_AI_FORMATS = {"auto", "chat", "completions", "responses", "anthropic"}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class AIConfig:
    provider: str = "openai-compatible"
    base_url: str = "https://api.openai.com/v1/chat/completions"
    model: str = "gpt-4o-mini"
    api_token: str = ""
    timeout: int = 60
    api_format: str = "auto"


AIHttpPost = Callable[[AIConfig, Sequence[Mapping[str, str]]], Mapping[str, Any]]


def ai_config_path(output_dir: Path, config_path: Optional[Path] = None) -> Path:
    if config_path is not None:
        return Path(config_path).expanduser()
    return Path(output_dir).expanduser() / DEFAULT_AI_CONFIG_NAME


def mask_token(token: str) -> str:
    token = (token or "").strip()
    if not token:
        return ""
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:3]}...{token[-4:]}"


def redact_secrets(text: str, secrets: Sequence[str]) -> str:
    safe = str(text)
    for secret in secrets:
        secret = (secret or "").strip()
        if secret:
            safe = safe.replace(secret, mask_token(secret))
    return safe


def public_ai_settings(config: AIConfig, output_dir: Path, config_path: Optional[Path] = None) -> Dict[str, Any]:
    path = ai_config_path(output_dir, config_path=config_path)
    return {
        "provider": config.provider,
        "baseUrl": config.base_url,
        "model": config.model,
        "apiFormat": config.api_format,
        "hasToken": bool(config.api_token.strip()),
        "maskedToken": mask_token(config.api_token),
        "timeout": config.timeout,
        "configPath": str(path),
    }


def normalize_ai_config_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    data = dict(payload)
    if "baseUrl" in data and "base_url" not in data:
        data["base_url"] = data["baseUrl"]
    if "apiToken" in data and "api_token" not in data:
        data["api_token"] = data["apiToken"]
    if "apiFormat" in data and "api_format" not in data:
        data["api_format"] = data["apiFormat"]
    return data


def _safe_profile_id(value: Any, fallback: str = DEFAULT_AI_PROFILE_ID) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in text)
    safe = "-".join(part for part in safe.split("-") if part)
    return safe or fallback


def _normalize_api_format(value: Any) -> str:
    api_format = str(value or "auto").strip().lower()
    return api_format if api_format in VALID_AI_FORMATS else "auto"


def _normalize_timeout(value: Any) -> int:
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        timeout = 60
    return max(5, timeout)


def _profile_from_config(config: AIConfig, profile_id: str = DEFAULT_AI_PROFILE_ID, name: str = "Default") -> Dict[str, Any]:
    return {
        "id": _safe_profile_id(profile_id),
        "name": str(name or profile_id or "Default"),
        "provider": config.provider,
        "base_url": config.base_url,
        "model": config.model,
        "api_format": _normalize_api_format(config.api_format),
        "api_token": config.api_token,
        "timeout": _normalize_timeout(config.timeout),
    }


def _config_from_profile(profile: Mapping[str, Any]) -> AIConfig:
    data = normalize_ai_config_payload(profile)
    defaults = AIConfig()
    return AIConfig(
        provider=str(data.get("provider") or "openai-compatible"),
        base_url=str(data.get("base_url") or defaults.base_url),
        model=str(data.get("model") or defaults.model),
        api_token=str(data.get("api_token") or ""),
        timeout=_normalize_timeout(data.get("timeout")),
        api_format=_normalize_api_format(data.get("api_format")),
    )


def _normalize_profile(profile: Mapping[str, Any], fallback_id: str = DEFAULT_AI_PROFILE_ID) -> Dict[str, Any]:
    data = normalize_ai_config_payload(profile)
    config = _config_from_profile(data)
    profile_id = _safe_profile_id(data.get("id") or data.get("profileId") or data.get("profile_id"), fallback=fallback_id)
    name = str(data.get("name") or data.get("profileName") or data.get("profile_name") or profile_id)
    return _profile_from_config(config, profile_id=profile_id, name=name)


def _default_profile_store() -> Dict[str, Any]:
    return {"activeProfileId": DEFAULT_AI_PROFILE_ID, "profiles": [_profile_from_config(AIConfig())]}


def _legacy_config_to_profile_store(raw: Mapping[str, Any]) -> Dict[str, Any]:
    data = normalize_ai_config_payload(raw)
    allowed = {field.name for field in AIConfig.__dataclass_fields__.values()}
    values = {key: data[key] for key in allowed if key in data}
    config = AIConfig(**values)
    return {"activeProfileId": DEFAULT_AI_PROFILE_ID, "profiles": [_profile_from_config(config)]}


def load_ai_profiles(output_dir: Path, config_path: Optional[Path] = None) -> Dict[str, Any]:
    path = ai_config_path(output_dir, config_path=config_path)
    if not path.exists():
        return _default_profile_store()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        return _default_profile_store()
    raw_profiles = raw.get("profiles")
    if not isinstance(raw_profiles, list):
        return _legacy_config_to_profile_store(raw)

    profiles: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_profile in enumerate(raw_profiles, start=1):
        if not isinstance(raw_profile, Mapping):
            continue
        profile = _normalize_profile(raw_profile, fallback_id=f"profile-{index}")
        if profile["id"] in seen:
            profile["id"] = _safe_profile_id(f"{profile['id']}-{index}")
        seen.add(profile["id"])
        profiles.append(profile)
    if not profiles:
        profiles = [_profile_from_config(AIConfig())]
    active_profile_id = _safe_profile_id(raw.get("activeProfileId") or raw.get("active_profile_id") or profiles[0]["id"])
    if active_profile_id not in {profile["id"] for profile in profiles}:
        active_profile_id = profiles[0]["id"]
    return {"activeProfileId": active_profile_id, "profiles": profiles}


def save_ai_profiles(store: Mapping[str, Any], output_dir: Path, config_path: Optional[Path] = None) -> Path:
    profiles = [
        _normalize_profile(profile, fallback_id=f"profile-{index}")
        for index, profile in enumerate(store.get("profiles") or [], start=1)
        if isinstance(profile, Mapping)
    ]
    if not profiles:
        profiles = [_profile_from_config(AIConfig())]
    active_profile_id = _safe_profile_id(store.get("activeProfileId") or profiles[0]["id"])
    if active_profile_id not in {profile["id"] for profile in profiles}:
        active_profile_id = profiles[0]["id"]
    path = ai_config_path(output_dir, config_path=config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"activeProfileId": active_profile_id, "profiles": profiles}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _active_profile(store: Mapping[str, Any]) -> Dict[str, Any]:
    profiles = list(store.get("profiles") or [])
    active_profile_id = store.get("activeProfileId")
    for profile in profiles:
        if profile.get("id") == active_profile_id:
            return dict(profile)
    return dict(profiles[0]) if profiles else _profile_from_config(AIConfig())


def public_ai_profile(profile: Mapping[str, Any], *, active_profile_id: str = "") -> Dict[str, Any]:
    config = _config_from_profile(profile)
    profile_id = str(profile.get("id") or DEFAULT_AI_PROFILE_ID)
    return {
        "id": profile_id,
        "name": str(profile.get("name") or profile_id),
        "provider": config.provider,
        "baseUrl": config.base_url,
        "model": config.model,
        "apiFormat": config.api_format,
        "hasToken": bool(config.api_token.strip()),
        "maskedToken": mask_token(config.api_token),
        "timeout": config.timeout,
        "isActive": bool(active_profile_id and profile_id == active_profile_id),
    }


def public_ai_profile_settings(output_dir: Path, config_path: Optional[Path] = None) -> Dict[str, Any]:
    path = ai_config_path(output_dir, config_path=config_path)
    store = load_ai_profiles(output_dir, config_path=config_path)
    active = _active_profile(store)
    active_public = public_ai_profile(active, active_profile_id=str(store.get("activeProfileId") or ""))
    profiles_public = [
        public_ai_profile(profile, active_profile_id=str(store.get("activeProfileId") or ""))
        for profile in store.get("profiles", [])
    ]
    return {
        **active_public,
        "activeProfileId": active_public["id"],
        "profiles": profiles_public,
        "configPath": str(path),
    }


def load_ai_config(output_dir: Path, config_path: Optional[Path] = None) -> AIConfig:
    store = load_ai_profiles(output_dir, config_path=config_path)
    return _config_from_profile(_active_profile(store))


def load_ai_config_for_profile(output_dir: Path, profile_id: str, config_path: Optional[Path] = None) -> AIConfig:
    store = load_ai_profiles(output_dir, config_path=config_path)
    requested_profile_id = _safe_profile_id(profile_id)
    for profile in store.get("profiles", []):
        if profile.get("id") == requested_profile_id:
            return _config_from_profile(profile)
    raise ValueError(f"AI profile not found: {profile_id}")


def save_ai_config(config: AIConfig, output_dir: Path, config_path: Optional[Path] = None) -> Path:
    return save_ai_profiles(
        {"activeProfileId": DEFAULT_AI_PROFILE_ID, "profiles": [_profile_from_config(config)]},
        output_dir,
        config_path=config_path,
    )


def update_ai_config(output_dir: Path, payload: Mapping[str, Any], config_path: Optional[Path] = None) -> AIConfig:
    store = load_ai_profiles(output_dir, config_path=config_path)
    data = normalize_ai_config_payload(payload)
    requested_profile_id = _safe_profile_id(
        data.get("profileId") or data.get("profile_id") or store.get("activeProfileId") or DEFAULT_AI_PROFILE_ID
    )
    profiles = [dict(profile) for profile in store.get("profiles", [])]
    current_profile = next((profile for profile in profiles if profile.get("id") == requested_profile_id), None)
    if current_profile is None:
        current_profile = _profile_from_config(
            AIConfig(),
            profile_id=requested_profile_id,
            name=str(data.get("profileName") or data.get("profile_name") or requested_profile_id),
        )
        profiles.append(current_profile)
    current = _config_from_profile(current_profile)
    updates: Dict[str, Any] = {}
    for key in ("provider", "base_url", "model", "timeout", "api_format"):
        if key in data and data[key] not in (None, ""):
            updates[key] = data[key]
    if "timeout" in updates:
        updates["timeout"] = max(5, int(updates["timeout"]))
    if "api_format" in updates:
        api_format = str(updates["api_format"]).strip().lower()
        updates["api_format"] = api_format if api_format in VALID_AI_FORMATS else "auto"
    if data.get("clearToken"):
        updates["api_token"] = ""
    elif data.get("api_token"):
        updates["api_token"] = str(data["api_token"]).strip()
    config = replace(current, **updates)
    updated_profile = _profile_from_config(
        config,
        profile_id=requested_profile_id,
        name=str(
            data.get("profileName")
            or data.get("profile_name")
            or data.get("name")
            or current_profile.get("name")
            or requested_profile_id
        ),
    )
    profiles = [updated_profile if profile.get("id") == requested_profile_id else profile for profile in profiles]
    save_ai_profiles(
        {"activeProfileId": requested_profile_id, "profiles": profiles},
        output_dir,
        config_path=config_path,
    )
    return config


def set_active_ai_profile(output_dir: Path, profile_id: str, config_path: Optional[Path] = None) -> Dict[str, Any]:
    store = load_ai_profiles(output_dir, config_path=config_path)
    requested_profile_id = _safe_profile_id(profile_id)
    if requested_profile_id not in {profile["id"] for profile in store.get("profiles", [])}:
        raise ValueError(f"AI profile not found: {profile_id}")
    store["activeProfileId"] = requested_profile_id
    save_ai_profiles(store, output_dir, config_path=config_path)
    return public_ai_profile_settings(output_dir, config_path=config_path)


def delete_ai_profile(output_dir: Path, profile_id: str, config_path: Optional[Path] = None) -> Dict[str, Any]:
    store = load_ai_profiles(output_dir, config_path=config_path)
    requested_profile_id = _safe_profile_id(profile_id)
    if requested_profile_id == DEFAULT_AI_PROFILE_ID:
        raise ValueError("The default AI profile cannot be deleted.")
    profiles = [profile for profile in store.get("profiles", []) if profile.get("id") != requested_profile_id]
    if len(profiles) == len(store.get("profiles", [])):
        raise ValueError(f"AI profile not found: {profile_id}")
    store["profiles"] = profiles
    if requested_profile_id == store.get("activeProfileId"):
        store["activeProfileId"] = DEFAULT_AI_PROFILE_ID if any(
            profile.get("id") == DEFAULT_AI_PROFILE_ID for profile in profiles
        ) else profiles[0]["id"]
    save_ai_profiles(store, output_dir, config_path=config_path)
    return public_ai_profile_settings(output_dir, config_path=config_path)


def messages_to_prompt(messages: Sequence[Mapping[str, str]]) -> str:
    parts = []
    for message in messages:
        role = str(message.get("role") or "user").strip()
        content = str(message.get("content") or "").strip()
        if content:
            parts.append(f"{role.upper()}:\n{content}")
    return "\n\n".join(parts)


def messages_to_anthropic(messages: Sequence[Mapping[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
    system_parts: List[str] = []
    conversation: List[Dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "user").strip().lower()
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            system_parts.append(content)
        elif role == "assistant":
            conversation.append({"role": "assistant", "content": content})
        else:
            conversation.append({"role": "user", "content": content})
    if not conversation:
        conversation.append({"role": "user", "content": messages_to_prompt(messages)})
    return "\n\n".join(system_parts), conversation


def messages_to_responses(messages: Sequence[Mapping[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
    instructions: List[str] = []
    input_items: List[Dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "user").strip().lower()
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            instructions.append(content)
        elif role == "assistant":
            input_items.append({"role": "assistant", "content": content})
        else:
            input_items.append({"role": "user", "content": content})
    if not input_items:
        input_items.append({"role": "user", "content": messages_to_prompt(messages)})
    return "\n\n".join(instructions), input_items


def build_ai_payload(
    config: AIConfig,
    messages: Sequence[Mapping[str, str]],
    api_format: Optional[str] = None,
) -> Dict[str, Any]:
    selected_format = (api_format or config.api_format or "auto").strip().lower()
    if selected_format == "auto":
        selected_format = _preferred_auto_formats(config.base_url)[0]
    prompt = messages_to_prompt(messages)
    if selected_format == "completions":
        return {"model": config.model, "prompt": prompt, "temperature": 0.2}
    if selected_format == "responses":
        instructions, input_items = messages_to_responses(messages)
        payload: Dict[str, Any] = {
            "model": config.model,
            "input": input_items,
            "temperature": 0.2,
        }
        if instructions:
            payload["instructions"] = instructions
        return payload
    if selected_format == "anthropic":
        system, anthropic_messages = messages_to_anthropic(messages)
        payload = {
            "model": config.model,
            "max_tokens": 1200,
            "messages": anthropic_messages,
            "temperature": 0.2,
        }
        if system:
            payload["system"] = system
        return payload
    return {"model": config.model, "messages": list(messages), "temperature": 0.2}


def ai_http_error_hint(status_code: int, detail: str) -> str:
    detail_text = str(detail or "")
    detail_lower = detail_text.lower()
    if status_code == 403 and "1010" in detail_text:
        return (
            "接口返回 403/1010，通常表示 API 域名的 Cloudflare/WAF 拦截了本机请求。"
            "请确认接口地址是 Chat Completions API URL，例如 https://api.openai.com/v1/chat/completions，"
            "不是网页登录页；如果使用第三方兼容服务，可能需要更换 API 域名或按服务商要求配置代理/白名单。"
        )
    if status_code in {401, 403}:
        return "接口拒绝访问，请检查 token、模型权限、接口地址和服务商账号状态。"
    if status_code == 404:
        return (
            "接口不存在。很多第三方服务要求请求完整 endpoint："
            "Responses 需要 /v1/responses，Chat 需要 /v1/chat/completions，"
            "Text Completions 需要 /v1/completions，Anthropic 需要 /v1/messages。"
        )
    if status_code == 429:
        return "接口限流或额度不足，请稍后重试或检查服务商额度。"
    if status_code == 400 and "input must be a list" in detail_lower:
        return (
            "Responses 接口要求 input 是数组。当前连接器已经按数组发送；如果仍报错，"
            "请确认接口格式选择 Responses(input)，并检查第三方服务是否兼容 OpenAI Responses API。"
        )
    if status_code == 400 and "unsupported parameter" in detail_lower:
        return (
            "接口不支持当前参数格式。请在 AI 面板把接口格式改成 Auto、Anthropic Messages、"
            "Text Completions(prompt) 或 Responses(input)，并确认 URL 与格式匹配。"
        )
    return ""


def _preferred_auto_formats(base_url: str) -> List[str]:
    normalized = str(base_url or "").lower()
    if "anthropic" in normalized:
        return ["anthropic", "chat", "completions", "responses"]
    if "/responses" in normalized:
        return ["responses", "chat", "completions"]
    if "/completions" in normalized and "/chat/" not in normalized:
        return ["completions", "chat", "responses"]
    return ["chat", "completions", "responses"]


class AIHTTPError(RuntimeError):
    def __init__(self, status_code: int, detail: str, token: str) -> None:
        self.status_code = status_code
        self.detail = detail
        hint = ai_http_error_hint(status_code, detail)
        message = f"AI request failed with HTTP {status_code}: {detail}"
        if hint:
            message = f"{message}\n\n{hint}"
        super().__init__(redact_secrets(message, [token]))


def _truncate_response_text(text: str, limit: int = 500) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def _json_loads_or_none(text: str) -> Optional[Mapping[str, Any]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, Mapping) else {"output_text": str(payload)}


def _parse_sse_response(text: str) -> Optional[Mapping[str, Any]]:
    json_events: List[Mapping[str, Any]] = []
    deltas: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        payload = _json_loads_or_none(data)
        if payload is None:
            continue
        json_events.append(payload)
        choices = payload.get("choices") or []
        if choices:
            delta = (choices[0] or {}).get("delta") or {}
            content = delta.get("content") or (choices[0] or {}).get("text")
            if content:
                deltas.append(str(content))
        event_delta = payload.get("delta")
        if event_delta:
            deltas.append(str(event_delta))
    if deltas:
        return {"output_text": "".join(deltas)}
    for payload in reversed(json_events):
        if payload.get("response"):
            response = payload.get("response")
            return response if isinstance(response, Mapping) else {"output_text": str(response)}
        if any(key in payload for key in ("choices", "content", "output", "output_text")):
            return payload
    return None


def parse_ai_response_body(text: str) -> Mapping[str, Any]:
    stripped = str(text or "").strip()
    if not stripped:
        raise RuntimeError("AI response body is empty. The provider returned HTTP 200 with no JSON content.")
    payload = _json_loads_or_none(stripped)
    if payload is not None:
        return payload
    sse_payload = _parse_sse_response(stripped)
    if sse_payload is not None:
        return sse_payload
    if stripped.startswith("<"):
        raise RuntimeError(f"AI response was HTML, not JSON: {_truncate_response_text(stripped)}")
    return {"output_text": stripped}


def detect_ai_response_kind(text: str) -> str:
    stripped = str(text or "").strip()
    if not stripped:
        return "empty"
    if stripped.startswith("<"):
        return "html"
    if stripped.startswith("data:"):
        return "sse"
    if _json_loads_or_none(stripped) is not None:
        return "json"
    return "plain_text"


def _unsupported_parameter_error(exc: AIHTTPError) -> bool:
    detail = str(exc.detail or "").lower()
    return exc.status_code == 400 and (
        "unsupported parameter" in detail
        or "messages" in detail
        or "prompt" in detail
        or "input" in detail
    )


def _anthropic_request_url(base_url: str) -> str:
    normalized = str(base_url or "").rstrip("/")
    lowered = normalized.lower()
    if lowered.endswith("/v1/messages") or lowered.endswith("/messages"):
        return normalized
    return f"{normalized}/v1/messages"


def _openai_request_url(base_url: str, api_format: str) -> str:
    normalized = str(base_url or "").rstrip("/")
    lowered = normalized.lower()
    suffixes = {
        "chat": "/chat/completions",
        "completions": "/completions",
        "responses": "/responses",
    }
    known_endpoints = ("/chat/completions", "/completions", "/responses")
    if any(lowered.endswith(endpoint) for endpoint in known_endpoints):
        return normalized
    suffix = suffixes.get(api_format)
    if not suffix:
        return normalized
    if lowered.endswith("/v1"):
        return f"{normalized}{suffix}"
    return f"{normalized}/v1{suffix}"


def _request_url(config: AIConfig, api_format: str) -> str:
    if api_format == "anthropic":
        return _anthropic_request_url(config.base_url)
    return _openai_request_url(config.base_url, api_format)


def _request_headers(config: AIConfig, api_format: str) -> Dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
    }
    if api_format == "anthropic":
        headers["x-api-key"] = config.api_token
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {config.api_token}"
    return headers


def _post_payload(config: AIConfig, payload: Mapping[str, Any], api_format: str) -> Mapping[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        _request_url(config, api_format),
        data=body,
        headers=_request_headers(config, api_format),
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=config.timeout) as response:  # noqa: S310
            return parse_ai_response_body(response.read().decode("utf-8", errors="replace"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AIHTTPError(exc.code, detail, config.api_token) from exc


def _probe_format(config: AIConfig) -> str:
    api_format = _normalize_api_format(config.api_format)
    if api_format != "auto":
        return api_format
    if config.provider == "anthropic-compatible":
        return "anthropic"
    return _preferred_auto_formats(config.base_url)[0]


def _probe_suggested_fix(status_code: int, response_text: str, response_kind: str) -> str:
    hint = ai_http_error_hint(status_code, response_text)
    if hint:
        return hint
    if response_kind == "html":
        return "接口返回 HTML，通常是网页登录页、网关错误或反代路径不正确。请检查 base URL 是否是 API endpoint。"
    if response_kind == "empty":
        return "接口返回空内容。请检查 endpoint、模型名、token 权限，或改用 Chat/Responses/Anthropic 对应格式。"
    if response_kind == "plain_text":
        return "接口返回纯文本；若分析可正常显示可以继续使用，否则请确认第三方服务是否返回标准兼容 JSON。"
    return ""


def probe_ai_connection(config: AIConfig) -> Dict[str, Any]:
    api_format = _probe_format(config)
    request_url = _request_url(config, api_format)
    base = {
        "ok": False,
        "provider": config.provider,
        "apiFormat": api_format,
        "requestUrl": request_url,
        "statusCode": 0,
        "responseKind": "empty",
        "message": "",
        "suggestedFix": "",
    }
    if not config.api_token.strip():
        return {**base, "message": "AI API token is not configured.", "suggestedFix": "请先填写并保存 API Token。"}
    if not config.model.strip():
        return {**base, "message": "AI model is not configured.", "suggestedFix": "请填写模型名称。"}

    messages = [{"role": "user", "content": "ping"}]
    payload = build_ai_payload(config, messages, api_format)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        request_url,
        data=body,
        headers=_request_headers(config, api_format),
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=config.timeout) as response:  # noqa: S310
            response_text = response.read().decode("utf-8", errors="replace")
            status_code = int(getattr(response, "status", 200) or 200)
    except error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        response_kind = detect_ai_response_kind(response_text)
        return {
            **base,
            "statusCode": int(exc.code),
            "responseKind": response_kind,
            "message": redact_secrets(_truncate_response_text(response_text) or str(exc), [config.api_token]),
            "suggestedFix": _probe_suggested_fix(int(exc.code), response_text, response_kind),
        }
    except Exception as exc:
        return {
            **base,
            "message": redact_secrets(str(exc), [config.api_token]),
            "suggestedFix": "连接失败。请检查网络、base URL、代理设置和服务商可用性。",
        }

    response_kind = detect_ai_response_kind(response_text)
    try:
        parsed = parse_ai_response_body(response_text)
        content = extract_ai_message_content(parsed)
    except Exception as exc:
        return {
            **base,
            "statusCode": status_code,
            "responseKind": response_kind,
            "message": redact_secrets(str(exc), [config.api_token]),
            "suggestedFix": _probe_suggested_fix(status_code, response_text, response_kind),
        }
    return {
        **base,
        "ok": True,
        "statusCode": status_code,
        "responseKind": response_kind,
        "message": "连接测试成功。" if content else "连接成功，但响应中没有可提取的文本。",
        "suggestedFix": "" if content else "如果正式分析为空，请检查模型是否支持当前接口格式。",
    }


def _default_http_post(config: AIConfig, messages: Sequence[Mapping[str, str]]) -> Mapping[str, Any]:
    if config.provider not in {"openai-compatible", "anthropic-compatible"}:
        raise ValueError(f"Unsupported AI provider: {config.provider}")
    if not config.api_token.strip():
        raise ValueError("AI API token is not configured.")
    if not config.model.strip():
        raise ValueError("AI model is not configured.")
    api_format = (config.api_format or "auto").strip().lower()
    if api_format != "auto":
        return _post_payload(config, build_ai_payload(config, messages, api_format), api_format)

    last_error: Optional[AIHTTPError] = None
    candidates = (
        ["anthropic", "chat", "completions", "responses"]
        if config.provider == "anthropic-compatible"
        else _preferred_auto_formats(config.base_url)
    )
    for candidate_format in candidates:
        try:
            return _post_payload(config, build_ai_payload(config, messages, candidate_format), candidate_format)
        except AIHTTPError as exc:
            last_error = exc
            if not _unsupported_parameter_error(exc):
                raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("AI request failed before a request was sent.")


def extract_ai_message_content(response: Mapping[str, Any]) -> str:
    content = response.get("content") or []
    content_parts: List[str] = []
    if isinstance(content, list):
        for content_item in content:
            if isinstance(content_item, Mapping):
                text = content_item.get("text") or content_item.get("content")
                if text:
                    content_parts.append(str(text))
            elif content_item:
                content_parts.append(str(content_item))
    if content_parts:
        return "\n".join(content_parts)
    output_text = response.get("output_text")
    if output_text:
        return str(output_text)
    output = response.get("output") or []
    output_parts: List[str] = []
    for item in output:
        if not isinstance(item, Mapping):
            continue
        for content_item in item.get("content") or []:
            if not isinstance(content_item, Mapping):
                continue
            text = content_item.get("text") or content_item.get("content")
            if text:
                output_parts.append(str(text))
    if output_parts:
        return "\n".join(output_parts)
    choices = response.get("choices") or []
    if not choices:
        return ""
    first = choices[0] or {}
    message = first.get("message") or {}
    content = message.get("content") or first.get("text") or ""
    if isinstance(content, list):
        return "\n".join(str(part.get("text", part)) if isinstance(part, Mapping) else str(part) for part in content)
    return str(content)


def default_cc_switch_paths(home: Optional[Path] = None) -> Tuple[Path, Path]:
    root = (home or Path.home()).expanduser() / ".cc-switch"
    return root / "settings.json", root / "cc-switch.db"


def load_cc_switch_current_ai_config(
    settings_path: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> Tuple[AIConfig, Dict[str, Any]]:
    default_settings_path, default_db_path = default_cc_switch_paths()
    settings_path = Path(settings_path or default_settings_path).expanduser()
    db_path = Path(db_path or default_db_path).expanduser()
    if not settings_path.exists():
        raise FileNotFoundError(f"cc-switch settings not found: {settings_path}")
    if not db_path.exists():
        raise FileNotFoundError(f"cc-switch database not found: {db_path}")

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    provider_id = settings.get("currentProviderClaude")
    if not provider_id:
        raise ValueError("cc-switch currentProviderClaude is not configured.")

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        provider = connection.execute(
            "select id,name,settings_config from providers where id=? and app_type=?",
            (provider_id, "claude"),
        ).fetchone()
        endpoint = connection.execute(
            "select url from provider_endpoints where provider_id=? and app_type=? order by rowid desc limit 1",
            (provider_id, "claude"),
        ).fetchone()

    if provider is None:
        raise ValueError(f"cc-switch Claude provider not found: {provider_id}")

    settings_config = json.loads(provider["settings_config"] or "{}")
    env = settings_config.get("env") or {}
    base_url = endpoint["url"] if endpoint and endpoint["url"] else env.get("ANTHROPIC_BASE_URL", "")
    token = env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY") or ""
    model = (
        env.get("ANTHROPIC_MODEL")
        or env.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
        or env.get("ANTHROPIC_DEFAULT_OPUS_MODEL")
        or env.get("ANTHROPIC_DEFAULT_HAIKU_MODEL")
        or ""
    )
    if not base_url:
        raise ValueError("cc-switch Claude provider has no ANTHROPIC_BASE_URL or endpoint URL.")
    if not token:
        raise ValueError("cc-switch Claude provider has no ANTHROPIC_AUTH_TOKEN.")
    if not model:
        raise ValueError("cc-switch Claude provider has no ANTHROPIC_MODEL.")

    config = AIConfig(
        provider="anthropic-compatible",
        base_url=str(base_url),
        model=str(model),
        api_token=str(token),
        api_format="anthropic",
    )
    metadata = {
        "providerId": provider_id,
        "providerName": provider["name"],
        "baseUrl": str(base_url),
        "model": str(model),
        "settingsPath": str(settings_path),
        "dbPath": str(db_path),
    }
    return config, metadata


def import_cc_switch_ai_config(
    output_dir: Path,
    settings_path: Optional[Path] = None,
    db_path: Optional[Path] = None,
    config_path: Optional[Path] = None,
    profile_id: str = "",
    profile_name: str = "",
    overwrite_profile_id: str = "",
) -> Dict[str, Any]:
    config, metadata = load_cc_switch_current_ai_config(settings_path=settings_path, db_path=db_path)
    store = load_ai_profiles(output_dir, config_path=config_path)
    target_profile_id = _safe_profile_id(
        overwrite_profile_id or profile_id or store.get("activeProfileId") or metadata.get("providerId") or DEFAULT_AI_PROFILE_ID
    )
    target_profile_name = profile_name or str(metadata.get("providerName") or target_profile_id)
    profile = _profile_from_config(config, profile_id=target_profile_id, name=target_profile_name)
    profiles = [dict(item) for item in store.get("profiles", [])]
    replaced = False
    for index, item in enumerate(profiles):
        if item.get("id") == target_profile_id:
            profiles[index] = profile
            replaced = True
            break
    if not replaced:
        profiles.append(profile)
    save_ai_profiles(
        {"activeProfileId": target_profile_id, "profiles": profiles},
        output_dir,
        config_path=config_path,
    )
    return {
        "ok": True,
        "settings": public_ai_profile_settings(output_dir, config_path=config_path),
        "ccSwitch": metadata,
    }


def analyze_messages_with_ai(
    config: AIConfig,
    messages: Sequence[Mapping[str, str]],
    http_post: Optional[AIHttpPost] = None,
) -> Dict[str, Any]:
    post = http_post or _default_http_post
    response = post(config, messages)
    analysis = extract_ai_message_content(response)
    if not analysis:
        raise RuntimeError("AI response did not include message content.")
    return {
        "ok": True,
        "provider": config.provider,
        "model": config.model,
        "analysis": analysis,
        "usage": response.get("usage", {}),
        "response": response,
    }


# Backward-compatible private alias for older tests/imports.
_extract_message_content = extract_ai_message_content
