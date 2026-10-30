#!/usr/bin/env python3
"""
任务范围：这个任务到底改了哪些文件？（git / svn 通用，只读工作区 + 写快照）

多个代理共用一个工作区时，开始前拍快照，结束后对比，只把本任务产生的改动归档：
  svn：放进以任务名命名的 changelist（之后提交时按 changelist 挑）
  git：写出文件清单，并给出 `git add` 命令（不自动执行）

用法：
  python3 -I scope.py start <任务>     # 派发前
  python3 -I scope.py end <任务>       # 编码角色结束后
  python3 -I scope.py show <任务>      # 再看一次清单

快照：$SOP_HOME/scope/<任务>.json（默认 ~/.cache/lead-coder-designer）
判定为本任务改动：开始时没有、结束时有；或两次都有但内容 sha1 变了；或状态列变了。
开始前就脏、内容没变的文件视为别的会话的改动，不碰。
"""
import hashlib
import json
import os
import subprocess
import sys

IGNORE_PARTS = {".DS_Store", "DesignMockups", ".sop", "node_modules", ".git", ".svn"}


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

def status(vcs, root):
    """-> {path: status_code}"""
    out = {}
    if vcs == "git":
        for line in sh(["git", "-c", "core.quotePath=false", "status", "--porcelain=v1", "-uall"], root).splitlines():
            code, path = line[:2], line[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            out[path.strip('"')] = code
    else:
        for line in sh(["svn", "status"], root).splitlines():
            if not line or line.startswith("---") or len(line) < 9:
                continue
            out[line[8:].strip()] = line[:7]
    return {p: c for p, c in out.items() if not (set(p.split("/")) & IGNORE_PARTS)}


def sha(path):
    try:
        if os.path.isdir(path):
            return "dir"
        with open(path, "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()
    except OSError:
        return "missing"


def snap_file(task):
    base = os.environ.get("SOP_HOME", os.path.expanduser("~/.cache/lead-coder-designer"))
    d = os.path.join(base, "scope")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, task + ".json")


def snapshot(vcs, root):
    st = status(vcs, root)
    return {p: [c, sha(os.path.join(root, p))] for p, c in st.items()}


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("start", "end", "show"):
        print(__doc__)
        sys.exit(2)
    cmd, task = sys.argv[1], sys.argv[2]
    if not task or "/" in task or task.startswith("-"):
        sys.exit("任务名不合法：" + task)
    vcs, root = detect(os.getcwd())
    path = snap_file(task)

    if cmd == "start":
        snap = {"vcs": vcs, "root": root, "files": snapshot(vcs, root)}
        json.dump(snap, open(path, "w"), ensure_ascii=False, indent=1)
        print(f"[{task}] 快照 {len(snap['files'])} 个已改动路径（{vcs}）→ {path}")
        return

    if not os.path.exists(path):
        sys.exit(f"没有 {task} 的快照，先运行 start")
    snap = json.load(open(path))
    before = snap["files"]

    if cmd == "end":
        after = snapshot(vcs, root)
        mine = sorted(p for p, v in after.items() if p not in before or before[p] != v)
        gone = sorted(p for p in before if p not in after)  # 开始时脏、现在干净 = 被还原
        snap["mine"], snap["reverted"] = mine, gone
        json.dump(snap, open(path, "w"), ensure_ascii=False, indent=1)
    mine, gone = snap.get("mine", []), snap.get("reverted", [])

    print(f"[{task}] 本任务改动 {len(mine)} 个：")
    for p in mine:
        print("  " + p)
    if gone:
        print(f"[{task}] 开始时有改动、现在已还原 {len(gone)} 个（确认是不是本任务误还原了别人的改动）：")
        for p in gone:
            print("  " + p)
    if cmd == "end" and mine:
        if vcs == "svn":
            st = status(vcs, root)
            versioned = [p for p in mine if not st.get(p, " ").startswith("?") and not os.path.isdir(os.path.join(root, p))]
            new = [p for p in mine if st.get(p, " ").startswith("?")]
            if versioned:
                print(sh(["svn", "changelist", task] + versioned, root).strip())
            if new:
                print("未入库（可能需要 svn add）：\n  " + "\n  ".join(new))
        else:
            print("提交前：git add -- " + " ".join(f"'{p}'" for p in mine))


if __name__ == "__main__":
    main()
