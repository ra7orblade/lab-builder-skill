# {{Lab title}}

A hands-on lab for **{{Book}}, Chapter {{N}}: {{Chapter title}}**, built for {{platform/images}} on {{emulator or physical}}.

## Start here

1. Open `lab-guide.pdf` (or `lab-guide.md`).
2. Build the topology: {{"open the CML lab '<name>'" | "import topology/cml-lab.yaml" | "follow the topology diagram"}}.
3. Work through the guide. Hints are in Appendix A, one level at a time.
4. Open `solutions/` only once you have a working result.

## Folder contents

| Path | What it is |
|---|---|
| `lab-guide.md` / `.pdf` | The learner guide |
| `concept-map.md` | Every chapter concept and where the lab covers it |
| `topology/topology.yaml` | Vendor-neutral topology (source of truth) |
| `topology/topology.svg`, `addressing-table.md` | Diagram and addressing table |
| `topology/cml-lab.yaml`, `ticket-N.cml.yaml` | CML import files (initial lab and one per ticket) |
| `initial-configs/` | Baseline configs |
| `troubleshooting/` | Ticket configs. Don't read them before solving. |
| `solutions/answer-key.md` / `.pdf` | Commands, outputs, model answers |
| `solutions/final-configs/`, `checkpoints/` | End state and resume points |
| `solutions/deltas/`, `solutions/tickets/` | Sources the configs and answer key are generated from |

## Reset to baseline

{{Platform-specific rollback / wipe procedure.}}

## Regenerate after edits

`python3 <skill>/scripts/labkit.py build . --pdf`
