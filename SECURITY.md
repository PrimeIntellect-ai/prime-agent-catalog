# Security policy

## Production trust boundary

This repository is the source of truth for the public Prime Agent catalog payloads:

- `models/catalog.v1.json`
- `plugins/catalog.v2.json`

Production consumers must treat these files as trusted release artifacts only after
repository review and CI pass. `plugins/catalog.v2.json` is generated from
`plugins/services/` and `plugins/index.json`; CI rejects a committed aggregate that
drifts from those sources. The validator catches structural drift, duplicate
ids, unsafe literal URLs, embedded credential-like values, OAuth client ids or
secrets, malformed MCP transports, and count/order drift. It is not a runtime
network sandbox. Consumers still own request-time DNS, redirect, credential, and
SSRF protections.

## Reporting security issues

Report suspected catalog security issues privately to the Prime Intellect
maintainers. Do not open a public issue with secrets or exploit details.
