# Example lab: the expected quality, artifact by artifact

Read this once before writing a lab's guide and answer key. It's a small, complete example: an HSRP lab at Medium depth, using the `cisco-ios` profile. **Match its level of detail, its precision and its structure.** Don't copy its topic or its values into another lab. Every value below is consistent with every other value, and yours must be too.

The topology: R1 and R2 share the user LAN 10.1.10.0/24 (R1 .2, R2 .3, virtual gateway .1, PC1 .10). R1's uplink to R3 is 10.1.13.0/24, R2's is 10.1.23.0/24, and R3 has the "internet" loopback 198.51.100.1/32. OSPF from an earlier chapter is in the baseline on all three routers, including the LAN.

## 1. `concept-map.md` (excerpt)

```markdown
| ID | Concept | Book ref | Kind | Tier | Lab treatment | Where in lab |
|----|---------|----------|------|------|---------------|--------------|
| C01 | Active/standby election: priority, then highest IP | §7.2 | MECH | Core | Predict + observe the election | P2 S1 |
| C02 | Preemption | §7.2 | CONFIG | Core | Task + Break it (without preempt) | P2 S1-S2 |
| C03 | Virtual MAC and why hosts don't notice a failover | §7.1 | MECH | Core | Readiness Q2 + observe ARP on PC1 | RC, P2 S2 |
| C04 | Interface tracking with decrement | §7.4 | CONFIG | Core | Task (L2) + Ticket 1 | P3 S1, T1 |
| C05 | HSRP version 1 vs 2 | §7.3 | THEORY | Support | Reflection Q1 | Reflection |
| C06 | Hello/hold timer tuning | §7.5 | CONFIG | Extra | Deferred (depth: Medium) | - |

Coverage: 5/6 covered, 1 deferred: C06 (timer tuning, Extra tier, depth Medium).

## Time plan

| Part | Covers | Minutes |
|---|---|---|
| Readiness Check | C03 + 2 questions | 6 |
| Part 1 | baseline, OSPF check | 10 |
| Part 2 | C01-C03, L1 | 28 |
| Part 3 | C04 + deep dive (who needs preempt), L2 | 22 |
| Part 4 | 2 tickets | 24 |
| Reflection | C05 + 1 | 4 |
| **Total** | | **94** (target 90, cap 110) |
```

Each concept has a tier, a treatment and a location, or a reason it's deferred. The time plan adds up, and it matches the headings in the guide.

## 2. `topology/topology.yaml` (excerpt)

```yaml
lab:
  title: "Ch7 - HSRP - First-Hop Redundancy"
  short_title: "Ch7 - HSRP"
  depth: medium
  included: "hostname, console, addressing, OSPF area 0 on all routers"
  not_included: "HSRP (you configure it in this lab)"
nodes:
  - name: R1
    role: router
    image: {cml: iol-xe}
    x: -200
    y: 0
    interfaces:
      - {name: Ethernet0/0, ipv4: 10.1.10.2/24, description: "User LAN"}
      - {name: Ethernet0/1, ipv4: 10.1.13.1/24, description: "Uplink to R3"}
      - {name: Ethernet0/2}
      - {name: Ethernet0/3}
```

## 3. Solution deltas: only what each Part adds

`solutions/deltas/R1.part2.cfg`:

```text
interface Ethernet0/0
 standby 10 ip 10.1.10.1
 standby 10 priority 110
 standby 10 preempt
exit
```

`solutions/deltas/R2.part2.cfg`:

```text
interface Ethernet0/0
 standby 10 ip 10.1.10.1
 standby 10 preempt
exit
```

`solutions/deltas/R1.part3.cfg`:

```text
track 1 interface Ethernet0/1 line-protocol
exit
interface Ethernet0/0
 standby 10 track 1 decrement 20
exit
```

`solutions/tickets/ticket-1/R1.delta` is the single fault. It's appended to the final config, so it overrides the decrement of 20:

```text
interface Ethernet0/0
 standby 10 track 1 decrement 5
exit
```

## 4. `lab-guide.md` (excerpts)

