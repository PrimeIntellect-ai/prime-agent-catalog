#!/usr/bin/env python3
"""Generate the plugins service catalog aggregate from per-entry sources.

The editable source of truth is `plugins/entries/<server>.json` plus
`plugins/index.json` (envelope metadata). This script deterministically builds
`plugins/catalog.v2.json` — the stable client-consumed artifact — and fails
closed on malformed sources. Run with --check to compare against the committed
aggregate without writing (CI drift gate).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = Path("plugins/index.json")
ENTRIES_DIR = Path("plugins/entries")
OUTPUT_PATH = Path("plugins/catalog.v2.json")

MAX_ENTRY_FILE_BYTES = 128_000
MAX_ENTRIES = 500
MAX_SOURCES = 50
SERVER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
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


def _canonical(data: Any) -> str:
    return json.dumps(data, indent="\t", ensure_ascii=False) + "\n"


def _fail(message: str) -> None:
    raise ValueError(message)


def _read_json_bounded(path: Path) -> Any:
    if path.stat().st_size > MAX_ENTRY_FILE_BYTES:
        _fail(f"{path.name} is over the {MAX_ENTRY_FILE_BYTES} byte limit")
    return json.loads(path.read_text(encoding="utf-8"))


def load_index(root: Path) -> dict[str, Any]:
    index = _read_json_bounded(root / INDEX_PATH)
    if not isinstance(index, dict) or list(index.keys()) != ["version", "sources"]:
        _fail(f"{INDEX_PATH} must carry keys ['version', 'sources'] in that order")
    if index["version"] != 2:
        _fail(f"{INDEX_PATH} version must be 2")
    sources = index["sources"]
    if not isinstance(sources, list) or not (1 <= len(sources) <= MAX_SOURCES):
        _fail(f"{INDEX_PATH} sources must be a bounded non-empty array")
    return index


def load_entries(root: Path) -> list[dict[str, Any]]:
    entries_dir = root / ENTRIES_DIR
    if not entries_dir.is_dir():
        _fail(f"{ENTRIES_DIR} directory is missing")
    files = sorted(entries_dir.iterdir())
    for item in files:
        if item.is_dir() or item.suffix != ".json":
            _fail(f"{ENTRIES_DIR} must contain only JSON files; found {item.name}")
    if not (1 <= len(files) <= MAX_ENTRIES):
        _fail(f"{ENTRIES_DIR} must hold 1..{MAX_ENTRIES} entry files")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in files:
        entry = _read_json_bounded(item)
        if not isinstance(entry, dict):
            _fail(f"{item.name} must contain an object")
        server = entry.get("server")
        if not isinstance(server, str) or not SERVER_ID_PATTERN.match(server):
            _fail(f"{item.name} server id must match ^[a-z0-9][a-z0-9-]{{0,63}}$")
        if server != item.stem:
            _fail(f"{item.name} must be named after its server id (expected {server}.json)")
        if server in seen:
            _fail(f"duplicate server id {server}")
        seen.add(server)
        entries.append(entry)
    return entries


def compute_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    transport = Counter()
    setup_status = Counter()
    setup_readiness = Counter()
    auth_strategy = Counter()
    metadata_status = Counter()
    verification_status = Counter()
    merged_from_both_sources = 0
    for entry in entries:
        transport_obj = entry.get("transport")
        if isinstance(transport_obj, dict) and isinstance(transport_obj.get("type"), str):
            transport[transport_obj["type"]] += 1
        setup = entry.get("setup")
        if isinstance(setup, dict):
            if isinstance(setup.get("status"), str):
                setup_status[setup["status"]] += 1
            if isinstance(setup.get("readiness"), str):
                setup_readiness[setup["readiness"]] += 1
        auth = entry.get("auth")
        if isinstance(auth, dict):
            if isinstance(auth.get("strategy"), str):
                auth_strategy[auth["strategy"]] += 1
            metadata = auth.get("metadata")
            if isinstance(metadata, dict) and isinstance(metadata.get("status"), str):
                metadata_status[metadata["status"]] += 1
        verification = entry.get("verification")
        if isinstance(verification, dict) and isinstance(verification.get("status"), str):
            verification_status[verification["status"]] += 1
        provenance = entry.get("provenance")
        if isinstance(provenance, list):
            provenance_sources = {item.get("source") for item in provenance if isinstance(item, dict)}
            if {"openai-plugins", "claude-plugins-official"}.issubset(provenance_sources):
                merged_from_both_sources += 1
    counts = {
        "total": len(entries),
        "http": transport["http"],
        "httpTemplate": transport["http-template"],
        "sse": transport["sse"],
        "stdio": transport["stdio"],
        "ready": setup_status["ready"],
        "requiresSetup": setup_status["requires-setup"],
        "metadataReviewed": verification_status["metadata-reviewed"],
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
    if list(counts.keys()) != COUNTS_KEYS:
        _fail("internal error: computed counts do not match COUNTS_KEYS order")
    return counts


def build_catalog(root: Path = ROOT) -> dict[str, Any]:
    index = load_index(root)
    entries = sorted(load_entries(root), key=lambda entry: entry["server"])
    return {
        "version": index["version"],
        "sources": index["sources"],
        "counts": compute_counts(entries),
        "entries": entries,
    }


def generate_text(root: Path = ROOT) -> str:
    return _canonical(build_catalog(root))


def check(root: Path = ROOT) -> list[str]:
    output_path = root / OUTPUT_PATH
    if not output_path.exists():
        return [f"{OUTPUT_PATH}: missing"]
    committed = output_path.read_text(encoding="utf-8")
    try:
        expected = generate_text(root)
    except ValueError as exc:
        return [f"{ENTRIES_DIR}: {exc}"]
    if committed != expected:
        return [
            f"{OUTPUT_PATH}: does not match the catalog generated from {ENTRIES_DIR} and {INDEX_PATH}; "
            "run scripts/generate_plugins_catalog.py and commit the result"
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed aggregate matches the generated catalog; exit 1 on drift",
    )
    args = parser.parse_args()
    if args.check:
        errors = check(ROOT)
        if errors:
            print("Plugins catalog drift check failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print("Plugins catalog matches the generated aggregate.")
        return 0
    (ROOT / OUTPUT_PATH).write_text(generate_text(ROOT), encoding="utf-8")
    print(f"Generated {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
