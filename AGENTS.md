# AGENTS.md — prime-agent-catalog

Implementation contract for agents and maintainers editing this repository.
`README.md` is the public overview; this file is how you actually work here.

## Layout

```text
models/
  whitelist/<provider>.yml        # EDITABLE admission policy for synced providers
  manual/<provider>.yml           # EDITABLE full entries for providers with no upstream
  catalog.v1.json                 # GENERATED aggregate; the client-fetched model artifact
  admission-manifest.v1.json      # GENERATED admitted id manifest; CI sync-review surface
defaults.v1.json                   # EDITABLE preferred default model (provider/model-id)
plugins/
  services/<server>.json          # EDITABLE truth: one MCP service entry per file
  catalog.v2.json                 # GENERATED aggregate; the client-fetched plugin artifact
  examples/                       # user-facing local-services authoring example
exporter/
  generate-models.ts              # the models exporter: upstream fetch + mapping knowledge
  vendor/                         # its trimmed type/constant deps (no client behavior)
  tsconfig.json                   # exporter typecheck (npm run exporter:typecheck)
scripts/
  generate_plugins_catalog.py     # builds plugins/catalog.v2.json; --check = drift gate
  validate_catalogs.py            # structural + security validation, Python stdlib only
  test_mutation_validation.py     # negative tests guarding the validator
.github/workflows/ci.yml          # validate -> plugins drift -> mutations
.github/CODEOWNERS                # required reviewers on every file
SECURITY.md                       # production trust boundary + required repo settings
```

## Authoring rules

- Synced models: edit `models/whitelist/<provider>.yml`, then run `npm run catalog:export` in this repo.
- Manual models: edit `models/manual/<provider>.yml`, then run `npm run catalog:export` in this repo.
- The model flow is `models/whitelist/*.yml` plus `models/manual/*.yml` through `exporter/generate-models.ts` to `models/catalog.v1.json` plus `models/admission-manifest.v1.json`.
- The old `models/providers/` layer is gone. `scripts/generate_models_catalog.py` is retired.
- The admission manifest is the CI id-set accident check and the sync review surface. It records the exact admitted ids per provider in aggregate order.
- Never hand-edit `models/catalog.v1.json` or `models/admission-manifest.v1.json`. Hand-editing the aggregate without a sync run fails CI via manifest mismatch.
- Plugins: edit `plugins/services/<server>.json`, then regenerate. `scripts/generate_plugins_catalog.py` hardcodes `PLUGINS_CATALOG_VERSION = 2`; there is no `plugins/index.json`.
- Never hand-edit `plugins/catalog.v2.json`; it is regenerated and drift fails CI.
- All JSON is canonical: tab-indented, deterministic key order, trailing newline. YAML is parsed only by the TypeScript exporter under `exporter/`, not by this repository's Python tooling.
- Each `models/*/<provider>.yml` file is per provider. Each `plugins/services/<server>.json` file is one connector = one server id; several files can share a service brand (for example, the zoom family: `zoom`, `zoom-chat`, `zoom-meetings`, `zoom-tasks`, `zoom-whiteboard`, and `zoom-canvas` all carry `service: zoom`).
- Plugin source files keep only working client data; the import-time audit dossier (`sources`, `auth.metadata`, `auth.alternatives`, detailed provenance) was stripped because git history preserves the audit evidence.

## Commands

```bash
python3 -m py_compile scripts/validate_catalogs.py scripts/generate_plugins_catalog.py scripts/test_mutation_validation.py
python3 scripts/validate_catalogs.py
python3 scripts/generate_plugins_catalog.py --check
python3 scripts/test_mutation_validation.py
npm run generate        # plugins generator only
npm test                # validate + mutation tests
npm install             # once, for the exporter toolchain (yaml, tsx, typescript)
npm run catalog:export  # regenerate catalog.v1.json + admission-manifest from live upstreams
npm run exporter:typecheck
```

## Validation (enforced by CI)

`scripts/validate_catalogs.py` checks:

