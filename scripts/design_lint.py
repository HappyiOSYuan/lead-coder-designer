#!/usr/bin/env python3
"""
Design mockup lint (read-only): checks a designer agent's mockup folder before review.
Expects <dir>/index.html (artboards) and <dir>/handoff.md.

Usage:
  python3 -I design_lint.py <mockup dir> [options]

Options:
  --base DIR          original mockup folder: compare in-frame text (lost / added lines)
  --source PATH       old source dir/file (repeatable): every user-facing string literal
                      matching --text-re must appear in index.html or handoff.md
  --source-ext LIST   extensions scanned under --source dirs (default .m,.swift,.kt,.java,.ts,.tsx,.js,.jsx,.vue,.dart,.py,.html)
  --text-re RE        which literals count as UI copy (default: contains CJK; use '[A-Za-z]{3,}' for English UIs)
  --font RE           expected font-family (default -apple-system|SF Pro|system-ui)
                      every Chinese @"..." literal must appear in index.html or handoff.md
  --frame-class RE    regex for a class token that marks a phone artboard
                      (default: phone|iphone-frame|device|screen)
  --ignore-class RE   class tokens whose text is a design annotation, not UI content
                      (default: reuse|note|.+-note|annot.*|caption|.+-caption|board-label|stress-.+)
  --min LEVEL         error | warn | info (default warn)
  --limit N           max findings printed per rule (default 8)

Checks
  index.html (whole page):
    E img-missing      <img src> / url() pointing to a file that does not exist
    E img-outside      local image outside icons/ (hand-made assets)
    E external-res     http(s) image/script/font (offline mockup, not allowed)
    E dark-mode        prefers-color-scheme: dark / [data-theme=dark] / dark tokens
    E ease-in          CSS ease-in (not ease-in-out) in transition/animation
    W svg-inline       inline <svg> inside an artboard (hand-drawn icon?)
    W font-family      stylesheet lacks the --font family
  inside artboards:
    E emoji            emoji characters in UI text
    W font-small       font-size < 11px (below Dynamic Type caption2)
    W contrast         rule with color + background below 4.5:1
    W uppercase-label  text-transform: uppercase
    W dot-join         "A · B · C" middle-dot joined labels
    W arrow-tail       text ending with →
    W seq-number       standalone 01 / 02 / 03 numbering
    W gradient         linear/radial-gradient
    W left-bar         border-left >= 3px colored bar
    W long-transition  CSS transition/animation > 300ms (non-infinite)
  handoff.md:
    E md-ease-in       .easeIn( used
    E md-scale-zero    scaleEffect(0) / scale(0)
    E md-reduce-motion no Reduce Motion / accessibilityReduceMotion section
    W md-long-anim     duration > 0.3 s without repeatForever
  --source:
    E text-missing     source string literal (split at format specifiers / \\n) not found in page text or handoff
  --base:
    E text-lost        in-frame text of the base mockup missing in the new one
    I text-added       in-frame text new in this mockup (review: sample data or real addition?)
Exit code: 1 if any error, else 0.
"""
import argparse
import html
import os
import re
import sys
from html.parser import HTMLParser

LEVELS = {"error": 0, "warn": 1, "info": 2}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr"}
# ✓✔✕✖ (U+2713–2716) stand in for SF Symbols checkmark/xmark and are allowed
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U00002712\U00002717-\U000027BF\U0001F000-\U0001F2FF]")


