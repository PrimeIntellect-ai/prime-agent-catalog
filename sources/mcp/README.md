# MCP source snapshot

This tree preserves the MCP catalog migration inputs copied from
`PrimeIntellect-ai/prime-agent` commit `b6ac5d014d99401b55820835a4966584271e9a3c`.

The files under `prime-agent-b6ac5d014/packages/ai/mcp-catalog/` are a
byte-preserved copy of the upstream pinned snapshots, overrides, import report,
audit evidence, examples, and README.

The TypeScript files copied under `prime-agent-b6ac5d014/packages/ai/scripts/`
and `prime-agent-b6ac5d014/packages/ai/src/mcp/` are reference-only migration
context. They still import Prime Agent package dependencies and are not runnable
standalone in this repository. CI does not claim deterministic regeneration from
these sources.

The stable runtime payloads remain:

- `catalog/models.v1.json`
- `catalog/mcp-services.v2.json`
