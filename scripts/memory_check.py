#!/usr/bin/env python3
"""
项目记忆体检、按标签摘抄与规则/技能清理审计工具（只读）。

用法：
  python3 -I memory_check.py [--file .agents/MEMORY.md] [--max-lines 150] [-q]
  python3 -I memory_check.py --match "关键词1 关键词2" [--limit 8]
  python3 -I memory_check.py --audit-rules .cursor/rules .cursor/skills [--stale-days 90]

检查项：
  error  超过 --max-lines 行
  error  列表条目缺少开头的 [标签]（供任务书按标签匹配）
  warn   同标签且文本相似度 >= 70% 的近重复条目
  warn   反引号里引用的仓库相对路径已不存在
  audit  统计规则/技能数量与行数，标出失效路径、超长文件（>300 行）和久未更新条目

存在 error 时退出码为 1，否则为 0。
"""
import argparse
import difflib
import os
import re
import subprocess
import sys
import time

BULLET = re.compile(r"^- \[([^\]]+)\]\s*(.+)$")
PATH_RE = re.compile(r"`([A-Za-z0-9._-]+/[A-Za-z0-9._/\u4e00-\u9fff-]+)`")


def sh(cmd, cwd="."):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def project_root(cwd="."):
    g = sh(["git", "-c", "core.quotePath=false", "rev-parse", "--show-toplevel"], cwd)
    s = sh(["svn", "info", "--show-item", "wc-root"], cwd)
    if g and s:
        return s if len(os.path.realpath(s)) > len(os.path.realpath(g)) else g
    return s or g or os.path.abspath(cwd)


def parse(path):
    """返回 (lines, bullets)，其中 bullets = [(lineno, tags:tuple, text)]。"""
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    bullets = []
    for n, line in enumerate(lines, 1):
        if not line.startswith("- "):
            continue
        m = BULLET.match(line)
        if m:
            tags = tuple(t.strip() for t in m.group(1).split("/") if t.strip())
            bullets.append((n, tags, m.group(2)))
        else:
            bullets.append((n, (), line[2:]))
    return lines, bullets


def check(path, root, max_lines):
    lines, bullets = parse(path)
    errors, warns = [], []
    if len(lines) > max_lines:
        errors.append(f"{len(lines)} lines > {max_lines}: 合并重复或清理过期条目")
    for n, tags, text in bullets:
        if not tags:
            errors.append(f"line {n}: 缺少 [标签]: {text[:60]}")
    for i, (n1, t1, x1) in enumerate(bullets):
        for n2, t2, x2 in bullets[i + 1 :]:
            if t1 and t1 == t2 and difflib.SequenceMatcher(None, x1, x2).ratio() >= 0.7:
                warns.append(f"lines {n1}/{n2}: 疑似重复 [{'/'.join(t1)}]")
    top_entries = set(os.listdir(root)) if os.path.isdir(root) else set()
    for n, line in enumerate(lines, 1):
        for p in PATH_RE.findall(line):
            p = p.rstrip("/").split(":")[0]
            if not p or any(c in p for c in "*{}<>…") or p.startswith(("http", "file")):
                continue
            head = p.split("/", 1)[0]
            if head not in top_entries:
                continue  # 跳过明显不是本仓库路径的片段（如 a/b 对比写法）
            if not os.path.exists(os.path.join(root, p)):
                warns.append(f"line {n}: 路径不存在: {p}")
    return len(lines), len(bullets), errors, warns


def match_entries(path, query, limit):
    """按 [标签] 命中 query（任务目标/路径/关键词），返回可直接贴进任务书的条目列表。"""
    hay = query.lower()
    scored = []
    for n, tags, text in parse(path)[1]:
        hit = [t for t in tags if len(t) >= 2 and t.lower() in hay]
        if hit:
            scored.append((-len(hit), n, f"- [{'/'.join(tags)}] {text}"))
    return [line for _, _, line in sorted(scored)[:limit]]


