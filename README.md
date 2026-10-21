# Lab Builder Skill

An [Agent Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) that turns a textbook chapter (PDF, Markdown or plain text) into a complete hands-on lab: topology, addressing, baseline configs, a learner guide, troubleshooting tickets and a separate answer key.

The guides follow the familiar Cisco Netacad lab structure, with one difference: the learner is not handed copy-paste commands. Each task gives the outcome and the values. The learner predicts before acting, proves the result at a checkpoint, and explains what they saw. Hints come in three levels, scaffolding fades from Part to Part, and the lab ends with real fault-finding tickets. The goal is a learner who can configure, verify and fix the technology **without the guide**.

The skill is vendor- and technology-neutral. It ships with Cisco IOS / IOS XE and Linux host profiles, and you can add other platforms with a YAML file. Optionally, it builds the initial lab in **Cisco Modeling Labs (CML)** or **GNS3** through an MCP server.

## What you get

For each chapter, the skill writes a lab folder like this:

```
lab-01-ospf/
├── README.md                      how to start, reset, regenerate
├── lab-guide.md / lab-guide.pdf   the learner guide
├── concept-map.md                 every chapter concept → where the lab covers it
├── topology/
│   ├── topology.yaml              vendor-neutral source of truth
│   ├── topology.svg               generated diagram
│   ├── addressing-table.md
│   ├── cml-lab.yaml               CML import file (initial lab)
│   └── ticket-N.cml.yaml          one CML import file per troubleshooting ticket
├── initial-configs/               baseline configs (chapter features left out)
├── troubleshooting/ticket-N/      ticket configs, each with one fault
└── solutions/
    ├── answer-key.md / .pdf       commands, outputs, model answers
    ├── final-configs/             complete end state
    ├── checkpoints/part-N/        resume points
    ├── deltas/                    per-Part config additions (source)
    └── tickets/                   per-ticket fault lines (source)
```

A typical guide contains:

- a Readiness Check on the theory the lab depends on
- Part 1, the baseline, given in full
- guided Parts, then semi-guided ones, then open Parts with acceptance tables
- "Break it" experiments: predict, break, observe, explain, restore
- a "Beyond the Book" extension
- 2 to 4 troubleshooting tickets, each a different kind of fault
- reflection questions, a build-your-own command reference and a hint appendix
- Platform Notes on emulator limits

## Requirements

