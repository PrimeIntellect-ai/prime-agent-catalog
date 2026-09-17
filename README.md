# prime-agent-catalog

The public catalogs for Prime Agent: the models it can use and the MCP service
plugins it can connect to. Prime Agent fetches these at runtime, so a merged PR
here ships new models and connectors to every user without a client release.

## Stable public paths

| Path | Envelope |
| --- | --- |
| `models/catalog.v1.json` | `{ "schemaVersion": 1, "models": [...] }` |
| `plugins/catalog.v2.json` | `{ "version": 2, "sources": [...], "counts": {...}, "entries": [...] }` |

These two files are the client contract: Prime Agent fetches exactly these URLs
and validates the payloads with its compiled parser. Their paths and schemas
change only with a client release. Everything else in this repository exists to
produce and protect them.

## How it works

- Catalog payloads are generated from small editable source files
  (`models/providers/`, `plugins/entries/`, `plugins/index.json`).
- CI validates structure, security invariants, and that the committed
  aggregates match their sources — drift fails the build.
- Every change is reviewed by a code owner (`.github/CODEOWNERS`) under the
  settings required by `SECURITY.md`.

## Contributing

- Add a model or refresh a provider's metadata.
- Add or update an MCP service connector.
- Bulk-sync gateway providers from their catalog endpoints, gated by a
  whitelist.

`AGENTS.md` documents the full layout, tooling commands, validation rules, and
invariants for agents and maintainers making those changes.

## History

The initial payloads were imported from `PrimeIntellect-ai/prime-agent`:
models from PR #2138 head `1089d8d1`, the MCP catalog from main `b6ac5d014`.
Exact import hashes are recorded in `AGENTS.md`; upstream snapshots and audit
evidence remain in prime-agent git history.

MIT licensed — see `LICENSE`.
