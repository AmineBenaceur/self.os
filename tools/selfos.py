#!/usr/bin/env python3
"""self.os CLI: a goal-coaching loop over a plain-text vault. Stdlib only.

Usage:
  selfos.py [--vault PATH] init [--git]
  selfos.py [--vault PATH] validate
  selfos.py [--vault PATH] index
  selfos.py [--vault PATH] goals [--all]
  selfos.py [--vault PATH] habits
  selfos.py [--vault PATH] review [--write]
  selfos.py [--vault PATH] birthdays [DAYS]
  selfos.py [--vault PATH] bundle [--include journal]

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

TYPES = {"profile", "goal", "habit", "person", "area", "journal", "review"}
REQUIRED = {
    "_all": ["type", "title", "description", "updated"],
    "goal": ["status"],
    "habit": ["status", "frequency"],
    "person": ["relationship"],
    "area": ["status"],
}
ENUMS = {
    ("goal", "status"): {"active", "paused", "done", "dropped"},
    ("goal", "horizon"): {"week", "month", "quarter", "year", "life"},
    ("habit", "status"): {"active", "paused", "retired"},
    ("area", "status"): {"active", "paused", "closed"},
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BDAY_RE = re.compile(r"^(\d{4}|-)-(\d{2})-(\d{2})$")
FREQ_RE = re.compile(r"^(?:daily|(\d+)/(week|month))$")
LOG_RE = re.compile(r"^\s*- (\d{4}-\d{2}-\d{2}):\s*(.*)$")
VALUE_RE = re.compile(r"\bvalue=(-?\d+(?:\.\d+)?)")
MISSED_RE = re.compile(r"^\s*missed\b", re.I)

DEFAULT_MAX_ACTIVE_GOALS = 5


# ---------- model ----------

@dataclass
class LogEntry:
    day: date
    text: str

    @property
    def value(self) -> float | None:
        m = VALUE_RE.search(self.text)
        return float(m.group(1)) if m else None

    @property
    def missed(self) -> bool:
        return bool(MISSED_RE.match(self.text))


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

    @property
    def title(self) -> str:
        return str(self.meta.get("title", self.path.stem))

    def date(self, key: str) -> date | None:
        v = self.meta.get(key)
        return date.fromisoformat(v) if isinstance(v, str) and DATE_RE.match(v) else None

    def num(self, key: str) -> float | None:
        try:
            return float(self.meta[key])
        except (KeyError, TypeError, ValueError):
            return None

    def log(self) -> list[LogEntry]:
        """Entries under '## Log', oldest first."""
        entries, in_log = [], False
        for line in self.body.splitlines():
            if line.startswith("## "):
                in_log = line.strip().lower() == "## log"
                continue
            m = LOG_RE.match(line) if in_log else None
            if m:
                try:
                    entries.append(LogEntry(date.fromisoformat(m.group(1)), m.group(2)))
                except ValueError:
                    pass
        return sorted(entries, key=lambda e: e.day)


# ---------- parsing ----------

def _value(raw: str):
    raw = raw.split(" #", 1)[0].strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [s.strip().strip("'\"") for s in inner.split(",")] if inner else []
    return raw.strip("'\"")


def parse(path: Path) -> Doc:
    text = path.read_text(encoding="utf-8")
    doc = Doc(path)
    parts = text.split("---", 2) if text.startswith("---") else []
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
        if p.name == "INDEX.md" or (p.name.startswith("_") and not include_templates):
            continue
        docs.append(parse(p))
    return docs


def of_type(docs: list[Doc], t: str) -> list[Doc]:
    return [d for d in docs if d.type == t]


def preferences(docs: list[Doc]) -> dict:
    for d in docs:
        if d.rel == "profile/preferences.md":
            return d.meta
    return {}


# ---------- goal analytics ----------

@dataclass
class Pace:
    latest: float
    expected: float
    target: float
    unit: str
    on_pace: bool
    pct_done: float

    def __str__(self) -> str:
        u = f" {self.unit}" if self.unit else ""
        verdict = "on pace" if self.on_pace else f"behind (expected {fmt(self.expected)}{u} by now)"
        return f"{fmt(self.latest)}/{fmt(self.target)}{u} · {self.pct_done:.0%} · {verdict}"


def fmt(x: float) -> str:
    return f"{round(x, 1):g}"


def pace(goal: Doc, today: date) -> Pace | None:
    base, target = goal.num("baseline"), goal.num("target")
    if base is None or target is None or target == base:
        return None
    values = [(e.day, e.value) for e in goal.log() if e.value is not None]
    latest = values[-1][1] if values else base
    pct = max(0.0, min(1.0, (latest - base) / (target - base)))
    start, end = goal.date("start_date"), goal.date("target_date")
    if start and end and end > start:
        frac = max(0.0, min(1.0, (today - start).days / (end - start).days))
        expected = base + frac * (target - base)
    else:
        expected = latest  # no timeline: can't be behind
    ahead = latest >= expected if target > base else latest <= expected
    return Pace(latest, expected, target, str(goal.meta.get("unit", "")), ahead, pct)


def last_checkin(goal: Doc) -> date | None:
    log = goal.log()
    return log[-1].day if log else None


def checkin_due(goal: Doc, today: date) -> tuple[bool, int | None]:
    last = last_checkin(goal)
    every = int(goal.num("checkin_every_days") or 7)
    since = (today - last).days if last else None
    return (since is None or since >= every), since


def stalled(goal: Doc, today: date) -> bool:
    _, since = checkin_due(goal, today)
    every = int(goal.num("checkin_every_days") or 7)
    return since is None or since >= 2 * every


# ---------- habit analytics ----------

def parse_freq(freq: str) -> tuple[int, str] | None:
    m = FREQ_RE.match(str(freq).strip())
    if not m:
        return None
    return (1, "day") if m.group(1) is None else (int(m.group(1)), m.group(2))


def period_start(day: date, unit: str) -> date:
    if unit == "day":
        return day
    if unit == "week":
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def prev_period(start: date, unit: str) -> date:
    if unit == "day":
        return start - timedelta(days=1)
    if unit == "week":
        return start - timedelta(days=7)
    return (start - timedelta(days=1)).replace(day=1)


@dataclass
class HabitStats:
    required: int
    unit: str
    this_period: int
    recent_hit_rate: float  # over the last 4 completed periods
    streak: int             # consecutive completed periods hit
    last_miss_reason: str | None


def habit_stats(h: Doc, today: date) -> HabitStats | None:
    f = parse_freq(h.meta.get("frequency", ""))
    if not f:
        return None
    req, unit = f
    log = h.log()
    done = [e.day for e in log if not e.missed]
    count = lambda s, e: sum(1 for d in done if s <= d < e)

    cur = period_start(today, unit)
    nxt = today + timedelta(days=1)
    this_period = count(cur, nxt)

    first = log[0].day if log else today
    hits, streak, checked, s, e = [], 0, 0, prev_period(cur, unit), cur
    streak_open = True
    while checked < 52 and e > first:
        hit = count(s, e) >= req
        if checked < 4:
            hits.append(hit)
        if streak_open:
            streak = streak + 1 if hit else streak
            streak_open = hit
        checked += 1
        s, e = prev_period(s, unit), s
    rate = sum(hits) / len(hits) if hits else 0.0
    misses = [e for e in log if e.missed]
    reason = None
    if misses:
        text = re.sub(r"\s*\[\w+\]\s*$", "", misses[-1].text)
        reason = re.sub(r"^missed\s*[—:-]*\s*", "", text, flags=re.I) or "no reason given"
    return HabitStats(req, unit, this_period, rate, streak, reason)


def habits_for(goal: Doc, habits: list[Doc]) -> list[Doc]:
    return [h for h in habits if h.meta.get("goal") == goal.path.stem]


# ---------- commands ----------

def cmd_init(args) -> int:
    if VAULT.exists() and any(VAULT.iterdir()):
        print(f"Vault already exists at {VAULT}. Leaving it alone.")
        return 0
    shutil.copytree(TEMPLATE, VAULT, dirs_exist_ok=True)
    today = date.today().isoformat()
    for p in (VAULT / "profile").glob("*.md"):
        p.write_text(p.read_text(encoding="utf-8").replace("YYYY-MM-DD", today), encoding="utf-8")
    print(f"Created vault at {VAULT}")
    if "--git" in args:
        subprocess.run(["git", "init", "-q"], cwd=VAULT, check=True)
        print("Initialized a separate git repo inside the vault for your private history.")
        print(f"Point it at a PRIVATE remote:  git -C {VAULT} remote add origin <private-repo-url>")
    cmd_index([])
    print(f"Next: fill in {VAULT / 'profile' / 'identity.md'} and preferences.md, then add a goal.")
    return 0


def cmd_validate(_args) -> int:
    if not VAULT.exists():
        print(f"No vault at {VAULT}. Run: python tools/selfos.py init")
        return 1
    docs = load()
    errors, warnings = [], []
    goal_stems = {d.path.stem for d in of_type(docs, "goal")}
    for d in docs:
        m = d.meta
        if not m:
            errors.append(f"{d.rel}: missing frontmatter")
            continue
        for k in REQUIRED["_all"] + REQUIRED.get(d.type, []):
            if not m.get(k):
                errors.append(f"{d.rel}: missing '{k}'")
        if d.type and d.type not in TYPES:
            errors.append(f"{d.rel}: unknown type '{d.type}'")
        for (t, k), allowed in ENUMS.items():
            if d.type == t and m.get(k) and m[k] not in allowed:
                errors.append(f"{d.rel}: {k} '{m[k]}' not in {sorted(allowed)}")
        for k in ("updated", "start_date", "target_date", "resume_date"):
            if m.get(k) and not DATE_RE.match(str(m[k])):
                errors.append(f"{d.rel}: {k} must be YYYY-MM-DD")
        if m.get("birthday") and not BDAY_RE.match(str(m["birthday"])):
            errors.append(f"{d.rel}: birthday must be YYYY-MM-DD or --MM-DD")

        if d.type == "goal":
            for k in ("baseline", "target", "checkin_every_days"):
                if m.get(k) and d.num(k) is None:
                    errors.append(f"{d.rel}: {k} must be a number")
            if m.get("metric") and (d.num("baseline") is None or d.num("target") is None):
                errors.append(f"{d.rel}: metric needs numeric baseline and target")
            if m.get("status") == "paused" and not m.get("resume_date"):
                warnings.append(f"{d.rel}: paused without resume_date. When should it be revisited?")
            if m.get("status") == "active":
                body = d.body.lower()
                if "## plan" not in body or "when " not in body.split("## plan", 1)[1].split("##", 1)[0]:
                    warnings.append(f"{d.rel}: no if-then plan under '## Plan' ('When <cue>, I will <action>.')")
        if d.type == "habit":
            if m.get("frequency") and not parse_freq(m["frequency"]):
                errors.append(f"{d.rel}: frequency must be 'daily', 'N/week' or 'N/month'")
            if m.get("goal") and m["goal"] not in goal_stems:
                errors.append(f"{d.rel}: goal '{m['goal']}' not found in goals/")

    cap = int(preferences(docs).get("max_active_goals") or DEFAULT_MAX_ACTIVE_GOALS)
    active = [g for g in of_type(docs, "goal") if g.meta.get("status") == "active"]
    if len(active) > cap:
        warnings.append(f"{len(active)} active goals (cap {cap}). Pause or drop one to keep focus.")

    for w in warnings:
        print(f"warn: {w}")
    for e in errors:
        print(f"error: {e}")
    print(f"{'FAIL' if errors else 'OK'}: {len(errors)} error(s), {len(warnings)} warning(s)")
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
            lines.append(f"- [{d.title}]({d.rel}){alias}{extra}: {d.meta.get('description', '')}")
        lines.append("")
    (VAULT / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {VAULT / 'INDEX.md'}")
    return 0


def _goal_line(g: Doc, habits: list[Doc], today: date) -> list[str]:
    due, since = checkin_due(g, today)
    status = g.meta.get("status")
    head = f"{'DUE ' if due and status == 'active' else '    '}{g.title} [{status}]"
    out = [head]
    p = pace(g, today)
    if p:
        out.append(f"      progress: {p}")
    since_txt = f"{since}d since check-in" if since is not None else "never checked in"
    tgt = f" · target {g.meta['target_date']}" if g.meta.get("target_date") else ""
    out.append(f"      {since_txt}{tgt}  [{g.rel}]")
    if status == "paused" and g.meta.get("resume_date"):
        out.append(f"      paused until {g.meta['resume_date']}")
    for h in habits_for(g, habits):
        s = habit_stats(h, today)
        if s:
            out.append(f"      habit: {h.title}: {s.this_period}/{s.required} this {s.unit}, "
                       f"{s.recent_hit_rate:.0%} of last 4 {s.unit}s, streak {s.streak}")
    return out


def cmd_goals(args) -> int:
    show_all = "--all" in args
    today = date.today()
    docs = load()
    habits = [h for h in of_type(docs, "habit") if h.meta.get("status") == "active"]
    goals = [g for g in of_type(docs, "goal") if show_all or g.meta.get("status") == "active"]
    if not goals:
        print("No active goals. Copy goals/_template.md to start one.")
    for g in goals:
        print("\n".join(_goal_line(g, habits, today)))
    return 0


def cmd_habits(_args) -> int:
    today = date.today()
    for h in of_type(load(), "habit"):
        if h.meta.get("status") != "active":
            continue
        s = habit_stats(h, today)
        if not s:
            print(f"{h.title}: invalid frequency  [{h.rel}]")
            continue
        left = max(0, s.required - s.this_period)
        todo = f"{left} to go this {s.unit}" if left else f"done for this {s.unit}"
        cue = f" · cue: {h.meta['cue']}" if h.meta.get("cue") else ""
        print(f"{h.title}: {s.this_period}/{s.required} ({todo}) · streak {s.streak} · "
              f"{s.recent_hit_rate:.0%} recent{cue}  [{h.rel}]")
        if s.last_miss_reason:
            print(f"      last miss: {s.last_miss_reason}")
    return 0


def _upcoming_birthdays(docs: list[Doc], today: date, days: int):
    hits = []
    for d in of_type(docs, "person"):
        res = _next_birthday(str(d.meta.get("birthday", "")), today)
        if res and (res[0] - today).days <= days:
            hits.append((res[0], res[1], d))
    return sorted(hits, key=lambda h: h[0])


def build_review(today: date) -> tuple[str, str]:
    docs = load()
    goals = of_type(docs, "goal")
    habits = [h for h in of_type(docs, "habit") if h.meta.get("status") == "active"]
    active = [g for g in goals if g.meta.get("status") == "active"]
    iso = today.isocalendar()
    week_id = f"{iso[0]}-W{iso[1]:02d}"
    wk_start = today - timedelta(days=today.weekday())
    L = [
        "---", "type: review", f"title: Weekly review {week_id}",
        f"description: Goals, habits and the week ahead, generated {today.isoformat()}",
        f"updated: {today.isoformat()}", "---", f"# Weekly review {week_id}", "",
        f"_Week of {wk_start:%b %d}. Generated by `selfos review`. Answer the questions inline._", "",
        "## Goals",
    ]
    if not active:
        L.append("- No active goals.")
    questions = []
    for g in active:
        p = pace(g, today)
        due, since = checkin_due(g, today)
        bits = [str(p)] if p else []
        bits.append(f"last check-in {since}d ago" if since is not None else "never checked in")
        L.append(f"- **{g.title}**: {' · '.join(bits)}")
        if stalled(g, today):
            questions.append(f"**{g.title}** has stalled. What got in the way, and what's the smallest step that would restart it? Or should it be paused?")
        elif p and not p.on_pace:
            questions.append(f"**{g.title}** is behind pace. Adjust the plan, the target, or the date?")
    L += ["", "## Habits"]
    if not habits:
        L.append("- No active habits.")
    for h in habits:
        s = habit_stats(h, today)
        if not s:
            continue
        L.append(f"- **{h.title}**: {s.this_period}/{s.required} this {s.unit} · streak {s.streak} · {s.recent_hit_rate:.0%} of last 4")
        if s.recent_hit_rate < 0.5 and s.last_miss_reason:
            questions.append(f"**{h.title}** is landing under half the time (last miss: {s.last_miss_reason}). Shrink it, move the cue, or plan for that obstacle?")
    paused_due = [g for g in goals if g.meta.get("status") == "paused" and g.date("resume_date") and g.date("resume_date") <= today]
    for g in paused_due:
        questions.append(f"**{g.title}** was paused until {g.meta['resume_date']}. Resume, push back, or drop?")
    cap = int(preferences(docs).get("max_active_goals") or DEFAULT_MAX_ACTIVE_GOALS)
    if len(active) > cap:
        questions.insert(0, f"You have {len(active)} active goals (cap {cap}). Which one can wait?")

    L += ["", "## Coming up"]
    soon = []
    for when, age, d in _upcoming_birthdays(docs, today, 14):
        soon.append(f"- {when:%a %b %d}: {d.title}'s birthday" + (f" (turning {age})" if age else ""))
    for g in active:
        td = g.date("target_date")
        if td and 0 <= (td - today).days <= 30:
            soon.append(f"- {td:%a %b %d}: target date for {g.title}")
    L += soon or ["- Nothing in the next two weeks."]

    L += ["", "## Questions"]
    L += [f"{i}. {q}" for i, q in enumerate(questions, 1)] or ["1. Everything's on track. What's one thing that would make next week great?"]
    L += ["", "## Wins this week", "- ", "", "## Focus for next week", "- ", ""]
    return week_id, "\n".join(L)


def cmd_review(args) -> int:
    week_id, text = build_review(date.today())
    if "--write" in args:
        out = VAULT / "reviews" / f"{week_id}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            print(f"{out} already exists. Not overwriting.")
            return 1
        out.write_text(text, encoding="utf-8")
        print(f"Wrote {out}")
    else:
        print(text)
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
            return nxt, (nxt.year - int(year) if year != "-" else None)
    return None


def cmd_birthdays(args) -> int:
    days = int(args[0]) if args else 30
    today = date.today()
    hits = _upcoming_birthdays(load(), today, days)
    for when, age, d in hits:
        turning = f", turning {age}" if age else ""
        print(f"{when:%a %b %d} (in {(when - today).days}d): {d.title}{turning}  [{d.rel}]")
    if not hits:
        print(f"No birthdays in the next {days} days.")
    return 0


def cmd_bundle(args) -> int:
    include_journal = "journal" in args
    out = [(ROOT / "AGENTS.md").read_text(encoding="utf-8"), ""]
    for d in load():
        if d.type in ("journal", "review") and not include_journal:
            continue
        out.append(f"\n<!-- file: vault/{d.rel} -->\n")
        out.append(d.path.read_text(encoding="utf-8"))
    sys.stdout.write("\n".join(out))
    return 0


COMMANDS = {
    "init": cmd_init,
    "validate": cmd_validate,
    "index": cmd_index,
    "goals": cmd_goals,
    "habits": cmd_habits,
    "review": cmd_review,
    "birthdays": cmd_birthdays,
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
