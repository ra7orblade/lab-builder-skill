#!/usr/bin/env python3
"""Render a lab Markdown file to a print-ready PDF (and optionally keep the HTML).

  md2pdf.py lab-guide.md [-o lab-guide.pdf] [--css ../assets/print.css] [--keep-html]
            [--title "..."] [--footer "..."] [--preview contact-sheet.png]

<!-- @... --> markers (see labkit.py expand) are expanded in memory before rendering when the file
lives in a lab folder. --preview writes ONE small PNG with every page side by side, so a visual
check costs a single image read.

Markdown -> HTML uses python-markdown when installed, otherwise the built-in converter
below (covers what the templates use: headings, paragraphs, emphasis, code, fenced code,
tables, nested lists, task lists, blockquotes, images, links, hr, raw HTML blocks).
HTML -> PDF uses, in order: WeasyPrint (python module), then a Chromium-family browser
in headless mode (chromium, google-chrome, msedge, brave; or $CHROME_PATH).

Blockquotes that start with a bold label (e.g. "> **Predict:** ...") get a CSS class
`callout callout-predict` so they render as coloured boxes.
"""
import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CSS = HERE.parent / "assets" / "print.css"

# --------------------------------------------------------------------------- mini markdown

BLOCK_TAGS = r"(div|table|details|summary|figure|section|aside|p|pre|ul|ol|dl|hr|img|svg|br|center|!--)"


def slug(text, seen):
    s = re.sub(r"<[^>]+>", "", text)
    s = re.sub(r"[^\w\- ]", "", s).strip().lower().replace(" ", "-")
    base, k = s or "section", 1
    while s in seen:
        k += 1
        s = f"{base}-{k}"
    seen.add(s)
    return s


def inline(t):
    codes = []

    def keep_code(m):
        codes.append("<code>" + html.escape(m.group(2)) + "</code>")
        return f"\x00{len(codes) - 1}\x00"

    t = re.sub(r"(`+)(.+?)\1", keep_code, t)
    # escape bare & and < that are not part of tags/entities
    t = re.sub(r"&(?!#?\w+;)", "&amp;", t)
    # only well-known inline tags pass through; "<area-id>" style placeholders are escaped
    t = re.sub(r"<(?!/?(?:br|span|sub|sup|kbd|em|strong|b|i|u|code|a|img|small|mark|abbr|div)\b|!--)", "&lt;", t)
    t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)",
               lambda m: f'<img src="{m.group(2)}" alt="{m.group(1)}"' +
               (f' title="{m.group(3)}"' if m.group(3) else "") + ">", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"__(.+?)__", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
    t = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"<em>\1</em>", t)
    t = re.sub(r"~~(.+?)~~", r"<del>\1</del>", t)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], t)


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells, cur, in_code = [], "", False
    for ch in line:
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code and not cur.endswith("\\"):
            cells.append(cur)
            cur = ""
        else:
            cur += ch
    cells.append(cur)
    return [c.strip().replace("\\|", "|") for c in cells]


LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")


def convert(md, seen=None):
    seen = set() if seen is None else seen
    lines = md.replace("\t", "    ").splitlines()
    out, i, para = [], 0, []

    def flush():
        if para:
            # a line ending in two spaces is a hard line break
            text = "".join(p[:-2].rstrip() + "<br>" if p.endswith("  ") else p + " " for p in para)
            out.append("<p>" + inline(text.strip()) + "</p>")
            para.clear()

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            flush(); i += 1; continue
        m = re.match(r"^(\s*)(```+|~~~+)\s*([\w+-]*)", ln)
        if m:
            flush()
            fence, lang, buf = m.group(2), m.group(3), []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence):
                buf.append(lines[i][len(m.group(1)):] if lines[i].startswith(m.group(1)) else lines[i])
                i += 1
            i += 1
            cls = f' class="language-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>" + html.escape("\n".join(buf)) + "</code></pre>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", s)
        if m:
            flush()
            lvl, txt = len(m.group(1)), m.group(2)
            idm = re.search(r"\s*\{#([\w\-.]+)\}$", txt)
            hid = idm.group(1) if idm else slug(txt, seen)
            txt = txt[:idm.start()] if idm else txt
            out.append(f'<h{lvl} id="{hid}">{inline(txt)}</h{lvl}>')
            i += 1; continue
        if re.match(r"^(\*\s*){3,}$|^(-\s*){3,}$|^(_\s*){3,}$", s):
            flush(); out.append("<hr>"); i += 1; continue
        if re.fullmatch(r"<!--.*?-->", s):
            flush(); out.append(s); i += 1; continue
        if re.match(rf"^<{BLOCK_TAGS}[\s>/]", s, re.I) or s.startswith("<!--"):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip():
                buf.append(lines[i]); i += 1
            out.append("\n".join(buf))
            continue
        if s.startswith(">"):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i])); i += 1
            out.append("<blockquote>\n" + convert("\n".join(buf), seen) + "\n</blockquote>")
            continue
        if "|" in s and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$",
                                                        lines[i + 1]):
            flush()
            heads = split_row(s)
            aligns = []
            for c in split_row(lines[i + 1]):
                aligns.append("center" if c.startswith(":") and c.endswith(":")
                              else "right" if c.endswith(":") else "")
            i += 2
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(split_row(lines[i])); i += 1

            def cell(tag, txt, k):
                al = aligns[k] if k < len(aligns) and aligns[k] else ""
                st = f' style="text-align:{al}"' if al else ""
                return f"<{tag}{st}>{inline(txt)}</{tag}>"

            t = ["<table>", "<thead><tr>" + "".join(cell("th", h, k) for k, h in enumerate(heads)) + "</tr></thead>",
                 "<tbody>"]
            for r in rows:
                r = r + [""] * (len(heads) - len(r))
                t.append("<tr>" + "".join(cell("td", c, k) for k, c in enumerate(r[:len(heads)])) + "</tr>")
            out.append("\n".join(t + ["</tbody></table>"]))
            continue
        if LIST_RE.match(ln):
            flush()
            i = parse_list(lines, i, out, seen)
            continue
        para.append(s if not ln.endswith("  ") else s + "  ")
        i += 1
    flush()
    return "\n".join(out)


