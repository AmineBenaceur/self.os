# Contributing

Thanks for helping. A few ground rules keep the framework useful across agents.

## What goes where

- **`AGENTS.md`**: the contract. Changes here affect every agent; keep them small and explain
  why in the PR.
- **`template/`**: what `init` copies. Placeholders only, never real data.
- **`examples/vault/`**: a fictional owner ("Sam Example"). Use it to demonstrate new fields.
- **`schema/frontmatter.md`**: document every new field here *and* enforce it in
  `tools/selfos.py validate`.
- **`selfos/mcp_server.py`**: MCP tools and prompts. New tools need a test in `tests/`.
- **`adapters/<runtime>/`**: one folder per runtime, with a README covering setup.

## Rules

1. **No personal data in PRs.** Don't commit anything from your own `vault/`.
2. **Stdlib only** in `selfos/`. The CLI and MCP server should run anywhere Python 3.10+ does.
3. **Backwards compatible format.** Existing vaults must keep validating. New fields are optional.
4. Run before opening a PR:
   ```bash
   python -m unittest discover tests
   python tools/selfos.py --vault examples/vault validate
   ```
