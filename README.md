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

These are the only files Prime Agent fetches, and their paths and payloads are
the client contract. `models/catalog.v1.json` is hand-editable. The plugins
aggregate is GENERATED from `plugins/entries/<server>.json` plus
`plugins/index.json` (envelope metadata) by `scripts/generate_plugins_catalog.py`;
CI rejects a committed aggregate that drifts from its sources. Build output in
`dist/` is local and untracked.

The bootstrap migration from `PrimeIntellect-ai/prime-agent` is recorded in
`.catalog-migration.v1.json`. That file is immutable history only. It is not a
live hash gate, and future catalog edits do not need to cite or hash the old
`prime-agent` source commits.

## File layout

```text
models/
  catalog.v1.json         # model catalog payload, schemaVersion 1 (hand-editable)
plugins/
  entries/                # EDITABLE truth: one <server>.json per MCP service
  index.json              # EDITABLE truth: version + sources envelope metadata
  catalog.v2.json          # GENERATED aggregate; the stable client artifact
  sources/                # pinned upstream plugin catalog snapshots
  audit/                  # public OAuth metadata audit evidence
  overrides.json          # Prime-curated adjustments
  import-report.json      # generated merge report
  examples/               # local-services authoring example
  reference/              # reference importer/validator TypeScript (not standalone)
scripts/
  generate_plugins_catalog.py     # builds plugins/catalog.v2.json from sources; --check = drift gate
  validate_catalogs.py            # self-contained validation, Python stdlib only
  test_mutation_validation.py     # negative mutation tests for validator coverage
  build_catalogs.py               # validates and writes an untracked dist bundle
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
- Each `plugins/entries/<server>.json` is named after its server id, validates
  as a catalog entry, and the committed `plugins/catalog.v2.json` equals the
  aggregate regenerated from `plugins/entries/` + `plugins/index.json`
  (drift fails CI).
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
catalog state and asserts the validator rejects duplicate ids, bad versions,
embedded secrets, credential and private URLs, OAuth client secrets, malformed
transports, count/order drift, a stale generated aggregate, hand-edited
aggregates, filename/server mismatches, and deleted entry files.

## Local commands

```bash
python3 -m py_compile scripts/validate_catalogs.py scripts/generate_plugins_catalog.py scripts/build_catalogs.py scripts/test_mutation_validation.py
python3 scripts/validate_catalogs.py
python3 scripts/generate_plugins_catalog.py --check
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

Models:

1. Edit `models/catalog.v1.json` directly.
2. Keep the file in canonical tab-indented JSON form.

Plugins:

1. Edit one file per service under `plugins/entries/`, or `plugins/index.json`
   for envelope metadata. Do not hand-edit `plugins/catalog.v2.json`.
2. Run `python3 scripts/generate_plugins_catalog.py` and commit the regenerated
   aggregate together with the source edit (one small file plus its aggregate
   update per connector change).

Both:

3. Run `python3 scripts/validate_catalogs.py`.
4. Run `python3 scripts/test_mutation_validation.py` if validation rules changed.
5. Run `python3 scripts/build_catalogs.py` for the local dist bundle.

Aggregate shards are permitted exactly as implemented here: per-entry source
files plus a generated, CI drift-checked aggregate. Do not add other shards
without the same drift gate.