- JSON parses; envelopes and versions stay compatible.
- `models/` top-level JSON files are exactly `models/catalog.v1.json` and `models/admission-manifest.v1.json`; plugin service files are named after their server ids, and `plugins/` top-level JSON files are exactly `catalog.v2.json`.
- The admission manifest has canonical form, provider names match `^[a-z0-9][a-z0-9-]*$`, and every per-provider id list matches the aggregate ids in the same order.
- Model entries match the consumer schema: allowed keys, limits, compat shapes.
- MCP entries match the transport, auth, setup, verification, and provenance shape.
- Ids and keys are unique; ordering is deterministic; sizes and counts are bounded; MCP summary counts match entries.
- URLs are HTTPS, carry no credentials or fragments, and never point at literal loopback/private/link-local hosts.
- No OAuth client ids or secrets anywhere; secret-pattern scan on all payloads.

`scripts/test_mutation_validation.py` mutates fresh copies and asserts the validator rejects: duplicate ids, model request headers, bad versions, embedded secrets, credential and private URLs, OAuth client id/secret, malformed transports, count/order drift, stale plugin aggregates, hand-edited aggregates, manifest missing/extra/order-drift ids, filename mismatches, deleted plugin source files, stripped dossier fields, top-level `sources`, and missing provenance.

## PR and commit conventions (tracking contract)

Model changes are tracked one model per PR, named for greppability:

- Add a model: title and commit subject `add model: <model-id>` (for example
  `add model: claude-opus-5-5`), branch `add-model/<model-id>`. The PR covers
  every provider surface for that one model — whitelist ids, manual entries,
  and the regenerated aggregate + manifest together.
- Remove a model: `remove model: <model-id>`, branch `remove-model/<model-id>`.
- Cross-cutting regenerations that no single model owns (upstream drift,
  exporter fixes that change derived data, sync-blocker repairs): prefix
  `sync:` — for example `sync: refresh catalog from live upstreams`, branch
  `sync/<topic>`.
<<<<<<< HEAD
=======
- Repo-process or CI changes: prefix `ci:` — for example `ci: enforce the
  pr title convention`, branch `ci/<topic>`.
>>>>>>> origin/main
- Stack per-model PRs when the aggregate would conflict: base the second
  model's branch on the first model's branch (and so on). GitHub retargets
  the stack automatically as each PR merges; never force-push to unstitch it.
- A PR body states: the surfaces added, the exporter commit that produced the
  generated artifacts, and the validation results (`npm test`).
<<<<<<< HEAD
=======
- The title formats are enforced: ci.yml runs `scripts/check_pr_title.py` on
  every PR whose diff touches `models/` and fails the build on a non-matching
  title; `scripts/test_check_pr_title.py` guards the matcher.
>>>>>>> origin/main
- The client repo (PrimeIntellect-ai/prime-agent) uses `models: add <ids>`
  for compiled-catalog regenerations; its compiled catalog is one generated
  artifact, so batching several models in one client PR is fine — the
  per-model tracking unit lives here.

## Syncing from provider catalog endpoints

This repository is self-sufficient: `exporter/generate-models.ts` (plus its
vendored type/constant deps) lives here and carries all per-provider fetch
and mapping knowledge. It fetches models.dev, the OpenRouter API, the Vercel
AI Gateway, and the public Prime Inference catalog, applies the admission
policy, and regenerates the model aggregate and admission manifest in place.
The prime-agent client only consumes the generated artifacts — no catalog
data logic lives there.

Run `npm run catalog:export` from the repo root after editing whitelist or
manual policy files. The exporter never runs in CI: it hits live upstreams
(non-deterministic), so syncs are maintainer-run commits validated by the
Python suite.

`models/whitelist/<provider>.yml` is the PR-reviewed admission policy for synced providers:

- `source` names the upstream source expected by the exporter.
- `ids` lists the exact admitted model ids in catalog order.
- `globs` admits matching upstream ids in addition to `ids`; each glob-admitted id is reported by the exporter.
- Removing an id from `ids` is the reviewed deletion path. The exporter delists that model from both the aggregate and manifest and reports it loudly.
- Whitelisted ids missing from upstream keep the last committed `models/catalog.v1.json` entry and are reported as not-in-upstream.

`models/manual/<provider>.yml` stores hand-written full entries for providers with no synced upstream. Manual providers are emitted verbatim by the exporter and are never synced.

Current policy inventory: `models/whitelist/` contains 30 synced providers; `models/manual/` contains only `openai-codex.yml`.

