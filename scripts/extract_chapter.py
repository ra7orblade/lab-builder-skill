#!/usr/bin/env python3
"""Extract a book chapter (PDF and/or Markdown/text) into material the lab designer can mine.

Usage:
  extract_chapter.py INPUT [INPUT ...] -o OUTDIR [--first N] [--last M]
  extract_chapter.py CHAPTER.pdf OUTDIR            (legacy form, one input)

INPUT can be .pdf, .md/.markdown or .txt. Several inputs are merged; every
reference is then prefixed with the source file name, e.g. "chapter4.pdf p12" or
"notes.md §Route Filtering". Typical mixes: the book PDF plus the learner's own
Markdown notes, or a Markdown export of the chapter when the PDF is scanned.

Produces, in OUTDIR:
  chapter.txt     full text with "=== [ref] ===" markers (page or section, for citations);
                  running headers, footers and watermarks removed, layout padding squeezed
  outline.md      headings (PDF: by font size; Markdown: by # level) with references
  key-terms.md    bold/italic phrases in body text (candidate concepts)
  captions.md     Figure / Table / Example / Listing captions
  commands.md     CLI / config lines (PDF: monospace font; Markdown: code blocks and spans)
  summary.json    counts per source

PDF input needs poppler-utils (pdftotext, pdftohtml). Otherwise standard library only.
"""
import argparse
import collections
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

MONO = re.compile(r"mono|courier|consol|code|menlo|typewriter|fixed", re.I)
CAPTION = re.compile(r"^\s*(Figure|Table|Example|Listing|Exhibit)\s+\d+[-.:]\d+", re.I)
TEXT_RE = re.compile(
    r'<text top="(\d+)" left="(\d+)" width="\d+" height="\d+" font="(\d+)">(.*?)</text>')
FONT_RE = re.compile(r'<fontspec id="(\d+)" size="(\d+)" family="([^"]*)"')
PAGE_RE = re.compile(r'<page number="(\d+)"')
MD_EXT = {".md", ".markdown", ".mdown", ".txt", ".text"}


class Extract:
    """What one source contributes. refs are strings like 'p12' or '§Route Filtering'."""

    def __init__(self, name):
        self.name = name
        self.text = []                                  # (ref, text block)
        self.outline = []                               # (level, title, ref)
        self.terms = collections.OrderedDict()          # term -> [refs]
        self.captions = []                              # (ref, caption)
        self.code = []                                  # (ref, line)

    def term(self, t, ref):
        refs = self.terms.setdefault(t, [])
        if ref not in refs:
            refs.append(ref)


# --------------------------------------------------------------------------- PDF

def need(tool):
    if not shutil.which(tool):
        sys.exit(f"error: '{tool}' not found - install poppler-utils, or give the chapter as Markdown/text")


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def page_args(a):
    out = []
    if a.first:
        out += ["-f", str(a.first)]
    if a.last:
        out += ["-l", str(a.last)]
    return out


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def norm_repeat(s):
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", s.strip()))


def parse_xml(xml):
    fonts, rows, page = {}, [], 0
    for line in xml.splitlines():
        m = PAGE_RE.search(line)
        if m:
            page = int(m.group(1))
        for fm in FONT_RE.finditer(line):
            fonts[fm.group(1)] = (int(fm.group(2)), fm.group(3))
        tm = TEXT_RE.search(line)
        if tm:
            rows.append((page, int(tm.group(1)), int(tm.group(2)), tm.group(3), tm.group(4)))
    return fonts, rows


def merge_lines(rows, fonts):
    """Merge text fragments on the same page+baseline into lines."""
    lines = collections.OrderedDict()
    for page, top, left, fid, inner in rows:
        lines.setdefault((page, top), []).append((left, fid, inner))
    merged = []
    for (page, top), frags in lines.items():
        frags.sort()
        text = " ".join(strip_tags(f[2]).strip() for f in frags).strip()
        if not text:
            continue
        fid = max(frags, key=lambda f: len(strip_tags(f[2])))[1]
        size, family = fonts.get(fid, (0, ""))
        bold = all("<b>" in f[2] for f in frags if strip_tags(f[2]).strip())
        merged.append({"page": page, "top": top, "text": text, "size": size,
                       "family": family, "bold": bold, "frags": frags})
    return merged


