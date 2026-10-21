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

Answer boxes (<div class="answer"></div>) and the cells of all-empty table columns (ticket
worksheets, "Pass?" columns, the command reference) become fillable PDF form fields when pypdf
is installed. Without it the PDF still renders, with drawn boxes only. --no-forms turns this off.
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


# --------------------------------------------------------------------------- fillable fields

# Every answer box and every cell of an all-empty table column gets an invisible link to FIELD_URI + index.
# Chromium and WeasyPrint both keep a link's exact box as a PDF annotation; add_form_fields() then turns
# each of those annotations into an AcroForm text field that any PDF reader (laptop or tablet) can fill.
FIELD_URI = "https://pdf-field.invalid/"
FIELD_CSS = ".answer, td.fill { position: relative; }\na.pdf-field { position: absolute; inset: 0; display: block; }\n"
TOKEN_RE = re.compile(r"<h[1-4][^>]*>(?P<head>.*?)</h[1-4]>|<blockquote[^>]*>(?P<quote>.*?)</blockquote>|"
                      r'<div class="(?P<cls>answer[^"]*)">\s*</div>|<table>(?P<table>.*?)</table>', re.S)
CELL_RE = re.compile(r"<td([^>]*)>(.*?)</td>", re.S)


def plain(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h))).strip()


def mark_fields(body):
    """Insert the field links. Returns (html, specs); specs[i] describes the field behind link i."""
    specs, names = [], set()
    state = {"section": "", "prompt": ""}

    def field(name, tip, size):
        name = re.sub(r"[.\s]+", " ", name).strip()[:100] or "Answer"  # '.' would nest fields
        base, k = name, 1
        while name in names:
            k += 1
            name = f"{base} ({k})"
        names.add(name)
        specs.append({"name": name, "tip": tip[:300], "size": size})
        return f'<a class="pdf-field" href="{FIELD_URI}{len(specs) - 1}"></a>'

    def table(tbl):
        if "<tbody>" not in tbl:
            return tbl
        head, _, rows = tbl.partition("<tbody>")
        heads = [plain(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)]
        trs = re.findall(r"<tr>.*?</tr>", rows, re.S)
        cells = [[plain(c[1]) for c in CELL_RE.findall(tr)] for tr in trs]
        empty = {c for c in range(len(heads)) if all(c >= len(r) or not r[c] for r in cells)}
        if not empty:
            return tbl
        out = []
        for r, tr in enumerate(trs):
            label = " | ".join(c for c in cells[r] if c)
            col = iter(range(len(cells[r])))

            def td(m):
                c = next(col)
                if c not in empty:
                    return m.group(0)
                h = heads[c] or f"Column {c + 1}"
                name = f"{state['section']} - {h}" + (f" {r + 1}" if len(trs) > 1 else "")
                return f'<td class="fill"{m.group(1)}>' + field(name, f"{h}: {label}" if label else h, 9) + "</td>"
            out.append(CELL_RE.sub(td, tr))
        return head + "<tbody>" + "".join(out) + rows[rows.rindex("</tr>") + 5:]

    def repl(m):
        if m["head"] is not None:
            state["section"], state["prompt"] = plain(m["head"]), ""
        elif m["quote"] is not None:
            state["prompt"] = plain(m["quote"])
        elif m["cls"] is not None:
            kind = re.match(r"[^:]{1,40}(?=:)", state["prompt"])
            name = f"{state['section']} - {kind.group(0) if kind else 'Answer'}"
            tip, state["prompt"] = state["prompt"] or state["section"], ""
            return f'<div class="{m["cls"]}">{field(name, tip, 10)}</div>'
        else:
            return "<table>" + table(m["table"]) + "</table>"
        return m.group(0)

    return TOKEN_RE.sub(repl, body), specs


def have_pypdf():
    try:
        import pypdf  # noqa: F401  # type: ignore
        return True
    except ImportError:
        return False