```markdown
## Before You Start: Readiness Check (6 min)

<!-- @include skill:snippets/readiness-intro.md -->

1. What decides which router becomes Active when both start at the same time? *(Book: §7.2)*
2. When the Active router fails, why do hosts keep working without changing their default gateway or clearing their ARP cache? *(Book: §7.1)*
3. What does preemption change about the election, and when does it matter? *(Book: §7.2)*

<div class="answer tall"></div>

## Part 2: Configure HSRP and Observe the Election (28 min)

In this part you give the LAN a virtual gateway and decide which router owns it. You'll watch the election happen, then see what preemption changes.

> **Concept:** HSRP routers in the same group share a virtual IP and a virtual MAC. One router is Active and answers for both, while the Standby router listens to its hellos and takes over when they stop. The highest priority wins (default 100), and on a tie the highest interface IP wins. A router with a higher priority takes over from a working Active router only if it is configured to preempt (Book §7.2). Syntax pattern: `standby <group> ip <virtual-ip>`, `standby <group> priority <value>`, `standby <group> preempt`.

### Step 1: Enable HSRP group 10 on both routers.

> **Predict:** You configure R2 first, then R1 with priority 110 and preemption. Which router is Active a minute later, and which log message on R1 tells you?

<div class="answer short"></div>

a. On R2's LAN interface, create HSRP group 10 with virtual IP 10.1.10.1. Leave R2's priority at the default, and enable preemption. (**Hint H2.1**)

b. On R1's LAN interface, create the same group with priority 110 and preemption.

> **Checkpoint:** R1 shows group 10 as Active with R2 (10.1.10.3) as Standby, and R2 shows itself as Standby. Verify with `show standby brief` on both routers.

> **Question:** R2 was already Active when R1 joined. Which setting allowed R1 to take over, and what would have happened without it?

<div class="answer"></div>

### Step 2: Fail over and watch the gateway move.

a. From PC1, start a continuous ping to 198.51.100.1. Shut down R1's LAN interface, wait for R2 to become Active, then bring R1's interface back up.

> **Checkpoint:** While R1's interface is down, R2 is Active. The ping recovers within the hold time (10 seconds by default), and PC1's ARP entry for 10.1.10.1 shows the same MAC address before and after.

> **Question:** Why did PC1's ARP entry for the gateway not change, even though a different router is answering now?

<div class="answer"></div>

> **Break it:** Predict what happens if R1 has no preemption when its interface comes back up. Remove preemption on R1, repeat the failover, and observe which router ends up Active. Explain the difference, then restore preemption.

<div class="answer short"></div>

## Part 3: Track the Uplink (22 min)

R1 is the preferred gateway, but only while its uplink works. In this part, R1 gives up the Active role when its uplink fails.

### Step 1: Make R1's priority depend on its uplink.

> **Predict:** R1 has priority 110 and R2 has 100. By how much must R1's priority drop for R2 to take over, and does R2 need anything else for that to happen?

<div class="answer short"></div>

a. Create a tracking object that follows the line protocol of R1's uplink to R3. When it goes down, R1's priority in group 10 must drop by 20. (**Hint H3.1**)

> **Checkpoint:** With R1's uplink shut down, R2 is Active and PC1's traceroute to 198.51.100.1 goes through R2. With the uplink back up, R1 is Active again. Write down the commands you used to prove both states.

<div class="answer short"></div>

> **Question:** Why does this failover need preemption on R2, and not only on R1?

<div class="answer"></div>

## Part 4: Trouble Tickets (24 min)

<!-- @include skill:snippets/ticket-method.md -->

**Loading a ticket:** import `topology/ticket-1.cml.yaml`, start it, and work in that lab.

### Ticket 1

> **Ticket:** "During last night's maintenance, R1's uplink was down for an hour. Our monitoring expected R2 to become the gateway, but R1 stayed Active the whole time. Please find out why, and make sure the next uplink failure moves the gateway to R2."

<!-- @include skill:snippets/ticket-worksheet.md -->

Hint: **H4.1**

## Appendix A: Hint Ladder

### H2.1

- **Level 1:** HSRP is configured per interface, on the interface that faces the hosts.
- **Level 2:** Both routers need the same group number and the same virtual IP. Priority and preemption are set per router.
- **Level 3:** `standby <group> ip <virtual-ip>` and `standby <group> preempt`, under the LAN interface.

### H3.1

- **Level 1:** Tracking has two parts: an object that watches something, and an HSRP setting that reacts to it.
- **Level 2:** The tracking object is created globally. The decrement is set in the HSRP group on the LAN interface.
- **Level 3:** `track <object> interface <uplink> line-protocol`, then `standby <group> track <object> decrement <value>` under the LAN interface.

### H4.1

- **Level 1:** Reproduce the failure, then compare the two routers' priorities while it lasts.
- **Level 2:** Work out what each router's priority is with the uplink down. Who should win?
- **Level 3:** Look at the HSRP tracking settings on R1's LAN interface: `show standby` lists the tracked objects with their decrements.
```

