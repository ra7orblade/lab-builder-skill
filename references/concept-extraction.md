# From chapter PDF to concept inventory to lab plan

The lab is only as complete as the inventory behind it. Do this before designing anything.

## 1. Extract

```bash
python3 <skill>/scripts/extract_chapter.py <chapter.pdf> [notes.md ...] -o "<LAB>/_work/extract" [--first N --last M]
```

**Inputs can be `.pdf`, `.md`/`.markdown` or `.txt`, or several at once.** With several inputs, every reference gets the file name as a prefix, e.g. `chapter4.pdf p12` or `notes.md §Stub`. Use Markdown when the PDF is scanned, when the user has already converted the chapter, or to add the learner's own notes.

| File | Use it for |
|---|---|
| `outline.md` | The chapter's structure. Read it first; its headings become the inventory skeleton. |
| `chapter.txt` | The full text with `=== [ref] ===` markers. Watermarks and running headers are removed and layout padding is squeezed, about 20% fewer tokens. **Read it once, in large chunks.** Don't sample, and don't re-read. |
| `commands.md` | Index of every distinct CLI and config command, once, with the page where it first appears (monospace in PDFs, code blocks and spans in Markdown). Nearly every CONFIG and VERIFY item is here. The full example configs and outputs are in `chapter.txt`. |
| `key-terms.md` | Bold or italic terms in body text: concept candidates. A lookup, not required reading. |
| `captions.md` | Figures, tables and examples. Tables often hold defaults, comparisons and decision orders. A lookup, not required reading. |

If a PDF yields almost no text, it's scanned. Ask the user for a Markdown or text version, or OCR it first (for example with `ocrmypdf`, which needs Tesseract; ask before installing it). If the user gives a whole book, ask which chapter, or find it in the outline and pass `--first/--last`.

**Token discipline:** write `concept-map.md` *while* reading, section by section. Afterwards, design from the concept map, not from the chapter text.

Also look for the chapter's own coverage aids. These are checklists you must cover:

- chapter objectives or "exam topics covered"
- "key topic" markers or tables
- command reference tables
- end-of-chapter summaries
- review questions and "do I know this already" quizzes
- "troubleshooting" sections, which are prime ticket material

Diagrams that exist only as images can carry concepts the text omits, such as a topology, a packet format or a state machine. If the text references a figure you need, render the page (`pdftoppm -f N -l N -png`) and look at it.

## 2. Build the inventory (`concept-map.md`)

One row per **distinct** knob, behaviour or idea. Typical chapters yield 25–80 rows. Keep it in the lab folder, because it is part of the deliverable and the user can audit coverage from it.

```markdown
| ID | Concept | Book ref | Kind | Tier | Lab treatment | Where in lab |
|----|---------|----------|------|------|---------------|--------------|
| C01 | Router ID selection order | §8.2, p.214 | MECH | Core | Predict + observe + Break it (change RID, clear process) | P2 S4 |
| C02 | network statement with wildcard | §8.3, p.216 | CONFIG | Core | Task (L1), compare with C03 | P2 S2 |
| C03 | Interface-level enablement | §8.3, p.217 | CONFIG | Support | Task (L1), compare question | P2 S3 |
| C04 | Hello/dead timers must match | §8.5, p.225 | FAILURE | Core | Break it + Ticket 1 | P4 S3, T1 |
| C05 | LSA types 1-5,7 | §9.2, p.240 | MECH | Support | Observe LSDB + explain-absence question | P3 S2 |
| C06 | When to use NSSA vs stub | §9.4 | DESIGN | Support | Reflection Q2 | Reflection |
| C07 | Virtual links | §9.5 | CONFIG | Extra | Task (L3) with acceptance table | P5 |
| C08 | Hardware-specific feature X | §9.7 | LIMIT | Extra | Not emulatable → Platform note + Question | App. B |
```

**Kinds and their mandatory treatment:**

