# AGENTS.md — prime-agent-catalog

Implementation contract for agents and maintainers editing this repository.
`README.md` is the public overview; this file is how you actually work here.

## Layout

```text
models/
  whitelist/<provider>.yml    # EDITABLE admission policy for synced providers
  manual/<provider>.yml       # EDITABLE full entries for providers with no upstream
  providers/<provider>.json   # GENERATED synced/manual record; ordered model array per provider
  catalog.v1.json             # GENERATED aggregate; the client-fetched artifact
plugins/
  services/<server>.json       # EDITABLE truth: one MCP service entry per file
  index.json                  # EDITABLE truth: version + sources envelope
  catalog.v2.json             # GENERATED aggregate; the client-fetched artifact
  examples/                   # user-facing local-services authoring example
scripts/
  generate_models_catalog.py   # builds models/catalog.v1.json; --check = drift gate
  generate_plugins_catalog.py  # builds plugins/catalog.v2.json; --check = drift gate
  validate_catalogs.py         # structural + security validation, Python stdlib only
  test_mutation_validation.py  # negative tests guarding the validator
.github/workflows/ci.yml       # validate -> models drift -> plugins drift -> mutations
.github/CODEOWNERS             # required reviewers on every file
SECURITY.md                    # production trust boundary + required repo settings
```

## Authoring rules

- Synced models: edit `models/whitelist/<provider>.yml`, then run the Prime Agent exporter and regenerate.
- Manual models: edit `models/manual/<provider>.yml`, then run the Prime Agent exporter and regenerate.
- Plugins: edit `plugins/services/<server>.json` (or `plugins/index.json` for
  envelope metadata), then regenerate.
- Never hand-edit the aggregates (`models/catalog.v1.json`,
  `plugins/catalog.v2.json`); they are regenerated and drift fails CI.
- Commit editable source files, generated provider files, and the regenerated aggregate together.
- All JSON is canonical: tab-indented, deterministic key order, trailing
  newline. Provider/service files are named after their id (provider slug /
  server id); the validators enforce the match. YAML is parsed only by the
  Prime Agent TypeScript exporter, not by this repository's Python tooling.
- Each `models/*/<provider>.yml` and `models/providers/<provider>.json` file is per provider. Each `plugins/services/<server>.json` file is one connector = one server id; several files can share a service brand (for example, the zoom family: `zoom`, `zoom-chat`, `zoom-meetings`, `zoom-tasks`, `zoom-whiteboard`, and `zoom-canvas` all carry `service: zoom`).

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
  service files are named after their server ids.
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
publish catalog endpoints. `PrimeIntellect-ai/prime-agent` carries all per-provider
fetch and mapping knowledge in `packages/ai/scripts/generate-models.ts`; run it
with `--catalog-out <this-repo>` to export provider files here.

`models/whitelist/<provider>.yml` is the PR-reviewed admission policy for synced
providers:

- `source` names the upstream source expected by the exporter.
- `ids` lists the exact admitted model ids in catalog order.
- `globs` admits matching upstream ids in addition to `ids`; each glob-admitted
  id is reported by the exporter.
- Removing an id from `ids` is the reviewed deletion path. The exporter delists
  that model from the generated provider file and reports it loudly.
- Whitelisted ids missing from upstream keep the last committed
  `models/providers/<provider>.json` entry and are reported as not-in-upstream.

`models/manual/<provider>.yml` stores hand-written full entries for providers
with no synced upstream. Manual providers are emitted verbatim by the exporter
and are never synced.

The Python catalog tooling remains stdlib-only and never parses `whitelist/` or
`manual/`; it validates only the generated JSON provider files and aggregates.
prime-inference is never synced here; clients fetch it live with credentials.

Run the exporter from a `PrimeIntellect-ai/prime-agent` checkout:

```bash
cd /path/to/prime-agent/packages/ai
npm run catalog:export -- /path/to/prime-agent-catalog
```

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