def audit_rules(root, dirs, stale_days):
    """扫描规则/技能目录，列出失效路径、超大文件与久未更新条目，供定期清理。"""
    top_entries = set(os.listdir(root)) if os.path.isdir(root) else set()
    now = time.time()
    cutoff = now - stale_days * 86400
    total_files, total_lines = 0, 0
    dead_refs, bloated, stale = [], [], []

    for d in dirs:
        base = d if os.path.isabs(d) else os.path.join(root, d)
        if not os.path.isdir(base):
            continue
        for cur, _, fs in os.walk(base):
            for fn in sorted(fs):
                if not fn.endswith((".md", ".mdc")):
                    continue
                full = os.path.join(cur, fn)
                rel = os.path.relpath(full, root)
                try:
                    lines = open(full, encoding="utf-8", errors="replace").read().splitlines()
                    mtime = os.path.getmtime(full)
                except OSError:
                    continue
                total_files += 1
                total_lines += len(lines)
                if len(lines) > 300:
                    bloated.append((rel, len(lines)))
                if mtime < cutoff:
                    days = int((now - mtime) / 86400)
                    stale.append((days, rel))
                for n, line in enumerate(lines, 1):
                    for p in PATH_RE.findall(line):
                        p = p.rstrip("/").split(":")[0]
                        if not p or any(c in p for c in "*{}<>…") or p.startswith(("http", "file")):
                            continue
                        if p.split("/", 1)[0] not in top_entries:
                            continue
                        if not os.path.exists(os.path.join(root, p)):
                            dead_refs.append((rel, n, p))

    print(f"rules-audit: {total_files} 个文件, 共 {total_lines} 行")
    if dead_refs:
        print(f"  失效路径引用 ({len(dead_refs)}):")
        for rel, n, p in dead_refs[:20]:
            print(f"    {rel}:{n} -> {p}")
    if bloated:
        print(f"  偏长文件 >300 行 ({len(bloated)}，建议拆分或裁剪):")
        for rel, cnt in sorted(bloated, key=lambda x: -x[1]):
            print(f"    {rel} ({cnt} 行)")
    if stale:
        print(f"  超过 {stale_days} 天未更新 ({len(stale)}，确认是否已过时或可归档):")
        for days, rel in sorted(stale, reverse=True)[:20]:
            print(f"    {rel} ({days} 天)")
    if not (dead_refs or bloated or stale):
        print("  无明显过时或失效项")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", help="记忆文件路径（默认 <项目根>/.agents/MEMORY.md）")
    ap.add_argument("--max-lines", type=int, default=150)
    ap.add_argument("--match", help="按 [标签] 筛选与该文本相关的记忆，供任务书摘抄")
    ap.add_argument("--limit", type=int, default=8, help="--match 最多输出条数（默认 8）")
    ap.add_argument("--audit-rules", nargs="+", help="审计规则/技能目录，筛出失效路径、超长和久未更新文件")
    ap.add_argument("--stale-days", type=int, default=90, help="--audit-rules 的久未更新阈值天数（默认 90）")
    ap.add_argument("-q", "--quiet", action="store_true", help="只输出一行汇总")
    a = ap.parse_args()

    root = project_root()
    if a.audit_rules:
        return audit_rules(root, a.audit_rules, a.stale_days)

    path = a.file or os.path.join(root, ".agents", "MEMORY.md")
    if not os.path.exists(path):
        print(f"memory: {path} 不存在")
        return 0 if a.match else 1

    if a.match:
        hits = match_entries(path, a.match, a.limit)
        for line in hits:
            print(line)
        return 0

    n_lines, n_bullets, errors, warns = check(path, root, a.max_lines)
    print(f"memory: {n_lines}/{a.max_lines} 行, {n_bullets} 条, error:{len(errors)} warn:{len(warns)}")
    if not a.quiet:
        for e in errors:
            print("  error " + e)
        for w in warns:
            print("  warn  " + w)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