def parse_list(lines, i, out, seen):
    m = LIST_RE.match(lines[i])
    base = len(m.group(1))
    ordered = m.group(2)[0].isdigit()
    start = int(re.match(r"\d+", m.group(2)).group()) if ordered else 1
    tag = "ol" if ordered else "ul"
    out.append(f'<{tag}{"" if start == 1 else f" start={start}"}>')
    while i < len(lines):
        m = LIST_RE.match(lines[i])
        if not m or len(m.group(1)) != base or m.group(2)[0].isdigit() != ordered:
            break
        body = [m.group(3)]
        i += 1
        # continuation lines and nested blocks: indented deeper than the marker
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip():
                if i + 1 < len(lines) and (len(lines[i + 1]) - len(lines[i + 1].lstrip())) > base and \
                        lines[i + 1].strip():
                    body.append(""); i += 1; continue
                break
            ind = len(nxt) - len(nxt.lstrip())
            if ind <= base and (LIST_RE.match(nxt) or ind < base or not body):
                break
            if ind <= base and not LIST_RE.match(nxt):
                body.append(nxt.strip()); i += 1; continue  # lazy continuation
            body.append(nxt[min(ind, base + 2):] if ind >= base + 2 else nxt.strip())
            i += 1
        # plain continuation lines directly after the bullet belong to the bullet's own text
        k = 1
        while k < len(body) and body[k].strip() and not LIST_RE.match(body[k]) and \
                not body[k].lstrip().startswith(("```", "~~~", ">", "|", "<")):
            k += 1
        first, rest = " ".join(b.strip() for b in body[:k]), "\n".join(body[k:])
        task = re.match(r"^\[([ xX])\]\s+(.*)", first)
        cls = ""
        if task:
            box = "&#9745;" if task.group(1) in "xX" else "&#9744;"
            first, cls = f'<span class="box">{box}</span> ' + task.group(2), ' class="task"'
        inner = inline(first)
        if rest.strip():
            sub = convert(rest, seen)
            # keep a simple paragraph inline with the bullet text
            inner += "\n" + sub
        out.append(f"<li{cls}>{inner}</li>")
        while i < len(lines) and not lines[i].strip():
            if i + 1 < len(lines) and LIST_RE.match(lines[i + 1]) and \
                    len(LIST_RE.match(lines[i + 1]).group(1)) == base:
                i += 1
            else:
                break
    out.append(f"</{tag}>")
    return i


def md_to_html(md):
    try:
        import markdown  # type: ignore
        return markdown.markdown(md, extensions=["tables", "fenced_code", "toc", "attr_list", "md_in_html",
                                                 "sane_lists"])
    except ImportError:
        return convert(md)


CALLOUTS = {
    "predict": "predict", "task": "task", "checkpoint": "checkpoint", "verify": "checkpoint",
    "question": "question", "questions": "question", "explain": "question", "reflect": "question",
    "break it": "break", "experiment": "break", "note": "note", "tip": "note", "warning": "warning",
    "caution": "warning", "beyond the book": "beyond", "going further": "beyond", "hint": "hint",
    "concept": "concept", "why it matters": "concept", "ticket": "ticket", "symptom": "ticket",
    "success criteria": "checkpoint", "you are done when": "checkpoint", "answer": "answer",
}


def add_callout_classes(h):
    def repl(m):
        label = re.sub(r"[^a-z ]", "", m.group(2).lower()).strip()
        for key, cls in CALLOUTS.items():
            if label.startswith(key):
                return f'<blockquote class="callout callout-{cls}">{m.group(1)}<strong>{m.group(2)}</strong>'
        return m.group(0)
    return re.sub(r"<blockquote>(\s*<p>)<strong>([^<]{1,40})</strong>", repl, h)


