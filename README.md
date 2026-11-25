# lead-coder-designer

A model-agnostic SOP skill for running a **lead** agent with two executor agents — a **coder** and a **designer** — on real product work. The lead locates code, writes briefs, reviews diffs and verifies on device; the coder edits code; the designer produces HTML mockups. The user approves design directions and does the final acceptance.

Which CLI and model plays each role lives in one config file, so you can swap Cursor ↔ Codex ↔ Claude Code ↔ Gemini (agy) ↔ aider without touching the docs. It also works with **a single model** (see "One model only").

[中文说明见下方](#中文)

## Workflow chart

![Lead × Designer × Coder workflow](docs/workflow-en.png)

Interactive version (toggle tool labels): [English](https://happyiosyuan.github.io/lead-coder-designer/workflow-en.html) · [中文](https://happyiosyuan.github.io/lead-coder-designer/workflow.html)

The chart is the author's real iOS setup. Labels such as `scope.py`, `review_diff.py`, `design_lint.py` and `run_role.sh` are in this repo; the remaining `gf_*` labels are that project's own helper scripts, shown as examples of what to build for your project.

## What's inside

| Path | Purpose |
|---|---|
| `SKILL.md` | The SOP the lead agent follows (English); Chinese: `SKILL.zh-CN.md` |
| `config.example.sh` | Role → adapter / model / fallback models |
| `scripts/run_role.sh` | Run the coder or designer; auto-falls back to the next model when quota runs out; `--probe` health check |
| `scripts/adapters/` | One small file per CLI: `cursor-agent`, `codex`, `claude`, `agy`, `aider` |
| `scripts/scope.py` | Snapshot before/after a task and collect only *this* task's changes (git file list or svn changelist) |
| `scripts/review_diff.py` | Diff pre-review: changed files, untracked files, out-of-scope files, debug leftovers, pluggable project rules, automatic memory check |
| `scripts/design_lint.py` | Mockup lint: anti-template decoration, external assets, ease-in, content parity vs. old mockup / old source strings |
| `scripts/memory_check.py` | Check `.agents/MEMORY.md` (line cap, `[tag]`, near-duplicates, dead paths) and `--match` relevant entries into briefs |
| `scripts/session_search.py` | Search past local session transcripts without an LLM to verify previous user rulings |
| `scripts/takeover_lead.sh` | Hand over the lead role to a backup CLI via shared `leader-handoff.md` when quota runs out |
| `scripts/handoff_rotate.py` | Keep only the last 7 days in `leader-handoff.md`, archive the rest (auto-run by `takeover_lead.sh`) |
| `templates/` | Coder brief, design brief, directions (with design thinking), direction approval, report, module doc |
| `references/` | Design gate, 6-dimension design review rubric, review checklist, worst-case UI stress test, runtime verification, memory & lead handover, token saving, pitfalls, module doc |
| `examples/ios-uikit-swiftui/` | A real (redacted) iOS project setup |

## Requirements

- bash, Python 3.8+, git or svn
- The CLIs you configure (any subset): `cursor-agent`, `codex`, `claude`, `agy`, `aider`
- For screenshots: whatever your platform uses (`xcrun simctl`, `adb`, headless Chrome, `screencapture` …); see `references/runtime-verify.md`

## Install

Copy (or clone) the folder where your lead agent discovers skills:

| Lead agent | Location |
|---|---|
| Claude Code | `~/.claude/skills/lead-coder-designer/` (all projects) or `<project>/.claude/skills/` |
| Cursor | `<project>/.cursor/skills/lead-coder-designer/` |
| Codex / Gemini / Antigravity | `<project>/.agents/skills/lead-coder-designer/` |
| Anything else | Point the agent at `SKILL.md` |

```bash
git clone https://github.com/HappyiOSYuan/lead-coder-designer ~/.claude/skills/lead-coder-designer
cd <your project>
mkdir -p .sop && cp ~/.claude/skills/lead-coder-designer/config.example.sh .sop/config.sh   # edit it
~/.claude/skills/lead-coder-designer/scripts/run_role.sh --probe coder
~/.claude/skills/lead-coder-designer/scripts/run_role.sh --probe designer
```

Then create an `AGENTS.md` at your project root (roles, rule index, per-task checklist). `examples/ios-uikit-swiftui/AGENTS.excerpt.md` is a starting point.

## The flow

Route by risk first (**Fast**: ≤2 files / clear fix → locate, edit, `review_diff`; **Standard**: features / refactors → skip design; **Full**: new visuals / redesigns → full flow below):

```
request → locate → design (Full) → direction gate (user picks) → full mockup
        → coder brief → coder (isolated scope) → lead review (+ logic self-check)
        → on-device acceptance → wrap-up & retro → (module doc, on request)
```

The user commits; the lead never does. Periodically prune stale rules/skills with `scripts/memory_check.py --audit-rules`.

## One model only

The three roles are a division of labour, not three models.

- **Same model, separate sessions (recommended):** set coder and designer to the same CLI/model. Each `run_role.sh` call starts a fresh session that sees only the brief, so the review stays independent of the author's context.
- **Same model, sub-agents (no CLI needed):** if the lead's agent can spawn sub-agents (e.g. Claude Code's Agent tool, Cursor background agents), hand the brief to a sub-agent instead of `run_role.sh`. It starts with a clean context and sees only the brief, so you keep the author/reviewer separation without any extra CLI or `config.sh`. Don't use a mode that inherits the lead's context.
- **Single session, all three roles (no CLI needed):** no `run_role.sh`, no `config.sh`. The lead plays every role in order but keeps every gate: stop after design directions, write the brief before coding, run `review_diff.py` / `design_lint.py` and the review checklist before handing over. Self-review is weaker, so don't skip the scripts or the user's acceptance.

Without a CLI, what you get depends on where the lead runs:

| Lead runs in | Without a CLI |
|---|---|
| A coding agent that can read/write files and run commands (Claude Code, Cursor, Codex …) | Everything works; the scripts only need Python and git/svn |
| Web chat with no file access | Process only (direction gate, brief template, review checklist); checks are done by hand |

## Limitations and costs

- **Not for everything**: skip it for one-off scripts, quick investigations, prototypes, folders without git/svn, or when nobody can build and accept on a device.
- **Slower and more tokens** than one agent editing directly: the full lane waits on the user twice, and each role call is a fresh session that re-reads the brief and code.
- **Setup and upkeep**: CLIs to install, log in and probe; `config.sh`, `AGENTS.md` and adapters to maintain.
- **The user stays in the loop**: directions, builds, acceptance and commits are theirs.
- **Static checks only**: scripts and screenshots don't prove business logic is right; output is only as good as the brief and the review.

Details: `SKILL.md` §9.

## Adding a CLI

Write `scripts/adapters/<name>.sh` with `ADAPTER_QUOTA_RE` and an `adapter_run <model> <workdir> <extra_dir> <prompt>` function (~20 lines; see `scripts/adapters/README.md`), set `CODER_ADAPTER=<name>`, run `--probe`.

## Changelog

### 2026-11-24
- **Always build before handing over**: any code change gets one incremental build of the changed module; a failing build never reaches the user (replaces "small changes skip the build").
- **Circuit breaker covers behaviour classes**: a second bug in the same module and the same kind of behaviour (back / save / refresh / delete) counts as round 2 — write a state table (screen × action → keep / roll back / delete), get the user's OK, then fix every path at once.
- **Prune gates with data**: log `rounds N · found by` on every acceptance; after 1–2 weeks drop gates that never catch anything; no new process rules until the data exists.
- **Keep the SOP small**: AGENTS.md line cap (move details into skills/rules), rules audit after every milestone, and `scripts/handoff_rotate.py` keeps only the last 7 days of `leader-handoff.md`.
- Role table: the lead's "no product code edits" now notes the fast-lane exception; two new pitfalls.
- **Where it fits, and what it costs**: new `SKILL.md` §9 (good/poor fit, costs, limits), a Limitations section here, and a matching band at the bottom of the workflow chart.

### 2026-11-23
- **Design review rubric (`references/design-review.md`)**: 6-dimension 1–10 weighted scoring (dim 0 concept veto caps total at 6.0), content-parity hard gate, and "report violations only, no design fixes from lead" boundary.
- **Worst-case UI stress test (`references/ui-stress-test.md`)**: realistic extreme-data stress test checklist (long names, `<null>`, 0/1/full-page+1, large/negative amounts, long filenames, bad image aspect ratios) before acceptance.
- **Persistent memory, transcript search & lead handover (`references/memory-and-handover.md`)**:
  - Single-source `.agents/MEMORY.md` (≤150 lines, `[tag]` bullets, wrap-up retro) + `scripts/memory_check.py` (lint + `--match` injection into briefs + auto-run in `review_diff.py`).
  - `scripts/session_search.py` for no-LLM lookup of past user rulings.
  - `scripts/takeover_lead.sh` + shared `$SOP_HOME/leader-handoff.md` for smooth backup-lead handover when quota runs out; `SOP_FORCE_FALLBACK=1` in `run_role.sh`.
- **First-principles workflow upgrades**:
  - **Fast / Standard / Full routing lanes** at the entry of `SKILL.md` to match process weight to risk.
  - **Lightweight dynamic logic self-check** before asking the user to build (data parsing, param assembly, formatting, pagination boundaries) + error-branch parity checks.
  - **Rule & skill GC (`memory_check.py --audit-rules`)** to flag dead paths, bloated (>300 lines) and stale rule files.
  - **2-round circuit breaker**: stop after 2 consecutive rejected revs or bug-fix rounds to re-investigate root cause instead of blind retries.
- **Workflow charts (`docs/workflow*.html` & `.png`)**: added all new gates/tools, color-coded Commit (amber) and Module Docs (indigo) stages, removed concrete model names, and annotated `≤2 rounds stop` on return edges.

### 2026-11-08
- Added design thinking (restate need, 4 form questions, direction cards, overreach check), keep-skeleton rule for redesigning shipped pages, module doc workflow, and new pitfalls.

### 2026-10-31
- Initial release: model-agnostic lead/coder/designer SOP, CLI adapters, `scope.py` / `review_diff.py` / `design_lint.py`, single-model modes, and bilingual interactive workflow charts.

## License

MIT

---

## 中文

一套**模型不锁死**的多代理协作 SOP：一个主控代理带编码、设计两个执行代理做真实需求。主控定位代码、写任务书、审 diff、上设备验收；编码改代码；设计出 HTML 设计稿；用户选设计方向、做最终验收。

- 谁来演哪个角色、用什么模型，都在 `config.sh` 一个文件里；换模型改一行，换 CLI 加一个约 20 行的适配器。主控额度耗尽时也可用 `scripts/takeover_lead.sh` + 共用 `leader-handoff.md` 平滑接管。
- 内置**轻/中/重三级分流**（小修直走快车道、重构跳过设计、大改版走完整方向门）、设计稿 6 维打分表（`references/design-review.md`）、动态逻辑自检与最坏数据 UI 压测（`references/ui-stress-test.md`），以及 `.agents/MEMORY.md` 唯一项目记忆体检、规则清理审计（`--audit-rules`）与历史会话检索（`scripts/memory_check.py`、`scripts/session_search.py`）。
- **单个模型也能用**，三种方式：
  - 编码和设计填同一个 CLI/模型，分开会话（推荐）；
  - 主控代理能起子代理时（如 Claude Code 的 Agent 工具），把任务书交给子代理，**不需要 CLI 和 config.sh**，上下文同样是分开的；
  - 单个会话里主控按顺序扮演三个角色，**不需要 CLI 和 config.sh**，但方向门、任务书、脚本检查、用户验收一道都不能省。
  - 在能读写文件、跑命令的编码代理里，脚本照常可用；只有网页聊天时只能用流程和清单，检查靠人工。
- 安装：把整个目录放到主控代理的 skills 目录（见上面的表），复制 `config.example.sh` 到项目的 `.sop/config.sh` 填好，`run_role.sh --probe` 探活，然后在项目根建 `AGENTS.md`。
- 流程图（中文版）：

  ![三 AI 协作流程](docs/workflow.png)

  交互版 https://happyiosyuan.github.io/lead-coder-designer/workflow.html 。图里 `gf_*` 开头的是作者 iOS 项目自己的辅助脚本，仅作示例。
- **边界与代价**（详见 `SKILL.zh-CN.md` §9）：
  - 不适合一次性脚本、临时排查、原型验证、没有 git/svn 的目录，以及没人能编译、上设备验收的场景；
  - 比单代理直接改更慢、更费 token：重装道要等用户两次，每次调起角色都是新会话，要重读任务书和代码；
  - 有接入和维护成本：装 CLI、登录、探活，维护 `config.sh`、`AGENTS.md` 和适配器；
  - 用户要全程参与：选方向、编译、验收、提交都在用户手里；
  - 脚本和截图只是静态检查，证明不了业务逻辑对；结果上限取决于任务书和审查质量。
- `SKILL.md` 是英文版，`SKILL.zh-CN.md` 是中文版（想让代理读中文，把它改名为 `SKILL.md`）；模板和参考文档目前是中文；`examples/ios-uikit-swiftui/` 是一个真实 iOS 项目（已脱敏）的接入示例。

### 更新记录

#### 2026-11-24
- **改了代码就编译**：任何代码改动都先增量编译改动模块一次，编译失败不交给用户（取代「小改动不编译」）。
- **熔断覆盖同类行为**：同一模块同一类行为（返回 / 保存 / 刷新 / 删除）第二次出 bug 就算第 2 轮——先出状态表（页面 × 操作 → 保留 / 回滚 / 删除），用户确认后一次修全。
- **用数据删关卡**：每次验收记「轮次 N · 发现者」，攒 1–2 周后删掉从不拦截的关卡；攒够数据前不新增流程规则。
- **控制 SOP 体量**：AGENTS.md 设行数上限（细节挪进 skill / 规则）、每个里程碑后审计规则、`scripts/handoff_rotate.py` 让交接文件只留最近 7 天。
- 分工表注明主控「不改业务代码」的快车道例外；踩坑表新增 2 条。
- **适用边界与代价**：`SKILL.zh-CN.md` 新增 §9（适合/不适合、代价、局限），README 补对应小节，流程图底部加同名区块。

#### 2026-11-23
- **界面设计 6 维打分表（`references/design-review.md`）**：方向稿审设计思路与 0/1 维，完整稿 / rev 按 6 维 1–10 分加权打分（0 维立意 ≤5 封顶 6 分）、内容一致性一票打回，主控只指标准与数值不出设计方案。
- **最坏数据 UI 压测（`references/ui-stress-test.md`）**：验收前用真实极限数据压测列表 / 详情 / 表单（超长名、`<null>`、0/1/满页+1、大额/负数、长文件名、异常图片比例等），默认只读出报告，假数据绝不交付。
- **持久记忆、历史检索与主控热接管（`references/memory-and-handover.md`）**：
  - 唯一项目记忆 `.agents/MEMORY.md`（≤150 行、带 `[标签]`、收尾复盘闭环）+ `scripts/memory_check.py`（体检、`--match` 注入任务书、`review_diff.py` 收尾自动运行）。
  - `scripts/session_search.py` 无 LLM 检索历史会话原话，核对过往用户拍板口径。
  - `scripts/takeover_lead.sh` + 共用 `leader-handoff.md` 支持主控额度耗尽时平滑接管；`run_role.sh` 新增 `SOP_FORCE_FALLBACK=1`。
- **第一性原理流程升级**：
  - **轻 / 中 / 重三级分流**：小修走快车道、重构走标准道、大改版走重装道。
  - **轻量级动态逻辑自检**：涉及数据解析、参数拼接、格式化、分页边界时，喊用户编译前先跑单测或命令行断言，并逐请求核对失败分支。
  - **规则与技能定期清理（`memory_check.py --audit-rules`）**：扫描失效路径、超 300 行偏长文件与久未更新规则，防止 SOP 熵增。
  - **连续 2 轮熔断机制**：同一阶段连续 2 轮被打回立即停手重查根因、必要时回滚或升级问用户，禁止盲派第 3 轮。
- **中英文流程图更新（`docs/workflow*.html/.png`）**：同步全部新工具与关卡，步骤 7（提交收尾）改暖琥珀色、步骤 8（模块文档）改靛紫色，去除具体模型名，并在退回红线标注「`≤2 轮熔断`」。

#### 2026-11-08
- 新增设计思路（重述需求、form 四问、方向卡、过头检查）、已上线页面改版保留骨架约定、模块文档流程及新踩坑条目。

#### 2026-10-31
- 首个版本发布：模型不锁死的三角色 SOP、CLI 适配器、`scope.py` / `review_diff.py` / `design_lint.py`、单模型用法与中英文交互流程图。
