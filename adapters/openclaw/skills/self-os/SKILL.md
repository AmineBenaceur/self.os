---
name: self-os
description: Read and update the owner's self.os vault — identity, preferences, goals, people and birthdays, ongoing areas, and daily journal. Use whenever a request touches the owner's life, plans, people, or progress, or when they tell you something worth remembering.
---

# self.os

The owner's long-term memory lives in a git repo at `$SELFOS_HOME`
(default `~/self.os`). The full rules are in `$SELFOS_HOME/AGENTS.md`. Read it once per session.

## Every session
1. Read `$SELFOS_HOME/vault/INDEX.md`, `vault/profile/identity.md`, `vault/profile/preferences.md`.
2. Follow preferences for the rest of the session.

## Useful commands
```bash
python3 $SELFOS_HOME/tools/selfos.py birthdays 14   # upcoming birthdays
python3 $SELFOS_HOME/tools/selfos.py goals          # active goals; DUE = needs a check-in
python3 $SELFOS_HOME/tools/selfos.py index          # run after any write
python3 $SELFOS_HOME/tools/selfos.py validate
```

## Writing
- Follow AGENTS.md: one subject per file, `[stated]` tags, update instead of duplicate.
- After writing, commit: `cd $SELFOS_HOME && git add -A && git commit -m "memory: <what changed>"`.
  Push only if the owner has enabled it.

## Daily heartbeat (optional)
When run on a schedule: check `birthdays 7` and `goals`. Message the owner only if something
is due, with one short line per item.
