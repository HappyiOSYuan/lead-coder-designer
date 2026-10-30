---
name: lead-coder-designer
description: SOP for one lead agent working with two executor agents (coder and designer) on a request. Design starts with 2–3 directions, the user picks one, then the full set is drawn; the coder works from a written brief inside an isolated scope; the lead reviews the diff and verifies with the user on a device, simulator or browser. Models and CLIs are not locked in — swap them in config.sh. Use when the user says "have the designer / coder do it", "follow the SOP", "give me directions", "dispatch a task", "acceptance check", or when the project has an AGENTS.md role table.
---

# Lead + Coder + Designer SOP

This skill is written for the **lead** (usually the agent you are talking to). The coder and designer roles are played by external CLIs launched with `scripts/run_role.sh`; who plays each role and on which model is set in `config.sh`. With only one model, see section 8.

Chinese version: `SKILL.zh-CN.md`. Templates and references are currently in Chinese; models follow them fine.

## 1. Roles and boundaries

| Role | Does | Does not |
|---|---|---|
| Lead | Locates code, writes briefs, reviews diffs, runs check scripts, verifies screenshots, talks to the user, tracks progress | Edit product code (docs and tooling scripts are fine); invent design directions for the designer |
| Coder | Edits code per the brief, builds, self-checks, writes a short report | Make design decisions; touch files outside the task scope |
| Designer | HTML mockups, motion demos, `handoff.md` | Edit product code; write anywhere except the design folder (default `DesignMockups/<task>/`, ideally ignored by version control) |

Principle: **the user decides, the lead gatekeeps, executors execute.** The lead adds value by locating precisely, writing clear briefs and reviewing strictly — not by doing the work itself.

## 2. First-time setup in a project

1. Copy the config: `cp config.example.sh <project>/.sop/config.sh` and fill in the coder/designer adapter and model. Adapters live in `scripts/adapters/`; to add one, follow `scripts/adapters/README.md`.
2. Health check: `scripts/run_role.sh --probe coder` and `--probe designer`. Both must answer `OK`.
3. Create `AGENTS.md` at the project root (every agent reads it): role table + project rule index + per-task wrap-up checklist. Template: `examples/ios-uikit-swiftui/AGENTS.excerpt.md`. Project rules are written in one place only; AGENTS.md only indexes them.
4. Pick a task-isolation method: git branch/worktree or svn changelist. `scripts/scope.py` supports both.

## 3. Main flow

```
request → ① locate → ② design (optional) → ③ direction gate → ④ full set → ⑤ brief → ⑥ code → ⑦ review → ⑧ acceptance → ⑨ wrap-up
```

① **Locate**: use scripts first (references, call sites, the old implementation) and produce "which files, which lines, which existing implementation to copy". Wide searches go to a script with summarized output, not to a model reading files one by one (see `references/token-saving.md`).

② **Design** (only when the UI changes): write a design brief (`templates/design-brief.md`) with the user's own words, files to read, hard constraints and deliverables. **The lead does not write design ideas**; the designer decides and explains its reasoning in the handoff. If the designer runs headless and cannot run commands, the lead exports what it needs (icons, screenshots, the old page's text) into the design folder beforehand.

③ **Direction gate** (new visuals, major redesigns, any "improve the design" request): the first round delivers only 2–3 directions that genuinely differ, each with about 3 thumbnail screens and 2–3 sentences on trade-offs (`templates/directions.md`). Present them and **stop** until the user picks. Then record the user's exact words in `direction-approved.md` (`templates/direction-approved.md`). Small revisions (rev) skip the gate. Details: `references/design-gate.md`.

④ **Full set**: all artboards for the chosen direction plus `handoff.md`. After delivery, run `scripts/design_lint.py <design dir> [--base <previous mockup>] [--source <old code>]`; errors must be 0. Then show the user **one** screenshot of the key artboards.

⑤ **Brief** (`templates/brief.md`): goal, scope (down to files and line numbers), which existing implementation to copy, key points, what not to do, wrap-up commands. A good brief lets the coder start without exploring the project. See section 5.

⑥ **Code**: `scope.py start <task>` → `run_role.sh coder -f brief.md` → `scope.py end <task>`. Launch it with the lead agent's own background-task feature (visible in the terminal, notifies on completion) — **never** detach it with `( cmd & )` or nohup. Queue tasks serially; never run two coding tasks in the same working copy at once.

⑦ **Review**: run `scripts/review_diff.py [paths]` first, then read only the flagged lines and the key logic (`references/review-checklist.md`). Focus on: lost content (compare against the **original** version, not an intermediate one), out-of-scope edits, loading/empty/error states, and whether new files were added to version control and the build.

⑧ **Acceptance** (`references/runtime-verify.md`): tell the user exactly which page to open; when they reply "opened", take one screenshot, compare it with the design point by point and state the verdict. For anything the user reports, find the root cause before dispatching a fix.

