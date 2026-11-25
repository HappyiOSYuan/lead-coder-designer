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
| Lead | Locates code, writes briefs, reviews diffs, runs check scripts, verifies screenshots, talks to the user, tracks progress | Edit product code (fast-lane small fixes may be an exception if the project allows; docs and tooling scripts are fine); invent design directions for the designer |
| Coder | Edits code per the brief, builds, self-checks, writes a short report | Make design decisions; touch files outside the task scope |
| Designer | HTML mockups, motion demos, `handoff.md` | Edit product code; write anywhere except the design folder (default `DesignMockups/<task>/`, ideally ignored by version control) |

Principle: **the user decides, the lead gatekeeps, executors execute.** The lead adds value by locating precisely, writing clear briefs and reviewing strictly — not by doing the work itself.

## 2. First-time setup in a project

1. Copy the config: `cp config.example.sh <project>/.sop/config.sh` and fill in the coder/designer adapter and model. Adapters live in `scripts/adapters/`; to add one, follow `scripts/adapters/README.md`.
2. Health check: `scripts/run_role.sh --probe coder` and `--probe designer`. Both must answer `OK`.
3. Create `AGENTS.md` at the project root (every agent reads it): role table + project rule index + per-task wrap-up checklist. Template: `examples/ios-uikit-swiftui/AGENTS.excerpt.md`. Project rules are written in one place only; AGENTS.md only indexes them.
4. Pick a task-isolation method: git branch/worktree or svn changelist. `scripts/scope.py` supports both.

## 3. Main flow

### Pick the lane first (match process weight to risk)

| Lane | Typical request | Steps to run |
|---|---|---|
| **Fast** | ≤2 files, clear root cause, no UI structure change (bug fix, copy/param tweak) | ① locate → short brief (or direct small fix if project allows) → `review_diff.py` → ⑨ wrap-up |
| **Standard** | Feature work, API integration, refactor / rewrite without redesign | ① locate → ⑤ brief → ⑥ code → ⑦ review (+ logic self-check) → ⑧ acceptance → ⑨ wrap-up |
| **Full** | New screen, new visuals, major redesign, "improve the design" | Full flow ① → ⑨ (direction gate + 6-dimension rubric + worst-case UI stress test) |

```
request → [Fast / Standard / Full] → ① locate → ② design (Full) → ③ direction gate → ④ full set
        → ⑤ brief → ⑥ code → ⑦ review → ⑧ acceptance → ⑨ wrap-up → (⑩ module doc)
```

① **Locate**: use scripts first (references, call sites, the old implementation) and produce "which files, which lines, which existing implementation to copy". Wide searches go to a script with summarized output, not to a model reading files one by one (see `references/token-saving.md`).

② **Design** (only when the UI changes): write a design brief (`templates/design-brief.md`) with the user's own words, files to read, hard constraints and deliverables. **The lead does not write design ideas**; the designer decides and explains its reasoning in the handoff. If the designer runs headless and cannot run commands, the lead exports what it needs (icons, screenshots, the old page's text) into the design folder beforehand.

③ **Direction gate** (new visuals, major redesigns, any "improve the design" request): the designer first writes the **design thinking** at the top of `directions.md` (restate the need, the four form questions, one direction card per direction, an overreach check), then draws thumbnails. The first round delivers only 2–3 directions that genuinely differ, each with about 3 thumbnail screens and 2–3 sentences on trade-offs (`templates/directions.md`). The lead checks design thinking plus dimensions 0–1 (`references/design-review.md`), presents the options and **stops** until the user picks. Then record the user's exact words in `direction-approved.md` (`templates/direction-approved.md`). Small revisions (rev) skip the gate. When redesigning a page that is **already shipped**, keep its skeleton and information order; directions differ only in visual hierarchy. Details: `references/design-gate.md`.

④ **Full set**: all artboards for the chosen direction plus `handoff.md`. After delivery, run `scripts/design_lint.py <design dir> [--base <previous mockup>] [--source <old code>]`; errors must be 0. Take **one** screenshot of the key artboards, score the deliverable on the 6-dimension rubric (`references/design-review.md` — state only violated standards and numbers, never invent design fixes), send back for a rev if needed, and show the user once it passes.

⑤ **Brief** (`templates/brief.md`): goal, scope (down to files and line numbers), which existing implementation to copy, key points, relevant entries from `.agents/MEMORY.md` (`scripts/memory_check.py --match`), what not to do, wrap-up commands. A good brief lets the coder start without exploring the project. See section 5.

