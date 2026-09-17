#!/usr/bin/env python3
"""Validate Prime Agent public catalog artifacts.

The editable sources of truth are models/providers/<provider>.json,
plugins/index.json, and plugins/entries/<server>.json. models/catalog.v1.json
and plugins/catalog.v2.json are generated aggregates: this script does not
rewrite them, but it does fail when a committed aggregate drifts from its
sources. It checks envelope compatibility,
consumer-facing schema shape, deterministic ordering, bounded size/counts, URL
safety, and basic secret hygiene.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]

MODEL_CATALOG = Path("models/catalog.v1.json")
MODELS_PROVIDERS_DIR = Path("models/providers")
MCP_CATALOG = Path("plugins/catalog.v2.json")
PLUGINS_INDEX = Path("plugins/index.json")
PLUGINS_ENTRIES_DIR = Path("plugins/entries")
MAX_ENTRY_FILE_BYTES = 128_000
MAX_MODEL_PROVIDER_FILE_BYTES = 512_000

MAX_BYTES = {
    MODEL_CATALOG: 2_000_000,
    MCP_CATALOG: 1_000_000,
}
MAX_COUNTS = {
    "models": 20_000,
    "mcp_entries": 500,
    "mcp_sources": 50,
}
MAX_STRING = 4096

SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ASIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{30,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
)

HEX_40 = re.compile(r"^[0-9a-f]{40}$")
SAFE_REL_PATH = re.compile(r"^[A-Za-z0-9._/-]+$")
CONTROL_CHARS = re.compile(r"[\u0000-\u001f\u007f-\u009f]")
SERVER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
PROVIDER_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SECRET_QUERY_NAMES = ("token", "secret", "password", "api_key", "apikey", "access_key", "client_secret")

THINKING_LEVEL_KEYS = {"off", "minimal", "low", "medium", "high", "xhigh", "max"}
MODEL_KEYS = {
    "id",
    "name",
    "api",
    "provider",
    "baseUrl",
    "reasoning",
    "thinkingLevelMap",
    "input",
    "cost",
    "contextWindow",
    "maxTokens",
    "featured",
    "compat",
}
MODEL_REQUIRED_KEYS = ["id", "name", "api", "provider", "baseUrl", "reasoning", "input", "cost", "contextWindow", "maxTokens"]
COST_KEYS = ["input", "output", "cacheRead", "cacheWrite"]
MODEL_INPUT_VALUES = {"text", "image"}

OPENAI_COMPLETIONS_COMPAT_KEYS = {
    "zaiToolStream",
    "sendSessionAffinityHeaders",
    "supportsStore",
    "supportsDeveloperRole",
    "supportsReasoningEffort",
    "supportsUsageInStreaming",
    "maxTokensField",
    "requiresToolResultName",
    "requiresAssistantAfterToolResult",
    "requiresThinkingAsText",
    "requiresReasoningContentOnAssistantMessages",
    "thinkingFormat",
    "cacheControlFormat",
    "openRouterRouting",
    "vercelGatewayRouting",
    "supportsStrictMode",
    "supportsLongCacheRetention",
}
OPENAI_BOOL_COMPAT_KEYS = OPENAI_COMPLETIONS_COMPAT_KEYS - {
    "maxTokensField",
    "thinkingFormat",
    "cacheControlFormat",
    "openRouterRouting",
    "vercelGatewayRouting",
}
OPENAI_RESPONSES_COMPAT_KEYS = {"sendSessionIdHeader", "supportsLongCacheRetention"}
ANTHROPIC_MESSAGES_COMPAT_KEYS = {"supportsEagerToolInputStreaming", "supportsLongCacheRetention"}
THINKING_FORMATS = {"openai", "openrouter", "deepseek", "zai", "qwen", "qwen-chat-template"}

TRANSPORT_TYPES = {"http", "http-template", "sse", "stdio"}
AUTH_STRATEGIES = {"oauth", "api_key", "none", "unknown"}
CLIENT_REGISTRATIONS = {"dynamic", "pre-registered", "unknown"}
SETUP_STATUSES = {"ready", "requires-setup"}
READINESS_STATES = {"oauth-ready", "user-setup", "prime-restricted", "unknown"}
SETUP_REQUIREMENTS = {"api-key", "bearer-token", "registered-client", "tenant", "unsupported-transport", "local-runtime"}
SETUP_FIELD_KINDS = {"env-var", "url", "client-id", "client-secret", "bearer-token", "api-key"}
AUTH_ALTERNATIVE_KINDS = {"oauth", "api-key", "bearer-token", "service-account"}
AUTH_METADATA_STATUSES = {"available", "unavailable", "not-audited"}
PROVENANCE_SOURCES = {"openai-plugins", "claude-plugins-official", "prime", "user"}
MCP_ENTRY_KEYS = {
    "server",
    "service",
    "label",
    "url",
    "description",
    "category",
    "aliases",
    "publisher",
    "transport",
    "auth",
    "setup",
    "verification",
    "legacyBuiltin",
    "provenance",
    "homepage",
    "docsUrl",
    "privacyUrl",
    "supportUrl",
    "oauth",
}
MCP_REQUIRED_KEYS = ["server", "service", "label", "url", "aliases", "transport", "auth", "setup", "verification", "legacyBuiltin", "provenance"]
COUNTS_KEYS = [
    "total",
    "http",
    "httpTemplate",
    "sse",
    "stdio",
    "ready",
    "requiresSetup",
    "metadataReviewed",
    "oauthStrategy",
    "apiKeyStrategy",
    "mergedFromBothSources",
    "readinessOauthReady",
    "readinessUserSetup",
    "readinessPrimeRestricted",
    "readinessUnknown",
    "metadataAvailable",
    "metadataUnavailable",
]


def _error(errors: list[str], path: Path | str, message: str) -> None:
    errors.append(f"{path}: {message}")


def _read_json(path: Path, errors: list[str]) -> Any | None:
    full_path = ROOT / path
    if not full_path.exists():
        _error(errors, path, "missing")
        return None
    size = full_path.stat().st_size
    limit = MAX_BYTES.get(path)
    if limit is not None and size > limit:
        _error(errors, path, f"file is {size} bytes, over {limit} byte limit")
    try:
        return json.loads(full_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _error(errors, path, f"invalid JSON: {exc}")
        return None


def _check_canonical_json(path: Path, data: Any, errors: list[str]) -> None:
    raw = (ROOT / path).read_text(encoding="utf-8")
    canonical = json.dumps(data, indent="\t", ensure_ascii=False) + "\n"
    if raw != canonical:
        _error(errors, path, "not in canonical tab-indented JSON form; fix the source file format")


def _walk_strings(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_strings(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_strings(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def _looks_like_url(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", value))


def _expand_ipv6(address: str) -> list[int] | None:
    if address.count("::") > 1:
        return None
    if "::" in address:
        head, tail = address.split("::", 1)
        head_parts = [] if head == "" else head.split(":")
        tail_parts = [] if tail == "" else tail.split(":")
        if len(head_parts) + len(tail_parts) > 7:
            return None
    else:
        head_parts = address.split(":")
        tail_parts = []
        if len(head_parts) != 8 or any(part == "" for part in head_parts):
            return None
    words: list[int] = []
    for part in head_parts:
        try:
            word = int(part or "0", 16)
        except ValueError:
            return None
        if word < 0 or word > 0xFFFF:
            return None
        words.append(word)
    words.extend([0] * (8 - len(head_parts) - len(tail_parts)))
    for part in tail_parts:
        try:
            word = int(part or "0", 16)
        except ValueError:
            return None
        if word < 0 or word > 0xFFFF:
            return None
        words.append(word)
    return words if len(words) == 8 else None


def _is_literal_private_or_loopback_host(hostname: str) -> bool:
    bare = hostname.strip("[]").lower()
    if bare == "localhost" or bare.endswith(".localhost"):
        return True
    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", bare):
        parts = [int(part) for part in bare.split(".")]
        if any(part < 0 or part > 255 for part in parts):
            return True
        a, b, *_ = parts
        return a in {0, 10, 127} or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168) or (a == 169 and b == 254)
    if ":" in bare:
        expanded = _expand_ipv6(bare)
        if expanded is None:
            return True
        if all(word == 0 for word in expanded):
            return True
        if expanded[:7] == [0, 0, 0, 0, 0, 0, 0] and expanded[7] == 1:
            return True
        if expanded[:6] == [0, 0, 0, 0, 0, 0xFFFF]:
            return _is_literal_private_or_loopback_host(
                f"{expanded[6] >> 8}.{expanded[6] & 0xFF}.{expanded[7] >> 8}.{expanded[7] & 0xFF}"
            )
        if (expanded[0] & 0xFFC0) == 0xFE80:
            return True
        if (expanded[0] & 0xFE00) == 0xFC00:
            return True
    return False


def _check_url(value: str, location: str, errors: list[str], *, require_non_empty: bool = True) -> None:
    if value == "" and not require_non_empty:
        return
    split = urlsplit(value)
    if split.scheme != "https" or not split.netloc:
        _error(errors, location, "URL must be an absolute https URL")
    if split.username or split.password:
        _error(errors, location, "URL must not contain embedded credentials")
    if split.fragment:
        _error(errors, location, "URL must not contain a fragment")
    if split.hostname and _is_literal_private_or_loopback_host(split.hostname):
        _error(errors, location, "URL must not use a literal loopback, private, link-local or unspecified endpoint")
    for name, val in parse_qsl(split.query, keep_blank_values=True):
        lowered = name.lower()
        if any(secret_name in lowered for secret_name in SECRET_QUERY_NAMES) and val:
            _error(errors, location, f"URL query contains a credential-like parameter: {name}")


def _check_urls_and_secrets(path: Path, data: Any, errors: list[str]) -> None:
    raw = (ROOT / path).read_text(encoding="utf-8")
    for pattern in SECRET_PATTERNS:
        if pattern.search(raw):
            _error(errors, path, f"possible embedded secret matching {pattern.pattern!r}")
    for string_path, value in _walk_strings(data):
        if _looks_like_url(value):
            _check_url(value, f"{path}:{string_path}", errors)


def _require_keys(obj: dict[str, Any], required: list[str], location: str, errors: list[str]) -> None:
    for key in required:
        if key not in obj:
            _error(errors, location, f"missing required key {key!r}")


def _reject_extra_keys(obj: dict[str, Any], allowed: set[str], location: str, errors: list[str]) -> None:
    extras = sorted(set(obj) - allowed)
    if extras:
        _error(errors, location, f"unexpected keys: {extras!r}")


def _is_non_empty_string(value: Any, max_len: int = MAX_STRING) -> bool:
    return isinstance(value, str) and 0 < len(value) <= max_len


def _is_clean_string(value: Any, min_len: int = 1, max_len: int = MAX_STRING) -> bool:
    return isinstance(value, str) and min_len <= len(value) <= max_len and CONTROL_CHARS.search(value) is None


def _bounded_number(value: Any, minimum: float = 0, maximum: float = 1_000_000) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and minimum <= value <= maximum


def _positive_int(value: Any, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= maximum


def _validate_compat(api: str, compat: Any, location: str, errors: list[str]) -> None:
    if compat is None:
        return
    if not isinstance(compat, dict):
        _error(errors, location, "compat must be an object when present")
        return
    if api == "openai-completions":
        _reject_extra_keys(compat, OPENAI_COMPLETIONS_COMPAT_KEYS, f"{location}.compat", errors)
        for key in OPENAI_BOOL_COMPAT_KEYS:
            if key in compat and not isinstance(compat[key], bool):
                _error(errors, location, f"compat.{key} must be boolean")
        if "maxTokensField" in compat and compat["maxTokensField"] not in {"max_completion_tokens", "max_tokens"}:
            _error(errors, location, "compat.maxTokensField has an unsupported value")
        if "thinkingFormat" in compat and compat["thinkingFormat"] not in THINKING_FORMATS:
            _error(errors, location, "compat.thinkingFormat has an unsupported value")
        if "cacheControlFormat" in compat and compat["cacheControlFormat"] != "anthropic":
            _error(errors, location, "compat.cacheControlFormat has an unsupported value")
        for key in ("openRouterRouting", "vercelGatewayRouting"):
            if key in compat and not isinstance(compat[key], dict):
                _error(errors, location, f"compat.{key} must be an object")
    elif api in {"openai-responses", "openai-codex-responses", "azure-openai-responses"}:
        _reject_extra_keys(compat, OPENAI_RESPONSES_COMPAT_KEYS, f"{location}.compat", errors)
        for key, value in compat.items():
            if not isinstance(value, bool):
                _error(errors, location, f"compat.{key} must be boolean")
    elif api == "anthropic-messages":
        _reject_extra_keys(compat, ANTHROPIC_MESSAGES_COMPAT_KEYS, f"{location}.compat", errors)
        for key, value in compat.items():
            if not isinstance(value, bool):
                _error(errors, location, f"compat.{key} must be boolean")
    else:
        _error(errors, location, "compat is only valid for supported compatible API types")


def _validate_model_entry(model: Any, location: str, errors: list[str]) -> tuple[str, str] | None:
    if not isinstance(model, dict):
        _error(errors, location, "model must be an object")
        return None
    _require_keys(model, MODEL_REQUIRED_KEYS, location, errors)
    _reject_extra_keys(model, MODEL_KEYS, location, errors)
    model_id = model.get("id")
    provider = model.get("provider")
    api = model.get("api")
    if not _is_clean_string(model_id, 1, 1_024):
        _error(errors, location, "id must be a non-empty clean string <= 1024 chars")
    if not _is_clean_string(model.get("name"), 1, 1_024):
        _error(errors, location, "name must be a non-empty clean string <= 1024 chars")
    if not _is_non_empty_string(api, 128):
        _error(errors, location, "api must be a non-empty string <= 128 chars")
    if not _is_non_empty_string(provider, 128):
        _error(errors, location, "provider must be a non-empty string <= 128 chars")
    base_url = model.get("baseUrl")
    if not isinstance(base_url, str) or len(base_url) > 2_048:
        _error(errors, location, "baseUrl must be a string <= 2048 chars")
    elif base_url:
        _check_url(base_url, f"{location}.baseUrl", errors)
    if not isinstance(model.get("reasoning"), bool):
        _error(errors, location, "reasoning must be boolean")
    input_value = model.get("input")
    if (
        not isinstance(input_value, list)
        or not (1 <= len(input_value) <= 2)
        or not all(isinstance(item, str) and item in MODEL_INPUT_VALUES for item in input_value)
    ):
        _error(errors, location, "input must be an array of one or two values from text/image")
    cost = model.get("cost")
    if not isinstance(cost, dict) or list(cost.keys()) != COST_KEYS:
        _error(errors, location, "cost must keep input/output/cacheRead/cacheWrite keys in order")
    else:
        for key, value in cost.items():
            if not _bounded_number(value):
                _error(errors, location, f"cost.{key} must be a bounded non-negative number")
    for key in ("contextWindow", "maxTokens"):
        if not _positive_int(model.get(key), 100_000_000):
            _error(errors, location, f"{key} must be a positive integer <= 100000000")
    thinking = model.get("thinkingLevelMap")
    if thinking is not None:
        if not isinstance(thinking, dict):
            _error(errors, location, "thinkingLevelMap must be an object")
        else:
            _reject_extra_keys(thinking, THINKING_LEVEL_KEYS, f"{location}.thinkingLevelMap", errors)
            for key, value in thinking.items():
                if value is not None and not _is_non_empty_string(value, 128):
                    _error(errors, location, f"thinkingLevelMap.{key} must be null or a non-empty string <= 128 chars")
    if "featured" in model and not isinstance(model["featured"], bool):
        _error(errors, location, "featured must be boolean")
    if "compat" in model and isinstance(api, str):
        _validate_compat(api, model["compat"], location, errors)
    if isinstance(provider, str) and isinstance(model_id, str):
        return provider, model_id
    return None


def _validate_model_catalog(data: Any, errors: list[str]) -> None:
    path = MODEL_CATALOG
    if not isinstance(data, dict):
        _error(errors, path, "top-level value must be an object")
        return
    if list(data.keys()) != ["schemaVersion", "models"]:
        _error(errors, path, "top-level keys must remain ['schemaVersion', 'models'] in that order")
    if data.get("schemaVersion") != 1:
        _error(errors, path, "schemaVersion must be 1")
    models = data.get("models")
    if not isinstance(models, list):
        _error(errors, path, "models must be an array")
        return
    if not (1 <= len(models) <= MAX_COUNTS["models"]):
        _error(errors, path, f"model count {len(models)} outside 1..{MAX_COUNTS['models']}")

    provider_ids: list[tuple[str, str]] = []
    providers: list[str] = []
    for index, model in enumerate(models):
        result = _validate_model_entry(model, f"{path}:models[{index}]", errors)
        if result is not None:
            provider, model_id = result
            provider_ids.append((provider, model_id))
            providers.append(provider)

    duplicates = [item for item, count in Counter(provider_ids).items() if count > 1]
    if duplicates:
        _error(errors, path, f"duplicate provider/id pairs: {duplicates[:20]}")
    if providers != sorted(providers):
        _error(errors, path, "models must remain grouped in non-decreasing provider order")


def _validate_string_array(value: Any, location: str, errors: list[str], *, non_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (non_empty and not value):
        _error(errors, location, "must be an array" + (" with at least one item" if non_empty else ""))
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        if not _is_non_empty_string(item):
            _error(errors, f"{location}[{index}]", "must be a non-empty bounded string")
        else:
            result.append(item)
    return result


def _validate_transport(entry: dict[str, Any], location: str, errors: list[str], counters: Counter[str]) -> str | None:
    transport = entry.get("transport")
    if not isinstance(transport, dict) or not isinstance(transport.get("type"), str):
        _error(errors, location, "transport must be an object with a type")
        return None
    transport_type = transport["type"]
    if transport_type not in TRANSPORT_TYPES:
        _error(errors, location, "transport.type must be one of http/http-template/sse/stdio")
        return None
    counters[transport_type] += 1
    url = entry.get("url")
    if not isinstance(url, str):
        _error(errors, location, "url must be a string")
        return transport_type
    if transport_type in {"http", "sse"}:
        if list(transport.keys()) != ["type", "url"]:
            _error(errors, location, f"{transport_type} transport keys must be ['type', 'url']")
        transport_url = transport.get("url")
        if not isinstance(transport_url, str):
            _error(errors, location, "transport.url must be a string")
        else:
            _check_url(transport_url, f"{location}.transport.url", errors)
            if url != transport_url:
                _error(errors, location, "url must equal transport.url")
    elif transport_type == "http-template":
        if list(transport.keys()) != ["type", "template", "variables"]:
            _error(errors, location, "http-template transport keys must be ['type', 'template', 'variables']")
        if url != "":
            _error(errors, location, "url must be empty for http-template transports")
        if not _is_non_empty_string(transport.get("template")):
            _error(errors, location, "transport.template must be a non-empty bounded string")
        variables = transport.get("variables")
        if not isinstance(variables, list) or not variables:
            _error(errors, location, "http-template transports need at least one variable")
        else:
            for index, variable in enumerate(variables):
                vloc = f"{location}.transport.variables[{index}]"
                if not isinstance(variable, dict):
                    _error(errors, vloc, "variable must be an object")
                    continue
                if list(variable.keys()) != ["name", "description"]:
                    _error(errors, vloc, "variable keys must be ['name', 'description']")
                if not _is_non_empty_string(variable.get("name")):
                    _error(errors, vloc, "name must be a non-empty bounded string")
                if not _is_non_empty_string(variable.get("description")):
                    _error(errors, vloc, "description must be a non-empty bounded string")
    else:
        if list(transport.keys()) != ["type", "servers"]:
            _error(errors, location, "stdio transport keys must be ['type', 'servers']")
        if url != "":
            _error(errors, location, "url must be empty for stdio transports")
        servers = transport.get("servers")
        if not isinstance(servers, list) or not servers:
            _error(errors, location, "stdio transports need at least one server")
        else:
            for index, server_def in enumerate(servers):
                sloc = f"{location}.transport.servers[{index}]"
                if not isinstance(server_def, dict):
                    _error(errors, sloc, "server definition must be an object")
                    continue
                _reject_extra_keys(server_def, {"name", "command", "args", "env"}, sloc, errors)
                if not _is_non_empty_string(server_def.get("name")):
                    _error(errors, sloc, "name must be a non-empty bounded string")
                if not _is_non_empty_string(server_def.get("command")):
                    _error(errors, sloc, "command must be a non-empty bounded string")
                if "args" in server_def:
                    _validate_string_array(server_def["args"], f"{sloc}.args", errors)
                if "env" in server_def:
                    env = server_def["env"]
                    if not isinstance(env, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in env.items()):
                        _error(errors, sloc, "env must be an object with string values")
    return transport_type


def _validate_auth(entry: dict[str, Any], location: str, errors: list[str], auth_strategy: Counter[str], metadata_status: Counter[str]) -> None:
    auth = entry.get("auth")
    if not isinstance(auth, dict):
        _error(errors, location, "auth must be an object")
        return
    _reject_extra_keys(auth, {"strategy", "clientRegistration", "reviewedScopes", "alternatives", "metadata"}, f"{location}.auth", errors)
    strategy = auth.get("strategy")
    if not isinstance(strategy, str) or strategy not in AUTH_STRATEGIES:
        _error(errors, location, "auth.strategy must be one of oauth/api_key/none/unknown")
    else:
        auth_strategy[strategy] += 1
    client_registration = auth.get("clientRegistration")
    if not isinstance(client_registration, str) or client_registration not in CLIENT_REGISTRATIONS:
        _error(errors, location, "auth.clientRegistration must be one of dynamic/pre-registered/unknown")
    if "reviewedScopes" in auth:
        _validate_string_array(auth["reviewedScopes"], f"{location}.auth.reviewedScopes", errors)
    if "alternatives" in auth:
        alternatives = auth["alternatives"]
        if not isinstance(alternatives, list):
            _error(errors, location, "auth.alternatives must be an array")
        else:
            for index, alternative in enumerate(alternatives):
                aloc = f"{location}.auth.alternatives[{index}]"
                if not isinstance(alternative, dict):
                    _error(errors, aloc, "alternative must be an object")
                    continue
                _reject_extra_keys(alternative, {"kind", "readiness", "note", "sourceUrl"}, aloc, errors)
                if alternative.get("kind") not in AUTH_ALTERNATIVE_KINDS:
                    _error(errors, aloc, "kind has an unsupported value")
                if alternative.get("readiness") not in READINESS_STATES:
                    _error(errors, aloc, "readiness has an unsupported value")
                if "sourceUrl" in alternative and isinstance(alternative["sourceUrl"], str):
                    _check_url(alternative["sourceUrl"], f"{aloc}.sourceUrl", errors)
    if "metadata" in auth:
        metadata = auth["metadata"]
        if not isinstance(metadata, dict):
            _error(errors, location, "auth.metadata must be an object")
            return
        _reject_extra_keys(
            metadata,
            {
                "status",
                "authorizationServer",
                "resource",
                "pkceS256",
                "dynamicClientRegistration",
                "clientIdMetadataDocument",
                "protectedResourceScopes",
                "authorizationServerScopes",
                "tokenAuthMethods",
                "sourceUrls",
                "fetchedAt",
                "note",
            },
            f"{location}.auth.metadata",
            errors,
        )
        status = metadata.get("status")
        if status not in AUTH_METADATA_STATUSES:
            _error(errors, location, "auth.metadata.status has an unsupported value")
        elif isinstance(status, str):
            metadata_status[status] += 1
        for key in ("authorizationServer", "resource"):
            if key in metadata:
                if not isinstance(metadata[key], str):
                    _error(errors, location, f"auth.metadata.{key} must be a string")
                elif metadata[key]:
                    _check_url(metadata[key], f"{location}.auth.metadata.{key}", errors)
        for key in ("pkceS256", "dynamicClientRegistration", "clientIdMetadataDocument"):
            if key in metadata and not isinstance(metadata[key], bool):
                _error(errors, location, f"auth.metadata.{key} must be boolean")
        for key in ("protectedResourceScopes", "authorizationServerScopes", "tokenAuthMethods"):
            if key in metadata:
                _validate_string_array(metadata[key], f"{location}.auth.metadata.{key}", errors)
        source_urls = metadata.get("sourceUrls")
        urls = _validate_string_array(source_urls, f"{location}.auth.metadata.sourceUrls", errors, non_empty=True)
        for index, source_url in enumerate(urls):
            _check_url(source_url, f"{location}.auth.metadata.sourceUrls[{index}]", errors)
        if not _is_non_empty_string(metadata.get("fetchedAt")):
            _error(errors, location, "auth.metadata.fetchedAt must be a non-empty string")


def _validate_setup(entry: dict[str, Any], location: str, errors: list[str], setup_status: Counter[str], setup_readiness: Counter[str]) -> None:
    setup = entry.get("setup")
    if not isinstance(setup, dict):
        _error(errors, location, "setup must be an object")
        return
    _reject_extra_keys(setup, {"status", "reason", "fields", "readiness", "requirement"}, f"{location}.setup", errors)
    status = setup.get("status")
    if status not in SETUP_STATUSES:
        _error(errors, location, "setup.status must be ready or requires-setup")
    elif isinstance(status, str):
        setup_status[status] += 1
        if status == "requires-setup" and not _is_non_empty_string(setup.get("reason")):
            _error(errors, location, "requires-setup entries need a reason")
    if "readiness" in setup:
        readiness = setup["readiness"]
        if readiness not in READINESS_STATES:
            _error(errors, location, "setup.readiness has an unsupported value")
        elif isinstance(readiness, str):
            setup_readiness[readiness] += 1
    if "requirement" in setup and setup["requirement"] not in SETUP_REQUIREMENTS:
        _error(errors, location, "setup.requirement has an unsupported value")
    if "fields" in setup:
        fields = setup["fields"]
        if not isinstance(fields, list):
            _error(errors, location, "setup.fields must be an array")
        else:
            for index, field in enumerate(fields):
                floc = f"{location}.setup.fields[{index}]"
                if not isinstance(field, dict):
                    _error(errors, floc, "field must be an object")
                    continue
                _reject_extra_keys(field, {"id", "label", "description", "required", "kind", "credentialSet"}, floc, errors)
                if not _is_non_empty_string(field.get("id")):
                    _error(errors, floc, "id must be a non-empty bounded string")
                if not _is_non_empty_string(field.get("label")):
                    _error(errors, floc, "label must be a non-empty bounded string")
                if not isinstance(field.get("required"), bool):
                    _error(errors, floc, "required must be boolean")
                if "kind" in field and field["kind"] not in SETUP_FIELD_KINDS:
                    _error(errors, floc, "kind has an unsupported value")
                if "credentialSet" in field and not _is_non_empty_string(field["credentialSet"]):
                    _error(errors, floc, "credentialSet must be a non-empty bounded string")


def _new_counters() -> dict[str, Any]:
	return {
		"servers": [],
		"urls": [],
		"transport": Counter(),
		"setup_status": Counter(),
		"setup_readiness": Counter(),
		"auth_strategy": Counter(),
		"metadata_status": Counter(),
		"verification_status": Counter(),
		"merged_from_both_sources": 0,
	}


def _validate_sources(sources: Any, path: Path, errors: list[str]) -> None:
	if not isinstance(sources, list) or not (1 <= len(sources) <= MAX_COUNTS["mcp_sources"]):
		_error(errors, path, "sources must be a bounded non-empty array")
		return
	for index, source in enumerate(sources):
		location = f"{path}:sources[{index}]"
		if not isinstance(source, dict):
			_error(errors, location, "source must be an object")
			continue
		if list(source.keys()) != ["source", "repository", "commit"]:
			_error(errors, location, "source keys must be ['source', 'repository', 'commit']")
		if not _is_non_empty_string(source.get("source"), 128):
			_error(errors, location, "source must be a non-empty bounded string")
		if not _is_non_empty_string(source.get("repository"), 256):
			_error(errors, location, "repository must be a non-empty bounded string")
		if not isinstance(source.get("commit"), str) or not HEX_40.match(source["commit"]):
			_error(errors, location, "commit must be a 40-character lowercase SHA-1")


def _validate_mcp_entry(entry: Any, location: str, errors: list[str], counters: dict[str, Any]) -> None:
	if not isinstance(entry, dict):
		_error(errors, location, "entry must be an object")
		return
	_require_keys(entry, MCP_REQUIRED_KEYS, location, errors)
	_reject_extra_keys(entry, MCP_ENTRY_KEYS, location, errors)
	server = entry.get("server")
	if not isinstance(server, str) or not SERVER_ID_PATTERN.match(server):
		_error(errors, location, "server id must match ^[a-z0-9][a-z0-9-]{0,63}$")
	else:
		counters["servers"].append(server)
	for key in ("service", "label"):
		if not _is_non_empty_string(entry.get(key)):
			_error(errors, location, f"{key} must be a non-empty bounded string")
	for key in ("description", "category", "publisher", "homepage", "docsUrl", "privacyUrl", "supportUrl"):
		if key in entry:
			if not isinstance(entry[key], str):
				_error(errors, location, f"{key} must be a string")
			elif key.endswith("Url") or key == "homepage":
				_check_url(entry[key], f"{location}.{key}", errors)
	transport_type = _validate_transport(entry, location, errors, counters["transport"])
	if transport_type in {"http", "sse"} and isinstance(entry.get("url"), str):
		counters["urls"].append(entry["url"])
		_check_url(entry["url"], f"{location}.url", errors)
	aliases = entry.get("aliases")
	if not isinstance(aliases, list):
		_error(errors, location, "aliases must be an array")
	else:
		previous = None
		for alias in aliases:
			if not isinstance(alias, str) or alias != alias.lower() or alias == server:
				_error(errors, location, "aliases must be lowercase strings distinct from the server id")
				break
			if previous is not None and alias <= previous:
				_error(errors, location, "aliases must be sorted and unique")
				break
			previous = alias
	if not isinstance(entry.get("legacyBuiltin"), bool):
		_error(errors, location, "legacyBuiltin must be boolean")
	_validate_auth(entry, location, errors, counters["auth_strategy"], counters["metadata_status"])
	_validate_setup(entry, location, errors, counters["setup_status"], counters["setup_readiness"])
	verification = entry.get("verification")
	if not isinstance(verification, dict) or list(verification.keys()) != ["status"]:
		_error(errors, location, "verification must be an object with only a status key")
	else:
		status = verification.get("status")
		if status not in {"metadata-reviewed", "unverified"}:
			_error(errors, location, "verification.status must be metadata-reviewed or unverified")
		elif isinstance(status, str):
			counters["verification_status"][status] += 1
	if "oauth" in entry:
		oauth = entry["oauth"]
		if not isinstance(oauth, dict) or oauth.get("kind") != "oauth":
			_error(errors, location, 'oauth must carry kind "oauth"')
		else:
			for forbidden in ("clientId", "clientSecret", "client_secret"):
				if forbidden in oauth:
					_error(errors, location, "catalog entries must not carry OAuth client ids or secrets")
			_reject_extra_keys(oauth, {"kind", "scopes"}, f"{location}.oauth", errors)
			if "scopes" in oauth and not isinstance(oauth["scopes"], str):
				_error(errors, location, "oauth.scopes must be a string")
			auth = entry.get("auth")
			if isinstance(auth, dict) and auth.get("strategy") != "oauth":
				_error(errors, location, "oauth is only allowed on oauth-strategy entries")
	provenance = entry.get("provenance")
	if not isinstance(provenance, list) or not provenance:
		_error(errors, location, "provenance must be a non-empty array")
	else:
		provenance_sources = set()
		for p_index, item in enumerate(provenance):
			p_location = f"{location}.provenance[{p_index}]"
			if not isinstance(item, dict):
				_error(errors, p_location, "provenance item must be an object")
				continue
			_reject_extra_keys(item, {"source", "repository", "commit", "path", "url", "license", "note"}, p_location, errors)
			if item.get("source") not in PROVENANCE_SOURCES:
				_error(errors, p_location, "provenance.source has an unsupported value")
			elif isinstance(item.get("source"), str):
				provenance_sources.add(item["source"])
			if "commit" in item and (not isinstance(item["commit"], str) or not HEX_40.match(item["commit"])):
				_error(errors, p_location, "provenance.commit must be a 40-character lowercase SHA-1")
			if "path" in item and (not isinstance(item["path"], str) or not SAFE_REL_PATH.match(item["path"])):
				_error(errors, p_location, "provenance.path must be a safe relative path")
			if "url" in item:
				if isinstance(item["url"], str):
					_check_url(item["url"], f"{p_location}.url", errors)
				else:
					_error(errors, p_location, "provenance.url must be a string")
		if {"openai-plugins", "claude-plugins-official"}.issubset(provenance_sources):
			counters["merged_from_both_sources"] += 1


def _check_entry_cross_rules(
	counters: dict[str, Any],
	entry_total: int,
	counts: Any,
	path: Path,
	errors: list[str],
	*,
	check_counts: bool = True,
	require_sorted: bool = True,
) -> None:
	servers = counters["servers"]
	if require_sorted and servers != sorted(servers):
		_error(errors, path, "entries must be sorted by server")
	duplicate_servers = [item for item, count in Counter(servers).items() if count > 1]
	if duplicate_servers:
		_error(errors, path, f"duplicate servers: {duplicate_servers[:20]}")
	duplicate_urls = [item for item, count in Counter(counters["urls"]).items() if count > 1]
	if duplicate_urls:
		_error(errors, path, f"duplicate entry urls: {duplicate_urls[:20]}")
	if not check_counts:
		return
	expected_counts = {
		"total": entry_total,
		"http": counters["transport"]["http"],
		"httpTemplate": counters["transport"]["http-template"],
		"sse": counters["transport"]["sse"],
		"stdio": counters["transport"]["stdio"],
		"ready": counters["setup_status"]["ready"],
		"requiresSetup": counters["setup_status"]["requires-setup"],
		"metadataReviewed": counters["verification_status"]["metadata-reviewed"],
		"oauthStrategy": counters["auth_strategy"]["oauth"],
		"apiKeyStrategy": counters["auth_strategy"]["api_key"],
		"mergedFromBothSources": counters["merged_from_both_sources"],
		"readinessOauthReady": counters["setup_readiness"]["oauth-ready"],
		"readinessUserSetup": counters["setup_readiness"]["user-setup"],
		"readinessPrimeRestricted": counters["setup_readiness"]["prime-restricted"],
		"readinessUnknown": counters["setup_readiness"]["unknown"],
		"metadataAvailable": counters["metadata_status"]["available"],
		"metadataUnavailable": counters["metadata_status"]["unavailable"],
	}
	for key, expected in expected_counts.items():
		actual = counts.get(key) if isinstance(counts, dict) else None
		if actual != expected:
			_error(errors, path, f"counts.{key} is {actual!r}, expected {expected!r}")


def _validate_mcp_catalog(data: Any, errors: list[str]) -> None:
	path = MCP_CATALOG
	if not isinstance(data, dict):
		_error(errors, path, "top-level value must be an object")
		return
	if list(data.keys()) != ["version", "sources", "counts", "entries"]:
		_error(errors, path, "top-level keys must remain ['version', 'sources', 'counts', 'entries'] in that order")
	if data.get("version") != 2:
		_error(errors, path, "version must be 2")
	sources = data.get("sources")
	counts = data.get("counts")
	entries = data.get("entries")
	_validate_sources(sources, path, errors)
	if not isinstance(counts, dict):
		_error(errors, path, "counts must be an object")
		counts = {}
	elif list(counts.keys()) != COUNTS_KEYS:
		_error(errors, path, f"counts keys must remain {COUNTS_KEYS!r} in order")
	if not isinstance(entries, list):
		_error(errors, path, "entries must be an array")
		return
	if not (1 <= len(entries) <= MAX_COUNTS["mcp_entries"]):
		_error(errors, path, f"entry count {len(entries)} outside 1..{MAX_COUNTS['mcp_entries']}")

	counters = _new_counters()
	for index, entry in enumerate(entries):
		_validate_mcp_entry(entry, f"{path}:entries[{index}]", errors, counters)
	_check_entry_cross_rules(counters, len(entries), counts, path, errors)


def _validate_models_sources(errors: list[str]) -> None:
    """Validate models/providers/, then fail on aggregate drift."""
    providers_full = ROOT / MODELS_PROVIDERS_DIR
    if not providers_full.is_dir():
        _error(errors, MODELS_PROVIDERS_DIR, "directory missing")
        return
    items = sorted(providers_full.iterdir())
    for item in items:
        if item.is_dir() or item.suffix != ".json":
            _error(errors, MODELS_PROVIDERS_DIR, f"must contain only JSON files; found {item.name}")
    json_files = [item for item in items if item.suffix == ".json" and not item.is_dir()]
    if not (1 <= len(json_files) <= 500):
        _error(errors, MODELS_PROVIDERS_DIR, f"provider file count {len(json_files)} outside 1..500")
        return

    provider_ids: list[tuple[str, str]] = []
    for item in json_files:
        rel = MODELS_PROVIDERS_DIR / item.name
        provider = item.stem
        if not PROVIDER_NAME_PATTERN.match(provider):
            _error(errors, rel, "provider file name must match ^[a-z0-9][a-z0-9-]*$")
        if item.stat().st_size > MAX_MODEL_PROVIDER_FILE_BYTES:
            _error(errors, rel, f"file is over the {MAX_MODEL_PROVIDER_FILE_BYTES} byte limit")
        data = _read_json(rel, errors)
        if data is None:
            continue
        _check_canonical_json(rel, data, errors)
        _check_urls_and_secrets(rel, data, errors)
        if not isinstance(data, list):
            _error(errors, rel, "provider source must be an array")
            continue
        if not (1 <= len(data) <= MAX_COUNTS["models"]):
            _error(errors, rel, f"model count {len(data)} outside 1..{MAX_COUNTS['models']}")
        seen_ids: set[str] = set()
        for index, model in enumerate(data):
            location = f"{rel}:models[{index}]"
            result = _validate_model_entry(model, location, errors)
            if result is None:
                continue
            model_provider, model_id = result
            if model_provider != provider:
                _error(errors, location, f"provider must match file name {provider!r}")
            if model_id in seen_ids:
                _error(errors, rel, f"duplicate model id {model_id!r}")
            seen_ids.add(model_id)
            provider_ids.append((model_provider, model_id))

    duplicates = [item for item, count in Counter(provider_ids).items() if count > 1]
    if duplicates:
        _error(errors, MODELS_PROVIDERS_DIR, f"duplicate provider/id pairs: {duplicates[:20]}")

    try:
        import generate_models_catalog

        for message in generate_models_catalog.check(ROOT):
            _error(errors, "models", message)
    except Exception as exc:
        _error(errors, "models", f"catalog generation failed: {exc}")


def _validate_plugins_sources(errors: list[str]) -> None:
	"""Validate plugins/index.json and plugins/entries/, then fail on aggregate drift."""
	if not (ROOT / PLUGINS_INDEX).exists():
		_error(errors, PLUGINS_INDEX, "missing")
	else:
		index = _read_json(PLUGINS_INDEX, errors)
		if index is not None:
			_check_canonical_json(PLUGINS_INDEX, index, errors)
			_check_urls_and_secrets(PLUGINS_INDEX, index, errors)
			if not isinstance(index, dict):
				_error(errors, PLUGINS_INDEX, "index must be an object")
			else:
				if list(index.keys()) != ["version", "sources"]:
					_error(errors, PLUGINS_INDEX, "index keys must be ['version', 'sources'] in that order")
				if index.get("version") != 2:
					_error(errors, PLUGINS_INDEX, "version must be 2")
				_validate_sources(index.get("sources"), PLUGINS_INDEX, errors)

	entries_full = ROOT / PLUGINS_ENTRIES_DIR
	if not entries_full.is_dir():
		_error(errors, PLUGINS_ENTRIES_DIR, "directory missing")
		return
	items = sorted(entries_full.iterdir())
	for item in items:
		if item.is_dir() or item.suffix != ".json":
			_error(errors, PLUGINS_ENTRIES_DIR, f"must contain only JSON files; found {item.name}")
	json_files = [item for item in items if item.suffix == ".json" and not item.is_dir()]
	if not (1 <= len(json_files) <= MAX_COUNTS["mcp_entries"]):
		_error(errors, PLUGINS_ENTRIES_DIR, f"entry file count {len(json_files)} outside 1..{MAX_COUNTS['mcp_entries']}")
		return

	counters = _new_counters()
	for item in json_files:
		rel = PLUGINS_ENTRIES_DIR / item.name
		if item.stat().st_size > MAX_ENTRY_FILE_BYTES:
			_error(errors, rel, f"file is over the {MAX_ENTRY_FILE_BYTES} byte limit")
		entry = _read_json(rel, errors)
		if entry is None:
			continue
		_check_canonical_json(rel, entry, errors)
		_check_urls_and_secrets(rel, entry, errors)
		_validate_mcp_entry(entry, str(rel), errors, counters)
		if isinstance(entry, dict) and isinstance(entry.get("server"), str):
			if entry["server"] != item.stem:
				_error(errors, rel, f"file name must match its server id (expected {entry['server']}.json)")
	_check_entry_cross_rules(counters, len(json_files), None, PLUGINS_ENTRIES_DIR, errors, check_counts=False, require_sorted=False)

	try:
		import generate_plugins_catalog

		for message in generate_plugins_catalog.check(ROOT):
			_error(errors, "plugins", message)
	except Exception as exc:
		_error(errors, "plugins", f"catalog generation failed: {exc}")


def validate(root: Path = ROOT) -> list[str]:
    global ROOT
    ROOT = root.resolve()
    errors: list[str] = []

    models_root = ROOT / "models"
    model_items = sorted(item.name for item in models_root.iterdir()) if models_root.exists() else []
    if model_items != ["catalog.v1.json", "providers"]:
        _error(errors, "models", f"expected exactly {str(MODEL_CATALOG)!r} and {str(MODELS_PROVIDERS_DIR)!r}, found {model_items!r}")
    plugins_catalog = (ROOT / MCP_CATALOG).exists()
    if not plugins_catalog:
        _error(errors, "plugins", f"missing stable plugins catalog {str(MCP_CATALOG)!r}")

    models = _read_json(MODEL_CATALOG, errors)
    mcp = _read_json(MCP_CATALOG, errors)

    for path, data in ((MODEL_CATALOG, models), (MCP_CATALOG, mcp)):
        if data is not None:
            _check_canonical_json(path, data, errors)
            _check_urls_and_secrets(path, data, errors)

    if models is not None:
        _validate_model_catalog(models, errors)
    if mcp is not None:
        _validate_mcp_catalog(mcp, errors)
    _validate_models_sources(errors)
    _validate_plugins_sources(errors)

    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        print("Catalog validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Catalog validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
