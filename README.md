# self.os

**A portable, plain-text goals and memory framework for AI assistants.**

self.os gives any AI agent a shared, structured place to keep what it knows about you:
who you are, how you want it to behave, the goals you're working toward, the people in your
life, and your ongoing projects. Everything is Markdown with a little YAML frontmatter, so
it's diffable, greppable, and readable by any model or runtime.

The framework is public. **Your data never is.** Your vault lives in a git-ignored `vault/`
folder (or anywhere you point `SELFOS_VAULT`), and can be versioned in its own private repo.

---

## Quick start

```bash
git clone https://github.com/AmineBenaceur/self.os.git
cd self.os
python tools/selfos.py init --git      # creates your private vault/ (git-ignored)
```

Then fill in `vault/profile/identity.md` and `vault/profile/preferences.md`, and add your
first goal from `vault/goals/_template.md`.

Requires Python 3.10+. No other dependencies.

## How it works

```
self.os/                  ← this repo (public framework)
├── AGENTS.md             ← the contract every assistant follows
├── template/             ← starter vault copied by `init`
├── examples/vault/       ← a fictional filled-in vault (docs + CI)
├── schema/               ← frontmatter field reference
├── tools/selfos.py       ← CLI
├── adapters/             ← runtime-specific glue (OpenClaw, Claude, generic)
└── vault/                ← YOUR data · git-ignored · optionally its own private repo
    ├── INDEX.md          ← generated map of the vault
    ├── profile/          ← identity.md, preferences.md
    ├── goals/            ← one file per goal, with check-in log
    ├── people/           ← one file per person, birthdays in frontmatter
    ├── areas/            ← ongoing projects and responsibilities
    └── journal/          ← dated, append-only log
```

**Principles**

1. **Plain text, versioned.** No database. Every change is a reviewable diff.
2. **One subject per file.** A fact about X lives in X's file, nowhere else.
3. **Model-agnostic core, thin adapters.** `AGENTS.md` + the vault format are the contract.
4. **The owner stays in control.** Facts are tagged `[stated]` (owner said it) or
   `[inferred]` (agent's guess) so you can always tell them apart.

## A goal file

```markdown
---
type: goal
title: Run a half marathon
description: Finish a 21.1 km race this spring
status: active
horizon: quarter
target_date: 2027-05-31
checkin_every_days: 7
updated: 2026-10-16
---
# Run a half marathon

## Why
- Want a concrete fitness target for the spring [stated]

## Next actions
- [ ] Pick a race and register

## Log
- 2026-10-16: Created goal [stated]
```

Agents append to `## Log` on each check-in; `selfos goals` flags any goal whose last log
entry is older than `checkin_every_days`.

## CLI

```bash
python tools/selfos.py init [--git]       # create vault from template (optionally as its own repo)
python tools/selfos.py validate           # check frontmatter across the vault
python tools/selfos.py index              # regenerate vault/INDEX.md
python tools/selfos.py goals [--all]      # active goals; DUE = needs a check-in
python tools/selfos.py birthdays [DAYS]   # upcoming birthdays (default 30 days)
python tools/selfos.py bundle             # whole vault as one file, for models without file access

python tools/selfos.py --vault examples/vault goals   # try it on the example data
```

## Connecting an agent

| Runtime | Setup |
|---|---|
| **OpenClaw** | Install the skill in `adapters/openclaw/`. See its README. |
| **Claude Code** | Copy `adapters/claude/CLAUDE.md` to the repo root. |
| **Any other model** | Use `adapters/generic/system-prompt.md` + `selfos bundle` output. |
| **Your own agent** | Have it read `AGENTS.md` and follow it. That's the whole API. |

## Keeping your data private

- `vault/` is in `.gitignore`. `git status` in the framework repo should never show your data.
- `init --git` makes `vault/` its own repo. Push it **only** to a private remote:
  `git -C vault remote add origin git@github.com:<you>/my-vault.git`
- To keep the vault somewhere else entirely (e.g. a synced folder), set `SELFOS_VAULT`.
- Bundles (`ctx.md`) are git-ignored too, since they contain your data.
- Never store passwords, API keys, account numbers, or government IDs in a vault.

## Contributing

Improvements to the format, CLI, and adapters are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
New runtime adapters are especially useful.

## License

[MIT](LICENSE)
