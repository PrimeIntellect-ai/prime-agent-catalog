#!/usr/bin/env python3
"""Generate the models catalog aggregate from per-provider sources.

The editable source of truth is `models/providers/<provider>.json`. Each file
contains the ordered model array for one provider. This script deterministically
builds `models/catalog.v1.json` — the stable client-consumed artifact — and
fails closed on malformed sources. Run with --check to compare against the
committed aggregate without writing (CI drift gate).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS_DIR = Path("models/providers")
OUTPUT_PATH = Path("models/catalog.v1.json")

MAX_PROVIDER_FILE_BYTES = 512_000
MAX_PROVIDERS = 500
MAX_MODELS_PER_PROVIDER = 5_000
PROVIDER_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _canonical(data: Any) -> str:
    return json.dumps(data, indent="\t", ensure_ascii=False) + "\n"


def _fail(message: str) -> None:
    raise ValueError(message)


def _read_json_bounded(path: Path) -> Any:
    if path.stat().st_size > MAX_PROVIDER_FILE_BYTES:
        _fail(f"{path.name} is over the {MAX_PROVIDER_FILE_BYTES} byte limit")
    return json.loads(path.read_text(encoding="utf-8"))


def load_provider_models(root: Path) -> dict[str, list[dict[str, Any]]]:
    providers_dir = root / PROVIDERS_DIR
    if not providers_dir.is_dir():
        _fail(f"{PROVIDERS_DIR} directory is missing")
    files = sorted(providers_dir.iterdir())
    for item in files:
        if item.is_dir() or item.suffix != ".json":
            _fail(f"{PROVIDERS_DIR} must contain only JSON files; found {item.name}")
    if not (1 <= len(files) <= MAX_PROVIDERS):
        _fail(f"{PROVIDERS_DIR} must hold 1..{MAX_PROVIDERS} provider files")

    providers: dict[str, list[dict[str, Any]]] = {}
    for item in files:
        provider = item.stem
        if not PROVIDER_NAME_PATTERN.match(provider):
            _fail(f"{item.name} provider name must match ^[a-z0-9][a-z0-9-]*$")
        models = _read_json_bounded(item)
        if not isinstance(models, list):
            _fail(f"{item.name} must contain an array of models")
        if not (1 <= len(models) <= MAX_MODELS_PER_PROVIDER):
            _fail(f"{item.name} must hold 1..{MAX_MODELS_PER_PROVIDER} models")
        seen_ids: set[str] = set()
        typed_models: list[dict[str, Any]] = []
        for index, model in enumerate(models):
            if not isinstance(model, dict):
                _fail(f"{item.name}[{index}] must be an object")
            model_provider = model.get("provider")
            if model_provider != provider:
                _fail(f"{item.name}[{index}] provider must match file name {provider!r}")
            model_id = model.get("id")
            if not isinstance(model_id, str):
                _fail(f"{item.name}[{index}] id must be a string")
            if model_id in seen_ids:
                _fail(f"{item.name} contains duplicate model id {model_id!r}")
            seen_ids.add(model_id)
            typed_models.append(model)
        providers[provider] = typed_models
    return providers


def build_catalog(root: Path = ROOT) -> dict[str, Any]:
    providers = load_provider_models(root)
    models: list[dict[str, Any]] = []
    for provider in sorted(providers):
        models.extend(providers[provider])
    return {"schemaVersion": 1, "models": models}


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
        return [f"{PROVIDERS_DIR}: {exc}"]
    if committed != expected:
        return [
            f"{OUTPUT_PATH}: does not match the catalog generated from {PROVIDERS_DIR}; "
            "run scripts/generate_models_catalog.py and commit the result"
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
            print("Models catalog drift check failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print("Models catalog matches the generated aggregate.")
        return 0
    (ROOT / OUTPUT_PATH).write_text(generate_text(ROOT), encoding="utf-8")
    print(f"Generated {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
