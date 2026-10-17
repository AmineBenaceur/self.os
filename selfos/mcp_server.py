"""self.os MCP server: exposes the vault and the goal-coaching loop to any MCP client.

Stdlib only. Speaks JSON-RPC 2.0 over stdio (newline-delimited), per the MCP spec.
Run with `selfos mcp` (or `python -m selfos mcp`). Vault: --vault / $SELFOS_VAULT / default.
"""
from __future__ import annotations

import json
import re
import sys
import traceback
from datetime import date, timedelta

from . import __version__, cli, edit

PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]

INSTRUCTIONS = """self.os is the user's private goal-coaching vault: identity, preferences, goals, habits,
people, projects and a journal, stored as Markdown.

- Call `get_context` at the start of a conversation. Follow the user's preferences in it for the whole session.
- You are a goal coach, not a tracker. When setting a goal, walk through: why, what done looks like,
  a metric if it's numeric, at least one if-then plan ("When <cue>, I will <action>."), likely obstacles
  ("If <obstacle>, then <response>."), and the habit that drives it. Ask one or two questions at a time.
- Respect the active-goal cap; if a new goal exceeds it, ask which goal it replaces or pauses.
- Check in at each goal's cadence, not more often. Ask for the number when there's a metric.
- After a miss: ask what got in the way, log it, and offer ONE adjustment (better cue, new if-then,
  minimum version, smaller target, later date). Never shame. Pausing with a resume date is a valid choice.
- When motivation dips, quote the user's own `Why`, not generic pep talk.
- Only record what the user actually said. Never store passwords, account numbers, or ID numbers.
The full protocol is in the `coach` prompt."""


# ---------- tool helpers ----------

def _today() -> date:
    return date.today()


def _parse_day(s: str | None) -> date:
    if not s:
        return _today()
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise edit.VaultError(f"date must be YYYY-MM-DD, got '{s}'")


def _rel(p) -> str:
    return p.relative_to(cli.VAULT).as_posix()


def _goal_summary(g: cli.Doc, habits: list[cli.Doc], today: date) -> dict:
    due, since = cli.checkin_due(g, today)
    p = cli.pace(g, today)
    out = {
        "name": g.path.stem,
        "title": g.title,
        "file": g.rel,
        "status": g.meta.get("status"),
        "description": g.meta.get("description"),
        "target_date": g.meta.get("target_date"),
        "days_since_checkin": since,
        "checkin_due": bool(due and g.meta.get("status") == "active"),
        "stalled": cli.stalled(g, today) if g.meta.get("status") == "active" else False,
    }
    if g.meta.get("resume_date"):
        out["resume_date"] = g.meta["resume_date"]
    if p:
        out["progress"] = {
            "metric": g.meta.get("metric"), "unit": p.unit, "latest": p.latest, "target": p.target,
            "expected_now": round(p.expected, 2), "percent": round(p.pct_done * 100), "on_pace": p.on_pace,
        }
    linked = []
    for h in cli.habits_for(g, habits):
        s = cli.habit_stats(h, today)
        if s:
            linked.append({"name": h.path.stem, "title": h.title, "this_period": s.this_period,
                           "required": s.required, "period": s.unit, "streak": s.streak})
    if linked:
        out["habits"] = linked
    return out


def _habit_summary(h: cli.Doc, today: date) -> dict:
    s = cli.habit_stats(h, today)
    out = {"name": h.path.stem, "title": h.title, "file": h.rel, "status": h.meta.get("status"),
           "goal": h.meta.get("goal"), "frequency": h.meta.get("frequency"), "cue": h.meta.get("cue")}
    if s:
        out.update(this_period=s.this_period, required=s.required, period=s.unit,
                   remaining=max(0, s.required - s.this_period), streak=s.streak,
                   recent_hit_rate=round(s.recent_hit_rate, 2), last_miss_reason=s.last_miss_reason)
    return out


def _cap(docs) -> tuple[int, int]:
    cap = int(cli.preferences(docs).get("max_active_goals") or cli.DEFAULT_MAX_ACTIVE_GOALS)
    active = sum(1 for g in cli.of_type(docs, "goal") if g.meta.get("status") == "active")
    return active, cap


