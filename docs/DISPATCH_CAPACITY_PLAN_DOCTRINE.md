# DISPATCH CAPACITY PLAN DOCTRINE

Status: DOCTRINE. Issued by the operator, 30 August 2026. Supersedes earlier drafts of the
day/commitment model in `DISPATCH_LOAD_ARRANGEMENT_SPEC.md` §7a.

---

## 1. The doctrine

**Day plans, stop sequences, and capacity allocations remain recommendations until approved
by human authority.**

**Locking a day records the currently approved execution plan. It does not create an
immutable schedule.**

A materially better opportunity may justify reopening a locked plan.

### The system may

- Continuously evaluate new opportunities
- Compare an opportunity against the current day
- Determine whether it still fits available capacity
- Determine whether it materially improves the day
- Propose reopening a locked day
- Propose a revised stop sequence
- Propose revised capacity allocations
- Explain the expected financial and operational effects
- Identify affected Mission Records and commitments

### The system may not

- Reopen a locked day autonomously
- Cancel or displace an accepted Mission autonomously
- Replace the approved stop sequence autonomously
- Alter broker commitments autonomously
- Modify the Outlook calendar autonomously outside approved rules
- **Treat a high score as authority to change the plan**

**Only authorized human authority may reopen the day, approve the revised plan, and
authorize resulting changes. Human authority remains final.**

## 2. The two objects

The operator's model resolves the day and the commitment into two objects with two jobs.

```
Capacity Plan  (the vehicle day — execution planning)
├── Vehicle Day
├── Stop Sequence
├── Capacity Allocation
├── Route Sequence
└── Remaining Capacity
        ▲
        │  Mission Records attach to Capacity Plans.
        │  Capacity Plans do not replace Mission Records.
        │
Mission Record  (the commitment — per broker)
```

| | **Mission Record** | **Capacity Plan** |
|---|---|---|
| Is | a **commitment** | an **execution plan** |
| Owns | the freight, the rate, the broker, the customer | the vehicle day, stop order, allocations, remaining capacity |
| Identity | mission number + their load number | vehicle + day |
| May span | **multiple days** — pickup Tuesday, delivery Thursday | one vehicle day |
| Changeable | no — a promise was made | **yes, by approved replanning** |
| Authoritative for | what was promised | what is being executed |

**One vehicle day may contain** one Mission, multiple Missions, multiple brokers, multiple
stakeholders, and multiple stops.

### How this resolves the earlier drafts

Two earlier framings were both partly right, and this settles them:

- *Execution is not fragmented — one truck, one route, one driver.* **True**, and it is the
  **Capacity Plan** that carries that unity. The driver sees one day, one route, one plan.
- *A commitment to a broker needs a durable identity across days.* **True**, and it is the
  **Mission Record** that carries it, unchanged from existing doctrine.

The driver's single view and the commitment's durable identity are different objects. An
earlier draft collapsed them into one and lost the second.

## 3. Stakeholder visibility

**Each stakeholder sees only their own:**

- Load Number
- Documents
- Proof Artifacts
- Tracking Information
- Status

Six brokers may share a vehicle day. **No broker sees another broker's freight, rate,
customer, or stops.** The Capacity Plan is the operator's view. It is never a stakeholder's
view.

This is a boundary with real consequences: any artifact, message, or tracking link produced
for a stakeholder is scoped to their Mission Record alone. A shared vehicle day must never
leak through a document, a status page, or a route map.

## 4. BOOK IT DANO

**A locked capacity plan exists to support profitable operations. It shall not prevent the
operator from accepting a materially superior opportunity merely because the current day
was previously approved.**

This is the rule that stops the system's own planning from becoming an obstacle to the
business it exists to serve.

### What Dispatch compares

When an opportunity could materially improve the current day, it is compared against:

| | |
|---|---|
| Existing accepted Mission commitments | Revenue |
| Pickup and delivery windows | Revenue per hour |
| Remaining pallet capacity | Return-position value |
| Remaining weight capacity | Route feasibility |
| Remaining cube capacity | Mission risk |
| Stop sequence | Reserve Capacity policy |
| Deadhead | Effect on the existing day's profitability |

### What Dispatch presents

- Current approved plan
- Proposed revised plan
- Expected improvement
- Existing commitments affected
- Capacity changes
- Schedule changes
- Route changes
- Risks
- Required communications
- Recommended action

**The operator decides.**

### The authorization

When the operator issues the equivalent of **BOOK IT DANO**, the system records the human
authorization and begins the approved replanning workflow.

`BOOK IT DANO` is the explicit human decision to replace the currently approved plan with a
superior one. It is recorded with who and when, like every other decision.

### What this changes about reopening

An earlier draft treated reopening as purely reactive — something that happens when a day
breaks. This doctrine makes it **proactive**: the system watches for better opportunities
and raises them, unprompted, against a plan that is already locked.

The re-reasoning rule still holds. What changes is who starts the conversation.

**Both plans are shown side by side.** The current approved plan is not replaced by a
proposal; it stands until a human authorizes the change. Presenting only the new plan would
make the recommendation an act.

## 5. Rescheduling

**Stop sequencing is not a commitment. Pickup and delivery obligations are commitments.**

The system may recommend alternate stop sequences. **Human authority approves sequence
changes.**

## 6. Durable allocation identity

Capacity allocations may move between days, keeping their identity.

```
Allocation A-4471
Tuesday  →  Rescheduled  →  Thursday
```

The allocation identity remains constant. The history remains traceable.

## 7. JOE authority

| JOE may | JOE may not |
|---|---|
| Analyze capacity | Lock a day |
| Analyze routes | Reopen a day |
| Analyze stop order | Alter commitments |
| Recommend locking a day | Commit capacity |
| Recommend reopening a day | |
| Recommend alternate sequencing | |

**Human authority remains final.** Nothing here extends JOE's permitted functions; it
states how they apply to capacity planning.

## 8. Avoid list

**Avoid List is a blocking condition. Default result: BLOCK.**

Reason: business trust failure — for example, non-payment.

**Avoid status may be removed by authorized human authority after remediation** such as
full payment or a settled dispute.

**Avoid status does not become permanent by default.** The list records a current state, not
a verdict.

## 9. Planned empty days

**Planned empty days are valid operational records.**

Examples: maintenance, recovery, personal time, Reserve Capacity, seasonal recovery.

**The system shall not treat planned empty days as missing work requiring correction.**

## 10. Vehicle capacity — NOT YET CONFIGURED

**CONFIRMED, 30 August 2026: the cargo van and trailer have not been purchased.** Every
specification is therefore unknown, and none may be invented.

| | Specification | Operator target |
|---|---|---|
| Vehicle | Cargo van with trailer | — |
| Payload | **UNCONFIGURED** | 10,000 lb (payload, not GVWR) |
| Pallet positions | **UNCONFIGURED** | 6 |
| Cube capacity | **UNCONFIGURED** | none stated |
| Length / width / height | **UNCONFIGURED** | none stated |

Targets inform planning. **They are never inputs to a calculation.**

**INFERRED, and requiring the operator's confirmation, not this document's:** a payload of
10,000 lb means combined gross vehicle weight rating is materially above 10,001 lb, which is
the FMCSA threshold at which federal hours-of-service rules attach. The profile should
therefore default to **HOS applying**, and `hours_available_default` is a real constraint
rather than a planning convenience.

**This is a regulatory question and the operator's to settle**, not one this document
decides. Defaulting to HOS applying is the safe direction: planning as though the rules
apply when they do not costs some efficiency; planning as though they do not when they do
is a violation.
