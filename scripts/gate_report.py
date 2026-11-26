#!/usr/bin/env python3
"""
关卡诊断（只读，无 LLM）：用证据回答「哪道关卡在拦问题、哪道在漏、哪道没跑」。

两种用法：

  1) stats —— 汇总交接文件里的验收行（「轮次 N · 发现者 …」/「rounds N · found by …」）
     python3 -I gate_report.py stats [--file leader-handoff.md] [--archive] [--since YYYY-MM-DD]
     输出：任务数、平均轮次、轮次分布、每个发现者拦下几次、从没拦过的关卡、用户兜底占比。
     用来执行 SKILL.md 第 6 节「用数据删关卡」。

  2) session —— 读一次主控会话记录（Claude Code 的 .jsonl），找出流程哪一步跳过或失灵
     python3 -I gate_report.py session [会话ID前缀 | latest] [--project SUBSTR] [--file x.jsonl]
                   [--build-re 正则] [--coder-re 正则] [--designer-re 正则] [--json]

     怎么切轮次：一次派发（run_role.sh / 项目自己的派发脚本 / 子代理 / 主控直接改代码）开一轮；
     后台任务等到它的完成通知，前台任务立即算完成；完成后的下一条用户消息就是用户对这一轮的反馈。
     派发到用户反馈之间跑过的检查都算这一轮的关卡；任务书里写明让执行代理收尾时跑的检查、
     主控读派发日志（tail/cat *.log / *.output）时看到的检查摘要也算（报告里标「执行方」）。

     报告：
       - [跳过] 编码轮交给用户前没跑 review_diff；设计轮没跑 design_lint
       - [跳过] 同一任务书派了 ≥3 次，或连续 2 轮被打回后又派第 3 轮 —— 熔断没生效
       - [漏网] 用户打回：列出这一轮跑过的关卡（它们都没拦住）
       - [提醒] 派编码前没跑 scope start；没编译；主控直接改代码后没审；验收后没补验收行
     每条带 `会话ID#序号`，可直接用 session_search.py --session <ID> --around <序号> 看上下文。
     项目给脚本加了前缀（gf_review_diff.py）也能认；自家派发脚本用 --coder-re / --designer-re 指定。

限制：只认 Claude Code 的会话格式（~/.claude/projects/*/*.jsonl）；用户「打回 / 验收」靠关键词判断，
结论当线索看，拿不准的回原文核对。
"""
import argparse
import collections
import glob
import json
import os
import re
import subprocess
import sys

# ======================= stats =======================

FINDER_ALIASES = {
    "script": "脚本", "scripts": "脚本", "脚本": "脚本", "lint": "脚本",
    "diff-review": "审diff", "review": "审diff", "审diff": "审diff",
    "build": "编译", "compile": "编译", "编译": "编译",
    "user": "用户", "用户": "用户",
}
CANON_FINDERS = ["脚本", "审diff", "编译"]
ACCEPT_ROW = re.compile(r"(?:轮次|rounds)\s*(\d+|\?)\s*[·・|,，]\s*(?:发现者|found by)\s*(.+)$", re.I)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def sop_home():
    return os.environ.get("SOP_HOME", os.path.expanduser("~/.cache/lead-coder-designer"))