def _reindex():
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        cli.cmd_index([])


def _need_vault():
    if not cli.VAULT.exists():
        raise edit.VaultError(f"No vault at {cli.VAULT}. Call `init_vault` first (or run `selfos init`).")


# ---------- tools ----------

def t_init_vault(args):
    if cli.VAULT.exists() and any(cli.VAULT.iterdir()):
        return {"created": False, "vault": str(cli.VAULT), "note": "Vault already exists."}
    cli.cmd_init(["--git"] if args.get("git") else [])
    return {"created": True, "vault": str(cli.VAULT),
            "next": "Ask the user about themselves and their preferences, then fill profile/identity.md and profile/preferences.md with add_note."}


def t_get_context(_args):
    _need_vault()
    today = _today()
    docs = cli.load()
    read = lambda rel: (cli.VAULT / rel).read_text(encoding="utf-8") if (cli.VAULT / rel).exists() else None
    habits = [h for h in cli.of_type(docs, "habit") if h.meta.get("status") == "active"]
    goals = [g for g in cli.of_type(docs, "goal") if g.meta.get("status") in ("active", "paused")]
    active, cap = _cap(docs)
    files = [{"file": d.rel, "type": d.type, "title": d.title, "description": d.meta.get("description")}
             for d in docs if d.type not in ("journal", "review")]
    return {
        "today": today.isoformat(),
        "vault": str(cli.VAULT),
        "preferences": read("profile/preferences.md"),
        "identity": read("profile/identity.md"),
        "goals": [_goal_summary(g, habits, today) for g in goals],
        "habits": [_habit_summary(h, today) for h in habits],
        "active_goals": active, "max_active_goals": cap,
        "upcoming_birthdays": t_upcoming_birthdays({"days": 14})["birthdays"],
        "files": files,
    }


def t_list_goals(args):
    _need_vault()
    today = _today()
    docs = cli.load()
    habits = [h for h in cli.of_type(docs, "habit") if h.meta.get("status") == "active"]
    goals = [g for g in cli.of_type(docs, "goal")
             if args.get("include_inactive") or g.meta.get("status") == "active"]
    active, cap = _cap(docs)
    return {"goals": [_goal_summary(g, habits, today) for g in goals],
            "active_goals": active, "max_active_goals": cap}


def t_list_habits(_args):
    _need_vault()
    today = _today()
    return {"habits": [_habit_summary(h, today) for h in cli.of_type(cli.load(), "habit")
                       if h.meta.get("status") == "active"]}


def t_read_file(args):
    _need_vault()
    p = edit.vault_path(args["path"])
    return {"file": _rel(p), "content": p.read_text(encoding="utf-8")}


def t_search(args):
    _need_vault()
    q = args["query"].strip().lower()
    if not q:
        raise edit.VaultError("query is empty")
    hits = []
    for d in cli.load():
        for i, line in enumerate(d.path.read_text(encoding="utf-8").splitlines(), 1):
            if q in line.lower():
                hits.append({"file": d.rel, "line": i, "text": line.strip()})
                if len(hits) >= 50:
                    return {"matches": hits, "truncated": True}
    return {"matches": hits, "truncated": False}


def _bullets(items, kind: str) -> str:
    items = [i for i in (items or []) if str(i).strip()]
    return "\n".join(edit.fact(i) for i in items) if items else f"<!-- {kind} -->"


