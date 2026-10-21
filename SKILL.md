---
name: lab-builder-skill
description: |
  Build a complete, learner-centred hands-on lab from a textbook chapter (PDF, Markdown or text): concept inventory, topology diagram, addressing table, baseline configs, a fillable lab guide (.md + .pdf) that teaches through tasks, predictions and graded hints instead of copy-paste commands, troubleshooting tickets and a separate answer key. Netacad-style structure, but vendor- and technology-neutral. Optionally builds the initial, unconfigured lab in Cisco Modeling Labs or GNS3 through an MCP server, and validates it there on request.
  Use when the user gives a chapter and asks for a lab, lab guide, practice lab, hands-on exercises or lab topology for it, or asks to build that chapter's lab in CML/GNS3/an emulator. Also use when a learner working through such a lab asks for help, a hint, or an explanation of one of its concepts (coaching mode).
  Do not use for general questions unrelated to a chapter or lab.
---

# Lab Builder Skill

You turn a book chapter into a lab the learner **builds themselves**. Netacad-style structure (`references/lab-anatomy.md`) plus established learning principles (`references/tutoring.md`): diagnose first, tasks instead of commands, predict before acting and explain after, fading scaffolds, graded hints, real troubleshooting. Answers live in a separate answer key.

`SKILL_DIR` means this skill's folder. `LAB` means the output lab folder. Scripts need Python 3 + PyYAML, plus poppler-utils for PDF input and Chromium (or WeasyPrint) for PDFs. pypdf makes the PDF answer boxes fillable; without it they are drawn only.

## Token budget rules (read first)

- **Scripts do the mechanical work.** You write only the chapter-specific content: `topology.yaml`, config *deltas*, ticket *deltas*, `concept-map.md`, the guide text and the answer-key text. Never hand-write baseline, final, checkpoint or ticket configs, addressing tables, objectives lists or standard guide sections. `labkit.py build` generates them.
- **Read the chapter once**, from the squeezed `chapter.txt`, in large chunks. Write `concept-map.md` straight away and work from it afterwards. Do not re-read the chapter.
- **Don't re-read files you just wrote.** Trust `build` and `lint` output, which are short summaries.
- **Check visuals with one image:** `build --pdf` writes `_work/preview-guide.png`, a contact sheet of every page.
- **Known platform facts are in `references/platform-notes.md`.** Use them; don't rediscover them. Append any new fact you validate.
- **Load references only when their step comes up.** After the first lab, the rules card at the top of `pedagogy.md` is usually enough.

## Hard rules

- **Ask before downloading or installing anything** (packages, tools, interpreters, MCP extras) and before writing outside the current working directory. Say what, why, roughly how big, and how to undo it.
- **Emulator testing is the user's decision.** Ask it at intake; the default is no. Testing costs many tokens and is rarely needed for simple labs.
- Never push solution, checkpoint or ticket configs into the learner's emulator lab unless the user approved testing. In that case, revert the lab to the baseline afterwards.
- Never delete or wipe an existing emulator lab or node without explicit confirmation.

## Workflow

### 0. Intake: one round of questions, only for what is missing

Ask everything in a single message. Use your environment's structured-question tool if it has one.

1. **Output folder.** Propose one, e.g. next to the course's other labs. It must be inside the working directory, or the user must confirm it.
2. **Platform and images.** Default to what the book teaches; lightweight emulator images where possible.
3. **Emulator build:** files only (default), CML via MCP, or GNS3 via MCP.
4. **Test the lab on the emulator before final delivery?** No (default) / Yes. Ask only if there will be an emulator build.

The learner's level sets the starting scaffold. Assume the course level unless the user says otherwise.

### 1. Extract

```bash
python3 SKILL_DIR/scripts/extract_chapter.py <chapter.pdf|.md|.txt> [more inputs] -o LAB/_work/extract
```

Read `outline.md`, then `chapter.txt` once, in large chunks, with `commands.md` alongside. Inputs can be mixed, for example the PDF plus the learner's notes in Markdown. Details: `references/concept-extraction.md`.

### 2. Concept inventory → `LAB/concept-map.md`

One row per concept: kind (CONFIG, MECH, VERIFY, FAILURE, THEORY, DESIGN, LIMIT), treatment, and location. Pick 1-2 "Beyond the Book" items. Decide whether the chapter needs one lab or several. Close with a coverage summary. See concept-extraction §2-5.

### 3. Design → `LAB/topology/topology.yaml`

Use the smallest topology that makes every MECH observable and every CONFIG testable. The schema covers platform profiles, interface `extra:` lines, host `gateway:`, `included` / `not_included`, `short_title` and `checkpoints`; see `references/topology-and-configs.md`. Assign each Part a scaffold level (pedagogy §2).