def cmd_stats(a):
    path = a.file or os.path.join(sop_home(), "leader-handoff.md")
    files = [path]
    if a.archive:
        files.append(os.path.join(os.path.dirname(path), "leader-handoff-archive.md"))
    rows = []
    for f in files:
        if not os.path.exists(f):
            continue
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = ACCEPT_ROW.search(line.strip())
                if not m:
                    continue
                d = DATE_RE.search(line)
                date = d.group(1) if d else ""
                if a.since and date and date < a.since:
                    continue
                finders = [x.strip().lower() for x in re.split(r"[/、,，+\s]+", m.group(2)) if x.strip()]
                rows.append((date, m.group(1), {FINDER_ALIASES.get(x, x) for x in finders}))
    if not rows:
        print(f"没找到验收行（{path}）。验收时补「· 验收 · 轮次 N · 发现者 …」，攒 1–2 周再跑。")
        return 0

    n = len(rows)
    dates = sorted(d for d, _, _ in rows if d)
    rounds = [int(r) for _, r, _ in rows if r.isdigit()]
    dist = collections.Counter(min(r, 4) for r in rounds)
    caught = collections.Counter(f for _, _, fs in rows for f in fs)
    print(f"验收 {n} 个任务（{dates[0] if dates else '?'} ~ {dates[-1] if dates else '?'}）")
    if rounds:
        avg = sum(rounds) / len(rounds)
        print(f"平均轮次 {avg:.2f}；分布 " + " · ".join(f"{k if k < 4 else '4+'}轮 {dist[k]}" for k in sorted(dist)))
        print(f"一次通过率 {dist[1] / len(rounds):.0%}")
    print("\n发现者（一个任务里出现过就记 1 次）：")
    for g in CANON_FINDERS + ["用户"] + sorted(k for k in caught if k not in CANON_FINDERS + ["用户", "?"]):
        print(f"  {g:<6} {caught.get(g, 0)}")
    if caught.get("?"):
        print(f"  ?      {caught['?']}（没记清）")

    print("\n结论：")
    never = [g for g in CANON_FINDERS if not caught.get(g)]
    if never:
        print(f"  - 从没拦下过问题：{'、'.join(never)} —— 样本够（≥10 个任务）后交用户确认是否删掉或改造")
    if caught.get("用户", 0) / n >= 0.3:
        print(f"  - 用户兜底 {caught['用户'] / n:.0%}：漏到用户的偏多，用 `gate_report.py session` 看漏在哪一步，补那一步")
    if rounds and sum(rounds) / len(rounds) > 2:
        print("  - 平均轮次 > 2：任务书不够准或熔断没起作用，抽几次会话看看")
    if n < 10:
        print(f"  - 只有 {n} 个样本，先别删关卡")
    return 0


# ======================= session =======================

USER_REJECT = re.compile(
    r"不对|不行|还是不|还是有|还是没|又出|又有|没变|没生效|没效果|报错|闪退|崩溃|崩了|有问题|错了|不是这样|不满意|"
    r"\bbug\b|\bwrong\b|still (?:broken|wrong|there)|broken|doesn'?t work|not working|crash", re.I)
USER_ACCEPT = re.compile(
    r"^(?:好了|可以了?|没问题|ok|okay|lgtm|通过|搞定|验收通过)[。!！.\s]*$|提交了|验收通过|改动没问题", re.I)
NOT_FEEDBACK = re.compile(r"^(?:This session is being continued|\[Request interrupted|<command-|<local-command)")
NOTIFY_ID = re.compile(r"<tool-use-id>(\S+?)</tool-use-id>")
ACCEPT_LINE = re.compile(r"轮次\s*(?:\d+|\?)|rounds\s*(?:\d+|\?)", re.I)
DEFAULT_BUILD = (r"xcodebuild|gradlew?\b|npm run build|pnpm (?:run )?build|yarn build|swift build|"
                 r"cargo build|^make\b|build\.sh")
GATES = [  # (名字, 正则, 匹配对象)  "prog" = 脚本文件名；"seg" = 整段命令
    ("scope_start", re.compile(r"(?:scope\.py|task_scope\S*)\s+start\b"), "seg"),
    ("review_diff", re.compile(r"review_diff"), "prog"),
    ("design_lint", re.compile(r"design_lint"), "prog"),
    ("memory_check", re.compile(r"memory_check"), "prog"),
    ("screenshot", re.compile(r"simctl io .*screenshot|adb .*screencap|screencapture|_shot\b"), "seg"),
]
ENV_ASSIGN = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)+")
NOT_RUN = ("cd ", "echo ", "grep ", "rg ", "cat ", "sed ", "/bin/ls", "ls ", "tail ", "head ", "wc ", "find ", "printf ",
           "for ", "do ", "done", "if ", "then", "fi", "svn ", "git ", "cp ", "mv ", "diff ", "open ", "mkdir ", "chmod ")