def t_create_goal(args):
    _need_vault()
    plan = [p for p in (args.get("plan") or []) if p.strip()]
    if not plan:
        raise edit.VaultError("A goal needs at least one if-then plan ('When <cue>, I will <action>.'). Ask the user for one.")
    docs = cli.load()
    active, cap = _cap(docs)
    status = args.get("status", "active")
    if status == "active" and active >= cap and not args.get("confirm_over_cap"):
        raise edit.VaultError(
            f"User already has {active} active goals (cap {cap}). Ask which goal this replaces or should be paused, "
            "or call again with confirm_over_cap=true if they explicitly want to exceed it.")
    has_metric = args.get("metric") is not None
    if has_metric and (args.get("baseline") is None or args.get("target") is None):
        raise edit.VaultError("metric needs baseline and target")
    today = _today()
    meta = {
        "type": "goal", "title": args["title"], "description": args["description"], "status": status,
        "horizon": args.get("horizon"), "start_date": args.get("start_date") or today.isoformat(),
        "target_date": args.get("target_date"), "checkin_every_days": args.get("checkin_every_days", 7),
        "metric": args.get("metric"), "unit": args.get("unit"),
        "baseline": args.get("baseline"), "target": args.get("target"),
    }
    first = f"Created goal. value={edit._fm_value(args['baseline'])}" if has_metric else "Created goal"
    body = "\n".join([
        f"# {args['title']}", "",
        "## Why", _bullets(args.get("why"), "Why this matters"), "",
        "## Done looks like", _bullets([args.get("done_looks_like", "")], "Specific, observable outcome"), "",
        "## Plan", _bullets(plan, "If-then plans"), "",
        "## Obstacles", _bullets(args.get("obstacles"), "If <obstacle>, then <response>."), "",
        "## Next actions", "\n".join(f"- [ ] {a}" for a in args.get("next_actions") or []) or "- [ ] ", "",
        "## Log", edit.log_line(today, first), "",
    ])
    p = edit.create(f"goals/{edit.slugify(args['title'])}", meta, body)
    _reindex()
    return {"created": _rel(p), "name": p.stem, "active_goals": active + (status == "active"), "max_active_goals": cap}


def t_log_goal_checkin(args):
    _need_vault()
    p = edit.find_doc("goals", args["goal"])
    day = _parse_day(args.get("date"))
    note = args.get("note", "").strip()
    if args.get("value") is not None:
        note = f"value={edit._fm_value(float(args['value']))} {note}".strip()
    if not note:
        raise edit.VaultError("Provide a note and/or a value")
    edit.append_to_section(p, "Log", edit.log_line(day, note))
    g = cli.parse(p)
    habits = [h for h in cli.of_type(cli.load(), "habit") if h.meta.get("status") == "active"]
    return {"logged": _rel(p), "goal": _goal_summary(g, habits, _today())}


def t_update_goal(args):
    _need_vault()
    p = edit.find_doc("goals", args["goal"])
    fields = {}
    if args.get("status"):
        if args["status"] not in cli.ENUMS[("goal", "status")]:
            raise edit.VaultError(f"status must be one of {sorted(cli.ENUMS[('goal', 'status')])}")
        fields["status"] = args["status"]
        if args["status"] == "paused" and not args.get("resume_date"):
            raise edit.VaultError("Pausing needs a resume_date. Ask the user when to revisit it.")
        if args["status"] != "paused":
            fields["resume_date"] = None
    for k in ("resume_date", "target_date", "target", "checkin_every_days", "description"):
        if args.get(k) is not None:
            fields[k] = args[k]
    if fields:
        edit.set_meta(p, **fields)
    for section, key in (("Plan", "add_plan"), ("Obstacles", "add_obstacle"), ("Why", "add_why")):
        for line in args.get(key) or []:
            edit.append_to_section(p, section, edit.fact(line))
    if args.get("note"):
        edit.append_to_section(p, "Log", edit.log_line(_today(), args["note"]))
    return {"updated": _rel(p), "fields": list(fields)}


def t_create_habit(args):
    _need_vault()
    if not cli.parse_freq(args["frequency"]):
        raise edit.VaultError("frequency must be 'daily', 'N/week' or 'N/month'")
    goal = None
    if args.get("goal"):
        goal = edit.find_doc("goals", args["goal"]).stem
    meta = {"type": "habit", "title": args["title"],
            "description": args.get("description") or f"Habit: {args['title']}",
            "status": "active", "goal": goal, "frequency": args["frequency"], "cue": args.get("cue")}
    body = "\n".join([f"# {args['title']}", "", "## Minimum version",
                      _bullets([args.get("minimum_version", "")], "The version you do on a bad day"), "",
                      "## Log", ""])
    p = edit.create(f"habits/{edit.slugify(args['title'])}", meta, body)
    _reindex()
    return {"created": _rel(p), "name": p.stem, "goal": goal}


