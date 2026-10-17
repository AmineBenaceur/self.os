# Frontmatter reference

Every vault file starts with YAML frontmatter between `---` lines. Keep values simple:
strings, dates (`YYYY-MM-DD`), and inline lists (`[a, b]`). `tools/selfos.py validate`
enforces this.

## All files

| Field | Required | Notes |
|---|---|---|
| `type` | yes | `profile` · `goal` · `person` · `area` · `journal` |
| `title` | yes | Human-readable name |
| `description` | yes | One line: what's in here and when to read it |
| `updated` | yes | `YYYY-MM-DD`, bumped on every edit |
| `aliases` | no | Other names this subject goes by, so mentions match one file |
| `tags` | no | Free-form |

## `goal`

| Field | Required | Notes |
|---|---|---|
| `status` | yes | `active` · `paused` · `done` · `dropped` |
| `horizon` | no | `week` · `month` · `quarter` · `year` · `life` |
| `target_date` | no | `YYYY-MM-DD` |
| `checkin_every_days` | no | How often the assistant should nudge (default 7) |
| `area` | no | Name of a related area file |

## `person`

| Field | Required | Notes |
|---|---|---|
| `relationship` | yes | e.g. `friend`, `family`, `coworker`, `partner` |
| `birthday` | no | `YYYY-MM-DD`, or `--MM-DD` if the year is unknown |
| `remind_days_before` | no | Default 7 |

## `area`

| Field | Required | Notes |
|---|---|---|
| `status` | yes | `active` · `paused` · `closed` |

## `journal`

File name is the date (`2026-10-16.md`); `type: journal`, `title` and `description` can be terse.
