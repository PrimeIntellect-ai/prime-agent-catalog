# Security policy

## Production trust boundary

This repository is the source of truth for the public Prime Agent catalog payloads:

- `catalog/models.v1.json`
- `catalog/mcp-services.v2.json`

Production consumers must treat these files as trusted release artifacts only after
repository review and CI pass. The validator catches structural drift, duplicate
ids, unsafe literal URLs, embedded credential-like values, OAuth client ids or
secrets, malformed MCP transports, and count/order drift. It is not a runtime
network sandbox. Consumers still own request-time DNS, redirect, credential, and
SSRF protections.

The `sources/mcp/` tree is migration evidence and reference material. It is not a
runtime input and CI does not claim deterministic regeneration from it.

## Required repository settings

Before this repository feeds production clients, configure repository settings in
GitHub. Do not encode these settings in catalog data.

- Protect `main`.
- Require the CI workflow to pass before merge.
- Require pull request review by a code owner.
- Require branches to be up to date before merge.
- Restrict direct pushes to `main`.
- Require signed or verified commits if organization policy supports it.
- Keep GitHub Actions permissions read-only by default.

## Reporting security issues

Report suspected catalog security issues privately to the Prime Intellect
maintainers. Do not open a public issue with secrets or exploit details.