# --------------------------------------------------------------------------- pdf


def find_browser():
    cands = [os.environ.get("CHROME_PATH", ""), "chromium", "chromium-browser", "google-chrome",
             "google-chrome-stable", "microsoft-edge", "msedge", "brave", "brave-browser",
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    for c in cands:
        if c and (shutil.which(c) or Path(c).exists()):
            return shutil.which(c) or c
    return None


def to_pdf(html_path, pdf_path):
    try:
        from weasyprint import HTML  # type: ignore
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        return "weasyprint"
    except ImportError:
        pass
    br = find_browser()
    if not br:
        sys.exit("error: no PDF engine - install WeasyPrint or a Chromium-based browser (or set CHROME_PATH)")
    with tempfile.TemporaryDirectory() as prof:
        cmd = [br, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               f"--user-data-dir={prof}", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
               "--virtual-time-budget=5000", f"--print-to-pdf={pdf_path}", html_path.as_uri()]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode != 0 or not Path(pdf_path).exists():
            # some sandboxes (containers, root) need --no-sandbox
            r = subprocess.run(cmd[:1] + ["--no-sandbox"] + cmd[1:], capture_output=True, text=True, timeout=180)
        if not Path(pdf_path).exists():
            sys.exit(f"error: browser failed to print:\n{r.stderr[-2000:]}")
    return Path(br).name


def expand_markers(md, src):
    """Use labkit.expand_text when the file sits in a lab folder (loaded by path: works under python -I)."""
    if "<!-- @" not in md:
        return md
    try:
        import importlib.util
        sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
        spec = importlib.util.spec_from_file_location("labkit", HERE / "labkit.py")
        lk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lk)
        for d in [src.parent] + list(src.parents):
            if (d / "topology" / "topology.yaml").exists() or (d / "topology" / "topology.json").exists():
                return lk.expand_text(md, d)
    except Exception as e:  # rendering must not fail because of an include
        print(f"warning: markers not expanded ({e})", file=sys.stderr)
    return md


def contact_sheet(pdf, png, cols=4, width=1600):
    """All pages as one PNG grid (needs pdftoppm; Pillow for the grid, else first page only)."""
    if not shutil.which("pdftoppm"):
        print("preview skipped: pdftoppm not found", file=sys.stderr)
        return
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", "36", "-png", str(pdf), f"{td}/p"], check=True)
        pages = sorted(Path(td).glob("p-*.png"))
        try:
            from PIL import Image
        except ImportError:
            shutil.copy(pages[0], png)
            print("preview: Pillow missing - wrote first page only", file=sys.stderr)
            return
        ims = [Image.open(p) for p in pages]
        w, h = ims[0].size
        rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (w * cols, h * rows), "white")
        for k, im in enumerate(ims):
            sheet.paste(im, ((k % cols) * w, (k // cols) * h))
        if sheet.width > width:
            sheet = sheet.resize((width, int(sheet.height * width / sheet.width)))
        sheet.save(png)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("markdown")
    ap.add_argument("-o", "--out")
    ap.add_argument("--css", default=str(DEFAULT_CSS))
    ap.add_argument("--title")
    ap.add_argument("--footer", default="", help="text for the page footer (left side)")
    ap.add_argument("--keep-html", action="store_true")
    ap.add_argument("--preview", help="also write a contact-sheet PNG of all pages")
    a = ap.parse_args()
    src = Path(a.markdown).resolve()
    out = Path(a.out).resolve() if a.out else src.with_suffix(".pdf")
    md = expand_markers(src.read_text(), src)
    title = a.title or (re.search(r"^#\s+(.+)$", md, re.M) or [None, src.stem])[1]
    css = Path(a.css).read_text() if Path(a.css).exists() else ""
    footer = html.escape(a.footer or title).replace('"', "'")
    css += f'\n@page {{ @bottom-left {{ content: "{footer}"; }} }}\n'
    body = add_callout_classes(md_to_html(md))
    doc = (f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
           f'<base href="{src.parent.as_uri()}/"><style>{css}</style></head><body>{body}</body></html>')
    html_path = src.with_suffix(".html")
    keep = a.keep_html
    if not keep:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".html", dir=src.parent, delete=False)
        html_path = Path(tmp.name)
        tmp.close()
    html_path.write_text(doc)
    try:
        engine = to_pdf(html_path, out)
    finally:
        if not keep:
            html_path.unlink(missing_ok=True)
    msg = f"wrote {out.name} (engine: {engine})"
    if a.preview:
        Path(a.preview).parent.mkdir(parents=True, exist_ok=True)
        contact_sheet(out, a.preview)
        msg += f", preview {a.preview}"
    print(msg)


if __name__ == "__main__":
    main()
