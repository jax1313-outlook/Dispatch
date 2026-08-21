# DISPATCH_OWNERSHIP_MATRIX_v1

**Document Type:** Function ownership register
**Program:** Dispatch
**Authority:** Mike Zachary, architectural adjudication of 2026-08-21
**Status:** Reflects the adjudication. Ownership assigned; implementation not authorized.

---

## 1. How to read this

**One accountable owner per function.** Contributors may be many; owners are singular
(Constitution v3; ONT-02 in the unadopted ontology says the same).

Owners are named in the form the adjudication fixed:

- **Spine/Mission**, **Spine/Scheduling**, **Spine/Orchestration** — deterministic ownership
  partitions *inside* Dispatch Spine. Not departments, not agents, not independent systems. They
  evaluate, refuse and raise; they never choose between two legitimate options.
- **Departments** — Intelligence, Publisher, Library, Archive, COMI, Route Risk.
- **Human** — Mike Zachary. Never delegated.
- **External wheel** — Outlook, ELD, accounting, load boards.

**Ownership is assignment, not authorization.** A function with an owner and no doctrine is still
blocked.

## 2. The matrix

| Function | Owner (adjudicated) | Implemented today | Status |
|---|---|---|---|
| **Mission identity** | Spine/Mission | Three identifier schemes — `SBX-`, `LOAD-`, `CIN-` — correlated one way via `engine_load_id` (`portal/routes/api.py:68`) | **Retrieval chain required, migration not authorized.** Decision 3 settles this: one answerable retrieval chain, not one physical identifier. |
| **Mission state** | Spine/Mission | `loads.status`, 11 values (`dispatch/models.py:25`) — **plus a duplicate copy** in `sandbox.card_data.engine_status` | Authoritative model confirmed. Duplicate copy is corrective mission **C1**. |
| **Transitions** | Spine/Mission | `_VALID_TRANSITIONS` + `validate_status_transition()`, enforced on both status paths since M1 | Aligned. Evidence-gating remains unadopted. |
| **Evidence** | Spine/Mission | SHA-256 checksums, fail-closed integrity verification, IDOR-checked external download | Artifacts strong; **binding to transitions absent**. Fable's evidence requirements are to be mapped into the existing model, not made a third model (Decision 2). |
| **Work-item / review state** | Spine (work-item state model) | Not implemented — `work_item`: 0 hits | Governing model for review, routing, approval, conflict, processing. **Coexists with load status. Neither may absorb the other.** |
| **Capacity** | Spine/Scheduling | Nothing | **Blocked.** Reserve Capacity Doctrine unwritten. Spine §3/§15 amendment approved in principle only. |
| **Scheduling** | Spine/Scheduling | Booking-time overlap + turnaround detection, non-blocking warnings (`portal/models/conflict.py:178`) | Posture already correct — advises, never blocks. Capacity half blocked. |
| **Outlook writing** | Spine/Scheduling — sole writer | Nothing. No Outlook, Graph, EWS or iCalendar code exists | **Blocked** on the Outlook integration decision. `/calendar` is corrective mission **C2**. |
| **Triggers** | Spine/Orchestration | 32 hardcoded call sites, no registry, **0 time-based** (`DISPATCH_TRIGGER_AND_SIDE_EFFECT_INVENTORY_v1`) | Owner assigned; registry unbuilt. |
| **Sequences** | Spine/Orchestration | One linear in-process pipeline (contracts). No sequence state held | Owner assigned; unbuilt. |
| **Workflow execution** | Spine/Orchestration | No workflow definitions exist; Library holds approved *records*, not definitions | Owner assigned. ORC-01 (execute only Library-approved definitions) remains **proposed**. |
| **Replay protection** | Spine/Orchestration | 8 mechanisms guarding 14 call sites; 15 sites unguarded | Corrective mission **C4**. Precondition for any unattended operation. |
| **Status-change audit** | Spine/Mission | Asymmetric — `services.update_load()` writes a `status_change` activity; `add_milestone()` does not | Corrective mission **C3**. |
| **COMI routing** | COMI (department) | Implemented — role-based fail-closed sanitization, consequence thresholds (`dispatch/comi_routing.py`) | Aligned. COMI context document still absent. |
| **Route Risk** | Route Risk (department) | Implemented and durable since M3 — ten event types, consequence 0–5, persisted | Aligned. Collection boundary (own feeds vs Intelligence) unresolved. |
| **Scoring** | Intelligence (department) | `dispatch/scoring.py` — deterministic, advisory | **Not a partition function.** Spine §13: scoring may recommend, may not decide. |
| **Startup** | Spine/Orchestration executes; Driver Portal opens the session | Nothing. Directory creation under `__main__`, which gunicorn never runs | Shape fixed by Driver-First D13: Power On · Open Dispatch · Resume Operations. Blocked on active-mission definition and store authority. |
| **Shutdown** | Spine/Orchestration executes; Driver Portal closes the session | Nothing. Nothing can block a power-off | Shape fixed by D7. Non-blocking guarantee currently free — must be preserved deliberately. |
| **Restart** | Reuses the startup path | systemd `Restart=always`. Survives correctly since M3 | Aligned. Reset function still requires the protected set to be adopted. |
| **Dormancy** | Doctrine — human-owned | Undefined, and vacuously true since nothing runs | **Blocked.** Driver-First D14 promises continuation that does not exist. |
| **Overnight operations** | Spine/Orchestration, under doctrine | Nothing runs | Provisional boundary adopted (Decision 7) — **planning only**. |
| **Doctrine and amendment** | **Human — Mike Zachary** | `RESERVED_SYSTEM_IDENTITIES` prevents machine approval in four modules | Enforced. Never delegated. |
| **Acceptance of a load** | **Human — Mike Zachary** | Booking is human-initiated; conflicts warn and never block | Enforced. |
| **External disclosure** | COMI decides · Publisher authors · Archive retains | Token-scoped, IDOR-checked stakeholder view; internal economics withheld | Governed by Driver-First **D11** (pending v2 adoption). |

## 3. Functions with no owner

Per ONT-07 and Constitution v3, a function with no owner is a **stop condition** — it is not built,
it is adjudicated first. Two remain:

| Function | Why unowned |
|---|---|
| **Receivable tracking and collections follow-up** | The lifecycle names six steps — find, book, run, deliver, bill, get paid. The narrated day and the repository both stop at invoice. Publisher is named as producing collections communications; nothing tracks the obligation. Candidate owner: COMI. **Not assigned here.** |
| **IFTA report generation** | Reports are retained; the repository computes them; no element is named as their producer in governance. Candidate owner: Publisher, sourced from Archive. **Not assigned here.** |

## 4. What changed from the pre-adjudication matrix

| Before | After |
|---|---|
| "Mission Layer / Scheduling Layer / Orchestration Layer" as candidate new elements | **Spine partitions.** No new element. The Spine remains the single deterministic runtime element. |
| Three competing state models, unresolved | **Two coexisting models on different subjects.** Fable's vocabulary is mapped in, never made a third authority. |
| Load identity — one identifier vs one retrieval, undecided | **One answerable retrieval chain.** No migration authorized. |
| Capacity ownership contested | **Spine/Scheduling**, approved in principle, blocked on doctrine. |
| Driver-First clauses cited with no source | **D6, D9, D11 pinned** in `DRIVER_FIRST_DOCTRINE_v2`; external disclosure written down for the first time. |
