# Building (and optionally testing) the lab in an emulator

Only do this when the user chose an emulator build at intake. The deliverable is the **initial lab**: nodes, links and baseline configs, with the chapter features left unconfigured. Validated platform quirks are in `platform-notes.md`; read them before you start.

## 0. Ground rules

- **Creating a new lab is what the user asked for.** Deleting, wiping or modifying an existing lab, even after a name collision, needs explicit confirmation. On a collision, pick a new title.
- **Testing is opt-in**, decided at intake; the default is no. Without testing, never push solution or ticket configs into the learner's lab.
- **Ask before downloading or installing anything** (MCP extras such as pyATS, images, packages), and before editing the MCP configuration or your own agent configuration.
- **Don't start nodes unless the user asked.** Starting them costs server resources.
- **Read back what you built** (node and link counts, endpoints) before reporting success.

## 1. Discover the MCP tools

Look for MCP tools whose server or tool names mention `cml`, `modeling`, `gns3`, `eve` or `containerlab`. If your environment loads tools on demand, load them in one search covering the capabilities you need:

- status and licensing
- node definitions or templates
- list labs
- import or create a lab
- read back nodes and links
- start the lab
- run a CLI command (for testing only)

If no server is connected, say so and deliver the import files (§5).

## 2. CML (verified with cml-mcp 0.32, CML 2.10)

1. `get_cml_labs` to check for title collisions. `get_cml_licensing_details` only if the node count is close to a free-tier limit.
2. If a node definition isn't in `assets/cml-nodedefs.json`, call `get_node_definition_detail` once. Add its `device.interfaces.physical` list to that file, so you never need to look it up again, and re-run `build`.
3. `create_full_lab_topology` with the **parsed JSON object** from `LAB/_work/cml-lab.json` (version 0.2.2, configs embedded). This is a single call.
4. `get_nodes_for_cml_lab` + `get_all_links_for_lab`: compare the counts and endpoints with `topology.yaml`.
5. Start the lab only if asked: `start_cml_lab(wait_for_convergence=true)`.
6. Report the lab title and ID. Tickets are **not** created as labs. Learners import `topology/ticket-N.cml.yaml` when they reach Part 7.

## 3. GNS3

1. List projects, to check collisions, and templates. Template names are user-defined, so match on `image.gns3` or the role, and ask the user once if it's ambiguous.
2. Create the project and the nodes at x/y.
3. Create the links. Use each node's port list to map interface names to adapter/port. Don't guess.
4. Initial configs: upload a startup-config file where the template supports it (IOU, Dynamips, VPCS); otherwise leave them for the learner to paste, and say so in Part 1.
5. Read back and compare, as for CML.

## 4. Optional testing (only if the user said yes)

Testing costs many tokens, so keep it batched and targeted:

1. **Preconditions.** CLI access must work. CML needs `cml-mcp[pyats]`, which is a download, so ask first. Boot the lab.
2. **Rollback point.** On each device: `write memory` of the baseline. CML's TFTP day-0 leaves `startup-config` empty. After that, `configure replace nvram:startup-config force` reverts in seconds.
3. **One batch per device and phase.** Send all of a device's config lines in one `send_cli_command(config_command=true)` call. Send all its `show` commands in one exec call, filtered with `| include`/`| begin`. Avoid one call per command.
4. **What to test:** each Part's checkpoint, the break-its whose exact symptoms the guide or answer key quotes, every ticket's symptom, and the fix. Skip anything already listed in `platform-notes.md`.
5. **Capture.** Paste only trimmed, validated outputs into the guide and key, and mark them "validated".
6. **Revert.** `configure replace nvram:startup-config force` on every device. Confirm with one `show running-config | include <chapter feature>` per device.
7. **Record.** Append new platform facts to `platform-notes.md` with the date.

## 5. Fallbacks (always produced by `build`)

- **CML:** `topology/cml-lab.yaml` (UI → Import) and `topology/ticket-N.cml.yaml`.
- **GNS3, EVE-NG, physical:** the diagram, the addressing table and `initial-configs/`. Add `topology/build-sheet.md` (node, template and link table) only if the user asks.
- **containerlab:** write `topology/<slug>.clab.yml` by hand (`kind`/`image` per node, `links: endpoints`, `startup-config` pointing at `initial-configs/`).
