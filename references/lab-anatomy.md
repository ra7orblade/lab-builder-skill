# Anatomy of a reference lab guide (Cisco Netacad CCNP ENCOR)

This analysis comes from 41 Netacad ENCOR lab guides covering switching, routing, BGP, FHRP, NAT/NTP, VPN, assurance, security and automation, and from 2 independently written QoS labs. It records what they do well, which you should keep, and where they fall short of real learning, which you should fix. Product names are incidental. The structure applies to any vendor or technology.

## 1. Fixed document skeleton

Every Netacad lab has the same sections, in the same order:

| # | Section | Content and conventions |
|---|---|---|
| 1 | **Title** | `Lab - <Verb> <Technology>`. The verb tells the learner the mode of work: *Implement*, *Configure*, *Investigate*, *Observe … and Implement …*, *Explore*, *Construct*, *Use … to …*. |
| 2 | **Topology** | One diagram. It shows device names, interface IDs on every link, subnets, loopbacks and grouping (areas, AS numbers, VLANs, inside/outside). |
| 3 | **Addressing Table** | Device / Interface / IPv4 / IPv6 / Link-local, one row per interface. Extra tables when needed: VLAN table, AS table, credentials. |
| 4 | **Objectives** | A numbered list of Parts. Part 1 is **always** "Build the Network and Configure Basic Device Settings (and Interface Addressing)". |
| 5 | **Background / Scenario** | 1–3 paragraphs on what the technology is and what the learner will do. Then standard notes: "exercise … does not reflect best practices", the platform and version used, and "erase devices first". |
| 6 | **Required Resources** | Device counts with model and image, cables, and any software (Python VM, TFTP, syslog server). |
| 7 | **Instructions** | Parts, then *Steps* (`Step n: <imperative sentence>.`), then lettered sub-steps `a.` `b.` `c.`. |
| 8 | **Questions** | Embedded right after the output they refer to, as `Question:` followed by a blank "Type your answers here." Some labs end with **Reflection Questions**. |
| 9 | **Challenge** (some labs) | A final Part with no instructions and a pass/fail table of tests, e.g. "From R1, `traceroute … source lo0` should show next hop 10.1.3.3". |
| 10 | **Appendix** | Router Interface Summary Table: how interface names map across hardware models. |

## 2. The rhythm inside a step

Almost every step follows the same micro-pattern. Keep it:

1. **Concept paragraph.** Why the step exists. It often lists the options, e.g. "There are three ways to enable OSPF on an interface: …" or "The router ID is chosen in this order: …".
2. **Action.** In Netacad this is the full command with the prompt, e.g. `D1(config-router)# network 10.10.0.2 0.0.0.0 area 0`.
3. **System feedback.** The syslog or console message the action triggers, e.g. an adjacency change or a "reload needed" warning.
4. **Interpretation sentence.** "Notice how the informational message confirms that …"
5. **Verification.** A `show` command filtered to the relevant lines (`| include`, `| section`, `| begin`), its output, then a sentence saying what the output proves.
6. **Fading by repetition.** "Repeat the process on D2" with no new commands. The learner transfers the pattern on their own.

## 3. How a lab is sequenced

The Parts follow a stable progression:

1. **Baseline:** cabling, hostnames and addressing, all handed out as copy-paste configs, followed by a connectivity check.
2. **Core feature, minimum viable:** get it working.
3. **Several methods for the same result:** e.g. network statement with a quad-zero mask on one device, wildcard masks on another, interface-level enablement on a third. The learner compares them.
4. **Verify and explore:** routing table, protocol databases, neighbour tables, LSDB/BGP table/CAM/CEF. Each output is tied back to theory.
5. **Tune and optimise:** timers, costs, priorities, passive interfaces, reference bandwidth, summarisation.
6. **Advanced and protective features:** authentication, object tracking, filtering, guards.
7. **Failure observation:** demonstrated failures, e.g. timer mismatches dropping adjacencies, GRE recursive routing, root bridge takeover blocked by Root Guard.
8. **Challenge** (sometimes): rebuild or extend with no instructions and a pass/fail table.

The labs observe mechanisms, not only configure features. LSA types, DR/BDR elections, STP port roles, BGP best-path attributes, IPsec SA counters and CEF tables are each made visible with a command and explained.

## 4. Recurring devices and conventions

