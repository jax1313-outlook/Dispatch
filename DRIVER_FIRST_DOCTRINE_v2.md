# DRIVER_FIRST_DOCTRINE_v2

**Document Type:** Governing Doctrine, subordinate to `DISPATCH_CONSTITUTION_v3`
**Program:** Dispatch
**Owner:** Mike Zachary / Level 1 Transport
**Supersedes:** `DRIVER_FIRST_DOCTRINE_v1` — renumbered only. **No clause meaning was changed.**
**Status:** Proposed for adoption. Not yet adopted.
**Authority:** Mike Zachary remains final authority.

---

## 0. Why v2 exists

`DRIVER_FIRST_DOCTRINE_v1` was substantively accepted. It was not adopted because **its clause
numbers collided with citations already live in shipped, tested code.**

| Clause | What the repository has meant by it since before v1 was written | What v1 assigned to that number |
|---|---|---|
| **D6** | Operational retrieval — read-only Load Search, plain operational language, blocked action controls | Startup Must Be Simple |
| **D9** | No accidental modification from a lookup flow (always cited paired with D6) | Session Is Not System |
| **D11** | The external disclosure chain — what a broker, shipper or customer may be shown | Driver Time Is Valuable |

Adopting v1 as written would have silently re-pointed every existing citation at a different rule.
The most serious case is D11: the rule governing **what an external party sees** would have come to
read *"Driver Time Is Valuable."*

v2 pins D6, D9 and D11 to their established meanings, adds the external-disclosure doctrine that v1
omitted entirely, and relocates the three displaced clauses. **Nine of v1's twelve clauses keep
their number unchanged.**

### Renumbering principle

> Pinned numbers are immovable. Among the rest, prefer **minimum disturbance** over thematic
> grouping — every number that moves is a future mis-citation.

Clause numbers are **identifiers, not an ordering**. §1 below groups the clauses thematically for
reading; the numbers carry no sequence.

---

## 1. Doctrine at a glance

| Theme | Clauses |
|---|---|
| Who Dispatch serves | D1 Driver Is The Customer · D15 Driver Time Is Valuable |
| Cognitive load | D2 The 70 MPH Test · D3 Reduce Cognitive Load · **D6 Operational Retrieval** |
| Truth and ownership | D4 Single Source Of Truth · D5 Portal Is A Window · **D9 Retrieval Is Not Modification** |
| Disclosure | **D11 External Disclosure Chain** |
| Authority | D10 Human Authority |
| Operating lifecycle | D13 Startup Must Be Simple · D7 Shutdown Must Be Simple · D8 Reset Is Normal · D14 Session Is Not System |
| Acceptance | D12 Acceptance Test |

**Bold** = pinned to an existing code citation.

---

## 2. Purpose

Dispatch exists to reduce owner/operator cognitive load.

Dispatch is designed around a commercial vehicle operator actively performing real-world
transportation work. The driver is the primary customer. All architecture, workflow, screens,
automation, reports, and future development shall support the driver first.

---

## 3. The clauses

### D1 · Driver Is The Customer
*(unchanged from v1)*

Dispatch serves the driver. The driver does not serve Dispatch.

If a workflow increases driver burden without providing significant operational value, the workflow
should be reviewed.

### D2 · The 70 MPH Test
*(unchanged from v1)*

Every feature shall pass the 70 MPH Test:

> Can the driver obtain the needed information within seconds during real-world operations?

If the answer is no, redesign the feature.

### D3 · Reduce Cognitive Load
*(unchanged from v1)*

Dispatch shall hide complexity whenever practical. Dispatch shall perform calculations, analysis,
sorting, routing, and organization whenever possible.

The driver should receive **information, decisions required, warnings, and recommendations** rather
than raw system complexity.

### D4 · Single Source Of Truth
*(unchanged from v1)*

The driver shall not be required to maintain duplicate records:

> One Calendar · One Mission State · One Record System · One Source Of Operational Truth

Dispatch may present information. **Presentation does not create ownership.**

### D5 · Portal Is A Window
*(unchanged from v1)*

The Driver Portal is a presentation surface. The Driver Portal is not a source of truth.
The Website is a presentation surface. The Website is not a source of truth.

