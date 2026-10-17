# OpenClaw adapter

Gets your OpenClaw agent (on the Pi) reading and writing self.os.

## Setup

```bash
# on the Pi
git clone git@github.com:AmineBenaceur/self.os.git ~/self.os
echo 'export SELFOS_HOME=~/self.os' >> ~/.bashrc

# install the skill into the OpenClaw workspace
cp -r ~/self.os/adapters/openclaw/skills/self-os ~/.openclaw/workspace/skills/
```

Adjust the workspace path if yours differs. Then add the snippet below to your workspace
`AGENTS.md` (or `USER.md`) so the agent loads self.os every session instead of relying
on OpenClaw's built-in `MEMORY.md`:

```markdown
## Long-term memory
Your long-term memory about me is the self.os vault at $SELFOS_HOME.
Use the `self-os` skill. Prefer it over MEMORY.md for anything durable.
```

## Heartbeat

To get birthday and goal check-in nudges, add a line to your `HEARTBEAT.md`
(or a cron job) telling the agent to run the skill's "Daily heartbeat" section once a day.

## Sync

The Pi is the only writer by default. Pull on other machines; if you edit from elsewhere,
have the agent `git pull --rebase` before writing.
