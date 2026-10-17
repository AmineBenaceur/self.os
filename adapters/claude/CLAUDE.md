# self.os for Claude

**Best option: the MCP server.** It gives Claude tools for goals, habits, check-ins and reviews.

```bash
claude mcp add selfos -- uvx --from git+https://github.com/AmineBenaceur/self.os selfos-mcp
```

**Alternative: file access.** If Claude Code is working inside a clone of this repo, copy this
file to the repo root as `CLAUDE.md`. Claude will then read and follow `AGENTS.md`, which defines
how to read the vault, write to it, and coach.

@AGENTS.md
