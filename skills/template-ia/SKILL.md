---
name: template-ia
description: Bootstraps the GRAPH pattern (.agents/graph/ + roles/) in the current project, porting the logic of the original template-ia.sh. Requires --mode=greenfield or --mode=brownfield. Use --migrate to absorb an existing .agents/ system (progress.md, tasks.md, system.md) without losing anything.
argument-hint: "--mode=greenfield|brownfield [--migrate]"
---

You are bootstrapping the GRAPH design pattern into the current project.
Arguments received: $ARGUMENTS

Parse `--mode=` (must be `greenfield` or `brownfield`), `--migrate`
(boolean, absent by default), `--reindex` (boolean, absent by default),
and `--update-docs` (boolean, absent by default).

**Two entry points:**

- **Fresh install or re-run of the full flow:** `--mode=` is required. If
  missing or invalid, stop and ask the user which one applies; do not
  guess. Follow Steps 0 through 6 below. If `--reindex` and/or
  `--update-docs` were also passed, run them as extra steps at the end
  (Step 7 / Step 8).
- **`--reindex` and/or `--update-docs` passed WITHOUT `--mode`:** the user
  already has GRAPH installed in this project and just wants to refresh
  something — this is also what to do when they ask in plain language,
  e.g. "reindexá esto" or "actualizá la doc de GRAPH". Skip straight to
  Step 7 / Step 8 — don't run Steps 0-6, don't ask for `--mode`. If
  `.agents/graph/` doesn't exist yet, stop and tell the user to run a full
  install first.

## Core rule for the whole command: never overwrite

Every step below follows the same discipline as the original script's
`safe_copy` function: if a destination file already exists, **skip it and
say so** — never overwrite silently. `mkdir -p` semantics are fine (creating
missing subfolders is always safe), but file contents are never replaced.

## Steps

### 0. Optional migration (only if --migrate was passed)

Check `.agents/` root (not `.agents/graph/`) for these three files, and for
each one found, **move** (not copy-and-leave-orphan) it into its GRAPH
location, prepending a provenance note:

- `.agents/progress.md` → `.agents/graph/sessions/progress.md`
- `.agents/tasks.md` → `.agents/graph/sessions/tasks.md`
- `.agents/system.md` → `.agents/graph/legacy-system.md`

For each move: prepend `<!-- Migrado automáticamente desde <old path> el
<today's date> -->` plus a blank line before the original content, write to
the new path, then remove the old file. If the destination already exists,
skip the migration for that file and tell the user both files were left
untouched (don't guess which one is authoritative).

`README.md` is never migrated — it's human documentation, not agent config.

### 1. Create the folder tree (safe even if `.agents/` already exists —
   this only adds missing subfolders, never touches existing ones)

```
.agents/graph/knowledge/nodes/
.agents/graph/knowledge/communities/
.agents/graph/history/
.agents/graph/gates/pending/
.agents/graph/gates/approved/
.agents/graph/sessions/
.agents/graph/enforcement/
.agents/roles/
.agents/skills/
```

### 2. Initialize `knowledge/index.json` (skip if it already exists)

- **greenfield:** write
  `{"status": "empty", "reason": "greenfield — se puebla en paralelo al código", "last_indexed": null}`
- **brownfield:** this step is **blocking** — no agent (including you, right
  now) proceeds to autonomous work until it resolves:
  1. Write `{"status": "indexing", "reason": "brownfield — indexación inicial en curso", "last_indexed": null}`.
  2. Run the plugin's own built-in indexer — it reads the actual repo with
     no external dependency and no third-party tool:
     `python3 ${PLUGIN_ROOT}/scripts/build-graph.py <repo_root>`.
     This populates `knowledge/nodes/*.json` (one file per source file,
     with real `references`/`referenced_by` resolved from actual
     imports/requires), `knowledge/communities/*.json` (grouped by
     top-level folder), and overwrites `knowledge/index.json` with real
     counts. Report those exact counts to the user — never invent numbers,
     and never substitute a different tool's output here. GRAPH stays
     agnostic precisely because this indexer ships with the plugin itself
     and requires nothing beyond Python's standard library — it must not
     be replaced by an external indexer as the default path.
  3. Reconcile git history: run `git log` and mark reconciled commits with
     `origen: pre-graph` in `.agents/graph/history/`. If `.agents/graph/history/.git-log-import-pending`
     doesn't already exist and this hasn't been done, create it as a
     marker, then perform the reconciliation, then remove the marker once
     done.
  4. Gates stay effectively unusable for autonomous work until both 2 and 3
     above are actually complete — don't tell the user gates are "enabled"
     while indexing is still pending.

### 3. Copy base files (skip any that already exist, per the no-overwrite rule)

From `${PLUGIN_ROOT}/templates/`:
- `graph/GRAPH.md` → `.agents/graph/GRAPH.md`
- `graph/README.md` → `.agents/graph/README.md`
- `graph/circuit-breaker.yml` → `.agents/graph/circuit-breaker.yml`
- `graph/gates/policy.yml` → `.agents/graph/gates/policy.yml`
- `roles/registry.yml`, `roles/planner.md`, `roles/executor.md`, `roles/reviewer.md` → `.agents/roles/`
- `graph/sessions/progress.md`, `graph/sessions/tasks.md` → `.agents/graph/sessions/` (skip if `--migrate` already placed files there)
- `graph/enforcement/README.md` → `.agents/graph/enforcement/README.md`