def t_log_habit(args):
    _need_vault()
    p = edit.find_doc("habits", args["habit"])
    day = _parse_day(args.get("date"))
    if args["done"]:
        text = "done" + (f" ({args['note']})" if args.get("note") else "")
    else:
        text = "missed — " + (args.get("reason") or "no reason given")
    edit.append_to_section(p, "Log", edit.log_line(day, text))
    return {"logged": _rel(p), "habit": _habit_summary(cli.parse(p), _today())}


def t_add_note(args):
    _need_vault()
    rel = args["path"]
    section = args.get("section")
    line = edit.fact(args["text"], "inferred" if args.get("inferred") else "stated")
    m = re.fullmatch(r"journal/(\d{4}-\d{2}-\d{2})(\.md)?", rel.strip().lstrip("/"))
    p = edit.vault_path(rel, must_exist=False)
    if not p.exists():
        if m:
            day = m.group(1)
            edit.create(f"journal/{day}", {"type": "journal", "title": day, "description": "Daily log"}, f"# {day}\n")
        elif args.get("create"):
            c = args["create"]
            folder = rel.split("/", 1)[0]
            ftype = {"people": "person", "areas": "area", "goals": "goal", "habits": "habit"}.get(folder, c.get("type"))
            meta = {"type": ftype, "title": c["title"], "description": c["description"]}
            if ftype == "person":
                meta.update(relationship=c.get("relationship", "friend"), birthday=c.get("birthday"),
                            aliases=c.get("aliases"))
            if ftype == "area":
                meta.update(status="active", aliases=c.get("aliases"))
            edit.create(rel, meta, f"# {c['title']}\n")
        else:
            raise edit.VaultError(f"'{rel}' doesn't exist. Pass `create` with title and description to create it.")
    _reindex()
    p = edit.vault_path(rel)
    if section:
        edit.append_to_section(p, section, line)
    else:
        with p.open("a", encoding="utf-8") as f:
            f.write(("" if p.read_text(encoding="utf-8").endswith("\n") else "\n") + line + "\n")
        edit.set_meta(p)
    return {"written": _rel(p), "line": line}


def t_weekly_review(args):
    _need_vault()
    week_id, text = cli.build_review(_today())
    out = {"week": week_id, "review": text}
    if args.get("write"):
        p = cli.VAULT / "reviews" / f"{week_id}.md"
        if p.exists():
            out["note"] = f"reviews/{week_id}.md already exists; not overwritten."
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            out["written"] = f"reviews/{week_id}.md"
    return out


def t_upcoming_birthdays(args):
    _need_vault()
    today = _today()
    days = int(args.get("days", 30))
    return {"birthdays": [
        {"date": when.isoformat(), "in_days": (when - today).days, "name": d.title, "file": d.rel,
         **({"turning": age} if age else {})}
        for when, age, d in cli._upcoming_birthdays(cli.load(), today, days)]}


def t_validate(_args):
    _need_vault()
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.cmd_validate([])
    return {"ok": code == 0, "report": buf.getvalue().strip()}


S = lambda **p: p  # noqa: E731  (schema helper)
STR, NUM, INT, BOOL = {"type": "string"}, {"type": "number"}, {"type": "integer"}, {"type": "boolean"}
LIST = {"type": "array", "items": {"type": "string"}}
DATE = {"type": "string", "description": "YYYY-MM-DD (defaults to today)"}


def obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