⑥ **Code**: `scope.py start <task>` → `run_role.sh coder -f brief.md` → `scope.py end <task>`. Launch it with the lead agent's own background-task feature (visible in the terminal, notifies on completion) — **never** detach it with `( cmd & )` or nohup. Queue tasks serially; never run two coding tasks in the same working copy at once.

⑦ **Review**: run `scripts/review_diff.py [paths]` first, then read only the flagged lines and the key logic (`references/review-checklist.md`). Focus on: lost content and error-branch parity (compare against the **original** version, not an intermediate one), out-of-scope edits, loading/empty/error states, and whether new files were added to version control and the build. For data parsing, parameter building, formatting or pagination changes, verify a lightweight unit test / CLI logic check before asking the user to build. Before acceptance on rewritten lists, details or forms, run a worst-case data stress test (`references/ui-stress-test.md`). Recurring bugs found in review should also be fed back into project rules or `.agents/MEMORY.md`.

⑧ **Acceptance** (`references/runtime-verify.md`): tell the user exactly which page to open; when they reply "opened", take one screenshot, compare it with the design point by point and state the verdict. For anything the user reports, find the root cause before dispatching a fix.

   On acceptance, append a "rounds N · found by" line to the handoff file (see "Prune gates with data" in section 6).

⑨ **Wrap-up**: list the changed files (added/modified/deleted) and their changelist/branch, the rules used, the build result and anything left undone. Do a quick retrospective: write any new pitfall, user ruling or convention into `.agents/MEMORY.md` and run `scripts/memory_check.py` (`references/memory-and-handover.md`). **The user commits**; the lead never does.

⑩ **Module doc** (only when the user names a module): after the whole module is accepted, add a PRD-style summary (APIs, business rules, flows, known issues). The lead creates the skeleton, the coder fills it from code only with `file:line` citations, the lead spot-checks. Details: `references/module-doc.md`.

## 4. When to ask the user and when to just do it

- Must ask: design direction, scope changes, deletions or other irreversible actions, and choices between reasonable options whose costs differ a lot.
- Just do it (and mention it in the report): choices with an established convention, facts you can look up in the code, small fixes inside a revision.
- Ask only the one question that actually blocks you, and give a recommended option.

## 5. Writing a brief

- **Locate before dispatching**: give `file:line` and the symbol to change. Vague tasks send the coder exploring the whole project, which is slow and expensive.
- **Give a model to copy**: "follow `X.swift` L52–125" is more precise than ten lines of requirements.
- **Content parity**: for rewrites and redesigns, require a line-by-line check of displayed text against the original version — nothing added, nothing dropped.
- **Name only 1–3 relevant rules**; don't paste the whole rulebook.
- **Any code change gets one incremental build** (only the changed module, via a summary script that prints only errors); a failing build never goes to the user. The user only checks runtime behaviour — they are not the compiler.
- **Spell out the wrap-up commands**: check scripts, errors must be 0, report format (≤10 lines + table of changed files + differences from the design).

## 6. Working discipline

- After every dispatch, tell the user how long it will take (based on measured run times).
- Read only the end of a log (the report), never the full log.
- Take one screenshot that covers the key area.
- Report in the user's language: conclusion first, then what the user needs to do.
- Keep one source of truth for project memory (`.agents/MEMORY.md`, ≤150 lines, tagged bullets); look up past user rulings with `scripts/session_search.py` instead of guessing; prune stale rules/skills periodically with `scripts/memory_check.py --audit-rules`.
- In long sessions, suggest a new session after each finished request.
- **Circuit breaker**: if the same stage fails review twice in a row (2 revs or 2 code fix rounds), stop — do not dispatch a 3rd blind retry. Re-investigate the root cause, revert broken edits if needed, or escalate to the user.
  - **Same behaviour class counts too**: a second bug in the same module and the same kind of behaviour (back / save / refresh / delete …) is round 2 even if it looks like a new task. Before fixing, write a **state table** (each screen × each action → data kept / rolled back / deleted), get the user's OK, and fix all paths at once instead of patching one path at a time.
