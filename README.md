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
the client contract. `models/catalog.v1.json` is GENERATED from
`models/providers/<provider>.json` by `scripts/generate_models_catalog.py`. The
plugins aggregate is GENERATED from `plugins/entries/<server>.json` plus
`plugins/index.json` (envelope metadata) by `scripts/generate_plugins_catalog.py`.
CI rejects a committed aggregate that drifts from its sources.

## File layout

```text
models/
  providers/              # EDITABLE truth: one <provider>.json model array per provider
  catalog.v1.json         # GENERATED aggregate; the stable client artifact
plugins/
  entries/                # EDITABLE truth: one <server>.json per MCP service
  index.json              # EDITABLE truth: version + sources envelope metadata
  catalog.v2.json         # GENERATED aggregate; the stable client artifact
  examples/               # local-services authoring example for users
scripts/
  generate_models_catalog.py      # builds models/catalog.v1.json from sources; --check = drift gate
  generate_plugins_catalog.py     # builds plugins/catalog.v2.json from sources; --check = drift gate
  validate_catalogs.py            # self-contained validation, Python stdlib only
  test_mutation_validation.py     # negative mutation tests for validator coverage
.github/workflows/ci.yml  # validation CI
.github/CODEOWNERS
SECURITY.md
package.json
```

## Validation rules

`python3 scripts/validate_catalogs.py` checks:

- JSON parses cleanly.
- Top-level envelopes and versions stay compatible.
- `models/` holds exactly `models/catalog.v1.json` and `models/providers/`, and
  the stable plugins payload exists at `plugins/catalog.v2.json`.
- Each `models/providers/<provider>.json` is named after its provider id, holds
  a canonical model array, uses provider ids matching `^[a-z0-9][a-z0-9-]*$`,
  has no duplicate model ids in the file, validates each model entry, and the
  committed `models/catalog.v1.json` equals the aggregate regenerated from
  `models/providers/` (drift fails CI).
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
transports, count/order drift, stale generated aggregates, hand-edited
aggregates, filename/server/provider mismatches, and deleted source files.

## Local commands

```bash
python3 -m py_compile scripts/validate_catalogs.py scripts/generate_models_catalog.py scripts/generate_plugins_catalog.py scripts/test_mutation_validation.py
python3 scripts/validate_catalogs.py
python3 scripts/generate_models_catalog.py --check
python3 scripts/generate_plugins_catalog.py --check
python3 scripts/test_mutation_validation.py
```

The same commands are also exposed through npm script names for convenience:

```bash
npm run validate
npm test
npm run generate
```

No npm dependencies are required.

## Updating catalog data

Models:

1. Edit the provider file under `models/providers/<provider>.json`.
2. Keep the file in canonical tab-indented JSON form.
3. Run `python3 scripts/generate_models_catalog.py` and commit the regenerated
   `models/catalog.v1.json` together with the provider source edit.

Plugins:

1. Edit one file per service under `plugins/entries/`, or `plugins/index.json`
   for envelope metadata. Do not hand-edit `plugins/catalog.v2.json`.
2. Run `python3 scripts/generate_plugins_catalog.py` and commit the regenerated
   aggregate together with the source edit (one small file plus its aggregate
   update per connector change).

Both:

1. Run `python3 scripts/validate_catalogs.py`.
2. Run `python3 scripts/test_mutation_validation.py` if validation rules changed.

Aggregate shards are permitted exactly as implemented here: per-provider or
per-entry source files plus a generated, CI drift-checked aggregate. Do not add
other shards without the same drift gate.

## History

The initial payloads were imported from `PrimeIntellect-ai/prime-agent`:
`models/catalog.v1.json` from PR #2138 head `1089d8d1`
(SHA-256 `238eedb13e770e3ec51d9f72849507e07cc6e8030fdb0c21804e54e241fd1a47`) and
`plugins/catalog.v2.json` from main `b6ac5d014`
(SHA-256 `adacb5f57f18c548bb95c04faa48de12f5e91d4dbe0be0d28ffdd6d4dfe2882a`).
The upstream plugin snapshots, import report, and OAuth metadata audit that
produced the MCP catalog remain in prime-agent git history at that commit.