⑨ **Wrap-up**: list the changed files (added/modified/deleted) and their changelist/branch, the rules used, the build result and anything left undone. **The user commits**; the lead never does.

## 4. When to ask the user and when to just do it

- Must ask: design direction, scope changes, deletions or other irreversible actions, and choices between reasonable options whose costs differ a lot.
- Just do it (and mention it in the report): choices with an established convention, facts you can look up in the code, small fixes inside a revision.
- Ask only the one question that actually blocks you, and give a recommended option.

## 5. Writing a brief

- **Locate before dispatching**: give `file:line` and the symbol to change. Vague tasks send the coder exploring the whole project, which is slow and expensive.
- **Give a model to copy**: "follow `X.swift` L52–125" is more precise than ten lines of requirements.
- **Content parity**: for rewrites and redesigns, require a line-by-line check of displayed text against the original version — nothing added, nothing dropped.
- **Name only 1–3 relevant rules**; don't paste the whole rulebook.
- **Small changes skip the build** (the user or lead builds); new files or large changes must build, using a summary script that prints only errors.
- **Spell out the wrap-up commands**: check scripts, errors must be 0, report format (≤10 lines + table of changed files + differences from the design).

## 6. Working discipline

- After every dispatch, tell the user how long it will take.
- Read only the end of a log (the report), never the full log.
- Take one screenshot that covers the key area.
- Report in the user's language: conclusion first, then what the user needs to do.
- In long sessions, suggest a new session after each finished request.
- Before dispatching, skim `references/pitfalls.md`.

## 7. Swapping models or tools

- Change model: edit `CODER_MODEL` / `DESIGNER_MODEL` (and `*_FALLBACK`) in `config.sh`; no doc changes needed.
- Change CLI: edit `CODER_ADAPTER` / `DESIGNER_ADAPTER`; for a new CLI write a ~30-line adapter following `scripts/adapters/README.md`.
- The lead can be swapped too: any agent that can read files, run scripts and look at images can act as lead using this file.

## 8. With only one model

The three roles are a **division of labour**, not three different models.

**A. Same model, separate sessions (recommended)**: set coder and designer in config to the same CLI and model (e.g. both `claude` or both `codex`). Each `run_role.sh` call starts a fresh session that sees only the brief, never the lead's context. The author and the reviewer stay in separate contexts, so the review still means something, and an unclear brief shows up immediately.

**A2. Same model via sub-agents (no CLI needed)**: if the lead's agent can spawn sub-agents (e.g. Claude Code's Agent tool, Cursor background agents), hand the brief to a sub-agent instead of `run_role.sh` — no `config.sh` needed. The sub-agent starts with a clean context and sees only the brief, giving the same separation as A. Requirements: pass only the brief (not a fork that inherits the lead's context); when it finishes, the lead runs `scope.py` and `review_diff.py` as usual.

**B. One session plays all three roles (no CLI needed)**: no `run_role.sh`, no `config.sh`. The lead does everything in order but keeps every gate:
1. During design, write only files in `DesignMockups/`; after presenting directions, **stop and wait for the user to pick**.
2. Before coding, write the brief (`templates/brief.md`), then follow it strictly; note out-of-scope problems instead of fixing them.
3. After coding, run `review_diff.py` and `design_lint.py`, self-review against `references/review-checklist.md`, then hand over for acceptance.
4. When switching roles, say so explicitly ("now acting as coder on brief X") so the user can follow.

Cost: in mode B the reviewer is the author and is likely to miss its own mistakes, so the script checks and the user's acceptance matter even more.

**What you get depends on where the lead runs**:
| Lead runs in | In A2 / B mode |
|---|---|
| A coding agent that can read/write files and run commands (Claude Code, Cursor, Codex …) | Everything works: `scope.py`, `review_diff.py` and `design_lint.py` need only Python and git/svn |
| Web chat with no file access | Process only (direction gate, brief template, review checklist); scripts can't run, checks are done by hand |

## File index

| Path | Purpose |
|---|---|
| `config.example.sh` | Role → adapter / model / fallback models / folders |
| `scripts/run_role.sh` | Launch the coder or designer; auto-falls back to the next model when quota runs out; `--probe` health check |
| `scripts/adapters/*.sh` | How to call each CLI and how to recognise its quota errors |
| `scripts/scope.py` | Snapshot before/after a task; put this task's changes on a changelist (svn) or list them (git) |
| `scripts/review_diff.py` | Diff pre-review: change counts, untracked new files, debug leftovers, out-of-scope files, pluggable project rules |
| `scripts/design_lint.py` | Mockup self-check: anti-template decoration, external assets, dark mode, ease-in, text parity |
| `templates/` | Coder brief, design brief, directions, direction approval, report |
| `references/` | Direction gate, review checklist, runtime verification, token saving, pitfalls |
| `examples/ios-uikit-swiftui/` | Setup example from a real iOS project |