DOC_FILE = re.compile(r"\.(?:md|txt|json|html|csv)$|/\.sop/|leader-handoff|MEMORY", re.I)
LOG_READ = re.compile(r"\b(?:tail|cat|less|head)\b[^|;&]*\.(?:output|log)\b")
LOG_SIGNS = [  # 派发脚本 / 执行代理日志里的检查摘要
    ("review_diff", re.compile(r"review[_ ]diff[^\n]{0,80}(?:error|warn|0 ?error|通过)|^--- ?review", re.I | re.M)),
    ("design_lint", re.compile(r"design[_ ]lint[^\n]{0,80}(?:error|warn|通过)|^--- ?design lint", re.I | re.M)),
    ("build", re.compile(r"BUILD (?:SUCCEEDED|FAILED)|编译(?:通过|成功|失败)|\berror: |Build complete", re.M)),
]
EDIT_TOOLS = ("tool:Edit", "tool:Write", "tool:MultiEdit", "tool:NotebookEdit")


def split_unquoted(cmd):
    """按引号外的 && || ; | 换行切分（引号里的 | 和换行不算）。"""
    parts, buf, q, i = [], [], None, 0
    while i < len(cmd):
        c = cmd[i]
        if q:
            buf.append(c)
            if c == "\\" and q == '"' and i + 1 < len(cmd):
                buf.append(cmd[i + 1])
                i += 1
            elif c == q:
                q = None
        elif c in "'\"":
            q = c
            buf.append(c)
        elif c == "\\" and cmd[i + 1:i + 2] == "\n":
            buf.append(" ")
            i += 1
        elif c in ";|&\n":
            if c == "&" and cmd[i + 1:i + 2] != "&":
                buf.append(c)
            else:
                parts.append("".join(buf))
                buf = []
                if cmd[i + 1:i + 2] == c and c in "|&":
                    i += 1
        else:
            buf.append(c)
        i += 1
    parts.append("".join(buf))
    return parts


def heads(cmd):
    """命令里真正执行的每一段（去掉环境变量和 python3 -I 前缀）。grep/cat 里提到脚本名不算跑过。"""
    cmd = re.sub(r"<<-?\s*'?(\w+)'?.*?^\1$", "", cmd, flags=re.S | re.M)  # 去掉 heredoc 正文
    for seg in split_unquoted(cmd):
        seg = ENV_ASSIGN.sub("", seg.strip())
        seg = re.sub(r"^(?:python3?|bash|sh|zsh)(?:\s+-\w+)*\s+", "", seg)
        if seg and not seg.startswith(NOT_RUN):
            yield seg


def short_path(p):
    p = os.path.expanduser(p or "").rstrip("/")
    parts = p.split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else p


def brief_of(seg):
    m = re.search(r"(?:-f|--file)\s+(\S+)", seg)
    return os.path.expanduser(m.group(1)) if m else ""


def gates_in(text, build_re):
    """一段文字（任务书收尾命令）里写明要跑的检查。"""
    found = {n for n, rx, _ in GATES if rx.search(text)}
    if build_re.search(text):
        found.add("build")
    return found


