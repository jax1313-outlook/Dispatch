# DISPATCH_SPINE_OWNERSHIP_PARTITION_AMENDMENT_v1

**Document Type:** Amendment to the Deterministic Runtime definition
**Program:** Dispatch
**Amends:** `DISPATCH_CONSTITUTION_v3` §6.4 · `DISPATCH_SPINE_OVERVIEW` · `DISPATCH_SPINE_SPECIFICATION_v1`
**Authority:** Mike Zachary. Adopted by his architectural adjudication of 2026-08-21.
**Status:** Adopted as to partitions. Capacity amendment approved in principle, blocked from implementation.

---

## 1. The adjudication

**Dispatch Spine remains the single deterministic runtime element** named by Constitution v3 §6.4
and governed by `DISPATCH_SPINE_SPECIFICATION_v1`.

**Mission, Scheduling and Orchestration are adopted as named deterministic ownership partitions
inside Dispatch Spine.** They are:

- **not** departments
- **not** agents
- **not** independent systems
- **not** replacements for Dispatch Spine

They exercise **no judgment and no discretion**.

## 2. The three ownership questions

A partition is defined by the question it alone answers. Any function whose ownership is disputed is
resolved by asking which question it answers.

| Partition | Ownership question |
|---|---|
| **Mission** | Where does this load stand, and what evidence supports that standing? |
| **Scheduling** | Does this proposed commitment fit approved time, capacity, reserve, conflict, and repositioning rules? |
| **Orchestration** | What approved deterministic action happens next, and where is the work handed? |

## 3. Partition assignment of the Spine's existing responsibilities

`DISPATCH_SPINE_SPECIFICATION_v1` §3 lists sixteen responsibilities in one flat list with no
statement of which answers which question. This amendment assigns each to exactly one partition.
**No responsibility is added, removed, or changed** — only assigned.

| Spine §3 responsibility | Partition |
|---|---|
| work item creation | Mission |
| work item state tracking | Mission |
| allowed state transitions | Mission |
| required field validation | Mission |
| schema validation | Mission |
| audit logging | Mission |
| approval event recording | Mission |
| routing table execution | Orchestration |
| queue assignment | Orchestration |
| event logging | Orchestration |
| Portal card generation triggers | Orchestration |
| Archive handoff triggers | Orchestration |
| Library candidate routing | Orchestration |
| approved automation hooks | Orchestration |
| conflict event recording | All three — each partition's failure mode is *raise a card* |
| scoring formula execution | **None.** Remains an Intelligence responsibility governed by scoring doctrine. Both the Spine (§13, "scoring may recommend but may not decide") and the proposed package agree scoring is not a layer function. |

**Scheduling receives no existing Spine responsibility.** Every function it would own — capacity
truth, reserve status, conflict detection across committed work, feasibility verdicts, sole calendar
write access — is absent from Spine §3 and from Spine §15's routing categories. Scheduling is an
addition, not a re-description.

## 4. The capacity amendment

Amendment of **Spine §3 and §15** to include capacity responsibilities is **approved in principle**
and **blocked from implementation** until `RESERVE_CAPACITY_DOCTRINE` and
`JACKSONVILLE_REPOSITIONING_DOCTRINE` are supplied and adopted.

Until then:

- No capacity function may be built.
- No feasibility verdict may be produced.
- Spine §3 and §15 remain unedited. This document records the approval; it does not perform it.

The reason is stated in the Scheduling ownership question itself: it asks whether a commitment fits
*approved* rules. There are no approved rules yet, so the question has no answer and the partition
has nothing to enforce.

## 5. What this amendment does not change

| | |
|---|---|
| The Spine's non-responsibilities | Unchanged. Spine §4 stands in full: the Spine may not approve, submit externally, book a load, sign a document, certify compliance, decide rates, decide legal sufficiency, invent missing facts, or interpret business meaning beyond deterministic rules. Each partition inherits every one of these. |
| Human approval gates | Unchanged. Spine §19's nine gates remain, Portal-mediated and audit-logged. |
| Build readiness | Unchanged. Spine §20 still governs, and Spine §21 still states that the specification does not authorize implementation by itself. This amendment does not authorize implementation either. |
| The state models | Unchanged and separate — see the state-model adjudication recorded in `DECISION_LOG.md`. The Mission partition owns freight execution state; the Spine work-item state model governs review, routing, approval, conflict and processing. Neither may be merged into the other. |
| Manager | Unchanged and dormant. Nothing in this amendment touches, revives, or references Manager as an operating element. |

## 6. The discretion rule, restated once for all three partitions

> A partition may **evaluate**, **refuse**, and **raise**.
> A partition may never **choose between two legitimate options**.

A partition observed making a judgment call is a **defect report**, not a feature request. This is
the same rule already stated in Spine §4 and in Constitution v3 §4 and §12; it is repeated here so a
builder holding only this document still holds the fence.

## 7. Citation form

Partitions are cited as **Spine partitions**, never as standalone elements:

- Correct: *"the Mission partition of Dispatch Spine"*, *"Spine/Mission"*
- Incorrect: *"the Mission Layer"*, *"Mission Layer Constitution"*, *"the Mission service"*

The proposed `MISSION_LAYER_CONSTITUTION_v1`, `SCHEDULING_LAYER_CONSTITUTION_v1` and
`ORCHESTRATION_LAYER_CONSTITUTION_v1` are **source material for partition definition**, not adopted
constitutions. Their boundary rules (M-01…M-08, S-01…S-08, ORC-01…ORC-07) may be cited as proposed
rules pending adoption, and must not be cited as governing.

## 8. Known naming hazard

The repository already uses `mission_visibility` (`dispatch/services.py:341`) to mean a narrow,
externally-safe read-only projection of one load's status — not mission state itself, and not this
partition. A builder reading "Mission" in a governance document and `get_mission_visibility()` in
code will meet two different meanings of the same word.

Recommended, not adopted: rename the code-level concept to `external_load_status` at the next
occasion that touches it, or state explicitly in the ontology that `mission_visibility` is a
Presentation projection and not a Mission-partition record. **No code change is authorized here.**

## 9. Amendment

Amendable only by Mike Zachary. Adding a fourth partition requires stating its ownership question
and demonstrating that no existing partition answers it.
