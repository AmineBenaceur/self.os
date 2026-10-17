# self.os

A portable, plain-text memory and goals system for AI assistants.

Your context — who you are, what you're working toward, the people in your life, how you want
assistants to behave — lives here as Markdown files with a little YAML frontmatter. Any model
that can read files (or be handed a text bundle) can use it. OpenClaw is the first-class
target; Claude, ChatGPT, local models, etc. work through the same files.

## Principles

1. **Plain text, git-versioned.** No database. Every change is a diff you can review or revert.
2. **One subject per file.** A fact about X lives in X's file, nowhere else.
3. **Model-agnostic core, thin adapters.** `vault/` + `AGENTS.md` are the contract.
   `adapters/` only teach a specific runtime where to look.
4. **You stay in control.** Assistants propose; writes are small, tagged, and reviewable.

## Layout

```
AGENTS.md              # The contract: how any assistant reads and writes this repo
vault/
  profile/
    identity.md        # Who you are (stable facts)
    preferences.md     # How assistants should behave with you
  goals/               # One file per goal, with status + check-ins
  people/              # One file per person (birthday lives in frontmatter)
  areas/               # Ongoing involvements: projects, responsibilities
  journal/             # Dated append-only log: YYYY-MM-DD.md
schema/
  frontmatter.md       # Field reference for each file type
adapters/
  openclaw/            # Skill + workspace snippet for OpenClaw (Finnigan)
  claude/              # CLAUDE.md pointer for Claude / Claude Code
  generic/             # System prompt for any other model
tools/
  selfos.py            # CLI: validate, index, birthdays, goals, bundle
```

## Quick start

```bash
python tools/selfos.py validate        # check frontmatter across the vault
python tools/selfos.py index           # regenerate vault/INDEX.md
python tools/selfos.py birthdays 30    # birthdays in the next 30 days
python tools/selfos.py goals           # active goals + days since last check-in
python tools/selfos.py bundle > ctx.md # one-file context for models without file access
```

No dependencies beyond Python 3.10+.

## Hooking up an assistant

| Runtime | How |
|---|---|
| OpenClaw | Copy `adapters/openclaw/skills/self-os` into your workspace `skills/`, set `SELFOS_HOME`. See `adapters/openclaw/README.md`. |
| Claude Code | Drop `adapters/claude/CLAUDE.md` in the repo root (or `@import` it). |
| Anything else | Paste `adapters/generic/system-prompt.md` plus `selfos.py bundle` output. |

## Privacy

This repo will hold personal information. **Keep it private.** The `vault/` here ships with
example placeholders only; replace them with your own data after the repo is private.
Never store passwords, account numbers, or government IDs here.