If Portal and Source disagree: **Source Wins.**

### D6 · Operational Retrieval
**PINNED — this number was already in use. Meaning preserved from existing code citations.**

The driver must be able to find an operational record using the identifiers he actually has on hand
— load number, customer, broker, pickup or delivery location, driver name, or a reference written in
a note — not the identifiers the system finds convenient.

Retrieval surfaces shall use **plain operational language**, not generic system labels.

A retrieval surface shall not offer controls that create, modify, delete, archive, complete,
dispatch, or send. Finding something is not doing something to it.

> This clause is the retrieval-specific application of D2 and D3. It is pinned to D6 because
> `dispatch/store.py`, `portal/routes/pages.py` and two test modules have cited "D6" with this
> meaning since before v1 was drafted.

### D7 · Shutdown Must Be Simple
*(unchanged from v1)*

End of day operations shall not require technical procedures. Shutdown should consist of:

> Finish Work · Close Dispatch · Power Off Device · Go Home

The owner/operator is not expected to perform system administration.

### D8 · Reset Is Normal
*(unchanged from v1)*

Long-running systems accumulate operational junk. Reset is a normal operational activity.

If Dispatch behaves unexpectedly, **Restart Dispatch** is a valid operational response.

> **If Dispatch cannot survive a shutdown and startup cycle, the architecture should be reviewed.**

### D9 · Retrieval Is Not Modification
**PINNED — this number was already in use. Meaning preserved from existing code citations.**

A lookup path shall never become an editing path.

Reaching a record by searching for it shall not expose the ability to change it. Where a record is
reachable both for review and for editing, the retrieval route shall lead to the read-only view.

There shall be no accidental modification from a lookup flow.

> Always cited paired with D6 in existing code. D6 governs *finding*; D9 governs *what finding may
> not do*.

### D10 · Human Authority
*(unchanged from v1)*

Dispatch provides information, analysis, and recommendations.

The human remains responsible for **acceptance, rejection, priority, override, commitment, and
business decisions**.

Dispatch shall not silently assume authority belonging to the owner/operator.

### D11 · External Disclosure Chain
**PINNED and NEW — the doctrine v1 omitted. Meaning preserved from existing code citations.**

Manufacturer, Shipper, Broker and Level 1 Transport are **genuinely distinct parties in a disclosure
chain**, not synonyms for one counterparty.

Each party in the chain is entitled to the commercial terms of the transaction it is party to.
Rate, fee and cost figures are **openly disclosed** to these parties; there is no curtain to build
around the terms of a deal the counterparty is already in.

**Level 1 Transport's own internal economics are never disclosed.** Expense breakdown, profit,
margin, internal scoring, internal notes, private reasoning and operator contact details do not
leave the company, to any external party, in any view.

External access is **scoped to the single record it was granted for**. A link to one load grants
visibility of that load and nothing else.

External visibility is a confidence-building window, never internal system access.

> This clause governs live broker-facing disclosure today. It had no counterpart in v1, which is why
> its absence was the most serious finding of the reconciliation.

### D12 · Acceptance Test
*(unchanged from v1)*

A Driver-First feature passes when the following is true:

> Mike can start the truck, start Dispatch, perform work, shut down Dispatch, go home, return
> tomorrow, start Dispatch, and continue operations **without technical intervention**.

If this condition is not satisfied, the design should be reviewed.

### D13 · Startup Must Be Simple
*(relocated from v1 D6 — meaning unchanged)*

Beginning work shall not require technical procedures. Startup should consist of:

> Power On · Open Dispatch · Resume Operations

**Dispatch performs reconciliation. The driver performs work.**

### D14 · Session Is Not System
*(relocated from v1 D9 — meaning unchanged)*

The driver's local operating session may end. Dispatch operations may continue.

Examples may include approved notifications, monitoring, tracking, and server-side scheduled
operations.

A driver ending the workday does not automatically imply all Dispatch operations cease.

> **Compliance note, recorded not resolved:** no server-side scheduled operation exists in the
> repository today — there is no scheduler, cron entry, worker, thread or daemon. D14 currently
> describes intent the architecture does not yet have. Closing that gap requires Overnight
> Operations Doctrine, which is unwritten.