def default_project_hint():
    for cmd in (["svn", "info", "--show-item", "wc-root"], ["git", "rev-parse", "--show-toplevel"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout.strip()
            if out:
                return os.path.basename(out).replace(".", "-")
        except Exception:
            pass
    return os.path.basename(os.getcwd()).replace(".", "-")


def find_session(a):
    if a.file:
        return a.file
    base = os.path.expanduser("~/.claude/projects")
    proj = (a.project if a.project is not None else default_project_hint()).lower()
    files = [f for d in glob.glob(os.path.join(base, "*"))
             if os.path.isdir(d) and proj in os.path.basename(d).lower()
             for f in glob.glob(os.path.join(d, "*.jsonl"))]
    if not files:
        return None
    if a.sid in (None, "latest"):
        return max(files, key=os.path.getmtime)
    match = [f for f in files if os.path.basename(f).startswith(a.sid)]
    return match[0] if match else None


def text_of(content):
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def events(path):
    """产出 (序号, 种类, 内容, tool_use_id)。序号与 session_search.py 一致；工具调用挂在前一条消息的序号上。"""
    idx = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") not in ("user", "assistant") or d.get("isMeta"):
                continue
            content = (d.get("message") or {}).get("content")
            t = text_of(content).strip()
            if "<task-notification>" in t[:200]:
                for tid in NOTIFY_ID.findall(t):
                    yield idx, "notify", "", tid
                continue
            if t and not t.startswith("<system-reminder>"):
                idx += 1
                yield idx, "user_text" if d["type"] == "user" else "lead_text", t, None
            if d["type"] == "user" and isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        yield idx, "result", text_of(b.get("content")), b.get("tool_use_id")
            if d["type"] == "assistant" and isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        yield idx, "tool:" + b.get("name", ""), b.get("input") or {}, b.get("id")


class Session:
    def __init__(self, a):
        self.build_re = re.compile(a.build_re or DEFAULT_BUILD)
        self.coder_re = re.compile(a.coder_re) if a.coder_re else None
        self.designer_re = re.compile(a.designer_re) if a.designer_re else None
        self.briefs = {}          # 任务书绝对路径 → 内容（主控 Write 时记下）
        self.open = []            # 还没收到用户反馈的轮次
        self.rounds = []          # 已结束的轮次
        self.loose = set()        # 不属于任何轮次时跑的关卡（如派发前的 scope start）
        self.seen_build = False
        self.accept_at = None
        self.notes = []           # (级别, 序号, 文字)
        self.cmd_of = {}          # tool_use_id → 命令（用来认「读派发日志」的结果）

    # ---- 轮次 ----
    def start(self, kind, brief, idx, tid, background):
        r = dict(kind=kind, brief=short_path(brief) or "?", at=idx, tid=tid, done=not background,
                 gates=set(self.loose), by_exec=set())
        if brief in self.briefs:
            r["by_exec"] = gates_in(self.briefs[brief], self.build_re)
        self.loose = set()
        self.open.append(r)

    def add_gates(self, names):
        if not names:
            return
        if self.open:
            for r in self.open:
                r["gates"] |= names
        else:
            self.loose |= names

    def role_of(self, seg):
        prog = os.path.basename(seg.split()[0])
        if prog == "run_role.sh":
            m = re.search(r"\b(coder|designer)\b", seg)
            return m.group(1) if m else None
        if len(seg.split()) < 2:   # 光秃秃的脚本名（多半是 sed / for 的参数被切出来）不算派发
            return None
        if self.coder_re and self.coder_re.search(prog):
            return "coder"
        if self.designer_re and self.designer_re.search(prog):
            return "designer"
        return None

    # ---- 事件 ----
    def feed(self, idx, kind, payload, tid):
        if kind == "result":
            cmd = self.cmd_of.pop(tid, "")
            if cmd and LOG_READ.search(cmd):
                found = {n for n, rx in LOG_SIGNS if rx.search(payload)}
                for r in self.open:
                    if r["kind"] in ("coder", "designer", "subagent"):
                        r["by_exec"] |= found
            return
        if kind == "tool:Bash":
            cmd = payload.get("command", "")
            self.cmd_of[tid] = cmd
            bg = bool(payload.get("run_in_background"))
            if ACCEPT_LINE.search(cmd):
                self.accept_at = None
            hit = set()
            for seg in heads(cmd):
                role = self.role_of(seg)
                if role:
                    self.start(role, brief_of(seg), idx, tid, bg)
                    continue
                prog = os.path.basename(seg.split()[0])
                hit |= {n for n, rx, on in GATES if rx.search(seg if on == "seg" else prog)}
                if self.build_re.search(seg):
                    hit.add("build")
                    self.seen_build = True
            self.add_gates(hit)
        elif kind in ("tool:Agent", "tool:Task"):
            self.start("subagent", (payload.get("description") or "?")[:40], idx, tid,
                       bool(payload.get("run_in_background")))
        elif kind in EDIT_TOOLS:
            fp = os.path.expanduser(payload.get("file_path", "") or payload.get("notebook_path", ""))
            body = payload.get("content") or payload.get("new_string") or ""
            if ACCEPT_LINE.search(body):
                self.accept_at = None
            if kind == "tool:Write" and fp:
                self.briefs[fp] = body
            if fp and not DOC_FILE.search(fp) and not any(r["kind"] == "lead-edit" for r in self.open):
                self.start("lead-edit", fp, idx, tid, False)
        elif kind == "notify":
            for r in self.open:
                if r["tid"] == tid:
                    r["done"] = True
        elif kind == "user_text":
            if NOT_FEEDBACK.search(payload):
                return
            self.on_user(idx, payload)

    def on_user(self, idx, text):
        done = [r for r in self.open if r["done"]]
        self.open = [r for r in self.open if not r["done"]]
        short = re.sub(r"\s+", " ", text)[:60]
        is_accept = bool(USER_ACCEPT.search(text.strip()))
        if is_accept:
            if self.accept_at:
                self.notes.append(("warn", self.accept_at, "验收后没补「轮次 N · 发现者」验收行"))
            self.accept_at = idx
        if not done:
            return
        end = "accept" if is_accept else "reject" if USER_REJECT.search(text) else "user"
        for r in done:
            r.update(end_idx=idx, end_kind=end, end_text=short)
            self.rounds.append(r)

    # ---- 检查 ----
    def finish(self):
        for r in self.open:
            r.update(end_idx=r["at"], end_kind="end", end_text="")
            self.rounds.append(r)
        self.open = []
        if self.accept_at:
            self.notes.append(("warn", self.accept_at, "验收后没补「轮次 N · 发现者」验收行"))

        streak = collections.Counter()   # 按角色记连续打回
        for r in sorted(self.rounds, key=lambda x: x["at"]):
            g, ex, who = r["gates"], r["by_exec"], f"`{r['brief']}`"
            handed = r["end_kind"] != "end"
            if r["kind"] in ("coder", "designer") and streak[r["kind"]] >= 2:
                self.notes.append(("error", r["at"], f"连续 2 轮被打回后又派了 {who} —— 熔断没生效（先查根因 / 状态表 / 问用户）"))
                streak[r["kind"]] = 0
            if r["kind"] == "coder":
                if "scope_start" not in g:
                    self.notes.append(("warn", r["at"], f"派编码 {who} 前没跑 scope start"))
                if handed and "review_diff" not in g:
                    if "review_diff" in ex:
                        self.notes.append(("info", r["at"], f"编码 {who} 的 review_diff 只由执行方在收尾跑，主控没再跑"))
                    else:
                        self.notes.append(("error", r["at"], f"编码 {who} 交给用户前没跑 review_diff"))
                if handed and self.seen_build and not ({"build"} & (g | ex)):
                    self.notes.append(("warn", r["at"], f"编码 {who} 交给用户前没编译"))
            elif r["kind"] == "designer":
                if handed and "design_lint" not in (g | ex):
                    self.notes.append(("error", r["at"], f"设计 {who} 交给用户前没跑 design_lint"))
            elif r["kind"] == "lead-edit":
                if handed and "review_diff" not in g:
                    self.notes.append(("warn", r["at"], f"主控直接改 {who} 后没跑 review_diff"))
            if r["end_kind"] == "reject":
                ran = sorted(g) + [f"{x}(执行方)" for x in sorted(ex - g)]
                self.notes.append(("leak" if r["kind"] != "subagent" else "info", r["end_idx"],
                                   f"{r['kind']} {who} 被打回「{r['end_text']}」—— 这一轮的关卡：{'、'.join(ran) or '无'}"))
                if r["kind"] in ("coder", "designer"):
                    streak[r["kind"]] += 1
            elif r["end_kind"] in ("accept", "user") and r["kind"] in ("coder", "designer"):
                streak[r["kind"]] = 0

        counts = collections.Counter(r["brief"] for r in self.rounds if r["kind"] in ("coder", "designer"))
        for b, c in counts.items():
            if c >= 3 and b != "?":
                self.notes.append(("error", 0, f"任务书 `{b}` 派了 {c} 次 —— 超过 2 轮熔断"))
        if not self.seen_build and any(r["kind"] in ("coder", "lead-edit") for r in self.rounds):
            self.notes.append(("info", 0, "整场没认出编译命令；用 --build-re 指定项目的编译脚本，才能检查「改代码就编译」"))


def cmd_session(a):
    path = find_session(a)
    if not path:
        print("没找到会话（用 --project / --file 指定）")
        return 1
    sid = os.path.basename(path)[:8]
    s = Session(a)
    for ev in events(path):
        s.feed(*ev)
    s.finish()
    has_error = any(l == "error" for l, _, _ in s.notes)

    if a.json:
        print(json.dumps(dict(
            session=sid, file=path,
            rounds=[dict(r, gates=sorted(r["gates"]), by_exec=sorted(r["by_exec"])) for r in s.rounds],
            findings=[dict(level=l, ref=f"{sid}#{i}" if i else sid, text=t) for l, i, t in s.notes],
        ), ensure_ascii=False, indent=1))
        return 1 if has_error else 0

    kinds = collections.Counter(r["kind"] for r in s.rounds)
    ends = collections.Counter(r["end_kind"] for r in s.rounds)
    print(f"会话 {sid}  {path}")
    print(f"轮次 {len(s.rounds)}（" + " · ".join(f"{k} {v}" for k, v in kinds.items()) + "）；"
          f"用户打回 {ends.get('reject', 0)} · 验收 {ends.get('accept', 0)} · 未收到反馈 {ends.get('end', 0)}")
    order = {"error": 0, "leak": 1, "warn": 2, "info": 3}
    label = {"error": "跳过", "leak": "漏网", "warn": "提醒", "info": "说明"}
    if not s.notes:
        print("没发现跳过的关卡或漏网问题。")
    for lvl, i, t in sorted(s.notes, key=lambda x: (order[x[0]], x[1])):
        ref = f"{sid}#{i}" if i else sid
        print(f"  [{label[lvl]}] {ref:<13} {t}")
    if s.notes:
        print(f"\n看上下文：python3 -I scripts/session_search.py --session {sid} --around <序号>")
    return 1 if has_error else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode")
    st = sub.add_parser("stats", help="汇总交接文件里的验收行")
    st.add_argument("--file", help="交接文件（默认 $SOP_HOME/leader-handoff.md）")
    st.add_argument("--archive", action="store_true", help="连 leader-handoff-archive.md 一起统计")
    st.add_argument("--since", help="只看该日期及之后（YYYY-MM-DD）")
    se = sub.add_parser("session", help="诊断一次主控会话")
    se.add_argument("sid", nargs="?", default="latest", help="会话 ID 前缀，默认最近一次")
    se.add_argument("--project", help="过滤项目目录名（默认取当前工作区目录名）")
    se.add_argument("--file", help="直接给 .jsonl 路径")
    se.add_argument("--build-re", help="项目编译命令的正则（默认认 xcodebuild / gradle / npm run build / *build.sh 等）")
    se.add_argument("--coder-re", help="项目自己的编码派发脚本名正则（run_role.sh coder 之外），如 gf_cursor")
    se.add_argument("--designer-re", help="项目自己的设计派发脚本名正则，如 gf_gemini")
    se.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.mode == "stats":
        return cmd_stats(a)
    if a.mode == "session":
        return cmd_session(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
