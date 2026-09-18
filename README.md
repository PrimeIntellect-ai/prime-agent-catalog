# prime-agent-catalog

This repository maintains public catalogs Prime Agent for the following:
- default models and providers
- default MCP service plugins

Prime Agent clients fetche these at runtime, so a merged PR here ships new models and connectors to every user without a Prime Agent release. `AGENTS.md` documents the full layout, tooling commands, validation rules, and invariants for agents and maintainers making catalog changes. CI validates structure, security invariants, and manifest/drift checks.

#### Models:
- For public provider models, we maintain a [whitelist](https://github.com/PrimeIntellect-ai/prime-agent-catalog/tree/main/models/whitelist) of ``models.dev`` models and providers, which list all models and providers available on Prime Agent by default
- We also maintain a [list](https://github.com/PrimeIntellect-ai/prime-agent-catalog/tree/main/models/manual) of providers that are not documented in ``models.dev``, like the OpenAI ChatGPT Subscription
- We use these sources of truth to generate our model catalog, which keeps track of model pricing and metadata across providers

#### Plugins:
- Plugin payloads are generated from small editable source files (`plugins/services/`)