def repeated_edge_lines(pages):
    """Lines in the top/bottom 3 lines of many pages: running headers, footers, watermarks."""
    seen = collections.defaultdict(set)
    for i, p in enumerate(pages):
        lines = [l for l in p.splitlines() if l.strip()]
        for l in lines[:3] + lines[-3:]:
            seen[norm_repeat(l)].add(i)
    n = len([p for p in pages if p.strip()])
    if n < 4:
        return set()
    return {k for k, v in seen.items() if len(v) > max(3, n * 0.3) and len(k) < 140}


def extract_pdf(path, a):
    need("pdftotext")
    need("pdftohtml")
    ex = Extract(path.name)
    first = a.first or 1
    raw = run(["pdftotext", "-layout", *page_args(a), str(path), "-"])
    pages = raw.split("\f")
    junk = repeated_edge_lines(pages)
    for i, p in enumerate(pages):
        if not p.strip():
            continue
        kept = [l.rstrip() for l in p.splitlines() if norm_repeat(l) not in junk]
        if not a.layout:  # squeeze layout padding: same content, far fewer tokens
            kept = [re.sub(r"^ {2,}", "  ", re.sub(r"(?<=\S) {3,}", "  ", l)) for l in kept]
        block = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip("\n")
        ex.text.append((f"p{first + i}", block))
    if sum(len(p.strip()) for p in pages) < 200:
        print(f"warning: {path.name}: almost no text - probably scanned; OCR it first", file=sys.stderr)

    xml = run(["pdftohtml", "-xml", "-i", "-stdout", "-q", *page_args(a), str(path)])
    fonts, rows = parse_xml(xml)
    lines = merge_lines(rows, fonts)
    n_pages = len({ln["page"] for ln in lines}) or 1
    seen_on = collections.defaultdict(set)
    for ln in lines:
        seen_on[norm_repeat(ln["text"])].add(ln["page"])
    lines = [ln for ln in lines if MONO.search(ln["family"]) or not (
        n_pages >= 4 and len(seen_on[norm_repeat(ln["text"])]) > max(3, n_pages * 0.3))]
    weight = collections.Counter()
    for ln in lines:
        if not MONO.search(ln["family"]):
            weight[ln["size"]] += len(ln["text"])
    body = weight.most_common(1)[0][0] if weight else 12
    heading_sizes = sorted({ln["size"] for ln in lines
                            if ln["size"] >= body * 1.15 and len(ln["text"]) < 140}, reverse=True)
    level = {s: min(i + 1, 4) for i, s in enumerate(heading_sizes)}
    for ln in lines:
        t, ref = ln["text"], f'p{ln["page"]}'
        if ln["size"] in level and not re.fullmatch(r"[\d\s.]+", t):
            ex.outline.append((level[ln["size"]], t, ref))
        elif ln["bold"] and ln["size"] >= body and len(t) < 90 and not CAPTION.match(t):
            ex.outline.append((5, t, ref))  # bold run-in heading
        if CAPTION.match(t):
            ex.captions.append((ref, t))
        if MONO.search(ln["family"]):
            ex.code.append((ref, t))
        if abs(ln["size"] - body) <= 1 and not ln["bold"]:
            for _, fid, inner in ln["frags"]:
                for m in re.finditer(r"<([bi])>(.*?)</\1>", inner):
                    term = strip_tags(m.group(2)).strip(" .,:;")
                    if 3 <= len(term) <= 60:
                        ex.term(term, ref)
    return ex


# --------------------------------------------------------------------------- Markdown / text