| Kind | Meaning | Treatment in the lab |
|---|---|---|
| CONFIG | Something you can configure | A Task with a Checkpoint. If the book shows alternative methods, add a compare step. |
| MECH | A behaviour or algorithm you can observe: election, state machine, table, packet exchange, selection order | An observation step plus an Explain question. Usually a Predict, often a Break it. |
| VERIFY | A verification or troubleshooting command or method | Used in Checkpoints (named in L1, chosen by the learner in L2+). It appears in the answer key's command reference. |
| FAILURE | A failure mode, caveat or gotcha the book describes | A Break it experiment **or** a Troubleshooting Ticket |
| THEORY | A definition, history or comparison not directly observable | A Readiness Check or Reflection question, tied to observable evidence where possible |
| DESIGN | When or why to choose an option | A Reflection question, or framed as a design decision in an L3 Part |
| LIMIT | Not reproducible on the chosen platform or emulator | A Platform Note, plus a substitute exercise or a question. Say so honestly. |

**Tier** (Core, Support, Extra) decides how much lab time a concept gets at the chosen depth level; see `depth-and-time.md` §3.

**Coverage rule:** every row ends up with a treatment and a location, or with an explicit reason it is out of scope or deferred at this depth. Close `concept-map.md` with a coverage summary, e.g. "62/64 concepts covered, 2 deferred: C41 (hardware ASIC detail, LIMIT) and C57 (covered in chapter 12's lab)".

## 3. Depth: set by the chosen level

The user's depth level (Low, Medium, High, Max) decides how deep the lab goes and how much time it may take. The levels, the time budget and the tier rules are in `depth-and-time.md`. Read it before designing. In short:

- **The book's depth is the upper limit for Low and Medium, not the minimum.** A feature the chapter mentions in one paragraph doesn't automatically earn a task. Its tier and the level decide whether it gets a step, a 2-minute question, or is deferred.
- For every CONFIG that gets a task, there is at least **one verification and one "why" question**.
- **Going beyond the input** depends on the level: none at Low, one short deep dive plus at most one small extra at Medium, more at High and Max. Every item must pass the track test (`depth-and-time.md` §2). Good candidates, when they pass:
  - a feature the book *mentions but does not explain*
  - an interaction with a technology from an earlier chapter (e.g. FHRP plus IP SLA tracking, or routing plus BFD)
  - the IPv6 or dual-stack variant when the book covers only IPv4, or the reverse
  - an operational concern: convergence timing, scale (summarisation, filtering), security hardening (authentication, protection features)
  - a programmatic verification angle, e.g. reading the same state over an API, when it fits the course
- Do **not** pile on features the chapter doesn't motivate. One well-chosen extension beats five shallow ones.

## 4. One lab or several?

Netacad splits by technology cluster. Chapter 15 (FHRP, NAT, NTP) becomes five labs: HSRP, VRRP, GLBP, NAT, NTP. Chapter 9 (multi-area OSPF) becomes two: implementation, then summarisation and filtering.

Split when:

- the inventory falls into clusters that need **different topologies**, or that don't depend on each other
- the planned time exceeds the depth level's **hard cap** even after the time savers in `depth-and-time.md` §4
- the chapter covers alternatives best learned side by side but separately, e.g. three redundancy protocols

Each lab gets its own folder (`lab-01-<slug>`, `lab-02-<slug>`), its own topology, its own guide and the same depth level. One shared `concept-map.md` at the chapter folder level maps each concept to its lab.

## 5. Ordering Parts

Order Parts by dependency first, and only then by the book's section order:

1. Baseline (L0)
2. Core feature, minimum working (L1)
3. Alternative methods and comparison (L1/L2)
4. Observe the mechanisms: databases, tables, elections (L2)
5. Tune and optimise: timers, costs, priorities, passive, summarisation (L2)
6. Advanced, protective and filtering features (L2/L3)
7. Beyond the Book (L3)
8. Troubleshooting Tickets (L4)
9. Challenge (optional, L3)

## 6. Readiness Check source

Take the most load-bearing THEORY or MECH rows (3 at Low, up to 6 at Max; see `depth-and-time.md` §1), the ones that a misunderstanding of would wreck the lab. Turn each into an explanation question with the book reference.