TOOLS = {
    "get_context": (t_get_context, True,
        "Call first. Returns today's date, the user's preferences and identity, active/paused goals with pace and "
        "check-in status, habits, upcoming birthdays, and a list of all vault files.", obj({})),
    "list_goals": (t_list_goals, True,
        "Goals with progress vs pace, days since check-in, whether a check-in is due, and linked habits.",
        obj({"include_inactive": {**BOOL, "description": "Include paused/done/dropped goals"}})),
    "list_habits": (t_list_habits, True,
        "Active habits with this period's count vs required, streak, recent hit rate and last miss reason.", obj({})),
    "read_file": (t_read_file, True, "Read any vault file by path relative to the vault, e.g. 'people/jane-doe.md'.",
        obj({"path": STR}, ["path"])),
    "search": (t_search, True, "Case-insensitive text search across the vault.", obj({"query": STR}, ["query"])),
    "upcoming_birthdays": (t_upcoming_birthdays, True, "Birthdays in the next N days.",
        obj({"days": {**INT, "default": 30}})),
    "weekly_review": (t_weekly_review, False,
        "Build this week's review: goals, habits, what's coming up, and the questions worth asking. "
        "Walk the user through it: wins first, then questions one at a time, then next week's focus.",
        obj({"write": {**BOOL, "description": "Save to reviews/YYYY-Www.md"}})),
    "create_goal": (t_create_goal, False,
        "Create a goal after coaching the user through it. Requires at least one if-then plan. "
        "Refuses if over the active-goal cap unless confirm_over_cap is true.",
        obj({"title": STR, "description": {**STR, "description": "One line: what done looks like"},
             "why": {**LIST, "description": "The user's reasons, in their words"},
             "done_looks_like": STR,
             "plan": {**LIST, "description": "If-then plans: 'When <cue>, I will <action>.'"},
             "obstacles": {**LIST, "description": "'If <obstacle>, then <response>.'"},
             "next_actions": LIST,
             "horizon": {"type": "string", "enum": ["week", "month", "quarter", "year", "life"]},
             "start_date": DATE, "target_date": DATE, "checkin_every_days": INT,
             "metric": {**STR, "description": "What is measured, if numeric"}, "unit": STR,
             "baseline": NUM, "target": NUM,
             "status": {"type": "string", "enum": ["active", "paused"]},
             "confirm_over_cap": BOOL},
            ["title", "description", "why", "done_looks_like", "plan"])),
    "log_goal_checkin": (t_log_goal_checkin, False,
        "Log a check-in on a goal (by name or title), optionally with the metric value. Returns updated pace.",
        obj({"goal": STR, "note": STR, "value": NUM, "date": DATE}, ["goal"])),
    "update_goal": (t_update_goal, False,
        "Change a goal: status (pausing needs resume_date), dates, target, cadence; add plans, obstacles or reasons; "
        "optionally log a note. Only change status when the user says so.",
        obj({"goal": STR, "status": {"type": "string", "enum": ["active", "paused", "done", "dropped"]},
             "resume_date": DATE, "target_date": DATE, "target": NUM, "checkin_every_days": INT,
             "description": STR, "add_plan": LIST, "add_obstacle": LIST, "add_why": LIST, "note": STR}, ["goal"])),
    "create_habit": (t_create_habit, False,
        "Create a repeatable habit, optionally linked to a goal, with a cue and a minimum version for bad days.",
        obj({"title": STR, "frequency": {**STR, "description": "'daily', 'N/week' or 'N/month'"},
             "goal": STR, "cue": STR, "minimum_version": STR, "description": STR},
            ["title", "frequency"])),
    "log_habit": (t_log_habit, False,
        "Log a habit occurrence as done, or missed with the reason the user gave.",
        obj({"habit": STR, "done": BOOL, "reason": STR, "note": STR, "date": DATE}, ["habit", "done"])),
    "add_note": (t_add_note, False,
        "Append a fact the user told you to a vault file (one subject per file), e.g. 'people/jane-doe.md', "
        "'profile/preferences.md', 'journal/2026-10-16.md' (auto-created). Pass `create` to make a new "
        "person/area file.",
        obj({"path": STR, "text": STR, "section": {**STR, "description": "Heading to append under, e.g. 'Communication'"},
             "inferred": {**BOOL, "description": "True only for your own conclusion, not something the user said"},
             "create": {"type": "object", "properties": {
                 "title": STR, "description": STR, "relationship": STR,
                 "birthday": {**STR, "description": "YYYY-MM-DD or --MM-DD"}, "aliases": LIST},
                 "required": ["title", "description"]}},
            ["path", "text"])),
    "init_vault": (t_init_vault, False, "Create the vault from the template if it doesn't exist yet.",
        obj({"git": {**BOOL, "description": "Make the vault its own git repo"}})),
    "validate": (t_validate, True, "Check every vault file's frontmatter; reports errors and coaching warnings.", obj({})),
}

