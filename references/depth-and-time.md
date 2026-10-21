# Depth levels and the time budget

The learner's time is the scarcest resource in a lab and the place where its value is created or wasted. A lab that runs an hour over its estimate isn't "more thorough". It loses learners halfway, and it teaches the ones who stay that the estimates can't be trusted. Every minute in the guide must earn its place.

The user picks a **depth level** at intake. It sets the time budget and decides how far the lab goes beyond the input. `labkit.py build` enforces the budget (§6).

## 1. The four levels

| Level | Target per lab | Hard cap | Chapter coverage | Beyond the input |
|---|---|---|---|---|
| **1 Low** | 45–60 min | 70 min | The **core** concepts only (§3): what the chapter's objectives are built on. The rest become quick questions or are deferred. | None. At most a one-line pointer in a Reflection question. |
| **2 Medium** (default) | about 90 min | 110 min | Every **core** and **support** concept. Failure modes mostly through tickets. Theory and design as quick questions. | One short **deep dive** (≤ 10 min) into the most important mechanism, plus at most one small, useful item from outside the input that passes the track test (§2). |
| **3 High** | about 180 min | 210 min | Everything, including the alternative methods compared side by side, and most failure modes as Break it experiments. | Two deep dives and 1–2 Beyond the Book items. |
| **4 Max** | as long as the content needs, but each lab ≤ 240 min | 240 min per lab | Every concept at full depth, including edge cases, platform limits with substitute exercises, and interactions with earlier chapters. | 2–3 Beyond the Book items per lab, each passing the track test. Beyond 240 minutes, split into a series of labs (§5). |

The structure per level:

| | Low | Medium | High | Max |
|---|---|---|---|---|
| Readiness Check | 3 questions | 3–4 | 4–5 | 5–6 |
| Feature Parts | 2 | 2–3 | 3–4, one of them open (L3) | 4–5 per lab, with an L3 Part |
| Break it experiments | 0–1 | 1–2 | 2–4 | every failure mode not used in a ticket |
| Troubleshooting tickets | 1–2 | 2 | 3 | 3–4 |
| Challenge | none | optional, not counted in the budget | yes | yes |
| Reflection questions | 1–2 | 2 | 2–3 | 3 |

If the user doesn't choose, use Medium.

## 2. The track test: how far "beyond" may go

Anything not in the input file (deep dives, Beyond the Book items, extra facts) must pass **all three** checks:

1. **On track.** It deepens a concept the chapter teaches, or connects it to a topic on the same certification track or exam blueprint, or to an earlier chapter of the same book.
2. **Useful.** A practitioner on this track would actually use it: in operations, in troubleshooting, or for a design decision.
3. **Verifiable.** The learner can see it on the lab's own platform. If they can't, it isn't worth their lab time.

If any check fails, leave it out. Never introduce a technology the chapter doesn't motivate. Max goes *deeper* into the chapter's topics, not *wider* into new ones.

## 3. Triage the concepts first

While building `concept-map.md`, give every concept a **tier**:

| Tier | Meaning | Low | Medium | High / Max |
|---|---|---|---|---|
| **Core** | The chapter can't be understood or applied without it | Task or observation step | Task or observation step | Task or observation step |
| **Support** | Important, but builds on the core: tuning, variants, secondary mechanisms | Quick question, or deferred | Step, often merged with a core step (§4) | Own step |
| **Extra** | Niche detail, rare cases, history, exotic options | Deferred | Quick question, or deferred | Step (High: selectively; Max: all that pass the track test) |

A **quick question** is a 1–2 minute Readiness or Reflection question. It's the cheapest way to cover theory, design and rare cases without spending lab time. **Deferred** concepts are listed in the concept map's coverage summary with the reason, e.g. "C31 deferred (depth: Low)", so the user can see exactly what a higher depth would add.

## 4. Spend time wisely: design techniques

Apply these before cutting content. They keep the learning and remove the waiting, typing and repetition.