What this shows:

- Tasks give the outcome and every value (group 10, 10.1.10.1, priority 110, decrement 20), never the command line.
- Each step has one Predict and one Question, and the Predict comes before the output that would answer it.
- Checkpoints are binary and observable. L1 names the command; L2 (Part 3) states what must be true, and the learner chooses and writes down the command.
- Hints go from concept, to location, to a pattern with placeholders. No hint contains a working line with this lab's values.
- The ticket report is in a user's voice, describes the symptom, and doesn't reveal the cause.
- The headings carry the time plan's minutes.

## 5. `solutions/answer-key.md` (excerpts)

```markdown
## Part 2: Configure HSRP and Observe the Election

<!-- @deltas part=2 -->

**Predict:** R1 becomes Active within a few seconds of being configured, because it has the higher priority (110 against 100) and preemption allows it to take over from R2. Its log shows the group changing state from Standby to Active. A common misconception is that the first router configured stays Active "because it was there first". That's only true without preemption.

**Step 1 question:** Preemption on R1. Without it, R1 would stay Standby, despite its higher priority, until R2 failed.

**Step 2 question:** The virtual MAC address belongs to the group, not to a router. The new Active router takes over the virtual MAC and announces it with a gratuitous ARP, so PC1's ARP entry stays valid.

**Break it:** Without preemption, R2 stays Active after R1's interface comes back. R1 becomes Standby although its priority is higher.

## Part 3: Track the Uplink

<!-- @deltas part=3 -->

**Predict:** By more than 10, so a decrement of 20 takes R1 to 90, below R2's 100. And R2 needs preemption: a higher priority alone doesn't take over from a working Active router.

**Checkpoint:** `show standby brief` on both routers (state and priority), and `show track 1` on R1 (object state). From PC1, `traceroute -n 198.51.100.1` shows 10.1.10.3 as the first hop while the uplink is down.

**Question:** When R1's priority drops to 90, R1 is still a working Active router. R2 has the higher priority now (100 > 90), but it only takes over because it's configured to preempt. Without preemption on R2, R1 would stay Active with a dead uplink.

## Part 4: Trouble Tickets

### Ticket 1

<!-- @ticket 1 -->

- **Cause:** R1 decrements its priority by only 5 when the uplink fails: 110 − 5 = 105, which is still higher than R2's 100. So R2 never preempts. Traffic still flows, via R1 and then across the LAN to R2, which is why nobody noticed an outage.
- **Isolation:**
  1. `show standby brief` on both routers with the uplink down: R1 is Active at priority 105, R2 Standby at 100. That shows the election is working as configured.
  2. `show standby` on R1: the tracked object is down, with a decrement of 5. That isolates it to the decrement value.
  3. `show track 1`: the object follows the right interface. That rules out a wrong tracking object.
- **Fix:** set the decrement in group 10 on R1's LAN interface back to 20.
- **Proof:** with the uplink down, R2 becomes Active, and PC1's traceroute to 198.51.100.1 goes through 10.1.10.3. With the uplink up, R1 is Active again. Nothing else changed.
```

The answer key explains *why*, names the misconception each Predict targets, gives the isolation steps in the order an expert would use them with what each rules in or out, and proves the fix without breaking anything else.

## 6. The same content done badly (don't do this)

| Instead of this | Write this |
|---|---|
| "a. Configure `standby 10 priority 110` on R1." (cookbook) | "a. Give R1 priority 110 in group 10." |
| "> **Checkpoint:** Verify that HSRP works." (not observable) | "> **Checkpoint:** R1 is Active and R2 (10.1.10.3) is Standby in `show standby brief`." |
| "Level 3: `standby 10 track 1 decrement 20`" (the answer, with extra steps) | "Level 3: `standby <group> track <object> decrement <value>`" |
| Sample output showing R1 as Active *above* the Predict that asks who becomes Active | The Predict first, the output (or the learner's own command) after it |
| An output block you didn't capture from a device | The expected state in words ("R2 should be Active, R1 Standby"), or output marked as representative in Platform Notes |
| "Ticket: R1's decrement is set to 5." (reveals the cause) | A user's report of what they saw, in their own words |