PROMPTS = {
    "coach": ("The full self.os coaching protocol (AGENTS.md).", [],
              lambda a: cli.AGENTS_MD.read_text(encoding="utf-8")),
    "set-goal": ("Coach the user through setting a new goal.", [{"name": "idea", "description": "What they want", "required": False}],
                 lambda a: (f"I want to set a goal{': ' + a['idea'] if a.get('idea') else ''}. Coach me through it using self.os: "
                            "call get_context, then ask me (one or two questions at a time) why it matters, what done looks like, "
                            "whether there's a number to track, an if-then plan, my likely obstacles, and the habit that drives it. "
                            "Check the active-goal cap. Then create the goal and habit.")),
    "check-in": ("Check in on goals and habits that are due.", [],
                 lambda a: ("Check in with me using self.os: call get_context, then go through anything due. Ask for numbers "
                            "where there's a metric and log them. If I've missed something, ask what got in the way and offer "
                            "one adjustment.")),
    "weekly-review": ("Run the weekly review.", [],
                      lambda a: ("Run my weekly review with self.os: call weekly_review with write=true, start with my wins, "
                                 "go through the questions one at a time, update goals/habits/plans with what we decide, and "
                                 "agree on next week's focus.")),
}


# ---------- JSON-RPC plumbing ----------

def _result(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle(msg: dict) -> dict | None:
    method, rid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if rid is None:  # notification
        return None
    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        return _result(rid, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}, "prompts": {"listChanged": False}},
            "serverInfo": {"name": "selfos", "title": "self.os goal coach", "version": __version__},
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return _result(rid, {})
    if method == "tools/list":
        return _result(rid, {"tools": [
            {"name": n, "description": d, "inputSchema": schema,
             "annotations": {"readOnlyHint": ro, "destructiveHint": False, "openWorldHint": False}}
            for n, (_, ro, d, schema) in TOOLS.items()]})
    if method == "tools/call":
        name = params.get("name")
        if name not in TOOLS:
            return _error(rid, -32602, f"Unknown tool: {name}")
        fn = TOOLS[name][0]
        try:
            data = fn(params.get("arguments") or {})
            return _result(rid, {"content": [{"type": "text", "text": json.dumps(data, indent=2, ensure_ascii=False, default=str)}],
                                 "structuredContent": data})
        except (edit.VaultError, KeyError, ValueError) as e:
            msg_ = f"Missing argument: {e}" if isinstance(e, KeyError) else str(e)
            return _result(rid, {"content": [{"type": "text", "text": msg_}], "isError": True})
        except Exception as e:  # report, don't crash the server
            traceback.print_exc(file=sys.stderr)
            return _result(rid, {"content": [{"type": "text", "text": f"Internal error: {e}"}], "isError": True})
    if method == "prompts/list":
        return _result(rid, {"prompts": [{"name": n, "description": d, "arguments": a} for n, (d, a, _) in PROMPTS.items()]})
    if method == "prompts/get":
        name = params.get("name")
        if name not in PROMPTS:
            return _error(rid, -32602, f"Unknown prompt: {name}")
        d, _, render = PROMPTS[name]
        return _result(rid, {"description": d, "messages": [
            {"role": "user", "content": {"type": "text", "text": render(params.get("arguments") or {})}}]})
    return _error(rid, -32601, f"Method not found: {method}")


def serve() -> int:
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    print(f"selfos MCP server {__version__} · vault: {cli.VAULT}", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            out = _error(None, -32700, "Parse error")
        else:
            batch = msg if isinstance(msg, list) else [msg]
            responses = [r for r in (handle(m) for m in batch) if r is not None]
            out = (responses if isinstance(msg, list) else responses[0]) if responses else None
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


def main() -> None:
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "--vault":
        cli.set_vault(args[1])
    sys.exit(serve())


if __name__ == "__main__":
    main()