1. **One observation, several concepts.** Design a step so that one command shows two or three mechanisms at once. For example, one neighbour table can show the election result, the timers and the network type. Ask about them together.
2. **Each failure appears once.** A failure mode is either a Break it *or* a ticket, never both. Use tickets for the failures that are hardest to spot.
3. **Repetition only where it teaches.** The learner configures the first device in full. For identical configuration on further devices, let them load the checkpoint config instead, unless doing it again unaided is the point (the L2 fading step). Typing the same block four times teaches typing.
4. **The baseline absorbs everything that isn't the lesson.** Addressing, hostnames, earlier chapters' protocols and every prerequisite go into the initial configs.
5. **Theory goes into questions, not steps.** THEORY, DESIGN and history are covered by a 2-minute written question, not a 10-minute task.
6. **No waiting.** Avoid steps that wait for long timers, reloads or slow convergence. Use a `clear` command, a shorter timer set in the baseline, or a smaller topology, and say why in the guide if it changes behaviour.
7. **Short concept text.** Two to four sentences plus the book reference. The book is the textbook; the guide is the workbench.
8. **Merge Parts that share a setup.** Two short Parts on the same devices and state are usually one Part with two steps, which saves the re-orientation time between them.
9. **Optional extras for fast learners.** At Medium and above, add at most one clearly marked optional item (heading ends in `(optional, N min)`). It isn't counted in the budget, so fast learners can go deeper without costing the others anything.
10. **Split, don't stretch.** If the core and support concepts don't fit the budget after all the above, split the chapter into several labs at the same depth (§5) rather than exceed the cap.

**Never cut:**

- Part 1's checkpoint
- at least one Predict and one Explain question per Part
- at least one ticket (two at Medium and above)
- any core concept

## 5. One lab or several

Split when the planned time exceeds the level's hard cap after applying §4, or when the concepts need different topologies. Each lab of a series has the same depth, its own budget and its own folder (`lab-01-<slug>`, `lab-02-<slug>`). At Max, a series is normal for a large chapter. At Low and Medium, prefer fitting the core into one lab and deferring the rest.

## 6. Budget, then build

1. **Plan before writing.** At the end of `concept-map.md`, add a `## Time plan` table: Part, what it covers, minutes. Use the costs below. The total must be at or under the target. Going up to the hard cap needs a one-line reason in the plan.
2. **Write the estimate into every heading** that the learner works through:
   - `## Part 2: Configure and Verify OSPF (20 min)`
   - `## Before You Start: Readiness Check (6 min)`
   - `## Reflection Questions (5 min)`
   - `## Part 6: Challenge (optional, 25 min)`
3. **Set `depth:`** in `topology.yaml` (`low`, `medium`, `high` or `max`).
4. **Build.** `labkit.py build` adds up the headings, fills in the `<!-- @time -->` marker with the learner-facing estimate, and fails the lint when:
   - a Part heading has no estimate
   - the total exceeds the level's hard cap
   - the headings add up to clearly less than the content needs. It counts steps, Break its, tickets, acceptance rows and questions. Estimates have to be honest.

**Time costs** for a learner at the course's level, including reading, predicting, typing and writing answers:

| Building block | Minutes |
|---|---|
| Readiness or Reflection question | 2 each |
| Part 1 (load the baseline, boot, verify) | 8–12 |
| Guided (L1) step: concept, predict, task, checkpoint, question | 7–10 |
| Semi-guided (L2) step | 6–10 |
| Open (L3) Part | about 5 per requirement, plus 5 for the acceptance table |
| Break it experiment | 5–8 |
| Deep dive step | 5–10 |
| Troubleshooting ticket (load, isolate, fix, verify, worksheet) | 12–20 |
| Challenge | 20–30 |
| Command reference fill-in | 5 |

**Example Medium budget (90 min):** Readiness 6 · Part 1 10 · Part 2 (3 guided steps) 25 · Part 3 (2 semi-guided steps, 1 Break it, the deep dive) 22 · Part 4 tickets (2) 24 · Reflection 4 → 91 min, with the Challenge as an optional extra.