The Python catalog tooling remains stdlib-only and never parses `whitelist/` or `manual/`; it validates only the committed model aggregate and admission manifest (the TypeScript exporter under `exporter/` is the YAML-reading generator). prime-inference is never synced here; clients fetch it live with credentials.

Run the exporter from this repository:

```bash
npm install
npm run catalog:export
```

## Adding a model — decision rules for agents

Follow this order. Every rule exists because a failure mode was observed.

1. **Is the provider implemented by the Prime Agent client?** If not, STOP. The
   client drops any catalog entry whose `(provider, api, baseUrl)` does not match
   a compiled transport. A new provider needs a client transport plus a client
   release first; the catalog can add models to existing providers only.
2. **Does an upstream catalog exist?** Check models.dev
   (`https://models.dev`) for the provider. Pick the slug by PRODUCT, not by
   name: match the endpoint the client actually calls. Verified traps: our
   `zai` is the coding-plan product, so its source is `zai-coding-plan`, NOT the
   plain `zai` API slug; our `kimi-coding` maps to `kimi-for-coding`;
   `vercel-ai-gateway` maps to the `vercel` slug. OpenRouter and Vercel fetch
   their own billing-authoritative endpoints instead of models.dev.
3. **Upstream exists → whitelist. NEVER manual.** Add the exact id (or an
   intentional glob) to `models/whitelist/<provider>.yml` and run the exporter;
   metadata (name, cost, context, limits, thinkingLevelMap from
   `reasoning_options`) comes from upstream. Manual entries for an upstream
   provider go stale and will drift from the next sync review.
4. **No upstream anywhere → manual.** This is the ONLY case for
   `models/manual/<provider>.yml`: hand-written full entries for surfaces no
   aggregator can enumerate. Today that is exactly one provider:
   `openai-codex.yml` (ChatGPT subscription — OAuth-gated, client-version-
   negotiated catalog). If you are adding a second manual file, you must be able
   to state why no upstream exists for it.
5. **Manual entry requirements:** complete schema (id, name, api, provider,
   baseUrl, reasoning, input, cost, contextWindow, maxTokens; optional
   thinkingLevelMap/featured/compat), verified against the provider's own
   docs — never guessed. NO `headers` key: the client silently drops entries
   carrying request headers; header values live in the client's compiled
   transport templates.
6. **After adding:** run the exporter, review the emitted
   `catalog.v1.json` + `admission-manifest.v1.json` diffs (a valid add appears
   in BOTH), run the full catalog suite, and commit the yml plus the two
   generated artifacts together. An id hand-added to the aggregate without the
   exporter fails CI on manifest mismatch.
7. **Removing a model:** delete its id from the whitelist (the reviewed
   deletion path) and run the exporter — it disappears from the aggregate and
   manifest together. Never edit the generated artifacts directly.
8. **New synced provider:** needs an exporter mapping block in
   `exporter/generate-models.ts` (api/baseUrl/compat knowledge)
   plus a new whitelist yml with a `source` the exporter recognizes — a mismatch
   is a hard error. Then the same flow as 3.

## Invariants

- Never hand-edit model artifacts; never bypass the manifest check.
- Schema changes ship as new versioned files (`catalog.v3.json`) plus a client release; old clients keep fetching the old path.
- Do not add source shards without a generated, drift-checked aggregate.
- `thinkingLevelMap` entries must be verified against the provider's real API surface; never blanket-populate.
- Model catalog entries never carry `headers`. Request headers live in the client's compiled transport templates; the sync exporter strips them, and the validator rejects them — catalog data must never change what a request sends.
- Catalog data must never contain credentials, OAuth client ids, or non-public endpoints.

## History

Initial payloads imported from `PrimeIntellect-ai/prime-agent`:
`models/catalog.v1.json` from PR #2138 head `1089d8d1`
(SHA-256 `238eedb13e770e3ec51d9f72849507e07cc6e8030fdb0c21804e54e241fd1a47`),
`plugins/catalog.v2.json` from main `b6ac5d014`
(SHA-256 `adacb5f57f18c548bb95c04faa48de12f5e91d4dbe0be0d28ffdd6d4dfe2882a`).
Upstream plugin snapshots, import report, and OAuth metadata audit remain in
prime-agent git history at that commit.
