# OpenClaw adapter

Gets an OpenClaw agent reading and writing a self.os vault.

## Setup

```bash
# on the machine running OpenClaw
git clone https://github.com/AmineBenaceur/self.os.git ~/self.os
cd ~/self.os && python3 tools/selfos.py init --git
echo 'export SELFOS_HOME=~/self.os' >> ~/.bashrc

# install the skill into your OpenClaw workspace (adjust path if yours differs)
cp -r ~/self.os/adapters/openclaw/skills/self-os ~/.openclaw/workspace/skills/
```

Then add this to your workspace `AGENTS.md` (or `USER.md`) so the agent uses self.os
for durable memory instead of OpenClaw's built-in `MEMORY.md`:

```markdown
## Long-term memory
Your long-term memory about me is the self.os vault at $SELFOS_HOME/vault.
Use the `self-os` skill. Prefer it over MEMORY.md for anything durable.
```

## Heartbeat

For birthday and goal check-in nudges, add a line to `HEARTBEAT.md` (or a cron job)
telling the agent to run the skill's "Heartbeat" section daily (habit nudges, check-ins, birthdays) and weekly (review).

## Sync

The vault is its own git repo (from `init --git`). Push it to a **private** remote to back
it up or share it across machines. The framework repo at `~/self.os` can be updated with
`git pull` without touching your data.