class Page(HTMLParser):
    """Collects visible text (tagged in/out of an artboard), styles, images, svgs."""

    def __init__(self, frame_re, ignore_re):
        super().__init__(convert_charrefs=True)
        self.frame_re = frame_re
        self.ignore_re = ignore_re
        self.stack = []          # (tag, is_frame, is_ignore)
        self.frame_depth = 0
        self.ignore_depth = 0
        self.skip = 0            # inside <script>/<style>
        self.in_style = False
        self.styles = []         # css text
        self.inline_styles = []  # (in_frame, css, line)
        self.texts = []          # (in_frame, text, line)
        self.imgs = []           # (src, line)
        self.svgs = []           # (in_frame, line)
        self.links = []          # (url, line)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        classes = (a.get("class") or "").split()
        is_frame = any(self.frame_re.fullmatch(c) for c in classes)
        is_ignore = any(self.ignore_re.fullmatch(c) for c in classes)
        if tag in ("script", "style"):
            self.skip += 1
            self.in_style = tag == "style"
            if tag == "script" and a.get("src"):
                self.links.append((a["src"], line))
        if tag == "img" and a.get("src"):
            self.imgs.append((a["src"], line))
        if tag == "link" and a.get("href"):
            self.links.append((a["href"], line))
        if tag == "svg":
            self.svgs.append((self.frame_depth > 0 or is_frame, line))
        if a.get("style"):
            self.inline_styles.append((self.frame_depth > 0 or is_frame, a["style"], line))
        if tag in VOID:
            return
        self.stack.append((tag, is_frame, is_ignore))
        if is_frame:
            self.frame_depth += 1
        if is_ignore:
            self.ignore_depth += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
            self.in_style = False
        if tag in VOID:
            return
        # pop to the matching tag (tolerates sloppy HTML)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for _, fr, ig in self.stack[i:]:
                    if fr:
                        self.frame_depth -= 1
                    if ig:
                        self.ignore_depth -= 1
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.skip:
            if self.in_style:
                self.styles.append(data)
            return
        t = " ".join(data.split())
        if t:
            self.texts.append((self.frame_depth > 0 and not self.ignore_depth, t, self.getpos()[0]))


