# AGENTS.md — prime-agent-catalog

Implementation contract for agents and maintainers editing this repository.
`README.md` is the public overview; this file is how you actually work here.

## Layout

```text
models/
  providers/<provider>.json   # EDITABLE truth: ordered model array per provider
  catalog.v1.json             # GENERATED aggregate; the client-fetched artifact
plugins/
  entries/<server>.json       # EDITABLE truth: one MCP service entry per file
  index.json                  # EDITABLE truth: version + sources envelope
  catalog.v2.json             # GENERATED aggregate; the client-fetched artifact
  examples/                   # user-facing local-services authoring example
scripts/
  generate_models_catalog.py   # builds models/catalog.v1.json; --check = drift gate
  generate_plugins_catalog.py  # builds plugins/catalog.v2.json; --check = drift gate
  validate_catalogs.py         # structural + security validation, Python stdlib only
  test_mutation_validation.py  # negative tests guarding the validator
sync-policy.json               # whitelist growth policy for upstream syncs
.github/workflows/ci.yml       # validate -> models drift -> plugins drift -> mutations
.github/CODEOWNERS             # required reviewers on every file
SECURITY.md                    # production trust boundary + required repo settings
```

## Authoring rules

- Models: edit `models/providers/<provider>.json`, then regenerate.
- Plugins: edit `plugins/entries/<server>.json` (or `plugins/index.json` for
  envelope metadata), then regenerate.
- Never hand-edit the aggregates (`models/catalog.v1.json`,
  `plugins/catalog.v2.json`); they are regenerated and drift fails CI.
- Commit source files and the regenerated aggregate together.
- All JSON is canonical: tab-indented, deterministic key order, trailing
  newline. Provider/entry files are named after their id (provider slug /
  server id); the validators enforce the match.

## Commands

```bash
python3 -m py_compile scripts/validate_catalogs.py scripts/generate_models_catalog.py scripts/generate_plugins_catalog.py scripts/test_mutation_validation.py
python3 scripts/validate_catalogs.py
python3 scripts/generate_models_catalog.py --check
python3 scripts/generate_plugins_catalog.py --check
python3 scripts/test_mutation_validation.py
npm run generate   # both generators
npm test            # validate + mutation tests
```

## Validation (enforced by CI)

`scripts/validate_catalogs.py` checks:

- JSON parses; envelopes and versions stay compatible.
- `models/` holds exactly the generated catalog plus `providers/`; plugins
  entry files are named after their server ids.
- Committed aggregates equal regeneration from their sources (drift fails).
- Model entries match the consumer schema: allowed keys, limits, compat shapes.
- MCP entries match the transport, auth, setup, verification, and provenance
  shape.
- Ids and keys are unique; ordering is deterministic; sizes and counts are
  bounded; MCP summary counts match entries.
- URLs are HTTPS, carry no credentials or fragments, and never point at literal
  loopback/private/link-local hosts.
- No OAuth client ids or secrets anywhere; secret-pattern scan on all payloads.

`scripts/test_mutation_validation.py` mutates fresh copies and asserts the
validator rejects: duplicate ids, bad versions, embedded secrets, credential and
private URLs, OAuth client id/secret, malformed transports, count/order drift,
stale aggregates, hand-edited aggregates, filename mismatches, and deleted
source files.

## Syncing from provider catalog endpoints

Gateway providers (OpenRouter, Vercel AI Gateway, models.dev-sourced providers)
publish catalog endpoints. `PrimeIntellect-ai/prime-agent` carries the fetch and
mapping logic in `packages/ai/scripts/generate-models.ts`; run it with
`--catalog-out <this-repo>` to export provider files here. The sync is
whitelist-safe:

- Refresh-only by default: metadata updates for model ids already present.
  Never adds, never deletes.
- New models require an explicit `--allow-new <provider>=<glob>` flag or a
  glob in root `sync-policy.json` (PR-reviewed growth policy).
- Deletions are always manual, reviewed PRs.
- prime-inference is never synced here; clients fetch it live with credentials.

Run the exporter from a `PrimeIntellect-ai/prime-agent` checkout:

```bash
cd /path/to/prime-agent/packages/ai
npm run catalog:export -- /path/to/prime-agent-catalog
```

The root `sync-policy.json` is the PR-reviewed growth policy. Keep `allowNew`
empty for refresh-only providers. Add globs there only when the PR intends to
admit matching new upstream model ids.

## Invariants

- Never hand-edit aggregates; never bypass the drift gate.
- Schema changes ship as new versioned files (`catalog.v3.json`) plus a client
  release; old clients keep fetching the old path.
- Do not add source shards without a generated, drift-checked aggregate.
- `thinkingLevelMap` entries must be verified against the provider's real API
  surface; never blanket-populate.
- Model catalog entries never carry `headers`. Request headers live in the
  client's compiled transport templates; the sync exporter strips them, and the
  validator rejects them — catalog data must never change what a request sends.
- Catalog data must never contain credentials, OAuth client ids, or
  non-public endpoints.

## History

Initial payloads imported from `PrimeIntellect-ai/prime-agent`:
`models/catalog.v1.json` from PR #2138 head `1089d8d1`
(SHA-256 `238eedb13e770e3ec51d9f72849507e07cc6e8030fdb0c21804e54e241fd1a47`),
`plugins/catalog.v2.json` from main `b6ac5d014`
(SHA-256 `adacb5f57f18c548bb95c04faa48de12f5e91d4dbe0be0d28ffdd6d4dfe2882a`).
Upstream plugin snapshots, import report, and OAuth metadata audit remain in
prime-agent git history at that commit.
