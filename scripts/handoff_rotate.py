#!/usr/bin/env python3
"""主控交接文件瘦身。

leader-handoff.md 只留最近 N 天（默认 7）的记录，更早的追加到同目录 leader-handoff-archive.md。
接手主控（原主控恢复 / 备选主控接管）时先跑一次再读；takeover_lead.sh 启动时自动跑。幂等。

  python3 -I scripts/handoff_rotate.py [--days 7] [--file <path>] [--dry-run]
"""
import argparse
import datetime as dt
import os
import re
import sys

DEFAULT = os.path.join(os.environ.get("SOP_HOME", os.path.expanduser("~/.cache/lead-coder-designer")), "leader-handoff.md")
ENTRY = re.compile(r"^- (\d{4}-\d{2}-\d{2})")
GLUED = re.compile(r"(?<=\S)\s*(?=- \d{4}-\d{2}-\d{2}[ \[])")  # 两条记录粘在同一行


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=DEFAULT)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.file):
        print(f"handoff: {a.file} missing")
        return 0
    text = open(a.file, encoding="utf-8").read()
    lines = []
    for ln in text.splitlines():
        lines.extend(p for p in GLUED.split(ln) if p != "" or ln == "")

    header, entries, cur = [], [], None  # entries: [date, [lines]]
    for ln in lines:
        m = ENTRY.match(ln)
        if m:
            cur = [m.group(1), [ln]]
            entries.append(cur)
        elif cur is None:
            header.append(ln)
        elif ln.strip():
            cur[1].append(ln)
    cutoff = (dt.date.today() - dt.timedelta(days=a.days)).isoformat()
    old = [e for e in entries if e[0] < cutoff]
    keep = [e for e in entries if e[0] >= cutoff]

    while header and not header[-1].strip():
        header.pop()
    new_text = "\n".join(header) + "\n\n" + "\n".join(l for e in keep for l in e[1]) + "\n"
    print(f"handoff: keep {len(keep)} (>= {cutoff}), archive {len(old)}, {len(new_text.encode())} bytes")
    if a.dry_run or (not old and new_text == text):
        return 0
    if old:
        arch = os.path.join(os.path.dirname(a.file), "leader-handoff-archive.md")
        with open(arch, "a", encoding="utf-8") as f:
            f.write("\n".join(l for e in old for l in e[1]) + "\n")
        print(f"  archived -> {arch}")
    tmp = a.file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new_text)
    os.replace(tmp, a.file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
