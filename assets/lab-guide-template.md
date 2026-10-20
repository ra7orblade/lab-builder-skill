# Lab - {{Verb}} {{Technology}}

<p class="meta">{{Book title}} · Chapter {{N}}: {{Chapter title}} · Estimated time: {{90-180 min}} · Platform: {{platform / images / emulator}}</p>

## Topology

![Topology](topology/topology.svg)

## Addressing Table

<!-- @table addressing -->

{{Optional extra table (AS / router IDs / VLANs / keys / logins). Delete if none.}}

## Objectives

<!-- @objectives -->

## Background / Scenario

{{Paragraph 1: a concrete scenario. Who runs this network, what problem they have, and why this technology is the answer.}}

{{Paragraph 2: what you will build, observe and break. Name the mechanisms you will watch happen.}}

> **Note:** This lab is an exercise in deploying, observing and troubleshooting {{technology}}. It does not necessarily reflect production best practices.

> **Note:** {{Platform and version used; how the interface names and metrics differ from the book.}}

## Required Resources

- {{devices and images, RAM}}
- {{emulator lab name or import file}}
- This lab folder: `initial-configs/`, `topology/`, `solutions/`

## Before You Start: Readiness Check

<!-- @include skill:snippets/readiness-intro.md -->

1. {{Load-bearing theory question}} *(Book: {{section}})*
2. {{...}} *(Book: {{section}})*
3. {{...}} *(Book: {{section}})*

<div class="answer tall"></div>

## How to Use This Guide

<!-- @include skill:snippets/how-to-use.md -->

# Instructions

## Part 1: Build the Network and Load the Initial Configurations

In Part 1 you start the topology and confirm the baseline. The baseline contains {{exact list}}. Everything this chapter covers is deliberately missing.

### Step 1: Build the topology.

a. {{Open the emulator lab "<name>" / import topology/cml-lab.yaml / cable as shown.}}

### Step 2: Prepare the devices.

a. {{Saving a rollback point, log buffer, anything needed later. Command blocks here need <!-- leak-ok --> on the line before.}}

### Step 3: Verify the baseline.

a. {{What to check.}}

> **Checkpoint:** {{Binary, observable. E.g. every direct link answers a ping; no chapter feature is running.}}

## Part 2: {{Configure and Verify <core feature>}}

{{What this part builds and why it comes first. Two sentences.}}

> **Concept:** {{3-6 sentences tied to the book section. Generic syntax templates with placeholders are allowed at the L1 level only.}}

### Step 1: {{Imperative title.}}

> **Predict:** {{...}}

<div class="answer short"></div>

a. {{Outcome plus every value needed, never the command.}} (**Hint H2.1**)

> **Checkpoint:** {{Observable criterion.}} Verify with `{{command}}`.

```text
{{Trimmed sample output, only if validated or certain. It must not answer the next question.}}
```

> **Question:** {{Explain what was seen.}}

<div class="answer"></div>

> **Break it:** {{Predict → change → observe → explain → restore.}}

<div class="answer short"></div>

## Part 3: {{Semi-guided part: checkpoints state WHAT must be true, the learner picks the command}}

{{Same building blocks as Part 2, with less help.}}

## Part 4: {{Open part}}

**Requirements**

1. {{Requirement with values}}

**Acceptance criteria**

| # | Test | Pass? |
|---|---|---|
| 1 | {{Observable result}} | |

## Part {{N-2}}: Beyond the Book: {{Topic}}

> **Beyond the book:** {{What this adds beyond the chapter, and why a practitioner needs it.}}

## Part {{N-1}}: Trouble Tickets

<!-- @include skill:snippets/ticket-method.md -->

**Loading a ticket:** {{e.g. import topology/ticket-N.cml.yaml, start it, work in that lab, then delete it}}

### Ticket 1

> **Ticket:** "{{Symptom in an end-user or NOC voice. No hint at the cause.}}"

<!-- @include skill:snippets/ticket-worksheet.md -->

Hint: **H{{N-1}}.1**

## Part {{N}}: Challenge (optional)

{{Import topology/challenge.cml.yaml. Several faults, no hints.}}

| Test | Pass? |
|---|---|
| {{Observable result}} | |

## Reflection Questions

1. {{Transfer question}}

<div class="answer"></div>

2. {{Design or judgement question}}

<div class="answer"></div>

## Build Your Own Command Reference

<!-- @include skill:snippets/command-reference.md -->

<div class="page-break"></div>

## Appendix A: Hint Ladder

<!-- @include skill:snippets/hint-intro.md -->

### H2.1

- **Level 1:** {{concept nudge}}
- **Level 2:** {{location or prerequisite}}
- **Level 3:** {{generic syntax with placeholders, never this lab's values}}

## Appendix B: Platform Notes

- **Interfaces:** {{naming, speeds/metrics that differ from the book}}
- **Reset:** {{rollback command, checkpoint configs, emulator wipe}}
- **Emulator limits:** {{what is emulated rather than real, and how}}
- **Sample outputs:** {{captured on <image/version> | representative, not captured}}