- **Naming:** R1..Rn routers, D1/D2 distribution (layer-3) switches, A1 access switch, PC1..PCn. ISP or "internet" routers sit outside the main domain.
- **Loopbacks simulate LANs and the internet**, which saves device count. A loopback needs the right network type, or it is advertised as a /32. The lab teaches this explicitly.
- **Router IDs** use a readable pattern (1.1.1.1, 2.2.2.2) so they are easy to spot in outputs.
- **Two layer-3 switches and one router** is the most common core. Some labs add a layer-2 switch with a default configuration to make a multi-access segment.
- **Filters:** output is trimmed with `| include`, `| section` and `| begin`. Showing learners how to cut output down to what matters is itself a skill.
- **Platform caveat:** an appendix covers interface naming differences between models.

## 5. Question patterns found

| Pattern | Example (paraphrased) | Value |
|---|---|---|
| Explain an absence | "Why does `show ip route ospf` display no routes here?" | High: forces a model of how the system works |
| Explain a state | "Why haven't any SAs been negotiated yet?" | High |
| Cause and effect after a change | "What is the effect on the interface state when changing broadcast to point-to-point?" | High |
| Read the output | "What does the `>` in this entry indicate?", "How many neighbours does R2 have?" | Medium: trains output literacy, but is easy to answer without understanding |
| Predict or transfer | "What other types of traffic would cause an SA to form?" | High |
| Recall | "Name the three common well-known communities." | Low: belongs in a readiness check |

## 6. What the reference labs get wrong for real learning

Netacad's guides are **cookbooks**. Every command for every step is printed, prompt included, so a learner can finish the lab by copying and learn very little. For example, single-area OSPFv2 Part 2 gives the exact `network` statements, and HSRP gives every `standby` command. Other weaknesses:

- **Questions are sparse and optional.** Several labs (HSRP, VRRP, GLBP, NAT, GRE, NetFlow) have **none**.
- **No prediction before action.** Outputs appear *before* the learner could form an expectation, so surprises teach nothing.
- **Expected output is shown up front.** The answer to "which router became DR?" sits in the printed output above the question.
- **Failure is demonstrated, never diagnosed.** The lab says "notice the adjacency dropped", but the learner never has to *find* a fault.
- **No readiness check.** Nothing confirms the learner has the theory before configuring.
- **No graded hints.** The learner either copies the answer or is stuck.
- **Errors slip through.** One OSPF lab suggests `network 10.10.24.0 0.0.254.255` to cover 10.10.24.0/24 and 10.10.25.0/24. That wildcard only matches *even* third octets, so it misses 10.10.25.0 and catches every other even subnet. The right one is `0.0.1.255`. Check every value you write.

The two independently written QoS labs show the opposite failure:

- Theory is copied in bulk ("What it is / Why it's needed / How it works" for each feature), followed by the full config. That is a reading exercise, not a lab.
- **The verification criteria are vague**, e.g. "look for minimal drops", with no numbers or specific fields.
- **Untestable sections** such as "Trust boundary (theoretical)": the topology could not exercise the concept, so it was described instead. **Design the topology so every concept can be exercised.**
- **Platform-incorrect commands.** Commands from one platform family were suggested for an image that does not support them. Check each command against the chosen image.
- **No questions, no troubleshooting, no progression.** All sections sit at the same level of guidance.

## 7. What the generated labs keep and change

| Keep from Netacad | Change |
|---|---|
| The fixed skeleton (sections 1–10) | Commands are replaced by **tasks with values**. Commands go to the answer key. |
| Baseline Part 1 given in full | Add a **Readiness Check** before Part 1 |
| Concept paragraph → action → feedback → verification rhythm | Add **Predict** before the action and **Explain** after it |
| Several methods for the same result | Make the comparison explicit with a question |
| Observe mechanisms with show/debug | Never show output that answers the next question |
| Demonstrated failures | Turn them into **Break it** experiments (predict → break → observe → explain → restore) and **Troubleshooting Tickets** (find an unknown fault) |
| "Repeat on D2" fading | Make fading systematic: guided → semi-guided → open → diagnose |
| Challenge with a pass/fail table | Keep it, and also use acceptance tables in the open parts |
| Interface summary appendix | Replace it with **Platform Notes**: naming, reset procedure, emulator limitations |
| Filtered verification output | Teach the filter in guided parts, and expect the learner to use it later |
