# Teaching rules for lab guides

## Rules card (mandatory; the sections below explain each rule)

1. **Tasks give the outcome and every value, never the command.** Generic syntax with `<placeholders>` is allowed only in L1 Concept callouts and Level-3 hints.
2. **Scaffolds fade:**
   - **L0:** Part 1, everything given
   - **L1:** the checkpoint names the verification command
   - **L2:** the checkpoint states what must be true; the learner picks the command and writes it down
   - **L3:** requirements plus an acceptance table
   - **L4:** tickets, symptom only
3. **One thinking prompt per step.** Every Part has at least one **Predict** and one **Explain** question. Every Predict and Question is followed by `<div class="answer[ short| tall]"></div>`.
4. **Checkpoints are binary and observable**, e.g. "R1 lists 2 neighbors in FULL", never "verify it works".
5. **Never show output that answers a later question.** Show output only if it was validated or is certain. Otherwise describe the expected state in words.
6. **Every L1-L3 task gets a hint `H<part>.<step>`** with three levels: nudge, narrow, generic pattern. A hint never contains the lab's values as a working line.
7. **Every failure mode from the book becomes a Break it** (predict, change, observe, explain, restore) **or a ticket.** Tickets: 2-4 per lab, one fault each, each a different kind of fault.
8. **Questions must be answerable from lab evidence plus the book.** Recall questions go in the Readiness Check.
9. **Concept text is in your own words**, citing the book section. Never copy long passages.
10. **Don't over-question or over-decorate.** Callout labels signal the type of thinking; use them only where it applies.

These rules apply well-established learning research. `tutoring.md` explains each principle and gives its sources. The goal is not for the learner to *finish* the lab. The goal is that afterwards they can configure, verify and fix the technology **without the guide**. A guide that hands over every command produces someone who can paste. A guide that only asks questions produces someone who gives up. The work happens in between.

## 1. Diagnose before you teach

- **Readiness Check** (start of the guide): 3–6 questions on the prerequisite and core theory, each pointing to a book section. They are written answers, not trivia. "Explain why …" and "What decides …" beat "Name the …".
- **In conversation:** if you don't know the learner's level, ask once when building the lab (see SKILL.md intake). Their answer sets the starting scaffold level (section 2).
- Fluent, expert phrasing in the request sets the *level*. It does not mean "skip the learning design".

## 2. Fading scaffolds

Each Part sits on one level. Levels only go down as the lab goes on.

| Level | Used for | The learner gets | The learner must produce |
|---|---|---|---|
| **L0 Given** | Part 1 (baseline) only | Complete configs and verification | Nothing new: load and check |
| **L1 Guided** | First 1–2 feature Parts | Concept with *generic* syntax templates, tasks with every value, checkpoint naming the verification command, trimmed sample output, 3-level hints | The actual commands |
| **L2 Semi-guided** | Middle Parts | Concept (no syntax), tasks with values, checkpoint stating *what must be true* | Commands **and** their choice of verification command (written down) |
| **L3 Open** | Late Parts, Beyond the Book | Brief, numbered requirements, acceptance-test table | The plan, the config and the proof |
| **L4 Diagnose** | Troubleshooting Tickets | Only a symptom report | Isolation path, root cause, fix, proof |

Calibrate to the learner: beginners get two L1 Parts, and experienced learners start at L2. Use the Netacad "Repeat on D2" move as fading within a Part. One device is done in full, the next on the learner's own.

## 3. One step forward, every step

Every Step carries **one** focused thinking prompt plus the scaffold for it. Never a wall of questions, and never a bare command list. A Step has:

