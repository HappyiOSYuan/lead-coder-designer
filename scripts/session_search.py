#!/usr/bin/env python3
"""
历史会话原话检索（只读，无 LLM）：从本地 Claude Code 会话日志里查以前说过的话。

用法：
  python3 -I session_search.py 关键词1 关键词2          # 同一条消息同时包含所有词
  python3 -I session_search.py "导航栏" --role user    # 只查用户原话
  python3 -I session_search.py 闪退 --all-projects --limit 30
  python3 -I session_search.py --session 08120e3a --around 12   # 看命中前后上下文

选项：
  --base DIR         会话日志根目录（默认 ~/.claude/projects）
  --project SUBSTR   过滤项目目录名（默认取当前工作区目录名）
  --all-projects     检索全部项目
  --role             user | assistant | any（默认 any）
  --since YYYY-MM-DD 仅看该日期及之后的消息
  --limit N          最多返回 N 条，按时间倒序（默认 15）
  --width N          摘要宽度（默认 160）
  --session ID --around K  打印指定会话第 K-3..K+3 条消息
"""
import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys


def default_project_hint():
    for cmd in (["svn", "info", "--show-item", "wc-root"], ["git", "rev-parse", "--show-toplevel"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout.strip()
            if out:
                return os.path.basename(out).replace(".", "-")
        except Exception:
            pass
    return os.path.basename(os.getcwd()).replace(".", "-")


def local_ts(raw):
    try:
        t = datetime.datetime.fromisoformat((raw or "").replace("Z", "+00:00"))
        return t.astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return (raw or "")[:16].replace("T", " ")


def text_of(content):
    if isinstance(content, str):
        return content
    parts = []
    for b in content or []:
        if isinstance(b, dict) and b.get("type") == "text":
            parts.append(b.get("text", ""))
    return "\n".join(parts)


def messages(path):
    idx = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") not in ("user", "assistant") or d.get("isMeta"):
                continue
            msg = d.get("message") or {}
            t = text_of(msg.get("content")).strip()
            if not t or t.startswith("<system-reminder>") or "<task-notification>" in t[:200]:
                continue
            idx += 1
            yield idx, d["type"], local_ts(d.get("timestamp")), t


def snippet(text, words, width):
    flat = re.sub(r"\s+", " ", text)
    low = flat.lower()
    pos = min((low.find(w) for w in words if low.find(w) >= 0), default=0)
    start = max(0, pos - width // 3)
    s = flat[start : start + width]
    return ("…" if start else "") + s + ("…" if start + width < len(flat) else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words", nargs="*")
    ap.add_argument("--base", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--project", default=None)
    ap.add_argument("--all-projects", action="store_true")
    ap.add_argument("--role", default="any", choices=["user", "assistant", "any"])
    ap.add_argument("--since")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--width", type=int, default=160)
    ap.add_argument("--session")
    ap.add_argument("--around", type=int)
    a = ap.parse_args()

    proj = a.project if a.project is not None else default_project_hint()
    dirs = [
        d for d in glob.glob(os.path.join(a.base, "*"))
        if os.path.isdir(d) and (a.all_projects or proj.lower() in os.path.basename(d).lower())
    ]
    files = [f for d in dirs for f in glob.glob(os.path.join(d, "*.jsonl"))]

    if a.session:
        match = [f for f in files if os.path.basename(f).startswith(a.session)]
        if not match:
            print("未找到会话: " + a.session)
            return 1
        k = a.around or 1
        for idx, role, ts, t in messages(match[0]):
            if k - 3 <= idx <= k + 3:
                print(f"--- #{idx} {role} {ts}\n{t[:2000]}\n")
        return 0

    words = [w.lower() for w in a.words]
    if not words:
        ap.print_help()
        return 2

    hits = []
    for f in files:
        sid = os.path.basename(f)[:8]
        for idx, role, ts, t in messages(f):
            if a.role != "any" and role != a.role:
                continue
            if a.since and ts[:10] < a.since:
                continue
            low = t.lower()
            if all(w in low for w in words):
                hits.append((ts, sid, idx, role, snippet(t, words, a.width)))
    hits.sort(reverse=True)
    scope = "全部项目" if a.all_projects else proj
    print(f"命中 {len(hits)} 条（范围：{scope}，显示最新 {min(len(hits), a.limit)} 条）")
    for ts, sid, idx, role, snip in hits[: a.limit]:
        print(f"{ts}  {sid}#{idx:<3} [{role[:4]}] {snip}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
