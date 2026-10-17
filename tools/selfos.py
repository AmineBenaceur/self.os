#!/usr/bin/env python3
"""self.os CLI — validate, index, and query the vault. Stdlib only.

Usage:
  selfos.py [--vault PATH] init [--git]
  selfos.py [--vault PATH] validate
  selfos.py index
  selfos.py birthdays [DAYS]
  selfos.py goals [--all]
  selfos.py bundle [--include journal]

Vault resolution (first match wins):
  --vault PATH  ->  $SELFOS_VAULT  ->  <repo>/vault

<repo>/vault is git-ignored: it holds YOUR data and never goes into the framework repo.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "template"
VAULT = Path(os.environ.get("SELFOS_VAULT", ROOT / "vault")).expanduser()

REQUIRED = {
    "_all": ["type", "title", "description", "updated"],
    "goal": ["status"],
    "person": ["relationship"],
    "area": ["status"],
}
ENUMS = {
    "type": {"profile", "goal", "person", "area", "journal"},
    ("goal", "status"): {"active", "paused", "done", "dropped"},
    ("area", "status"): {"active", "paused", "closed"},
    ("goal", "horizon"): {"week", "month", "quarter", "year", "life"},
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BDAY_RE = re.compile(r"^(\d{4}|-)-(\d{2})-(\d{2})$")
LOG_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2}):")


@dataclass
class Doc:
    path: Path
    meta: dict = field(default_factory=dict)
    body: str = ""

    @property
    def rel(self) -> str:
        return self.path.relative_to(VAULT).as_posix()

    @property
    def type(self) -> str:
        return str(self.meta.get("type", ""))


# ---------- parsing ----------

def _value(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [s.strip().strip("'\"") for s in inner.split(",")] if inner else []
    return raw.strip("'\"")


def parse(path: Path) -> Doc:
    text = path.read_text(encoding="utf-8")
    doc = Doc(path)
    if not text.startswith("---"):
        doc.body = text
        return doc
    parts = text.split("---", 2)
    if len(parts) < 3:
        doc.body = text
        return doc
    for line in parts[1].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, val = line.partition(":")
        if sep:
            doc.meta[key.strip()] = _value(val)
    doc.body = parts[2].lstrip("\n")
    return doc


def load(include_templates: bool = False) -> list[Doc]:
    docs = []
    for p in sorted(VAULT.rglob("*.md")):
        if p.name == "INDEX.md":
            continue
        if p.name.startswith("_") and not include_templates:
            continue
        docs.append(parse(p))
    return docs


# ---------- commands ----------

def cmd_init(args) -> int:
    if VAULT.exists() and any(VAULT.iterdir()):
        print(f"Vault already exists at {VAULT} — leaving it alone.")
        return 0
    shutil.copytree(TEMPLATE, VAULT, dirs_exist_ok=True)
    today = date.today().isoformat()
    for p in (VAULT / "profile").glob("*.md"):
        p.write_text(p.read_text(encoding="utf-8").replace("YYYY-MM-DD", today), encoding="utf-8")
    print(f"Created vault at {VAULT}")
    if "--git" in args:
        subprocess.run(["git", "init", "-q"], cwd=VAULT, check=True)
        print("Initialized a separate git repo inside the vault for your private history.")
        print("Point it at a PRIVATE remote:  git -C vault remote add origin <private-repo-url>")
    cmd_index([])
    print(f"Next: fill in {VAULT / 'profile' / 'identity.md'} and preferences.md")
    return 0

def cmd_validate(_args) -> int:
    if not VAULT.exists():
        print(f"No vault at {VAULT}. Run: python tools/selfos.py init")
        return 1
    errors = []
    for d in load():
        m = d.meta
        if not m:
            errors.append(f"{d.rel}: missing frontmatter")
            continue
        for k in REQUIRED["_all"] + REQUIRED.get(d.type, []):
            if not m.get(k):
                errors.append(f"{d.rel}: missing '{k}'")
        if d.type and d.type not in ENUMS["type"]:
            errors.append(f"{d.rel}: unknown type '{d.type}'")
        for (t, k), allowed in ((k, v) for k, v in ENUMS.items() if isinstance(k, tuple)):
            if d.type == t and m.get(k) and m[k] not in allowed:
                errors.append(f"{d.rel}: {k} '{m[k]}' not in {sorted(allowed)}")
        for k in ("updated", "target_date"):
            if m.get(k) and not DATE_RE.match(str(m[k])):
                errors.append(f"{d.rel}: {k} must be YYYY-MM-DD")
        if m.get("birthday") and not BDAY_RE.match(str(m["birthday"])):
            errors.append(f"{d.rel}: birthday must be YYYY-MM-DD or --MM-DD")
    for e in errors:
        print(e)
    print(f"{'FAIL' if errors else 'OK'}: {len(errors)} problem(s)")
    return 1 if errors else 0


def cmd_index(_args) -> int:
    groups: dict[str, list[Doc]] = {}
    for d in load():
        groups.setdefault(d.path.parent.relative_to(VAULT).as_posix(), []).append(d)
    lines = ["# Vault index", "", "_Generated by `tools/selfos.py index`. Do not edit._", ""]
    for folder in sorted(groups):
        lines.append(f"## {folder}")
        for d in groups[folder]:
            extra = f" · {d.meta['status']}" if d.meta.get("status") else ""
            aliases = d.meta.get("aliases") or []
            alias = f" (aka {', '.join(aliases)})" if aliases else ""
            lines.append(f"- [{d.meta.get('title', d.path.stem)}]({d.rel}){alias}{extra} — {d.meta.get('description', '')}")
        lines.append("")
    (VAULT / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {VAULT / 'INDEX.md'}")
    return 0


def _next_birthday(bday: str, today: date) -> tuple[date, int | None] | None:
    m = BDAY_RE.match(bday)
    if not m:
        return None
    year, month, day = m.group(1), int(m.group(2)), int(m.group(3))
    for y in (today.year, today.year + 1):
        try:
            nxt = date(y, month, day)
        except ValueError:  # Feb 29 in a non-leap year
            nxt = date(y, 3, 1)
        if nxt >= today:
            age = nxt.year - int(year) if year != "-" else None
            return nxt, age
    return None


def cmd_birthdays(args) -> int:
    days = int(args[0]) if args else 30
    today = date.today()
    hits = []
    for d in load():
        if d.type != "person" or not d.meta.get("birthday"):
            continue
        res = _next_birthday(str(d.meta["birthday"]), today)
        if res and (res[0] - today).days <= days:
            hits.append((res[0], res[1], d))
    for when, age, d in sorted(hits, key=lambda h: h[0]):
        delta = (when - today).days
        turning = f", turning {age}" if age else ""
        print(f"{when:%a %b %d} (in {delta}d) — {d.meta['title']}{turning}  [{d.rel}]")
    if not hits:
        print(f"No birthdays in the next {days} days.")
    return 0


def cmd_goals(args) -> int:
    show_all = "--all" in args
    today = date.today()
    for d in load():
        if d.type != "goal" or (not show_all and d.meta.get("status") != "active"):
            continue
        logs = [LOG_RE.match(l) for l in d.body.splitlines()]
        last = max((date.fromisoformat(m.group(1)) for m in logs if m), default=None)
        every = int(d.meta.get("checkin_every_days") or 7)
        since = (today - last).days if last else None
        due = since is None or since >= every
        flag = "DUE " if due else "    "
        since_txt = f"{since}d since check-in" if since is not None else "never checked in"
        target = f", target {d.meta['target_date']}" if d.meta.get("target_date") else ""
        print(f"{flag}{d.meta['title']} [{d.meta.get('status')}] — {since_txt}{target}  [{d.rel}]")
    return 0


def cmd_bundle(args) -> int:
    include_journal = "journal" in args
    out = [(ROOT / "AGENTS.md").read_text(encoding="utf-8"), ""]
    for d in load():
        if d.type == "journal" and not include_journal:
            continue
        out.append(f"\n<!-- file: vault/{d.rel} -->\n")
        out.append(d.path.read_text(encoding="utf-8"))
    sys.stdout.write("\n".join(out))
    return 0


COMMANDS = {
    "init": cmd_init,
    "validate": cmd_validate,
    "index": cmd_index,
    "birthdays": cmd_birthdays,
    "goals": cmd_goals,
    "bundle": cmd_bundle,
}


def main(argv: list[str]) -> int:
    global VAULT
    if len(argv) >= 2 and argv[0] == "--vault":
        VAULT = Path(argv[1]).expanduser().resolve()
        argv = argv[2:]
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 2
    return COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
