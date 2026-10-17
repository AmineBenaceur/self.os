# Frontmatter reference

Every vault file starts with YAML frontmatter between `---` lines. Keep values simple:
strings, numbers, dates (`YYYY-MM-DD`), and inline lists (`[a, b]`). Lines starting with
`#` are comments. `tools/selfos.py validate` enforces this.

## All files

| Field | Required | Notes |
|---|---|---|
| `type` | yes | `profile` · `goal` · `habit` · `person` · `area` · `journal` · `review` |
| `title` | yes | Human-readable name |
| `description` | yes | One line: what's in here and when to read it |
| `updated` | yes | `YYYY-MM-DD`, bumped on every edit |
| `aliases` | no | Other names this subject goes by |
| `tags` | no | Free-form |

## `goal` — an outcome you want

| Field | Required | Notes |
|---|---|---|
| `status` | yes | `active` · `paused` · `done` · `dropped` |
| `horizon` | no | `week` · `month` · `quarter` · `year` · `life` |
| `start_date` | no | `YYYY-MM-DD`. Needed for pace tracking |
| `target_date` | no | `YYYY-MM-DD` |
| `checkin_every_days` | no | Check-in cadence (default 7) |
| `resume_date` | if paused | When to revisit a paused goal |
| `metric` | no | What's measured, e.g. `weekly distance` |
| `unit` | with metric | e.g. `km` |
| `baseline` | with metric | Number at `start_date` |
| `target` | with metric | Number at `target_date`. Can be below baseline (e.g. weight, debt) |

Body sections: `## Why`, `## Done looks like`, `## Plan` (if-then), `## Obstacles`,
`## Next actions`, `## Log`.

Log lines: `- YYYY-MM-DD: <note> [stated]`. Add `value=<number>` to record the metric,
e.g. `- 2026-10-20: value=12 long run felt good [stated]`.

## `habit` — a repeatable action that drives a goal

| Field | Required | Notes |
|---|---|---|
| `status` | yes | `active` · `paused` · `retired` |
| `frequency` | yes | `daily`, `N/week`, or `N/month` |
| `goal` | no | File name (no `.md`) of the goal it serves |
| `cue` | no | When/where it happens |

Log lines: `- YYYY-MM-DD: done [stated]` or `- YYYY-MM-DD: missed — <reason> [stated]`.

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

## `profile/preferences.md` (optional fields)

| Field | Notes |
|---|---|
| `max_active_goals` | Soft cap on active goals (default 5). `validate` warns above it |
| `review_day` | Day for the weekly review, e.g. `sunday` (default) |

## `journal` and `review`

Journal files are named by date (`journal/2026-10-16.md`). Reviews are written by
`selfos review --write` to `reviews/YYYY-Www.md`.