### 4. Solutions as deltas

Write only what each Part adds, and only the fault lines of each ticket:

```
LAB/solutions/deltas/<dev>.part<N>.cfg          lines added in Part N (in the device's CLI syntax)
LAB/solutions/tickets/ticket-<N>/<dev>.delta    the single fault (appended to the final config)
LAB/solutions/tickets/challenge/<dev>.delta     optional multi-fault challenge
```

Make 2-4 tickets, each a different kind of fault. Use a symptom-first design: prefer faults that cause *suboptimal* behaviour as well as outages.

### 5. Build

```bash
python3 SKILL_DIR/scripts/labkit.py build LAB
```

This generates initial configs from the platform profiles, validates, and assembles final configs and checkpoints. It builds the ticket configs plus one CML import file per ticket, the SVG diagram, `topology/addressing-table.md`, `topology/cml-lab.yaml` and `_work/cml-lab.json`. It then expands the markers and lints. Fix what it reports and re-run; it is idempotent.

### 6. Write the guide and the answer key

Copy `assets/lab-guide-template.md` → `LAB/lab-guide.md` and `assets/answer-key-template.md` → `LAB/solutions/answer-key.md`. Fill every `{{placeholder}}`. Keep the markers:

| Marker | Fills in |
|---|---|
| `<!-- @objectives -->` | Part list, from the `## Part N:` headings |
| `<!-- @table addressing -->` | addressing table |
| `<!-- @include skill:snippets/<x>.md -->` | standard sections (how-to-use, ticket method, worksheets, command reference, ...) |
| `<!-- @deltas part=N -->` | answer key: every device's configuration for Part N |
| `<!-- @ticket N -->` / `<!-- @ticket challenge -->` | answer key: the injected fault lines |
| `<!-- @code PATH [lang] -->` | any file as a code block |

Writing rules: follow the pedagogy rules card. Tasks give the outcome and the values, never the commands. Each step has one thinking prompt. Show no output that answers a later question. Hints go in Appendix A, three levels each.

Copy `assets/lab-readme-template.md` → `LAB/README.md` and fill it in.

### 7. Quality gate + render

```bash
python3 SKILL_DIR/scripts/labkit.py build LAB --pdf     # must end with "lint: 0 issue(s)" and "build: OK"
```

If the PDF line says the answer fields are "NOT fillable", pypdf is missing. Tell the user, and offer to install it (ask first, per the hard rules).

Then read `LAB/_work/preview-guide.png`, one image, and fix anything visibly broken. The checklist that `lint` cannot do for you:

- concept-map coverage
- every value correct (masks, wildcards, AS numbers, keys, interface names)
- scaffolding fades
- each ticket has one fault and a realistic symptom
- Platform Notes disclose emulator limits and unverified outputs

### 8. Emulator (only if chosen)

Follow `references/emulators.md`. For CML: check for name collisions with `get_cml_labs`, then import `_work/cml-lab.json` with `create_full_lab_topology`, passing the parsed object. Read back the nodes and links. Start the lab only if the user asked.

**Testing (only if the user said yes):** follow emulators.md §4, the batched procedure: save the baseline, apply the solution, run one command batch per device, run the tickets, revert, record facts in `platform-notes.md`. Otherwise, mark sample outputs you did not capture as representative in Platform Notes.

### 9. Deliver

Report briefly:

- the folder, and the labs with their Part titles
- coverage numbers
- the emulator lab name and ID, or how to import it
- what was and was not validated

Don't paste the guide. Don't keep `_work/` in the delivered folder, unless the user wants the extraction.

## Coaching mode

When a learner asks for help, a hint or an explanation while working through a lab (rather than asking you to build one), skip the workflow above:

1. Load `references/tutoring.md` and follow its tutoring loop.
2. Find the lab folder. Read the relevant step in `lab-guide.md`, its hint in Appendix A, and the matching part of `solutions/answer-key.md`, so your help matches the lab's values and scaffold level.
3. Never paste solution configs or ticket answers unless the tutoring guide's conditions for telling are met.

## Reference files (load on demand)

| File | Load when |
|---|---|
| `references/tutoring.md` | Coaching mode; also when you need the reasoning behind a pedagogy rule |
| `references/pedagogy.md` | Writing the guide. The rules card at the top is mandatory; the rest only when unsure |
| `references/concept-extraction.md` | Steps 1-2, if this is your first lab with the skill |
| `references/topology-and-configs.md` | Step 3-4: schema, markers, deltas, platform profiles |
| `references/emulators.md` | Step 8 only |
| `references/platform-notes.md` | Steps 3 and 8: validated CML/IOL/Alpine facts; append new ones |
| `references/lab-anatomy.md` | Only if you need the Netacad structure rationale |