Note: the three enforcement hook scripts (`claude-code-hook.sh`,
`session-reset-hook.sh`, `stagnation-hook.sh`) do **not** need to be copied
into the project — they run directly from the plugin
(`${PLUGIN_ROOT}/hooks/`) and auto-register via the plugin's
`hooks.codex.json`. Mention this to the user so they don't go looking for
those files inside `.agents/graph/enforcement/` — only `README.md` lives
there, as documentation of what's enforcing what.

### 4. Place the AGENTS.md / CLAUDE.md bridge

Codex and equivalent tools auto-discover `AGENTS.md` from the **repo
root**, not from inside `.agents/`. The bridge lives inside a managed block
delimited by `<!-- template-ia:bridge-block -->` and
`<!-- /template-ia:bridge-block -->`, so it can be found and replaced later
without touching anything else in the file:

1. Look for `AGENTS.md` first at repo root, then at `.agents/AGENTS.md`.
2. If found at either location:
   - No start marker present: **append** (never rewrite existing content) a
     managed block — start marker, body pointing to `graph/GRAPH.md`,
     `roles/registry.yml`, `graph/gates/policy.yml`,
     `graph/sessions/progress.md`/`tasks.md`, end marker — using the
     `.agents/` prefix only if the file lives at repo root, no prefix if
     it's already inside `.agents/`. If `.agents/graph/legacy-system.md`
     exists (from step 0), add a line pointing to it too.
   - Start marker present but the block content is stale (differs from
     the current plugin's block, or has no end marker yet from an older
     install): leave it untouched here and report it as stale — Step 8
     (`--update-docs`) is what resynchronizes it in place, without
     touching anything outside the block.
   - Block already matches the current plugin version: skip.
3. If not found anywhere: copy `${PLUGIN_ROOT}/templates/AGENTS.md`
   to the repo root (not into `.agents/`) — that's where tools discover it.
   That template already contains the full managed block; don't append
   anything extra or the block will be duplicated.
4. Also place `CLAUDE.md` the same way, in case the project later gets
   opened with Claude Code too — it's inert documentation for any tool
   that doesn't look for it, so it doesn't hurt to leave it.

### 5. Stamp the detected mode into tasks.md

If `.agents/graph/sessions/tasks.md` is the one just created in step 3
(i.e. not migrated from an existing file in step 0), replace the literal
placeholder line `Modo detectado: greenfield | brownfield` with `Modo
detectado: <actual mode>`. If it came from migration, don't touch it.

### 6. Report a summary

- What was created vs. skipped (and why, if `--migrate` was used).
- Confirm the 3 enforcement hooks are active via plugin registration —
  `claude-code-hook.sh` (PreToolUse), `session-reset-hook.sh`
  (UserPromptSubmit), `stagnation-hook.sh` (PostToolUse). On Codex, note
  that `PreToolUse`/`PostToolUse` only intercept `apply_patch` and `Bash` —
  there's no separate `MultiEdit`/`NotebookEdit` tool to match, unlike
  Claude Code.
- Remind the user `circuit-breaker.yml` and `gates/policy.yml` are both
  protected — editing either requires an approval file in
  `.agents/graph/gates/approved/` matching the `config-edit` pattern the
  hooks check for (see `enforcement/README.md`), not just editing the YAML
  directly.
- If mode was `brownfield`, report the real node/edge/community counts the
  built-in indexer produced. Mention that the regex-based import detection
  is a heuristic, not full AST parsing — some references (dynamic imports,
  unusual syntax, non-relative aliases) may not resolve, and that's a known
  limitation to note in `sessions/progress.md`, not something to hide.

### 7. `--reindex` (runs if this flag was passed, standalone or combined with a fresh install, or when asked in plain language e.g. "reindexá")

Re-run the built-in indexer even if `knowledge/index.json` already exists
— useful when the project had no code yet at install time (greenfield) and
real code got added afterward:

`python3 ${PLUGIN_ROOT}/scripts/build-graph.py <repo_root>`

This always overwrites `knowledge/nodes/`, `knowledge/communities/`, and
`knowledge/index.json` — it's derived data, nothing to preserve. Report
the new real counts. Also re-run git history reconciliation unless
`.agents/graph/history/pre-graph-commits.md` already exists.

### 8. `--update-docs` (runs if this flag was passed, standalone or combined with a fresh install, or when asked in plain language e.g. "actualizá la documentación de GRAPH")

Refreshes ONLY the generic pattern documentation to the version that ships
with this plugin — never config, never user data:

- `templates/graph/GRAPH.md` → `.agents/graph/GRAPH.md`
- `templates/graph/README.md` → `.agents/graph/README.md`
- `templates/roles/planner.md`, `executor.md`, `reviewer.md` → `.agents/roles/`

For each: if the destination differs from the template, back it up to
`<file>.bak` first, then overwrite. If already identical, skip silently.

This is also the entry point that resynchronizes the AGENTS.md/CLAUDE.md
managed block: replace exactly the span between
`<!-- template-ia:bridge-block -->` and `<!-- /template-ia:bridge-block -->`
(or, for a pre-existing bridge with no end marker, from the start marker to
end of file) with the current plugin's block. Nothing outside that span —
including content the user added after the block — gets touched. Skip
silently if the block already matches; safe to run repeatedly.

**Never** touch with this flag: `circuit-breaker.yml`, `gates/policy.yml`,
`roles/registry.yml`, `sessions/progress.md`, `sessions/tasks.md` —
protected config or the user's own project state.

Report which files were updated and which `.bak` files were created, if
any, plus whether the AGENTS.md/CLAUDE.md bridge blocks were resynced,
already up to date, or newly created.

Never invent node/edge/community counts — compute them from what actually
ran, or state plainly that they're not available yet.
