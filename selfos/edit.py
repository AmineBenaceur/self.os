"""Safe, minimal edits to vault files: create from fields, append to a section, set frontmatter.

Every write stays inside the vault, keeps frontmatter valid, and bumps `updated:`.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from . import cli


class VaultError(ValueError):
    """A write was refused (bad path, missing file, invalid value)."""


def vault_path(rel: str, must_exist: bool = True) -> Path:
    rel = rel.strip().lstrip("/\\")
    if not rel.endswith(".md"):
        rel += ".md"
    root = cli.VAULT.resolve()
    p = (root / rel).resolve()
    if root != p and root not in p.parents:
        raise VaultError(f"'{rel}' is outside the vault")
    if must_exist and not p.exists():
        raise VaultError(f"'{rel}' does not exist in the vault")
    return p


def slugify(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:60] or "untitled"


def find_doc(folder: str, name: str) -> Path:
    """Resolve a goal/habit by file stem, path, or title (case-insensitive)."""
    name = name.strip()
    candidates = [vault_path(name, must_exist=False), vault_path(f"{folder}/{name}", must_exist=False)]
    for c in candidates:
        if c.exists():
            return c
    target = name.lower()
    for p in sorted((cli.VAULT / folder).glob("*.md")):
        if p.name.startswith("_"):
            continue
        d = cli.parse(p)
        if d.title.lower() == target or p.stem == slugify(name):
            return p
    raise VaultError(f"No {folder[:-1]} matching '{name}'. Use list_goals / list_habits to see names.")


def _fm_value(v) -> str:
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(str(x) for x in v) + "]"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    s = str(v).replace("\n", " ").strip()
    return s


def render(meta: dict, body: str) -> str:
    lines = ["---"] + [f"{k}: {_fm_value(v)}" for k, v in meta.items() if v not in (None, "")] + ["---", ""]
    return "\n".join(lines) + body.rstrip() + "\n"


def create(rel: str, meta: dict, body: str) -> Path:
    p = vault_path(rel, must_exist=False)
    if p.exists():
        raise VaultError(f"'{p.relative_to(cli.VAULT).as_posix()}' already exists")
    meta = {**meta, "updated": date.today().isoformat()}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(meta, body), encoding="utf-8")
    return p


def _split(text: str) -> tuple[list[str], list[str]]:
    if not text.startswith("---"):
        raise VaultError("file has no frontmatter")
    lines = text.split("\n")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise VaultError("unterminated frontmatter")
    return lines[: end + 1], lines[end + 1 :]


def set_meta(p: Path, **fields) -> None:
    fm, body = _split(p.read_text(encoding="utf-8"))
    fields.setdefault("updated", date.today().isoformat())
    for key, val in fields.items():
        line = f"{key}: {_fm_value(val)}"
        idx = next((i for i, l in enumerate(fm[1:-1], 1) if re.match(rf"^{re.escape(key)}\s*:", l)), None)
        if val is None:
            if idx is not None:
                fm.pop(idx)
        elif idx is not None:
            fm[idx] = line
        else:
            fm.insert(len(fm) - 1, line)
    p.write_text("\n".join(fm + body), encoding="utf-8")


def append_to_section(p: Path, section: str, line: str) -> None:
    """Append `line` at the end of '## section' (created at the end of the file if missing)."""
    text = p.read_text(encoding="utf-8")
    fm, body = _split(text)
    head = f"## {section}".lower()
    start = next((i for i, l in enumerate(body) if l.strip().lower() == head), None)
    if start is None:
        while body and not body[-1].strip():
            body.pop()
        body += ["", f"## {section}", line, ""]
    else:
        end = next((i for i in range(start + 1, len(body)) if body[i].startswith("## ")), len(body))
        insert_at = end
        while insert_at > start + 1 and not body[insert_at - 1].strip():
            insert_at -= 1
        body.insert(insert_at, line)
    p.write_text("\n".join(fm + body), encoding="utf-8")
    set_meta(p)


def fact(text: str, tag: str = "stated") -> str:
    text = " ".join(text.split())
    if re.search(r"\[(stated|inferred)\]\s*$", text):
        return f"- {text}"
    return f"- {text} [{tag}]"


def log_line(day: date, text: str, tag: str = "stated") -> str:
    return fact(f"{day.isoformat()}: {text}", tag)