### D15 · Driver Time Is Valuable
*(relocated from v1 D11 — meaning unchanged)*

Every unnecessary click, screen, workflow, duplicate entry, manual transfer, or repeated action
consumes driver time. Time spent operating Dispatch is time not spent hauling freight.

Dispatch shall minimize administrative burden whenever practical.

---

## 4. Authoritative citation map

The single authoritative mapping. Any other mapping is superseded.

| v2 | Clause | v1 number | Change |
|---|---|---|---|
| D1 | Driver Is The Customer | D1 | none |
| D2 | The 70 MPH Test | D2 | none |
| D3 | Reduce Cognitive Load | D3 | none |
| D4 | Single Source Of Truth | D4 | none |
| D5 | Portal Is A Window | D5 | none |
| **D6** | **Operational Retrieval** | — | **new clause, pinned to existing citations** |
| D7 | Shutdown Must Be Simple | D7 | none |
| D8 | Reset Is Normal | D8 | none |
| **D9** | **Retrieval Is Not Modification** | — | **new clause, pinned to existing citations** |
| D10 | Human Authority | D10 | none |
| **D11** | **External Disclosure Chain** | — | **new clause, pinned to existing citations; absent from v1** |
| D12 | Acceptance Test | D12 | none |
| D13 | Startup Must Be Simple | **D6** | relocated |
| D14 | Session Is Not System | **D9** | relocated |
| D15 | Driver Time Is Valuable | **D11** | relocated |

**Result: every existing repository citation of D6, D9 and D11 remains correct under v2 with no code
change.** The three relocations affect no existing citation, because v1 was never adopted and
nothing cites v1 numbering.

---

## 5. Affected references

Every code, test, docstring, template and governance reference to a Driver-First clause. **All are
correct as written under v2 and require no edit.** Listed so the claim is checkable rather than
asserted.

### 5.1 Citations that become correct-by-construction

| File | Line | Citation | Under v2 |
|---|---|---|---|
| `dispatch/store.py` | 1243 | "Load Search / Operational Retrieval (Driver-First Doctrine D6/D9)" | ✔ exact |
| `portal/routes/pages.py` | 714 | "Read-only load lookup (Driver-First Doctrine D6/D9)" | ✔ exact |
| `tests/test_load_readonly_detail.py` | 2 | "Driver-First Doctrine D6/D9 — no accidental modification from a lookup flow" | ✔ exact |
| `tests/test_load_readonly_detail.py` | 104 | "Driver-First Doctrine (D6/D9): blocked actions" | ✔ exact |
| `tests/test_global_search.py` | 94 | "Driver-First Doctrine (D6): BOL/PO/reference numbers…" | ✔ exact |
| `tests/test_global_search.py` | 196 | "Driver-First Doctrine (D6): plain operational language" | ✔ exact |
| `tests/test_global_search.py` | 202 | "Driver-First Doctrine (D6): blocked actions" | ✔ exact |
| `dispatch/services.py` | 1637 | "rate/fee/cost figure covered by D11's disclosure rule" | ✔ exact |
| `dispatch/services.py` | 1676 | "per D11 these are genuinely distinct" | ✔ exact |
| `dispatch/services.py` | 1682 | "D11 establishes an open-disclosure rule" | ✔ exact |
| `dispatch/services.py` | 1685 | "profit, margin_pct … are EXCLUDED — D11" | ✔ exact |
| `dispatch/services.py` | 1690 | "regardless of D11 … not rate/fee/cost figures" | ✔ exact |
| `portal/routes/stakeholder.py` | 3 | "D11: Manufacturer → Shipper → Broker → Level 1 Transport is a genuine disclosure chain" | ✔ exact |
| `portal/templates/dispatch_detail.html` | 37 | "chain (D11)" | ✔ exact |
| `tests/test_stakeholder_portal.py` | 2 | "D11 disclosure chain" | ✔ exact |
| `tests/test_stakeholder_portal.py` | 136 | "D11: rate/fee/cost figures ARE shared with this chain" | ✔ exact |
| `tests/test_stakeholder_portal.py` | 152 | "figure covered by D11 — it must never reach this external view" | ✔ exact |

**17 clause citations across 8 files. Zero require editing.**

