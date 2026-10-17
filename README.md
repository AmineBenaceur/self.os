# self.os

**Turn any AI assistant into a goal coach that actually helps you follow through.**

self.os is a plain-text framework your agents share: your goals, the habits that drive them,
your reasons, your plans for when things go wrong, plus the context a good assistant needs
(who you are, how you like to work, the people in your life). It's Markdown with a little
YAML frontmatter, so it's diffable, greppable, and readable by any model or runtime.

It's built around what research on goal pursuit consistently supports, rather than a to-do list:

| Practice | In self.os |
|---|---|
| Specific if-then plans ("When X, I'll do Y") | `## Plan` in every goal; agents remind at the cue |
| Planning for obstacles up front | `## Obstacles` as "If <obstacle>, then <response>" |
| Tracking measurable progress | `metric`/`baseline`/`target` + `value=` check-ins → pace |
| Outcomes driven by habits | `habits/` linked to goals, with a minimum version for bad days |
| Regular review and re-planning | `selfos review` builds a weekly review with questions |
| Focus | Soft cap on active goals; agents ask what a new goal replaces |
| Supportive accountability | Agents ask what got in the way and adjust the plan, never shame |

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
    ├── goals/            ← one file per goal: why, plan, obstacles, metric, log
    ├── habits/           ← repeatable actions linked to goals
    ├── reviews/          ← weekly reviews written by `selfos review --write`
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

## The coaching loop

1. **Set**: the agent walks you through why, what done looks like, a metric (if any),
   an if-then plan, likely obstacles, and the habit that drives it.
2. **Do**: the agent nudges at the habit's cue and logs `done` or `missed — <reason>`.
3. **Check in**: at the goal's cadence it asks for the number and compares it to pace.
   When you're behind, it asks what got in the way and offers one adjustment.
4. **Review**: weekly, `selfos review` summarizes goals, habits, what's coming up, and
   the questions worth answering. You re-plan; the agent updates the files.

The full agent protocol is in [`AGENTS.md`](AGENTS.md#coaching).

## A goal file

```markdown
---
type: goal
title: Run a half marathon
description: Finish the Calgary half marathon in under 2:15
status: active
start_date: 2026-09-28
target_date: 2027-05-30
checkin_every_days: 7
metric: weekly distance
unit: km
baseline: 8
target: 40
updated: 2026-10-16
---
## Why
- I want proof I can commit to something hard outside work [stated]

## Plan
- When my alarm goes off Tue/Thu/Sat at 6:00, I put on the clothes I laid out and go. [stated]

## Obstacles
- If it's below -15°C, then I run on the treadmill instead. [stated]

## Log
- 2026-10-12: value=14 skipped Saturday, cold [stated]
```

```
$ selfos goals
    Run a half marathon [active]
      progress: 14/40 km · 19% · on pace
      4d since check-in · target 2027-05-30
      habit: Run 3x per week: 2/3 this week, 100% of last 4 weeks, streak 2
```

See [`examples/vault/`](examples/vault) for a complete vault with a goal, a habit, a paused
goal, and a person.

## CLI

```bash
python tools/selfos.py init [--git]       # create vault from template (optionally as its own repo)
python tools/selfos.py validate           # check frontmatter across the vault
python tools/selfos.py index              # regenerate vault/INDEX.md
python tools/selfos.py goals [--all]      # goals with pace, check-in status, linked habits
python tools/selfos.py habits             # this week's habit progress, streaks, last miss
python tools/selfos.py review [--write]   # weekly review; --write saves to vault/reviews/
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