1. **Concept** (optional if covered by the Part's concept): why this exists, 2–6 sentences, citing the book section.
2. **Predict**: before acting, what do you expect to see, change or break? This is where misconceptions surface. Use it on every step whose outcome isn't obvious.
3. **Task(s)**: the outcome and all the values, never the command. "Enable OSPF process 123 for area 0 on D2's transit interface with a statement that matches the whole /29", not `network 10.10.0.0 0.0.0.7 area 0`.
4. **Checkpoint**: an observable, binary success criterion, e.g. "R1 lists both neighbours in FULL state". It is never "verify OSPF works".
5. **Question**: explain what was seen. There is an answer box after every Predict and Question.

## 4. Question design

Each Part needs at least one **Predict** and one **Explain** question. Across the lab, use every type:

| Type | Form | Example |
|---|---|---|
| Predict | "Before you apply X, what will happen to Y?" | "Which router will become DR after you set D2's priority to 0, and why not D1?" |
| Explain a state | "Why does the output show X?" | "Why is the default route marked E2 and not E1?" |
| Explain an absence | "Why is X *not* here?" | "Why doesn't `show ip route ospf` list anything on R1?" |
| Compare | "Method A vs method B: what differs, and when would you pick each?" | Network statement vs interface-level enablement |
| What-if / transfer | "What would change if …?" | "…if the link were point-to-point instead of broadcast?" |
| Design | "When would you *not* use this?" | "When is summarisation at this ABR a bad idea?" |
| Connect | "How does this interact with <earlier chapter>?" | "How does this tracking interact with the FHRP from chapter 15?" |

Rules:

- Questions are answerable from **lab evidence plus the book**. No trivia, and no questions about details the lab never showed.
- **Never print output that contains the answer to the next question.** Show the output *after* the question, or ask the learner to run the command.
- Recall questions ("name the three …") go in the Readiness Check or reflection, not mid-lab.
- One question per callout, followed by `<div class="answer"></div>`. Use `answer short` for predictions and `answer tall` for design questions.

## 5. Hint ladder

Every Task in L1–L3 Parts, and every ticket, has a hint ID (`H<part>.<step>[letter]`) that points to Appendix A. Each hint has **three levels**, read one at a time:

1. **Nudge:** the concept or mechanism involved, or where to look. "Think about which side of the mask is 'don't care'."
2. **Narrow:** the configuration context, the prerequisite, or the comparison that reveals it. "This is configured under the routing process, not the interface. The statement needs the *subnet* address, not the interface address."
3. **Pattern:** the generic syntax with placeholders, or the command family plus the parameter that matters. `network <subnet-address> <wildcard> area <area-id>`. **It never contains this lab's values as a working line.**

`labkit.py lint` enforces this: any line of the solution configs that appears in the guide, hints included, is flagged. The one exemption is a code block preceded by `<!-- leak-ok -->`, which is for Part 1 baseline material only.

## 6. Break it, then fix it

Every mechanism that has a failure mode described in the book, such as mismatches, missing prerequisites or ordering problems, gets a **Break it** experiment:

1. Predict the symptom (in writing).
2. Make the specific change.
3. Observe it: logs, state, counters, a capture.
4. Explain the gap between the prediction and what happened.
5. Restore, and verify the restore.

**Troubleshooting Tickets** go further. The fault is unknown, the learner gets only a symptom, and they must isolate it. Use 2–4 tickets per lab, each a different *kind* of fault: parameter mismatch, missing statement, wrong value or scope, feature interaction, underlay problem. A ticket's config is the full working end-state with **one** fault buried in it, so reading it does not trivially reveal the fault. Even so, the guide tells the learner to load it blind.

## 7. Showing, not just telling

- One **topology diagram**, accurate and labelled, is mandatory.
- Add a small extra diagram (SVG, a table, or an ASCII sketch in a code block) only when a concept has *shape*: a state machine, a packet exchange, a decision order such as BGP best-path or a router-ID selection order. Show one relationship and let a question ask for what is missing. A fully annotated diagram of the whole mechanism is the answer dressed up.
- Tables beat paragraphs for comparisons such as method A vs B, or timer defaults per network type.

## 8. Sample output and honesty

- Sample output is **trimmed** to the lines that prove the checkpoint, with `<output omitted>` for gaps, and labelled with a note that timers, uptimes and IDs will differ.
- Only include output you are confident matches the chosen platform. If you are not sure of the exact format, describe the expected state in words ("both neighbours should be FULL; R1 should be DR") instead of inventing output. Real captured output (from an emulator validation run) beats remembered output. Say which it is in Platform Notes.
- Every value in the guide must be checked: wildcards, masks, AS paths, timers, priorities, key strings and interface names must match the topology and configs exactly. `labkit.py validate` checks addressing, and you check the rest.

## 9. What consistently goes wrong (do not do these)

- **Cookbook drift:** writing "configure `<exact command>`" because it's easier. Every task describes an outcome.
- **Hidden answers in hints:** "Hint: use `network 10.10.0.0 0.0.0.7 area 0`" is the answer with extra steps.
- **Over-questioning:** three questions per step makes learners skip them all. Use one, and make it count.
- **Decoration:** callouts, diagrams and bold text on everything. The labels exist so learners know *what kind of thinking* is asked. Overuse kills the signal.
- **Untestable content:** a "theoretical" section means the topology is wrong. Change the topology, or turn it into a reflection question tied to something observable.
- **False precision:** invented outputs, version-specific claims you haven't verified, or commands from another platform family.
- **Endless lab:** match the depth to the chapter, plus one step further. Do not add every feature you know.

## 10. When the learner comes back for help

Follow `tutoring.md`, the complete tutoring guide. In short:

- Ask what they observed (outputs, logs) before suggesting anything.
- Offer the next unused hint level, not the answer.
- If they're genuinely stuck, give a foothold: do the first part with your reasoning narrated, then hand it back.
- Point to the answer key only after they have a working result or have used every hint level. Then ask what differs from their solution, and why.

## 11. Worked transformation (Netacad step → this skill's step)

**Netacad original (cookbook):**

> c. Configure D2 to advertise the G1/0/5 /29 interface in OSPF area 0. The wildcard mask is 255.255.255.255 − 255.255.255.248 = 0.0.0.7.
> `D2(config-router)# network 10.10.0.0 0.0.0.7 area 0`
> `%OSPF-5-ADJCHG: Process 123, Nbr 10.10.9.1 … from LOADING to FULL`
> Notice the informational message confirming that D2 has established a neighbour relationship with D1.

**Generated guide (L1 Guided):**

```markdown
> **Concept:** A `network` statement does not advertise a prefix. It *selects interfaces*:
> any interface whose primary address matches the address/wildcard pair joins the given area, and
> OSPF then advertises that interface's real prefix. Wildcard bits set to 1 mean "don't care"
> (Book §8.3). Syntax pattern: `network <address> <wildcard> area <area-id>`.

### Step 2: Enable OSPF on D2 using subnet-matching wildcard masks.

> **Predict:** The moment D2's transit interface joins area 0, which console message do you expect,
> and which neighbour will it name?

<div class="answer short"></div>

a. In process 123, place D2's transit interface in area 0 with **one** statement that matches the
   entire /29 subnet, not just D2's own address. Work the wildcard out yourself. (**Hint H2.2a**)

b. Place both D2 LAN interfaces in area 0. Try to do it with a single statement that matches
   exactly those two /24s and nothing else. (**Hint H2.2b**)

> **Checkpoint:** D2 reaches FULL with D1, and D2's routing-protocol summary lists exactly the
> statements you entered. Verify with `show ip protocols | section ospf`.

> **Question:** Write down the single wildcard you used in step b. Which addresses does it match,
> and could it accidentally match anything outside the two LANs?

<div class="answer"></div>
```

**Hint appendix entry:**

```markdown
### H2.2b
- **Level 1:** Two adjacent /24s can be covered by one /23-sized match, if they are aligned.
- **Level 2:** Write the third octets (24 and 25) in binary. Which bits differ? Only those bits may be "don't care".
- **Level 3:** `network <first-subnet-address> <wildcard with exactly one don't-care bit in the third octet> area <area-id>`
```

**Answer key entry:** the exact commands with prompts, the expected adjacency message, and the model answer: "`0.0.1.255` matches 10.10.24.0–10.10.25.255 only, because 24 and 25 differ in the last bit of the third octet alone. A mask like 0.0.254.255 would match every even third octet instead."