### 5.1b The one reference that does go stale

| File | Line | Reference | Under v2 |
|---|---|---|---|
| `portal/models/operations_feed.py` | 18 | *"independently corroborates Driver-First Doctrine's 'Mike decides' posture (§0)"* | ⚠ **section reference, not a clause.** v1 §0 was the Purpose section; v2 §0 is the renumbering rationale and Purpose moved to §2. The posture it names is now **D10 Human Authority**. |

This is the only reference in the repository that v2 invalidates, and it invalidates only the
section pointer, not the statement. Recommended correction, deferred until numbering is approved:
cite **D10** instead of §0. One docstring line, in one file.

### 5.2 Governance references

| Document | Reference | Under v2 |
|---|---|---|
| `DISPATCH_REPO_RECONCILIATION_PLAN_v1` | Reports Driver-First as UNDEFINED | Superseded by this document |
| `DISPATCH_ARCHITECTURE_ALIGNMENT_v1` | Reports the clause collision | Resolved by this document |
| `DISPATCH_BUILD_MATRIX_v2` | Cites D4 for the calendar and duplicate-state corrective missions | ✔ correct — D4 unchanged |

---

## 6. Second collision layer — found during this reconciliation, NOT resolved here

The repository contains **at least three separate `D<n>` registers**, all cited in bare form. Only
the Driver-First ones say "Driver-First Doctrine".

| Register | Evidence | Numbers in use |
|---|---|---|
| **Driver-First Doctrine** | Always labelled | D6, D9, D11 |
| **Deployment decision register** | `tests/test_status_transition_gate.py:1,3` — *"the deployment decision register's D1 item"*; also `tests/test_dispatch.py:496,519,860` | D1 |
| **Requirements register** | `tests/test_email_helper.py:1` (D3 pipeline) · `tests/test_integrations_registry.py:1` (D4 System Keys) · `tests/test_email_archive_handling.py:1` (D10 Email Archive Handling) · `portal/models/email_helper.py:3` | D3, D4, D10 |

A bare "D3", "D4" or "D10" is therefore **ambiguous today**, and adopting Driver-First D1–D15
widens the overlap.

**Recommended, not adopted:** cite Driver-First clauses with an explicit prefix — `DF-6`, `DF-9`,
`DF-11` — and give the other registers their own prefixes. This is a documentation-only change,
mechanical, and safe to fold into the first mission that touches each file. It is **not** performed
here: Decision 4.5 bars code modification until the numbering is approved, and a prefix change would
touch all 17 citations above.

Until a prefix is adopted, the rule is: **a Driver-First citation must name the doctrine.**
`D6` alone is ambiguous; `Driver-First Doctrine D6` is not — which is what every existing citation
already does.

---

## 7. Compliance status at adoption

Recorded so adoption is not mistaken for compliance.

| Clause | Status | Evidence |
|---|---|---|
| D1, D2, D3, D15 | Satisfied | Driver Portal deliberately minimal; operations feed consequence-sorted |
| D4 — One Calendar | **Violated** | `/calendar` renders a month grid from Dispatch's own records — corrective mission C2 |
| D4 — One Mission State | **Violated** | Status copied into `sandbox.card_data.engine_status` — corrective mission C1 |
| D5 | Satisfied by construction | Every surface computed per request; nothing display-side persisted |
| D6, D9 | Satisfied | The clauses were written from the behavior |
| D7 | Vacuously satisfied | Nothing can block a power-off because no shutdown path exists |
| D8 | Satisfied since mission M3 | Route Risk survived no restart before it; verified across two processes |
| D10 | Enforced | `RESERVED_SYSTEM_IDENTITIES` — machine identities cannot approve, promote or submit |
| D11 | Satisfied | Token-scoped, IDOR-checked, internal economics withheld |
| D12 | Partially satisfied | Passes for stored records; untested across a full operating day — no session concept exists |
| D13 | **Not satisfied** | No startup function exists |
| D14 | **Not satisfied** | No server-side scheduled operation exists |

## 8. Amendment

Amendable only by Mike Zachary. **A pinned clause number may not be reassigned** — D6, D9 and D11
are bound to live citations. Adding a clause takes the next free number.
