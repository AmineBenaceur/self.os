# OpenClaw adapter

Turns your OpenClaw agent into a goal coach with long-term memory, backed by a self.os vault.
Works well on a Raspberry Pi: it's pure Python 3.10+, no other dependencies.

## 1. Install selfos

On the machine running OpenClaw:

```bash
# with uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install git+https://github.com/AmineBenaceur/self.os

# or with pipx
pipx install git+https://github.com/AmineBenaceur/self.os

selfos init --git      # creates ~/.selfos/vault as its own private git repo
```

Make sure the `selfos` command is on the PATH that OpenClaw uses (`which selfos`). To keep the
vault somewhere else, set `SELFOS_VAULT` in OpenClaw's environment.

## 2. Install the skill

Copy the skill folder into your OpenClaw workspace's `skills/` directory:

```bash
git clone --depth 1 https://github.com/AmineBenaceur/self.os /tmp/self.os
cp -r /tmp/self.os/adapters/openclaw/skills/self-os ~/.openclaw/workspace/skills/
```

(Adjust the workspace path if yours differs.) Restart the gateway or start a new session so
the skill is picked up.

## 3. Point the agent at it

Add to your workspace `AGENTS.md` (or `USER.md`):

```markdown
## Goals and long-term memory
My goals, habits, people and preferences live in self.os. Use the `self-os` skill: run
`selfos context` at the start of conversations, and record durable facts with `selfos` commands
rather than MEMORY.md.
```

## 4. Nudges (heartbeat)

Add to `HEARTBEAT.md`:

```markdown
- Follow the Heartbeat section of the self-os skill (habit nudges, due check-ins, birthdays;
  weekly review on my review day). Say nothing if nothing is due.
```

## Try it

Message your agent: *"Help me set a goal."* It should ask why, what done looks like, an if-then
plan and likely obstacles before creating anything. Then try *"I skipped my run today, it was
too cold"* and check it logs the miss with the reason and offers one adjustment.

## Back up the vault

`selfos init --git` made the vault a git repo. Add a **private** remote to back it up:

```bash
git -C ~/.selfos/vault remote add origin git@github.com:<you>/my-vault.git
git -C ~/.selfos/vault push -u origin main
```

Update self.os itself any time with `uv tool upgrade selfos` (or `pipx upgrade selfos`). Your vault is untouched.
