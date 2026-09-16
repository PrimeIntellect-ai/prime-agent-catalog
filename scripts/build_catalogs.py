#!/usr/bin/env python3
"""Build a local distributable catalog bundle.

The build output is intentionally untracked. The editable source of truth remains:
- models/catalog.v1.json
- plugins/catalog.v2.json
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import validate_catalogs

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CATALOGS = [Path("models/catalog.v1.json"), Path("plugins/catalog.v2.json")]


def main() -> int:
    errors = validate_catalogs.validate(ROOT)
    if errors:
        print("Catalog validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "catalog").mkdir(parents=True)

    artifacts = []
    for rel_path in CATALOGS:
        source = ROOT / rel_path
        target = DIST / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        payload = source.read_bytes()
        artifacts.append(
            {
                "path": str(rel_path),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )

    manifest = {
        "schemaVersion": 1,
        "artifacts": artifacts,
    }
    (DIST / "catalog-manifest.v1.json").write_text(
        json.dumps(manifest, indent="\t", ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Built {len(artifacts)} catalog artifacts in {DIST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