def extract_md(path):
    ex = Extract(path.name)
    lines = path.read_text(errors="replace").splitlines()
    ref, buf, in_code, fence = "§(start)", [], False, ""

    def flush():
        if any(l.strip() for l in buf):
            ex.text.append((ref, "\n".join(buf).strip("\n")))
        buf.clear()

    for n, ln in enumerate(lines, 1):
        s = ln.strip()
        if in_code:
            if s.startswith(fence):
                in_code = False
            elif s:
                ex.code.append((ref, s))
            buf.append(ln)
            continue
        m = re.match(r"^(```+|~~~+)", s)
        if m:
            in_code, fence = True, m.group(1)[:3]
            buf.append(ln)
            continue
        h = re.match(r"^(#{1,6})\s+(.+?)\s*#*$", s)
        if h:
            flush()
            title = re.sub(r"[*_`]", "", h.group(2)).strip()
            ref = f"§{title[:60]}"
            ex.outline.append((len(h.group(1)), title, f"L{n}"))
            buf.append(ln)
            continue
        # setext headings (Title\n=====)
        if re.fullmatch(r"=+|-{3,}", s) and buf and buf[-1].strip() and not buf[-1].lstrip().startswith(("-", "*")):
            title = buf[-1].strip()
            if len(title) < 120:
                ex.outline.append((1 if s[0] == "=" else 2, title, f"L{n - 1}"))
        if ln.startswith(("    ", "\t")) and s and not re.match(r"^([-*+]|\d+[.)])\s", s):
            ex.code.append((ref, s))  # indented code block
        cap = re.sub(r"\*\*|__|(?<!\w)[*_]|[*_](?!\w)", "", s).lstrip("> ").strip()
        if CAPTION.match(cap):
            ex.captions.append((ref, cap))
        for img in re.finditer(r"!\[([^\]]+)\]", s):
            if CAPTION.match(img.group(1)):
                ex.captions.append((ref, img.group(1)))
        body = re.sub(r"`[^`]*`", "", s)
        for m in re.finditer(r"(\*\*|__)(.+?)\1|(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", body):
            term = (m.group(2) or m.group(3) or "").strip(" .,:;")
            if 3 <= len(term) <= 60:
                ex.term(term, ref)
        for m in re.finditer(r"`([^`]{4,})`", s):
            ex.code.append((ref, m.group(1).strip()))
        buf.append(ln)
    flush()
    return ex


# --------------------------------------------------------------------------- output

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help=".pdf, .md, .markdown or .txt files")
    ap.add_argument("-o", "--outdir")
    ap.add_argument("--first", type=int, help="PDF: first page to extract")
    ap.add_argument("--last", type=int, help="PDF: last page to extract")
    ap.add_argument("--layout", action="store_true", help="keep the PDF's full layout spacing (more tokens)")
    a = ap.parse_args()
    inputs = [Path(p) for p in a.inputs]
    if not a.outdir:
        # legacy form: extract_chapter.py CHAPTER.pdf OUTDIR
        if len(inputs) == 2 and not inputs[1].suffix.lower() in MD_EXT | {".pdf"}:
            a.outdir = str(inputs.pop())
        else:
            ap.error("give the output folder with -o OUTDIR")
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    extracts = []
    for p in inputs:
        if not p.exists():
            sys.exit(f"error: {p} not found")
        suf = p.suffix.lower()
        if suf == ".pdf":
            extracts.append(extract_pdf(p, a))
        elif suf in MD_EXT:
            extracts.append(extract_md(p))
        else:
            sys.exit(f"error: unsupported input type {p.suffix} (use .pdf, .md or .txt)")

    multi = len(extracts) > 1

    def R(ex, ref):
        return f"{ex.name} {ref}" if multi else ref

    text, outline, terms, caps, code, summary = [], [], [], [], [], {}
    for ex in extracts:
        if multi:
            text.append(f"\n##### SOURCE: {ex.name} #####\n")
            outline.append(f"\n## {ex.name}\n")
            caps.append(f"\n## {ex.name}\n")
        text += [f"=== [{R(ex, ref)}] ===\n{block}\n" for ref, block in ex.text]
        base = min((lvl for lvl, _, _ in ex.outline), default=1)
        outline += [f'{"  " * (lvl - base)}- {t}  _({R(ex, ref)})_' for lvl, t, ref in ex.outline]
        terms += [f"- {t} _({', '.join(R(ex, r) for r in refs)})_" for t, refs in ex.terms.items()]
        caps += [f"- {R(ex, ref)}: {c}" for ref, c in ex.captions]
        last = None
        for ref, line in ex.code:
            if ref != last:
                code.append(f"\n## {R(ex, ref)}\n")
                last = ref
            code.append(f"    {line}")
        summary[ex.name] = {"blocks": len(ex.text), "headings": len(ex.outline), "key_terms": len(ex.terms),
                            "captions": len(ex.captions), "command_lines": len(ex.code)}
        if not ex.code:
            print(f"note: {ex.name}: no CLI/config lines found - commands may be in images or plain text; "
                  "read chapter.txt", file=sys.stderr)

    (out / "chapter.txt").write_text("\n".join(text))
    (out / "outline.md").write_text("# Detected outline\n\n" + "\n".join(outline) + "\n")
    (out / "key-terms.md").write_text("# Emphasised terms in body text (concept candidates)\n\n"
                                      + "\n".join(terms) + "\n")
    (out / "captions.md").write_text("# Figure / table / example captions\n\n" + "\n".join(caps) + "\n")
    (out / "commands.md").write_text("# CLI / config lines\n" + "\n".join(code) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
