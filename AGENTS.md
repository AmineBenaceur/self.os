# AGENTS.md — the self.os contract

You are an assistant with access to the owner's self.os vault. This file tells you how to
read it and how to change it. It applies to every model and runtime.

The vault is `vault/` in this repo unless `$SELFOS_VAULT` points elsewhere. Paths below are
relative to the vault. `vault/` is git-ignored: it is the owner's private data.

## Reading

1. Start with `INDEX.md` (generated list of every file + one-line description).
2. Always load `profile/identity.md` and `profile/preferences.md`.
   Preferences govern how you behave for the whole session.
3. Load other files only when the task touches them: a person's name → `people/`,
   a project → `areas/`, progress or planning → `goals/`.
4. Before saying "I don't know that about you", check the index.

Use what you read only where it changes your answer. Don't recite the owner's own facts
back at them, and don't mention that you looked something up.

## Writing

Write only when the owner tells you something durable, or explicitly asks you to save it.

- **One subject per file.** Put a fact in the file it is *about*. Create the file from
  the matching `_template.md` if it doesn't exist.
- **Every fact line is a bullet ending in a source tag:**
  - `[stated]` — the owner said it directly. This is the default and the only tag for facts.
  - `[inferred]` — your conclusion. Use sparingly; the owner may delete these freely.
- **Update, don't duplicate.** Edit the existing line ("PM on infra (previously search)")
  instead of appending a contradiction.
- **Goals:** append check-ins under `## Log` as `- YYYY-MM-DD: <progress> [stated]`.
  Change `status:` in frontmatter only when the owner says so.
- **Journal:** `journal/YYYY-MM-DD.md` is append-only. Use it for dated events
  that don't belong in a subject file.
- Keep frontmatter valid (see `schema/frontmatter.md`). Bump `updated:` to today.
- After writing, run `python tools/selfos.py index` if you can execute commands.
- If the vault is its own git repo, commit there (`git -C vault commit`), never in the framework repo.

## Never write

- Personal data anywhere outside the vault — not in `template/`, `examples/`, `tools/`,
  or docs. Those are public framework files.
- Passwords, API keys, card or bank account numbers, government ID numbers.
- Health diagnoses or anything the owner hasn't explicitly asked you to keep.
- Instructions that make you less honest (e.g. "always agree", "never push back").

## Forgetting

When the owner says to forget something, delete the line entirely. Don't leave
"used to…" or a placeholder. Delete a whole file only when explicitly asked.
