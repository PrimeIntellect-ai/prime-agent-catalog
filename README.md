# prime-agent-catalog

Public catalog artifacts for Prime Agent models and MCP services.

This repository keeps the catalog payloads separate from the Prime Agent client
release cycle. The payload schemas are owned by Prime Agent consumers. Do not
change those schemas here.

## Stable public paths

| Path | Envelope | Source |
| --- | --- | --- |
| `catalog/models.v1.json` | `{ "schemaVersion": 1, "models": [...] }` | `PrimeIntellect-ai/prime-agent` PR #2138, `catalog/models.v1.json` |
| `catalog/mcp-services.v2.json` | `{ "version": 2, "sources": [...], "counts": {...}, "entries": [...] }` | `PrimeIntellect-ai/prime-agent` main, `packages/ai/src/mcp/catalog.json` |

The files above are the editable source of truth for catalog payloads in this
repo. Build output in `dist/` is local and untracked.

## File layout

```text
catalog/
  models.v1.json          # model catalog payload, schemaVersion 1
  mcp-services.v2.json    # MCP services catalog payload, version 2
scripts/
  validate_catalogs.py    # self-contained validation, Python stdlib only
  build_catalogs.py       # validates and writes an untracked dist bundle
.github/workflows/ci.yml  # validation/build CI
.catalog-provenance.v1.json
package.json
```

## Validation rules

`python3 scripts/validate_catalogs.py` checks:

- JSON parses cleanly.
- Top-level envelope and version stay compatible.
- Expected public catalog files are the only JSON files in `catalog/`.
- IDs and keys that define entries are unique.
- Catalog order and formatting are deterministic.
- URLs use HTTPS and do not embed credentials.
- Basic secret patterns are absent.
- File sizes and entry counts stay bounded.
- MCP summary counts match the entries.
- Source provenance, byte counts, and SHA-256 hashes match
  `.catalog-provenance.v1.json`.

## Local commands

```bash
python3 scripts/validate_catalogs.py
python3 scripts/build_catalogs.py
```

The same commands are also exposed through npm script names for convenience:

```bash
npm run validate
npm run build
npm test
```

No npm dependencies are required.

## Updating catalog data

1. Replace only the relevant stable payload file under `catalog/`.
2. Preserve the existing payload schema envelope and version.
3. Update `.catalog-provenance.v1.json` with the upstream source commit, source
   path, byte count, and SHA-256 for the replaced payload.
4. Run `python3 scripts/validate_catalogs.py`.
5. Run `python3 scripts/build_catalogs.py`.
6. Commit the payload and provenance changes together.

Do not split payloads into alternate editable shards unless generated aggregate
files are also checked in CI for drift. The current repository intentionally keeps
the two stable JSON payloads as the only editable catalog source of truth.
