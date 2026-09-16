#!/usr/bin/env python3
"""Validate Prime Agent public catalog artifacts.

The catalog JSON files are the editable source of truth. This script does not
rewrite them. It checks envelope compatibility, deterministic serialization,
bounded size/counts, URL safety, basic secret hygiene, and source provenance.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]

MODEL_CATALOG = Path("catalog/models.v1.json")
MCP_CATALOG = Path("catalog/mcp-services.v2.json")
PROVENANCE = Path(".catalog-provenance.v1.json")
CATALOG_PATHS = (MODEL_CATALOG, MCP_CATALOG)

MAX_BYTES = {
    MODEL_CATALOG: 2_000_000,
    MCP_CATALOG: 1_000_000,
    PROVENANCE: 100_000,
}
MAX_COUNTS = {
    "models": 2_000,
    "mcp_entries": 500,
    "mcp_sources": 50,
}

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
SECRET_QUERY_NAMES = ("token", "secret", "password", "api_key", "apikey", "access_key", "client_secret")


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
        _error(errors, path, "not in canonical tab-indented JSON form; run scripts/build_catalogs.py only after fixing source order/format")


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


def _check_url(value: str, location: str, errors: list[str]) -> None:
    split = urlsplit(value)
    if split.scheme != "https":
        _error(errors, location, f"URL must use https: {value}")
    if split.username or split.password:
        _error(errors, location, "URL must not contain embedded credentials")
    for name, val in parse_qsl(split.query, keep_blank_values=True):
        lowered = name.lower()
        if any(secret_name in lowered for secret_name in SECRET_QUERY_NAMES) and val:
            _error(errors, location, f"URL query contains a credential-like parameter: {name}")


def _check_urls_and_secrets(path: Path, data: Any, errors: list[str]) -> None:
    raw = (ROOT / path).read_text(encoding="utf-8")
    for pattern in SECRET_PATTERNS:
        match = pattern.search(raw)
        if match:
            _error(errors, path, f"possible embedded secret matching {pattern.pattern!r}")
    for string_path, value in _walk_strings(data):
        if _looks_like_url(value):
            _check_url(value, f"{path}:{string_path}", errors)


def _require_keys(obj: dict[str, Any], required: list[str], location: str, errors: list[str]) -> None:
    for key in required:
        if key not in obj:
            _error(errors, location, f"missing required key {key!r}")


def _is_non_empty_string(value: Any, max_len: int = 4096) -> bool:
    return isinstance(value, str) and 0 < len(value) <= max_len


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

    ids: list[str] = []
    providers: list[str] = []
    for index, model in enumerate(models):
        location = f"{path}:models[{index}]"
        if not isinstance(model, dict):
            _error(errors, location, "model must be an object")
            continue
        _require_keys(model, ["id", "name", "api", "provider", "baseUrl", "reasoning", "input", "cost", "contextWindow", "maxTokens"], location, errors)
        model_id = model.get("id")
        provider = model.get("provider")
        if not _is_non_empty_string(model_id, 256):
            _error(errors, location, "id must be a non-empty string <= 256 chars")
        else:
            ids.append(model_id)
        if not _is_non_empty_string(provider, 128):
            _error(errors, location, "provider must be a non-empty string <= 128 chars")
        else:
            providers.append(provider)
        for key in ("name", "api", "baseUrl"):
            if key == "baseUrl":
                if not isinstance(model.get(key), str) or len(model.get(key, "")) > 4096:
                    _error(errors, location, "baseUrl must be a bounded string")
            elif not _is_non_empty_string(model.get(key), 4096):
                _error(errors, location, f"{key} must be a non-empty bounded string")
        if isinstance(model.get("baseUrl"), str) and model["baseUrl"]:
            _check_url(model["baseUrl"], f"{location}.baseUrl", errors)
        if not isinstance(model.get("reasoning"), bool):
            _error(errors, location, "reasoning must be boolean")
        if not isinstance(model.get("input"), list) or not model.get("input") or not all(isinstance(item, str) for item in model.get("input", [])):
            _error(errors, location, "input must be a non-empty string array")
        cost = model.get("cost")
        if not isinstance(cost, dict) or list(cost.keys()) != ["input", "output", "cacheRead", "cacheWrite"]:
            _error(errors, location, "cost must keep input/output/cacheRead/cacheWrite keys in order")
        else:
            for key, value in cost.items():
                if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0 or value > 1_000_000:
                    _error(errors, location, f"cost.{key} must be a bounded non-negative number")
        for key in ("contextWindow", "maxTokens"):
            value = model.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0 or value > 10_000_000:
                _error(errors, location, f"{key} must be a positive bounded integer")

    provider_ids = [
        (model.get("provider"), model.get("id"))
        for model in models
        if isinstance(model, dict) and isinstance(model.get("provider"), str) and isinstance(model.get("id"), str)
    ]
    duplicates = [item for item, count in Counter(provider_ids).items() if count > 1]
    if duplicates:
        _error(errors, path, f"duplicate provider/id pairs: {duplicates[:20]}")
    if providers != sorted(providers):
        _error(errors, path, "models must remain grouped in non-decreasing provider order")


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
    if not isinstance(sources, list) or not (1 <= len(sources) <= MAX_COUNTS["mcp_sources"]):
        _error(errors, path, "sources must be a bounded non-empty array")
    if not isinstance(counts, dict):
        _error(errors, path, "counts must be an object")
        counts = {}
    if not isinstance(entries, list):
        _error(errors, path, "entries must be an array")
        return
    if not (1 <= len(entries) <= MAX_COUNTS["mcp_entries"]):
        _error(errors, path, f"entry count {len(entries)} outside 1..{MAX_COUNTS['mcp_entries']}")

    if isinstance(sources, list):
        for index, source in enumerate(sources):
            location = f"{path}:sources[{index}]"
            if not isinstance(source, dict):
                _error(errors, location, "source must be an object")
                continue
            _require_keys(source, ["source", "repository", "commit"], location, errors)
            if not _is_non_empty_string(source.get("source"), 128):
                _error(errors, location, "source must be a non-empty bounded string")
            if not _is_non_empty_string(source.get("repository"), 256):
                _error(errors, location, "repository must be a non-empty bounded string")
            if not isinstance(source.get("commit"), str) or not HEX_40.match(source["commit"]):
                _error(errors, location, "commit must be a 40-character lowercase SHA-1")

    servers: list[str] = []
    urls: list[str] = []
    derived_transport = Counter()
    setup_status = Counter()
    setup_readiness = Counter()
    auth_strategy = Counter()
    metadata_status = Counter()
    merged_from_both_sources = 0
    for index, entry in enumerate(entries):
        location = f"{path}:entries[{index}]"
        if not isinstance(entry, dict):
            _error(errors, location, "entry must be an object")
            continue
        _require_keys(entry, ["server", "service", "label", "url", "aliases", "transport", "auth", "setup", "verification", "legacyBuiltin", "provenance"], location, errors)
        server = entry.get("server")
        if not _is_non_empty_string(server, 128):
            _error(errors, location, "server must be a non-empty bounded string")
        else:
            servers.append(server)
        for key in ("service", "label", "url"):
            if not _is_non_empty_string(entry.get(key), 4096):
                _error(errors, location, f"{key} must be a non-empty bounded string")
        if isinstance(entry.get("url"), str):
            urls.append(entry["url"])
            _check_url(entry["url"], f"{location}.url", errors)
        if not isinstance(entry.get("aliases"), list) or not all(isinstance(item, str) for item in entry.get("aliases", [])):
            _error(errors, location, "aliases must be a string array")
        if not isinstance(entry.get("legacyBuiltin"), bool):
            _error(errors, location, "legacyBuiltin must be boolean")
        transport = entry.get("transport")
        if not isinstance(transport, dict):
            _error(errors, location, "transport must be an object")
        else:
            transport_type = transport.get("type")
            if transport_type not in {"http", "httpTemplate", "sse", "stdio"}:
                _error(errors, location, "transport.type must be one of http/httpTemplate/sse/stdio")
            else:
                derived_transport[transport_type] += 1
            if transport_type != "stdio" and isinstance(transport.get("url"), str):
                _check_url(transport["url"], f"{location}.transport.url", errors)
                if isinstance(entry.get("url"), str) and transport["url"] != entry["url"]:
                    _error(errors, location, "transport.url must match top-level url")
        auth = entry.get("auth")
        if isinstance(auth, dict):
            if isinstance(auth.get("strategy"), str):
                auth_strategy[auth["strategy"]] += 1
            metadata = auth.get("metadata")
            if isinstance(metadata, dict) and isinstance(metadata.get("status"), str):
                metadata_status[metadata["status"]] += 1
        else:
            _error(errors, location, "auth must be an object")
        setup = entry.get("setup")
        if isinstance(setup, dict):
            if isinstance(setup.get("status"), str):
                setup_status[setup["status"]] += 1
            if isinstance(setup.get("readiness"), str):
                setup_readiness[setup["readiness"]] += 1
        else:
            _error(errors, location, "setup must be an object")
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
                if not _is_non_empty_string(item.get("source"), 128):
                    _error(errors, p_location, "provenance.source must be present")
                else:
                    provenance_sources.add(item["source"])
                if "url" in item and isinstance(item["url"], str):
                    _check_url(item["url"], f"{p_location}.url", errors)
            if {"openai-plugins", "claude-plugins-official"}.issubset(provenance_sources):
                merged_from_both_sources += 1

    if servers != sorted(servers):
        _error(errors, path, "entries must be sorted by server")
    duplicate_servers = [item for item, count in Counter(servers).items() if count > 1]
    if duplicate_servers:
        _error(errors, path, f"duplicate servers: {duplicate_servers[:20]}")
    duplicate_urls = [item for item, count in Counter(urls).items() if count > 1]
    if duplicate_urls:
        _error(errors, path, f"duplicate entry urls: {duplicate_urls[:20]}")

    expected_counts = {
        "total": len(entries),
        "http": derived_transport["http"],
        "httpTemplate": derived_transport["httpTemplate"],
        "sse": derived_transport["sse"],
        "stdio": derived_transport["stdio"],
        "ready": setup_status["ready"],
        "requiresSetup": setup_status["requires-setup"],
        "oauthStrategy": auth_strategy["oauth"],
        "apiKeyStrategy": auth_strategy["api_key"],
        "mergedFromBothSources": merged_from_both_sources,
        "readinessOauthReady": setup_readiness["oauth-ready"],
        "readinessUserSetup": setup_readiness["user-setup"],
        "readinessPrimeRestricted": setup_readiness["prime-restricted"],
        "readinessUnknown": setup_readiness["unknown"],
        "metadataAvailable": metadata_status["available"],
        "metadataUnavailable": metadata_status["unavailable"],
    }
    verification_status = Counter(
        entry.get("verification", {}).get("status")
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("verification"), dict)
    )
    expected_counts["metadataReviewed"] = verification_status["metadata-reviewed"]
    for key, expected in expected_counts.items():
        actual = counts.get(key)
        if actual != expected:
            _error(errors, path, f"counts.{key} is {actual!r}, expected {expected!r}")


def _validate_provenance(data: Any, errors: list[str]) -> None:
    path = PROVENANCE
    if not isinstance(data, dict):
        _error(errors, path, "top-level value must be an object")
        return
    if list(data.keys()) != ["schemaVersion", "catalogs"]:
        _error(errors, path, "top-level keys must remain ['schemaVersion', 'catalogs'] in that order")
    if data.get("schemaVersion") != 1:
        _error(errors, path, "schemaVersion must be 1")
    catalogs = data.get("catalogs")
    if not isinstance(catalogs, list):
        _error(errors, path, "catalogs must be an array")
        return
    paths = [item.get("path") for item in catalogs if isinstance(item, dict)]
    expected_paths = [str(item) for item in CATALOG_PATHS]
    if paths != expected_paths:
        _error(errors, path, f"catalog paths must be {expected_paths!r} in order")
    for index, item in enumerate(catalogs):
        location = f"{path}:catalogs[{index}]"
        if not isinstance(item, dict):
            _error(errors, location, "catalog entry must be an object")
            continue
        _require_keys(item, ["path", "bytes", "sha256", "source"], location, errors)
        rel = item.get("path")
        if not isinstance(rel, str) or rel not in expected_paths:
            _error(errors, location, "path must point to a known public catalog artifact")
            continue
        catalog_path = Path(rel)
        payload = (ROOT / catalog_path).read_bytes() if (ROOT / catalog_path).exists() else b""
        if item.get("bytes") != len(payload):
            _error(errors, location, f"bytes is {item.get('bytes')!r}, expected {len(payload)!r}")
        digest = hashlib.sha256(payload).hexdigest()
        if item.get("sha256") != digest:
            _error(errors, location, f"sha256 is {item.get('sha256')!r}, expected {digest!r}")
        source = item.get("source")
        if not isinstance(source, dict):
            _error(errors, location, "source must be an object")
            continue
        _require_keys(source, ["repository", "sourceRef", "sourceCommit", "sourcePath", "sourceUrl"], f"{location}.source", errors)
        if source.get("repository") != "PrimeIntellect-ai/prime-agent":
            _error(errors, location, "source.repository must be PrimeIntellect-ai/prime-agent")
        if not isinstance(source.get("sourceCommit"), str) or not HEX_40.match(source["sourceCommit"]):
            _error(errors, location, "sourceCommit must be a 40-character lowercase SHA-1")
        if not isinstance(source.get("sourcePath"), str) or not SAFE_REL_PATH.match(source["sourcePath"]):
            _error(errors, location, "sourcePath must be a safe relative path")
        if isinstance(source.get("sourceUrl"), str):
            _check_url(source["sourceUrl"], f"{location}.source.sourceUrl", errors)
        else:
            _error(errors, location, "sourceUrl must be an https URL")


def validate(root: Path = ROOT) -> list[str]:
    global ROOT
    ROOT = root.resolve()
    errors: list[str] = []

    unexpected_catalog_json = sorted(p.relative_to(ROOT) for p in (ROOT / "catalog").glob("*.json")) if (ROOT / "catalog").exists() else []
    if unexpected_catalog_json != sorted(CATALOG_PATHS):
        _error(errors, "catalog", f"expected exactly public catalog JSON files {list(CATALOG_PATHS)!r}, found {unexpected_catalog_json!r}")

    models = _read_json(MODEL_CATALOG, errors)
    mcp = _read_json(MCP_CATALOG, errors)
    provenance = _read_json(PROVENANCE, errors)

    for path, data in ((MODEL_CATALOG, models), (MCP_CATALOG, mcp), (PROVENANCE, provenance)):
        if data is not None:
            _check_canonical_json(path, data, errors)
            _check_urls_and_secrets(path, data, errors)

    if models is not None:
        _validate_model_catalog(models, errors)
    if mcp is not None:
        _validate_mcp_catalog(mcp, errors)
    if provenance is not None:
        _validate_provenance(provenance, errors)

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
