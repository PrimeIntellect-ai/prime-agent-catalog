#!/usr/bin/env python3
"""Negative mutation tests for catalog validation.

Each case starts from the committed valid payloads, applies one bad edit, writes
canonical JSON, and asserts that validation fails.
"""

from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

import validate_catalogs

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path("catalog/models.v1.json")
MCP_PATH = Path("catalog/mcp-services.v2.json")
MIGRATION_PATH = Path(".catalog-migration.v1.json")

Mutation = Callable[[dict[str, Any], dict[str, Any]], None]


def _write_json(root: Path, rel: Path, data: Any) -> None:
    (root / rel).write_text(json.dumps(data, indent="\t", ensure_ascii=False) + "\n", encoding="utf-8")


def _prepare_root(tmpdir: Path) -> None:
    (tmpdir / "catalog").mkdir()
    shutil.copyfile(ROOT / MODEL_PATH, tmpdir / MODEL_PATH)
    shutil.copyfile(ROOT / MCP_PATH, tmpdir / MCP_PATH)
    shutil.copyfile(ROOT / MIGRATION_PATH, tmpdir / MIGRATION_PATH)


def _run_case(name: str, mutate: Mutation) -> tuple[bool, list[str]]:
    with tempfile.TemporaryDirectory(prefix=f"catalog-mutation-{name}-") as raw_tmp:
        tmp = Path(raw_tmp)
        _prepare_root(tmp)
        models = json.loads((tmp / MODEL_PATH).read_text(encoding="utf-8"))
        mcp = json.loads((tmp / MCP_PATH).read_text(encoding="utf-8"))
        baseline_errors = validate_catalogs.validate(tmp)
        if baseline_errors:
            return False, [f"baseline validation failed before mutation: {baseline_errors[:3]!r}"]
        mutate(models, mcp)
        _write_json(tmp, MODEL_PATH, models)
        _write_json(tmp, MCP_PATH, mcp)
        errors = validate_catalogs.validate(tmp)
        return bool(errors), errors


def duplicate_model_id(models: dict[str, Any], mcp: dict[str, Any]) -> None:
    models["models"].insert(1, copy.deepcopy(models["models"][0]))


def duplicate_mcp_server(models: dict[str, Any], mcp: dict[str, Any]) -> None:
    clone = copy.deepcopy(mcp["entries"][0])
    mcp["entries"].insert(1, clone)
    mcp["counts"]["total"] += 1
    mcp["counts"]["http"] += 1


def bad_catalog_version(models: dict[str, Any], mcp: dict[str, Any]) -> None:
    models["schemaVersion"] = 2
    mcp["version"] = 999


def embedded_secret(models: dict[str, Any], mcp: dict[str, Any]) -> None:
    mcp["entries"][0]["description"] = "example leaked secret sk-abcdefghijklmnopqrstuvwxyz"


def credential_url(models: dict[str, Any], mcp: dict[str, Any]) -> None:
    mcp["entries"][0]["url"] = "https://user:pass@example.com/mcp"
    mcp["entries"][0]["transport"]["url"] = "https://user:pass@example.com/mcp"


def private_url(models: dict[str, Any], mcp: dict[str, Any]) -> None:
    mcp["entries"][0]["url"] = "https://127.0.0.1/mcp"
    mcp["entries"][0]["transport"]["url"] = "https://127.0.0.1/mcp"


def oauth_client_id(models: dict[str, Any], mcp: dict[str, Any]) -> None:
    entry = next(entry for entry in mcp["entries"] if "oauth" in entry)
    entry["oauth"]["clientId"] = "not-allowed-in-catalog"


def oauth_client_secret(models: dict[str, Any], mcp: dict[str, Any]) -> None:
    entry = next(entry for entry in mcp["entries"] if "oauth" in entry)
    entry["oauth"]["clientSecret"] = "not-allowed-in-catalog"


def malformed_transport(models: dict[str, Any], mcp: dict[str, Any]) -> None:
    mcp["entries"][0]["transport"]["type"] = "httpTemplate"


def count_drift(models: dict[str, Any], mcp: dict[str, Any]) -> None:
    mcp["counts"]["total"] += 1


def order_drift(models: dict[str, Any], mcp: dict[str, Any]) -> None:
    mcp["entries"][0], mcp["entries"][1] = mcp["entries"][1], mcp["entries"][0]


CASES: list[tuple[str, Mutation]] = [
    ("duplicate-model-id", duplicate_model_id),
    ("duplicate-mcp-server", duplicate_mcp_server),
    ("bad-catalog-version", bad_catalog_version),
    ("embedded-secret", embedded_secret),
    ("credential-url", credential_url),
    ("private-url", private_url),
    ("oauth-client-id", oauth_client_id),
    ("oauth-client-secret", oauth_client_secret),
    ("malformed-transport", malformed_transport),
    ("count-drift", count_drift),
    ("order-drift", order_drift),
]


def main() -> int:
    failures: list[str] = []
    for name, mutate in CASES:
        failed_as_expected, errors = _run_case(name, mutate)
        if not failed_as_expected:
            failures.append(f"{name}: mutation unexpectedly passed; details: {errors[:3]!r}")
        else:
            print(f"ok {name}: {errors[0]}")
    if failures:
        print("Mutation validation tests failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"{len(CASES)} mutation validation tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