- **Prune gates with data**: on every acceptance append `· accepted · rounds N · found by script/diff-review/build/user` to the handoff file (N = dispatches until it passed; found by = who caught each round's problem). Trigger: the user says "done / OK / committed" or starts the next task; write "?" when unsure. After 1–2 weeks, drop gates that never catch anything and reinforce the step that leaks most; **add no new process rules until that data exists**.
- **Keep it small**: cap AGENTS.md (e.g. 140 lines) and move details into skills/rules when it grows; keep only the last 7 days in the handoff file (`scripts/handoff_rotate.py`); run the rules audit after every milestone.
- Before dispatching, skim `references/pitfalls.md`.

## 7. Swapping models or tools

- Change model: edit `CODER_MODEL` / `DESIGNER_MODEL` (and `*_FALLBACK`) in `config.sh`; no doc changes needed. Set `SOP_FORCE_FALLBACK=1` to skip directly to the fallback model when the primary quota is exhausted.
- Change CLI: edit `CODER_ADAPTER` / `DESIGNER_ADAPTER`; for a new CLI write a ~30-line adapter following `scripts/adapters/README.md`.
- Swap or temporarily hand over the lead: any agent that can read files, run scripts and look at images can act as lead. When the primary lead runs out of quota, run `scripts/takeover_lead.sh` and share `$SOP_HOME/leader-handoff.md` between both leads (`references/memory-and-handover.md`).

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

## 9. Where it fits, and what it costs

**Good fit**: product work with a UI that someone accepts by hand (app / web pages, forms, lists, redesigns); changes that go into version control and get maintained; a user willing to spend time at the direction gate and at acceptance.

**Poor fit** (just do it, or use the fast lane only):
- One-off scripts, data processing, quick investigations: no direction to choose, nobody to accept.
- Folders without version control: `scope.py` and `review_diff.py` rely on git/svn to find the change set; without it only the manual checklist is left.
- Pure exploration or prototypes: speed matters more, and three gates multiply the cost of each try.
- A user who can't build or can't look at a device: step ⑧ can't happen, so half the process is gone.

**Costs**:
- **Slower**: the full lane stops at least twice for the user (direction gate, acceptance); brief, review and wrap-up are extra steps. Even a fast-lane fix needs locating plus `review_diff.py`.
- **More tokens**: every coder/designer call is a fresh session that re-reads the brief and the relevant code; the lead's diff review and screenshot checks add more. `references/token-saving.md` reduces this, but not to the level of one agent editing directly.
- **Setup and upkeep**: multi-CLI mode means installing, logging in and probing each CLI, filling `config.sh`, and writing `AGENTS.md`; quotas, CLI upgrades and changed error formats mean maintaining the adapters.
- **The user has to take part**: picking directions, building (per project convention), on-device acceptance and committing are all the user's; when the user is away, work stops.
- **Rules pile up**: every mistake tempts a new rule and the SOP gets heavier. Keep it in check with the AGENTS.md line cap, `memory_check.py --audit-rules`, and pruning gates by data.

**Limits** (what the process can't catch):
- The scripts are static checks (stats, leftovers, out-of-scope files, mockup rules); they can't tell that business logic is wrong.
- Screenshot acceptance covers only the screens and data you looked at; worst-case data stress tests cover some of the rest, not all.
- Results are capped by the quality of the brief and the strictness of the lead's review; a wrong brief gets implemented faithfully.
- Single-session mode B reviews its own work (see §8), the weakest form of independence.

## File index

| Path | Purpose |
|---|---|
| `config.example.sh` | Role → adapter / model / fallback models / folders |
| `scripts/run_role.sh` | Launch the coder or designer; auto-falls back to the next model when quota runs out; `--probe` health check |
| `scripts/adapters/*.sh` | How to call each CLI and how to recognise its quota errors |
| `scripts/scope.py` | Snapshot before/after a task; put this task's changes on a changelist (svn) or list them (git) |
| `scripts/review_diff.py` | Diff pre-review: change counts, untracked new files, debug leftovers, out-of-scope files, pluggable project rules, automatic memory check |
| `scripts/design_lint.py` | Mockup self-check: anti-template decoration, external assets, dark mode, ease-in, text parity |
| `scripts/memory_check.py` | Check `.agents/MEMORY.md` (line cap, `[tag]`, near-duplicates, dead paths) and `--match` relevant entries for briefs |
| `scripts/session_search.py` | Search past local session transcripts without an LLM to verify previous user rulings |
| `scripts/takeover_lead.sh` | Launch a backup lead CLI with `leader-handoff.md` when the primary lead runs out of quota |
| `scripts/handoff_rotate.py` | Keep only the last N days (default 7) in the handoff file and archive the rest; run before taking over as lead |
| `templates/` | Coder brief, design brief, directions (with design thinking), direction approval, report, module doc |
| `references/` | Direction gate, design review rubric, review checklist, worst-case UI stress test, runtime verification, memory & handover, token saving, pitfalls, module doc |
| `examples/ios-uikit-swiftui/` | Setup example from a real iOS project |
