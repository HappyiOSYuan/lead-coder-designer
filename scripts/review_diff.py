#!/usr/bin/env python3
"""
diff 预审（只读，git / svn 通用）：先看这张汇总，再只读被标记的行，不用通读整份 diff。

用法：
  python3 -I review_diff.py [路径 ...] [--scope 路径 ...] [--rules rules.py] [--limit N]

  路径          只看这些路径的改动（默认整个工作区）
  --scope       任务允许改动的路径前缀；超出的文件标为「越界」
  --rules FILE  项目规则插件：一个 .py，定义 RULES = [(编号, 级别, 正则, 扩展名元组, 说明), ...]
                级别 error|warn；只检查新增行；行内写 `lint:ignore 编号` 可豁免
  --limit N     每节最多显示 N 行（默认 30）

输出：
  - 改动文件和 +/- 行数
  - 未入库的新文件（svn ? / git ??）
  - 越界文件（给了 --scope 时）
  - 内置检查（新增行）：调试输出残留、冲突标记、TODO/FIXME、超长行
  - 项目规则插件的命中
退出码：有 error 级命中返回 1，否则 0。
"""
import argparse
import importlib.util
import os
import re
import subprocess
import sys

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

BUILTIN = [
    ("B01", "error", r"^(<<<<<<<|>>>>>>>|=======$)", None, "冲突标记"),
    ("B02", "warn", r"\b(console\.log|debugger;|print\(|NSLog\(|dump\(|pdb\.set_trace|breakpoint\(\))", None, "调试输出残留（确认是否该留）"),
    ("B03", "warn", r"\b(TODO|FIXME|XXX|HACK)\b", None, "遗留待办标记"),
    ("B04", "warn", r"^.{241,}$", None, "超长行（>240 字符）"),
]


def sh(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True).stdout


def detect(cwd="."):
    """Pick the innermost working copy (a git repo can wrap an svn checkout, e.g. a git-tracked home dir)."""
    g = sh(["git", "-c", "core.quotePath=false", "rev-parse", "--show-toplevel"], cwd).strip()
    s = sh(["svn", "info", "--show-item", "wc-root"], cwd).strip()
    if g and s:
        return ("svn", s) if len(os.path.realpath(s)) > len(os.path.realpath(g)) else ("git", g)
    if g:
        return "git", g
    if s:
        return "svn", s
    sys.exit("当前目录不在 git 或 svn 工作区里")

def parse_diff(text, vcs):
    files, cur, ln = {}, None, 0
    for line in text.splitlines():
        if vcs == "svn" and line.startswith("Index: "):
            cur = line[7:].strip()
            files[cur] = {"added": [], "plus": 0, "minus": 0}
            continue
        if vcs == "git" and line.startswith("+++ b/"):
            cur = line[6:].strip()
            files[cur] = {"added": [], "plus": 0, "minus": 0}
            continue
        if cur is None or line.startswith(("===", "--- ", "+++ ", "diff --git", "index ")):
            continue
        m = HUNK_RE.match(line)
        if m:
            ln = int(m.group(1))
            continue
        if line.startswith("+"):
            files[cur]["added"].append((ln, line[1:]))
            files[cur]["plus"] += 1
            ln += 1
        elif line.startswith("-"):
            files[cur]["minus"] += 1
        elif not line.startswith("\\"):
            ln += 1
    return files


def untracked(vcs, root, paths):
    if vcs == "git":
        out = sh(["git", "-c", "core.quotePath=false", "ls-files", "--others", "--exclude-standard", "--"] + paths, root)
        return [p for p in out.splitlines() if p]
    out = sh(["svn", "status"] + paths, root)
    return [l[8:].strip() for l in out.splitlines() if l.startswith("?")]


def load_rules(path):
    spec = importlib.util.spec_from_file_location("project_rules", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(getattr(mod, "RULES", []))


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--scope", nargs="*", default=[])
    ap.add_argument("--rules")
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()

    vcs, root = detect()
    paths = [os.path.relpath(os.path.abspath(p), root) for p in a.paths]
    diff = sh(["git", "-c", "core.quotePath=false", "diff", "HEAD", "--"] + paths, root) if vcs == "git" else sh(["svn", "diff"] + paths, root)
    files = parse_diff(diff, vcs)
    new = untracked(vcs, root, paths)
    for p in new:  # 新文件整篇当新增行
        full = os.path.join(root, p)
        if os.path.isfile(full):
            try:
                lines = open(full, encoding="utf-8", errors="replace").read().splitlines()
            except OSError:
                continue
            files[p] = {"added": list(enumerate(lines, 1)), "plus": len(lines), "minus": 0}

    print(f"== 改动文件 {len(files)} 个（{vcs}）")
    for p, f in sorted(files.items())[: a.limit]:
        print(f"  {p}  +{f['plus']} -{f['minus']}")
    if len(files) > a.limit:
        print(f"  …还有 {len(files) - a.limit} 个")

    if new:
        print(f"== 未入库新文件 {len(new)} 个（需要 {'git add' if vcs == 'git' else 'svn add'}）")
        for p in new[: a.limit]:
            print("  " + p)

    if a.scope:
        scope = [s.rstrip("/") for s in a.scope]
        out = [p for p in files if not any(p == s or p.startswith(s + "/") for s in scope)]
        if out:
            print(f"== 越界文件 {len(out)} 个（不在 --scope 内）")
            for p in out[: a.limit]:
                print("  " + p)

    rules = BUILTIN + (load_rules(a.rules) if a.rules else [])
    compiled = [(rid, lvl, re.compile(rx), exts, msg) for rid, lvl, rx, exts, msg in rules]
    hits = []
    for p, f in files.items():
        for ln, text in f["added"]:
            for rid, lvl, rx, exts, msg in compiled:
                if exts and not p.endswith(tuple(exts)):
                    continue
                if rx.search(text) and f"lint:ignore {rid}" not in text:
                    hits.append((lvl, rid, p, ln, msg, text.strip()[:100]))
    errors = sum(1 for h in hits if h[0] == "error")
    warns = len(hits) - errors
    print(f"== 新增行检查：error {errors} · warn {warns}")
    for lvl, rid, p, ln, msg, snip in sorted(hits)[: a.limit]:
        print(f"  {lvl:5} {rid} {p}:{ln}  {msg}\n        {snip}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