def lum(hexc):
    hexc = hexc.lstrip("#")
    if len(hexc) == 3:
        hexc = "".join(c * 2 for c in hexc)
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def css_rules(css):
    """Yield (selector, body) for flat rules; @media bodies are recursed."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    i = 0
    while i < len(css):
        j = css.find("{", i)
        if j < 0:
            return
        sel = css[i:j].strip()
        depth, k = 1, j + 1
        while k < len(css) and depth:
            depth += {"{": 1, "}": -1}.get(css[k], 0)
            k += 1
        body = css[j + 1:k - 1]
        if sel.startswith("@"):
            yield sel, None
            yield from ((s, b) for s, b in css_rules(body))
        else:
            yield sel, body
        i = k


def ms(v):
    m = re.fullmatch(r"([\d.]+)(ms|s)", v)
    if not m:
        return None
    return float(m.group(1)) * (1000 if m.group(2) == "s" else 1)


def frame_texts(path, frame_re, ignore_re):
    p = Page(frame_re, ignore_re)
    p.feed(open(path, encoding="utf-8").read())
    return p


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("dir")
    ap.add_argument("--base")
    ap.add_argument("--source", action="append", default=[])
    ap.add_argument("--source-ext", default=".m,.swift,.kt,.java,.ts,.tsx,.js,.jsx,.vue,.dart,.py,.html")
    ap.add_argument("--text-re", default=r"[\u4e00-\u9fff]")
    ap.add_argument("--font", default=r"-apple-system|SF Pro|system-ui")
    ap.add_argument("--frame-class", default=r"phone|iphone-frame|device|screen")
    ap.add_argument("--ignore-class", default=r"reuse|note|.+-note|annot.*|caption|.+-caption|board-label|stress-.+")
    ap.add_argument("--min", default="warn", choices=LEVELS)
    ap.add_argument("--limit", type=int, default=8)
    args = ap.parse_args()

    d = args.dir.rstrip("/")
    page_path = os.path.join(d, "index.html")
    if not os.path.isfile(page_path):
        sys.exit(f"no index.html in {d}")
    frame_re = re.compile(args.frame_class)
    ignore_re = re.compile(args.ignore_class)
    src = open(page_path, encoding="utf-8").read()
    p = frame_texts(page_path, frame_re, ignore_re)
    findings = []  # (level, rule, line, msg)

    def add(level, rule, line, msg):
        findings.append((level, rule, line, msg))

    if not any(fr for fr, _, _ in p.texts):
        add("warn", "no-frames", 0, f"no artboard matched --frame-class '{args.frame_class}'; in-frame checks skipped")

    # images / external resources
    urls = [(s, ln) for s, ln in p.imgs]
    for m in re.finditer(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", src):
        urls.append((m.group(1), src.count("\n", 0, m.start()) + 1))
    for u, ln in urls + p.links:
        if u.startswith("data:") or u.startswith("#"):
            continue
        if re.match(r"https?://", u):
            add("error", "external-res", ln, u[:80])
            continue
        if (u, ln) in p.links:
            continue
        local = html.unescape(u.split("?")[0].split("#")[0])
        if not os.path.exists(os.path.join(d, local)):
            add("error", "img-missing", ln, u)
        elif not os.path.normpath(local).startswith("icons" + os.sep):
            add("error", "img-outside", ln, u)

    # dark mode
    for m in re.finditer(r"prefers-color-scheme\s*:\s*dark|data-theme\s*=\s*['\"]?dark", src):
        add("error", "dark-mode", src.count("\n", 0, m.start()) + 1, m.group(0))

    # visible text checks
    for in_frame, t, ln in p.texts:
        if not in_frame:
            continue
        if EMOJI_RE.search(t):
            add("error", "emoji", ln, t[:60])
        if re.search(r"\S\s*·\s*\S+\s*·\s*\S", t):
            add("warn", "dot-join", ln, t[:60])
        if t.rstrip().endswith("→"):
            add("warn", "arrow-tail", ln, t[:60])
        if re.fullmatch(r"0\d[.、·]?", t):
            add("warn", "seq-number", ln, t)

    for in_frame, ln in p.svgs:
        if in_frame:
            add("warn", "svg-inline", ln, "inline <svg> inside an artboard")

    # css checks: stylesheet rules (selector-level, can't know frame scope -> treat all)
    css_all = "\n".join(p.styles)
    if not re.search(args.font, css_all):
        add("warn", "font-family", 0, f"no font matching {args.font} in stylesheet")

    def css_body_checks(body, ln, where):
        for m in re.finditer(r"font-size\s*:\s*([\d.]+)px", body):
            if float(m.group(1)) < 11:
                add("warn", "font-small", ln, f"{where}: font-size {m.group(1)}px")
        if re.search(r"text-transform\s*:\s*uppercase", body):
            add("warn", "uppercase-label", ln, f"{where}: text-transform uppercase")
        if re.search(r"(linear|radial)-gradient", body):
            add("warn", "gradient", ln, f"{where}: gradient")
        m = re.search(r"border-left\s*:\s*([\d.]+)px\s+solid\s+(#[0-9a-fA-F]{3,6}|rgba?\([^)]*\)|var\([^)]*\))", body)
        if m and float(m.group(1)) >= 3:
            add("warn", "left-bar", ln, f"{where}: border-left {m.group(1)}px")
        for m in re.finditer(r"(transition|animation)\s*:\s*([^;]+)", body):
            val = m.group(2)
            if re.search(r"\bease-in\b(?!-out)", val):
                add("error", "ease-in", ln, f"{where}: {val.strip()[:60]}")
            if "infinite" in val:
                continue
            for tok in re.findall(r"[\d.]+m?s\b", val):
                v = ms(tok)
                if v and v > 300:
                    add("warn", "long-transition", ln, f"{where}: {val.strip()[:60]}")
                    break
        fg = re.search(r"(?<![-\w])color\s*:\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\b", body)
        bg = re.search(r"background(?:-color)?\s*:\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\b", body)
        if fg and bg:
            c = contrast(fg.group(1), bg.group(1))
            if c < 4.5:
                add("warn", "contrast", ln, f"{where}: {fg.group(1)} on {bg.group(1)} = {c:.2f}:1")

    style_start = src.find("<style")
    base_line = src.count("\n", 0, style_start) + 1 if style_start >= 0 else 0
    for css in p.styles:
        for sel, body in css_rules(css):
            if body is None:
                continue
            off = css.find(sel)
            ln = base_line + css.count("\n", 0, max(off, 0))
            css_body_checks(body, ln, sel[:40])
    for in_frame, css, ln in p.inline_styles:
        if in_frame:
            css_body_checks(css, ln, "style=")

    # handoff.md
    hp = os.path.join(d, "handoff.md")
    if os.path.isfile(hp):
        lines = open(hp, encoding="utf-8").read().splitlines()
        whole = "\n".join(lines)
        if not re.search(r"accessibilityReduceMotion|Reduce Motion|减弱动态效果", whole):
            add("error", "md-reduce-motion", 0, "handoff.md has no Reduce Motion handling")
        for i, l in enumerate(lines, 1):
            if re.search(r"\.easeIn\(|\.easeIn\b(?!Out)", l) and not re.search(r"不用|禁用|严禁|杜绝|禁止|不使用|no ", l):
                add("error", "md-ease-in", i, l.strip()[:70])
            if re.search(r"scaleEffect\(\s*0(\.0)?\s*\)|scale\(\s*0\s*\)", l) and not re.search(r"不要|禁止|严禁|杜绝|不从|绝不|避免", l):
                add("error", "md-scale-zero", i, l.strip()[:70])
            if "repeatForever" in l:
                continue
            for m in re.finditer(r"duration:\s*([\d.]+)", l):
                if float(m.group(1)) > 0.3:
                    add("warn", "md-long-anim", i, l.strip()[:70])
    else:
        add("warn", "md-missing", 0, "no handoff.md")

    # source literal parity
    if args.source:
        import glob
        files = []
        exts = tuple(e.strip() for e in args.source_ext.split(",") if e.strip())
        text_re = re.compile(args.text_re)
        for o in args.source:
            files += [o] if os.path.isfile(o) else [f for f in glob.glob(os.path.join(o, "**", "*"), recursive=True) if f.endswith(exts)]
        page_txt = re.sub(r"\s+", "", "".join(t for _, t, _ in p.texts))
        md_txt = re.sub(r"\s+", "", open(hp, encoding="utf-8").read()) if os.path.isfile(hp) else ""
        seen = set()
        for f in files:
            for lit in re.findall(r'@?"((?:[^"\\]|\\.)*)"', open(f, encoding="utf-8", errors="ignore").read()):
                if not text_re.search(lit) or lit in seen:
                    continue
                seen.add(lit)
                parts = [x for x in re.split(r"%[-+ #0-9.]*[@dlufsxi]+|\\n|\$\{[^}]*\}|\{[^}]*\}|\s+", lit) if text_re.search(x)]
                if not all(x in page_txt or x in md_txt for x in parts):
                    add("error", "text-missing", 0, f"{os.path.basename(f)}: {lit[:60]}")

    # base comparison
    if args.base:
        bp = os.path.join(args.base.rstrip("/"), "index.html")
        b = frame_texts(bp, frame_re, ignore_re)
        old = {t for fr, t, _ in b.texts if fr}
        new = {t for fr, t, _ in p.texts if fr}
        norm = lambda s: re.sub(r"\s+", "", s)  # noqa: E731
        new_n = {norm(t) for t in new}
        old_n = {norm(t) for t in old}
        new_join = norm("".join(t for fr, t, _ in p.texts if fr))  # text split across spans
        for t in sorted(old):
            if norm(t) not in new_n and norm(t) not in new_join:
                add("error", "text-lost", 0, t[:70])
        for t in sorted(new):
            if norm(t) not in old_n:
                add("info", "text-added", 0, t[:70])

    # report
    minlvl = LEVELS[args.min]
    shown = [f for f in findings if LEVELS[f[0]] <= minlvl]
    counts = {k: sum(1 for f in findings if f[0] == k) for k in LEVELS}
    print(f"design lint: {d}  error {counts['error']} · warn {counts['warn']} · info {counts['info']}")
    by_rule = {}
    for f in shown:
        by_rule.setdefault((f[0], f[1]), []).append(f)
    for (lvl, rule), items in sorted(by_rule.items(), key=lambda kv: (LEVELS[kv[0][0]], kv[0][1])):
        print(f"\n[{lvl.upper()}] {rule} ({len(items)})")
        for _, _, ln, msg in items[:args.limit]:
            print(f"  {('L' + str(ln)) if ln else '  -'}  {msg}")
        if len(items) > args.limit:
            print(f"  … +{len(items) - args.limit}")
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
