#!/usr/bin/env python3
"""Negative mutation tests for catalog validation.

Each case starts from the committed valid catalog state, applies one bad edit,
and asserts that validation fails. Mutations cover the models catalog, the
plugins entry sources, and the generated plugins aggregate (including drift).
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
MODEL_PATH = Path("models/catalog.v1.json")
MCP_PATH = Path("plugins/catalog.v2.json")
INDEX_PATH = Path("plugins/index.json")
ENTRIES_DIR = Path("plugins/entries")


class Ctx:
	"""Parsed copies of every editable catalog source plus the tmp tree root."""

	def __init__(self, root: Path) -> None:
		self.root = root
		self.models = json.loads((root / MODEL_PATH).read_text(encoding="utf-8"))
		self.mcp = json.loads((root / MCP_PATH).read_text(encoding="utf-8"))
		self.index = json.loads((root / INDEX_PATH).read_text(encoding="utf-8"))
		self.entries = {
			item.stem: json.loads(item.read_text(encoding="utf-8"))
			for item in sorted((root / ENTRIES_DIR).glob("*.json"))
		}

	def write_back(self) -> None:
		def dump(path: Path, data: Any) -> None:
			path.write_text(json.dumps(data, indent="\t", ensure_ascii=False) + "\n", encoding="utf-8")

		dump(self.root / MODEL_PATH, self.models)
		dump(self.root / MCP_PATH, self.mcp)
		dump(self.root / INDEX_PATH, self.index)
		for stem, entry in self.entries.items():
			dump(self.root / ENTRIES_DIR / f"{stem}.json", entry)


def _prepare_root(tmpdir: Path) -> None:
	(tmpdir / "models").mkdir()
	shutil.copyfile(ROOT / MODEL_PATH, tmpdir / MODEL_PATH)
	(tmpdir / "plugins" / "entries").mkdir(parents=True)
	shutil.copyfile(ROOT / MCP_PATH, tmpdir / MCP_PATH)
	shutil.copyfile(ROOT / INDEX_PATH, tmpdir / INDEX_PATH)
	for item in sorted((ROOT / ENTRIES_DIR).glob("*.json")):
		shutil.copyfile(item, tmpdir / ENTRIES_DIR / item.name)


def _run_case(name: str, mutate: Callable[[Ctx], None]) -> tuple[bool, list[str]]:
	with tempfile.TemporaryDirectory(prefix=f"catalog-mutation-{name}-") as raw_tmp:
		tmp = Path(raw_tmp)
		_prepare_root(tmp)
		ctx = Ctx(tmp)
		baseline_errors = validate_catalogs.validate(tmp)
		if baseline_errors:
			return False, [f"baseline validation failed before mutation: {baseline_errors[:3]!r}"]
		mutate(ctx)
		ctx.write_back()
		errors = validate_catalogs.validate(tmp)
		return bool(errors), errors


def _first_entry(ctx: Ctx) -> str:
	return sorted(ctx.entries)[0]


def duplicate_model_id(ctx: Ctx) -> None:
	ctx.models["models"].insert(1, copy.deepcopy(ctx.models["models"][0]))


def duplicate_mcp_server(ctx: Ctx) -> None:
	stems = sorted(ctx.entries)
	ctx.entries[stems[0]]["server"] = ctx.entries[stems[1]]["server"]


def bad_catalog_version(ctx: Ctx) -> None:
	ctx.models["schemaVersion"] = 2


def bad_plugins_index_version(ctx: Ctx) -> None:
	ctx.index["version"] = 999


def embedded_secret(ctx: Ctx) -> None:
	ctx.entries[_first_entry(ctx)]["description"] = "example leaked secret sk-abcdefghijklmnopqrstuvwxyz"


def credential_url(ctx: Ctx) -> None:
	stem = _first_entry(ctx)
	ctx.entries[stem]["url"] = "https://user:pass@example.com/mcp"
	ctx.entries[stem]["transport"]["url"] = "https://user:pass@example.com/mcp"


def private_url(ctx: Ctx) -> None:
	stem = _first_entry(ctx)
	ctx.entries[stem]["url"] = "https://127.0.0.1/mcp"
	ctx.entries[stem]["transport"]["url"] = "https://127.0.0.1/mcp"


def oauth_client_id(ctx: Ctx) -> None:
	for entry in ctx.entries.values():
		if "oauth" in entry:
			entry["oauth"]["clientId"] = "not-allowed-in-catalog"
			return


def oauth_client_secret(ctx: Ctx) -> None:
	for entry in ctx.entries.values():
		if "oauth" in entry:
			entry["oauth"]["clientSecret"] = "not-allowed-in-catalog"
			return


def malformed_transport(ctx: Ctx) -> None:
	ctx.entries[_first_entry(ctx)]["transport"]["type"] = "httpTemplate"


def count_drift(ctx: Ctx) -> None:
	ctx.mcp["counts"]["total"] += 1


def order_drift(ctx: Ctx) -> None:
	ctx.mcp["entries"][0], ctx.mcp["entries"][1] = ctx.mcp["entries"][1], ctx.mcp["entries"][0]


def stale_aggregate(ctx: Ctx) -> None:
	"""Edit an entry source without regenerating the committed aggregate."""
	ctx.entries[_first_entry(ctx)]["label"] = "Renamed Without Regenerate"


def aggregate_entry_edit(ctx: Ctx) -> None:
	"""Edit the committed aggregate without touching the entry sources."""
	ctx.mcp["entries"][0]["label"] = "Hand Edited Aggregate"


def filename_mismatch(ctx: Ctx) -> None:
	ctx.entries[_first_entry(ctx)]["server"] = "renamed-server-id"


def deleted_entry_file(ctx: Ctx) -> None:
	stem = _first_entry(ctx)
	del ctx.entries[stem]
	(ctx.root / ENTRIES_DIR / f"{stem}.json").unlink()


CASES: list[tuple[str, Callable[[Ctx], None]]] = [
	("duplicate-model-id", duplicate_model_id),
	("duplicate-mcp-server", duplicate_mcp_server),
	("bad-catalog-version", bad_catalog_version),
	("bad-plugins-index-version", bad_plugins_index_version),
	("embedded-secret", embedded_secret),
	("credential-url", credential_url),
	("private-url", private_url),
	("oauth-client-id", oauth_client_id),
	("oauth-client-secret", oauth_client_secret),
	("malformed-transport", malformed_transport),
	("count-drift", count_drift),
	("order-drift", order_drift),
	("stale-aggregate", stale_aggregate),
	("aggregate-entry-edit", aggregate_entry_edit),
	("filename-mismatch", filename_mismatch),
	("deleted-entry-file", deleted_entry_file),
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