def add_form_fields(pdf, specs):
    """Turn the field links left by mark_fields() into AcroForm text fields. Returns the number made."""
    from pypdf import PdfWriter  # type: ignore
    from pypdf.generic import (ArrayObject, BooleanObject, DecodedStreamObject, DictionaryObject, FloatObject,
                               IndirectObject, NameObject, NumberObject, TextStringObject)  # type: ignore

    def d(**kw):
        return DictionaryObject({NameObject("/" + k): v for k, v in kw.items()})

    w = PdfWriter(clone_from=str(pdf))
    helv = w._add_object(d(Type=NameObject("/Font"), Subtype=NameObject("/Type1"),
                           BaseFont=NameObject("/Helvetica"), Encoding=NameObject("/WinAnsiEncoding")))
    fields = ArrayObject()
    for page in w.pages:
        annots = page.get("/Annots")
        annots = annots.get_object() if annots is not None else []
        for k in range(len(annots)):
            a = annots[k].get_object()
            act = a.get("/A")
            uri = str(act.get_object().get("/URI", "")) if act is not None else ""
            if a.get("/Subtype") != "/Link" or not uri.startswith(FIELD_URI):
                continue
            spec = specs[int(uri[len(FIELD_URI):])]
            for key in ("/A", "/Border", "/BS", "/H", "/C"):
                a.pop(key, None)
            x0, y0, x1, y1 = (float(v) for v in a["/Rect"])
            blank = DecodedStreamObject()  # empty appearance; NeedAppearances makes readers draw typed text
            blank.set_data(b"/Tx BMC EMC")
            blank.update(d(Type=NameObject("/XObject"), Subtype=NameObject("/Form"),
                           BBox=ArrayObject([FloatObject(0), FloatObject(0),
                                             FloatObject(abs(x1 - x0)), FloatObject(abs(y1 - y0))])))
            a.update(d(Subtype=NameObject("/Widget"), FT=NameObject("/Tx"), T=TextStringObject(spec["name"]),
                       TU=TextStringObject(spec["tip"]), Ff=NumberObject(4096),  # 4096 = multiline
                       DA=TextStringObject(f"/Helv {spec['size']} Tf 0 g"), F=NumberObject(4),  # 4 = print
                       P=page.indirect_reference, MK=DictionaryObject(), V=TextStringObject(""),
                       AP=d(N=w._add_object(blank))))
            if not isinstance(annots[k], IndirectObject):
                annots[k] = w._add_object(a)
            fields.append(annots[k])
    if fields:
        w.root_object[NameObject("/AcroForm")] = d(Fields=fields, NeedAppearances=BooleanObject(True),
                                                   DA=TextStringObject("/Helv 0 Tf 0 g"),
                                                   DR=d(Font=d(Helv=helv)))
        w.write(str(pdf))
    return len(fields)


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
    ap.add_argument("--no-forms", action="store_true", help="don't make answer boxes fillable")
    a = ap.parse_args()
    src = Path(a.markdown).resolve()
    out = Path(a.out).resolve() if a.out else src.with_suffix(".pdf")
    md = expand_markers(src.read_text(), src)
    title = a.title or (re.search(r"^#\s+(.+)$", md, re.M) or [None, src.stem])[1]
    css = Path(a.css).read_text() if Path(a.css).exists() else ""
    footer = html.escape(a.footer or title).replace('"', "'")
    css += f'\n@page {{ @bottom-left {{ content: "{footer}"; }} }}\n'
    body = add_callout_classes(md_to_html(md))
    specs, forms = [], not a.no_forms and have_pypdf()
    if not a.no_forms:
        marked, specs = mark_fields(body)
        if forms:
            body = marked
            css += FIELD_CSS
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
    if specs and forms:
        msg += f", {add_form_fields(out, specs)} fillable field(s)"
    elif specs:
        msg += f", {len(specs)} answer field(s) NOT fillable: install pypdf"
    if a.preview:
        Path(a.preview).parent.mkdir(parents=True, exist_ok=True)
        contact_sheet(out, a.preview)
        msg += f", preview {a.preview}"
    print(msg)


if __name__ == "__main__":
    main()