| Needed for | Requirement |
|---|---|
| Everything | Python 3.8+ and [PyYAML](https://pypi.org/project/PyYAML/) |
| PDF chapters as input | `poppler-utils` (`pdftotext`, `pdftohtml`, `pdftoppm`) |
| PDF guides as output | [WeasyPrint](https://weasyprint.org/) **or** a Chromium-based browser (Chromium, Chrome, Edge, Brave; or set `CHROME_PATH`) |
| Fillable answer boxes in the PDF (recommended) | [pypdf](https://pypi.org/project/pypdf/). Without it the boxes are drawn but can't be typed into |
| Page preview image (optional) | [Pillow](https://pypi.org/project/pillow/) |
| Nicer Markdown rendering (optional) | [Python-Markdown](https://pypi.org/project/Markdown/). A built-in converter is used otherwise |
| Emulator build (optional) | An MCP server for your emulator, e.g. [`cml-mcp`](https://pypi.org/project/cml-mcp/) for CML |

Example install on Debian/Ubuntu:

```bash
sudo apt install python3-yaml python3-pypdf poppler-utils chromium
```

macOS (Homebrew):

```bash
brew install poppler && pip3 install pyyaml pypdf
# Google Chrome in /Applications is detected automatically
```

## Installation

### Claude Code

Clone the repo into your skills folder. The folder name should match the skill name, `lab-builder-skill`:

```bash
# personal (all projects)
git clone https://github.com/ra7orblade/lab-builder-skill.git ~/.claude/skills/lab-builder-skill

# or for one project only
git clone https://github.com/ra7orblade/lab-builder-skill.git .claude/skills/lab-builder-skill
```

Restart Claude Code. The skill is picked up automatically when you ask for a lab.

### Claude.ai / Claude Desktop

Zip the repository folder and upload it under **Settings → Capabilities → Skills**. The scripts need code execution enabled.

### Other AI agents

The skill is self-contained: plain Markdown instructions plus Python scripts, with no dependency on other skills or on any one vendor's tools. Agents that support the open Agent Skills format (a folder containing `SKILL.md`) can load it directly. For any other agent that can read files and run Python, put the folder somewhere it can reach and tell it:

> Read `lab-builder-skill/SKILL.md` and follow it to build a lab from `chapter.pdf`.

## Usage

Give your agent a chapter and ask for a lab:

> Build a hands-on lab from `chapter-08-ospf.pdf`.

> Here's chapter 15 as Markdown plus my notes in `fhrp-notes.md`. Make practice labs for it and put them in `labs/ch15/`.

> Create the lab for this chapter and build it in CML.

The skill first asks, in one round, about anything it can't work out from your request:

1. **Output folder.**
2. **Platform and images.** The default is whatever the book teaches.
3. **Emulator build:** files only (the default), CML via MCP, or GNS3 via MCP.
4. **Test on the emulator before delivery?** Off by default, because it uses many tokens.

It then extracts the chapter, builds a concept inventory, designs the smallest topology that exercises every concept, and writes the solution deltas and tickets. Next it generates everything mechanical with `labkit.py`, writes the guide and answer key, and checks them with a lint pass and a rendered preview.

If a chapter covers several unrelated technologies, the skill may split it into several labs (`lab-01-…`, `lab-02-…`) with one shared concept map.

### Coaching mode

The skill also tutors the learner while they work through a lab. Ask for help as you would ask a lab instructor:

> I'm on Part 3 Step 2 of the OSPF lab and R2 won't form an adjacency. Here's my `show ip ospf neighbor` output.

> Why does the router with priority 0 never become DR?

It asks what you observed before advising, gives the next hint level rather than the answer, explains concepts using your own lab topology, and turns misconceptions into small predict-and-observe experiments. On request it makes quizzes, flashcards and summaries from the chapter's concept map. For graded coursework it helps you get to the answer without writing it for you. Its approach is grounded in published learning research, summarised with sources in [`references/tutoring.md`](references/tutoring.md).

### Safety defaults

The skill is designed to be cautious with your environment:

- It **asks before** installing or downloading anything, and before writing outside the working directory.
- It never deletes or wipes an existing emulator lab or node without explicit confirmation.
- It never pushes solution or ticket configs into the learner's emulator lab unless you opted into testing. If you did, it reverts the lab to the baseline afterwards.
- It doesn't start emulator nodes unless you ask.

## Using the scripts directly

The scripts also work without an AI agent, which is handy when you edit a lab by hand:

```bash
# Extract a chapter (PDF, Markdown or text; several inputs can be merged)
python3 scripts/extract_chapter.py chapter.pdf notes.md -o LAB/_work/extract [--first 210 --last 248]

# Regenerate everything from topology.yaml + deltas, fill the guide markers, lint, and render PDFs
python3 scripts/labkit.py build LAB --pdf

# Individual steps
python3 scripts/labkit.py validate LAB/topology/topology.yaml
python3 scripts/labkit.py svg      LAB/topology/topology.yaml out.svg
python3 scripts/labkit.py cml      LAB/topology/topology.yaml out.json
python3 scripts/labkit.py lint     LAB/lab-guide.md

# Render any lab Markdown file to PDF
python3 scripts/md2pdf.py LAB/lab-guide.md --preview preview.png
```

The PDF guide is a fillable form. Every answer box, ticket worksheet, "Pass?" column and command-reference cell is a text field, so learners can type their answers in any PDF reader on a laptop or tablet (Okular, Adobe Acrobat Reader, Xodo, Firefox and others). Pass `--no-forms` to `md2pdf.py` for a plain PDF.

`build` is idempotent. A successful run ends with `lint: 0 issue(s)` and `build: OK`. The linter flags missing hints, broken images, questions without an answer box, unfilled `{{placeholders}}`, and any solution command that leaks into the learner guide.

## Adding a platform

Initial configs come from platform profiles in [`assets/platforms/`](assets/platforms/). To support another vendor (Junos, EOS, FRR, VyOS, …), copy `cisco-ios.yaml`, change the comment character, base lines and interface templates, and set `platform: <name>` in `topology.yaml`. No code changes are needed. To override a profile for one lab, put it in `LAB/topology/platforms/<name>.yaml`.

For CML, interface names per node definition are cached in [`assets/cml-nodedefs.json`](assets/cml-nodedefs.json). Add entries for node definitions you use that aren't listed yet.

## Repository layout

| Path | Contents |
|---|---|
| `SKILL.md` | The skill's instructions and workflow (loaded by the agent) |
| `references/` | Detailed guidance, loaded on demand: pedagogy rules, learning principles and tutoring, concept extraction, topology schema, emulator procedures, validated platform facts, and the reference-lab analysis |
| `scripts/` | `extract_chapter.py`, `labkit.py` and `md2pdf.py` |
| `assets/` | Guide, answer-key and lab README templates; reusable snippets; platform profiles; print CSS; CML node-definition cache |

## Validated platforms

The facts in [`references/platform-notes.md`](references/platform-notes.md) were checked on CML 2.10 with `cml-mcp` 0.32, IOL-XE (IOS XE 17.18.2) and Alpine Linux. Other platforms and emulators should work, but they haven't been validated yet. If you validate something new, add a dated entry to that file.

## Contributing

Issues and pull requests are welcome, especially new platform profiles, CML node definitions, and validated platform notes for other emulators.

## Disclaimer

This project is not affiliated with or endorsed by Cisco Systems. Cisco, Cisco Modeling Labs, IOS, Networking Academy (Netacad) and CCNP are trademarks of Cisco Systems, Inc. GNS3 and other product names are trademarks of their respective owners. The skill does not include any course or textbook content. You supply your own chapter, and you're responsible for having the right to use it.
