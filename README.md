# prime-agent-catalog

Public catalog artifacts for Prime Agent models and MCP service plugins.

This repository is the source of truth for the public catalog payloads. The
payload schemas are owned by Prime Agent consumers. Do not change those schemas
here unless the consumer contract changes first.

## Stable public paths

| Path | Envelope |
| --- | --- |
| `models/catalog.v1.json` | `{ "schemaVersion": 1, "models": [...] }` |
| `plugins/catalog.v2.json` | `{ "version": 2, "sources": [...], "counts": {...}, "entries": [...] }` |

The files above are the editable source of truth for catalog payloads in this
repo. Build output in `dist/` is local and untracked.

The bootstrap migration from `PrimeIntellect-ai/prime-agent` is recorded in
`.catalog-migration.v1.json`. That file is immutable history only. It is not a
live hash gate, and future catalog edits do not need to cite or hash the old
`prime-agent` source commits.

## File layout

```text
models/
  catalog.v1.json         # model catalog payload, schemaVersion 1
plugins/
  catalog.v2.json         # MCP service plugin catalog payload, version 2
  sources/                # pinned upstream plugin catalog snapshots
  audit/                  # public OAuth metadata audit evidence
  overrides.json          # Prime-curated adjustments
  import-report.json      # generated merge report
  examples/               # local-services authoring example
  reference/              # reference importer/validator TypeScript (not standalone)
scripts/
  validate_catalogs.py        # self-contained validation, Python stdlib only
  test_mutation_validation.py # negative mutation tests for validator coverage
  build_catalogs.py           # validates and writes an untracked dist bundle
.github/workflows/ci.yml  # validation/build CI
.github/CODEOWNERS
.catalog-migration.v1.json
SECURITY.md
package.json
```

The `plugins/sources/`, `plugins/audit/`, `plugins/reference/`, overrides, and
import report trees document history and review context. They are not runtime
inputs, and CI does not claim deterministic regeneration from them.

## Validation rules

`python3 scripts/validate_catalogs.py` checks:

- JSON parses cleanly.
- Top-level envelopes and versions stay compatible.
- `models/` holds exactly the one model catalog JSON file, and the stable
  plugins payload exists at `plugins/catalog.v2.json`.
- Model entries match the consumer schema limits and allowed keys.
- MCP entries match the consumer transport, auth, setup, verification, and
  provenance shape.
- IDs and keys that define entries are unique.
- Catalog order and formatting are deterministic.
- URLs use HTTPS, do not embed credentials, do not contain fragments, and do not
  point at literal loopback/private/link-local/unspecified hosts.
- OAuth catalog markers do not carry `clientId`, `clientSecret`, or
  `client_secret`.
- Basic secret patterns are absent.
- File sizes and entry counts stay bounded.
- MCP summary counts match the entries.

`python3 scripts/test_mutation_validation.py` mutates temporary copies of the
payloads and asserts the validator rejects duplicate ids, bad versions, embedded
secrets, credential and private URLs, OAuth client secrets, malformed transports,
and count/order drift.

## Local commands

```bash
python3 -m py_compile scripts/validate_catalogs.py scripts/build_catalogs.py scripts/test_mutation_validation.py
python3 scripts/validate_catalogs.py
python3 scripts/test_mutation_validation.py
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

1. Replace only the relevant stable payload file (`models/` or `plugins/`).
2. Preserve the existing payload schema envelope and version.
3. Keep the catalog file in canonical tab-indented JSON form.
4. Run `python3 scripts/validate_catalogs.py`.
5. Run `python3 scripts/test_mutation_validation.py` if validation rules changed.
6. Run `python3 scripts/build_catalogs.py`.
7. Commit payload, validator, source, and documentation changes together when
   they are part of the same catalog update.

Do not split payloads into alternate editable shards unless generated aggregate
files are also checked in CI for drift. The current repository intentionally keeps
the two stable JSON payloads as the only editable catalog source of truth.
