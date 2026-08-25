# CLAUDE.md — Dispatch cold-start brief

This is the first file to read in this repository. It exists so that a builder arriving
with **no conversation history** can be useful within one reading, and so that no builder
has to reconstruct doctrine from chat logs that no longer exist.

Everything below is either a statement of fact about the repository (checkable) or a
standing rule (binding). Where a rule has a fuller treatment elsewhere, this file names
the document rather than restating it.

---

## 1. The program

**Dispatch** is the freight-operations platform of **Level 1 Transport**, a small
owner-operator trucking business. It exists to reduce the owner/operator's cognitive load:
to show what is true now, lay out what could become true, let a human choose, and then
help execute the mission that was chosen.

Its purpose statement — the four verbs everything is measured against — is
`DISPATCH_PURPOSE_STATEMENT.md`:

> 1. See Reality. 2. Evaluate Possibilities. 3. Choose A Future. 4. Execute The Mission.

**Mike Zachary** is the owner/operator and the **final authority**. Not a stakeholder, not
a reviewer — the decision-maker. Software, automation and AI in this repository hold
**zero** decision authority. See §4.

### Dispatch's standing in its own ecosystem

> **Dispatch is the General Contractor, System of Record, and Operational Authority.**
>
> Dispatch coordinates core operational work and uses external wheels or optional plug-ins
> where appropriate.
>
> **Dispatch remains complete and operational without optional plug-ins.**

*(General Contractor Doctrine, `DECISION_LOG.md` 2026-08-25.)*

Three things follow, and they are the ones builders get wrong:

- **General Contractor** — Dispatch coordinates. It does not rebuild an external wheel that
  already turns. Use the provider; own the interface.
- **System of Record** — operational truth lives in Dispatch. A plug-in's copy is a copy.
- **Operational Authority** — with the standing limit that it is authority over *operations*,
  never over Mike's decisions (§4).

The third line of the doctrine is the testable one, and `tests/test_repository_doctrine.py`
tests it.

### The two halves of this repository, and why both are here

This repository holds two related programs. A builder who reads only one of them will make
wrong assumptions, so both are stated:

| | `dispatch/`, `portal/`, `dispatch_launcher/` | `cin_lite/` |
|---|---|---|
| What it is | The **freight** platform: loads, drivers, equipment, capacity, milestones, evidence, POD, IFTA, settlement | The **government-contracting** pipeline: acquire solicitations, run deterministic rule modules, email a human a checkbox decision, archive or route |
| Size | ~34,000 lines of Python | ~3,200 lines of Python |
| Status | The active program. Nearly all current work is here. | Implemented and passing; not the focus of current work. It is also Dispatch's **only** mail transport — the freight side sends through it. |
| Its own spec | `DISPATCH_PURPOSE_STATEMENT.md`, `DRIVER_FIRST_DOCTRINE_v2.md`, `docs/architecture/DISPATCH_ARCHITECTURE.md` | `Final_Architecture_for_Hybrid_CIN-Lite_System (1).docx`, `cin_lite/README.md` |

> **Recorded conflict.** Until 2026-08-25 this file described *only* the CIN-Lite
> government-contracting half, and described it as though it were the whole program. That
> was not wrong about CIN-Lite; it was silent about the ~34,000 lines of freight code that
> is the actual program. The silence is what made it dangerous — a cold-start builder read
> it and concluded Dispatch was a contract-archiving tool. Corrected here rather than
> quietly overwritten, per the working rule in §7 about not editing history to hide it.
> The CIN-Lite architecture summary that used to live in this file now lives, unchanged in
> substance, in `docs/architecture/DISPATCH_ARCHITECTURE.md` §6.

---

## 2. The mission

Dispatch is being built to the point where **Mike can bring it to his laptop, launch it,
operate it, and use it for real freight work.**

That sentence is the completion gate. Not "the tests pass", not "the feature is
implemented" — *he uses it to run a load and get paid*. Every readiness claim in this
repository is written against that gate, which is why the vocabulary in §6 distinguishes
so sharply between software that works and software that has been proven to work on his
machine.

---

## 3. Driver-First, and the 70 MPH Test

`DRIVER_FIRST_DOCTRINE_v2.md` is binding. Its fifteen clauses (D1–D15) are the design
constraints for every driver-facing surface. The one to hold in your head while writing
anything:

### D2 · The 70 MPH Test

> **Can the driver obtain the needed information within seconds during real-world
> operations?**
>
> If the answer is no, redesign the feature.

The driver is moving, is tired, and has one hand. A feature that requires reading, hunting
or deciding fails. Related clauses you will hit constantly:

- **D1 Driver Is The Customer** — the driver, not the dispatcher, is who the interface serves.
- **D3 Reduce Cognitive Load** — Dispatch does the calculating; the driver receives
  information, decisions required, warnings and recommendations, never raw complexity.
- **D4 Single Source Of Truth** / **D5 Portal Is A Window** — the portal displays state, it
  does not hold a second copy of it.
- **D9 Retrieval Is Not Modification** — reading something must never change it.
- **D10 Human Authority** — see §4.
- **D13 Startup Must Be Simple** / **D7 Shutdown Must Be Simple** / **D8 Reset Is Normal** —
  the launcher exists because of these three.

A silent failure is the classic 70 MPH violation and this repository has already shipped
one: `driver_step_milestone` once swallowed a refused transition inside
`except Exception: pass`, so a driver at a dock tapped "Picked Up", nothing was recorded,
and the screen said it worked. That defect is fixed. Do not reintroduce its shape.

---

## 4. Authority

Full treatment: `docs/governance/DISPATCH_AUTHORITY_AND_BOUNDARIES.md`.

1. **Mike Zachary is the final authority.** AI decides nothing.
2. **Score does not decide.** Scoring reduces noise and sorts human attention. It does not
   approve, reject, or choose.
3. **Never manufacture a Mike attribution.** No record may say *Verified by / Approved by /
   Accepted by / Authorized by / Confirmed by Mike Zachary* unless Mike personally performed
   an authenticated action that produced it. Not as a default, not as a seed, not as a test
   fixture, not as an inference.
4. **Recommendations are labelled as recommendations.** A recommendation that reads like a
   decision is a decision made without authority.

---

## 5. Architectural boundaries

Full treatment: `docs/architecture/DISPATCH_ARCHITECTURE.md`. The load-bearing rules:

### 5.1 The Spine is the lifecycle authority

`dispatch/spine/` owns load lifecycle state. `spine.state.transition()` computes a
transition; `spine.store.apply_transition()` persists it. Opportunity **advises**; the Spine
**decides** (CF-04, `DECISION_LOG.md` 2026-08-23). Do not add a second lifecycle engine and
do not let a route mutate lifecycle state directly.

### 5.2 Reality and Possibility never merge

- **Calendar stores commitments** — what is true.
- **Opportunity Cards store possibilities** — what could become true.

The transition from possibility to reality is one-way and explicit. Never merge the two
concepts, and never let a possibility render as though it were a commitment.

### 5.3 Week View is capacity visualization, not scheduling

It shows available / consumed / reserve / position capacity and schedule gaps. It is not a
dispatch board, planning board, or scheduler. The Driver Portal Calendar is a
**presentation layer** over committed reality — it does not own scheduling either.

### 5.4 Plug-in separation

Route Risk, Mission Visibility, SAM, and Assistant are **plug-ins**. Dispatch must start and
run its core operation without any of them.

- Do not embed Assistant code into Dispatch, and do not redesign Dispatch around Assistant.
- **No direct Dispatch write authority may be granted to Assistant.**
- Every external system enters through `dispatch/connectors/` — a governed boundary with a
  fixed contract, an audit trail, and an honest status. See `docs/connectors/PROVIDER_INSERTION.md`.
- **Degradation is permitted. Incapacity is not.** An absent plug-in makes a surface report
  `UNCONFIGURED` or `UNAVAILABLE`. It does not make Dispatch fail to start.

Guarded by `tests/test_repository_doctrine.py`.

### 5.5 Outlook is the scheduling authority

Dispatch **may** create or request schedule information through an approved interface, read
it, present it, use it for capacity awareness, and show gaps and conflicts.

**Dispatch must not create a separate competing scheduling system.**

The Driver Portal Calendar is a Monday-through-Sunday visual capacity board that *presents*
Outlook schedule data. It is **not an independent calendar database**. Use familiar terms —
`Calendar`, `PU`, `DEL` — and no scheduling jargon.

### 5.6 There is no Manager component

**There is no Manager component in the current architecture. Do not create, restore,
reference, or infer a Manager component, Manager agent, or Manager authority.**

`docs/MANAGER.md` is the permanent record of a capability that was *named* in planning and
*never built*; it authorizes no code, no route, no data model and no runtime behaviour. It
is history, not a backlog item. Guarded by `tests/test_repository_doctrine.py`.

### 5.7 THE MIKE RULE

Subsystems are deliberately kept standalone even where that duplicates a little code. A
subsystem that can be lifted out and run on its own is worth more than a subsystem that
shares a clever abstraction. Do not "clean up" duplication across subsystem boundaries
without a decision recorded in `DECISION_LOG.md`.

---

## 6. The truth vocabulary — the most important convention here

Status words are **fixed**. These eight, and no synonyms, no invented variants:

| Word | Means |
|---|---|
| `LIVE` | Connected to a real external system and working right now |
| `CONFIGURED` | Settings are present; not yet exercised |
| `UNCONFIGURED` | Settings are absent |
| `SIMULATED` | A mock or fixture is answering |
| `UNAVAILABLE` | Should be reachable, is not |
| `MANUAL` | A human does this step; there is no automation |
| `ABSENT` | The thing does not exist |
| `UNVERIFIED` | Not established by evidence |

Several modules validate these in `__post_init__` and will raise on a synonym. That is
intentional.

### IMPLEMENTED is not OPERATIONALLY PROVEN

- **IMPLEMENTED** — the code exists and the repository suite exercises it.
- **OPERATIONALLY PROVEN** — it has been run **on Mike's machine** and evidence was recorded.

**The repository test suite is evidence of software behaviour only.** It is never operational
proof. A green CI run says nothing about whether Dispatch starts on a Windows laptop, finds
the `D:` drive, or keeps a load across a restart.

Never represent:

- sample data as live data
- a requested action as a completed action
- an interface definition as a working integration
- test success as operational deployment proof

Do not mark an item verified without actual runtime evidence. Current readiness:
`docs/readiness/OPERATIONAL_PROOF.md` and `docs/readiness/KNOWN_LIMITATIONS.md`.

---

## 7. Working rules

**Doctrine.**

- Read existing repository doctrine before creating anything. Reuse and update rather than
  duplicate. `docs/architecture/DISPATCH_ARCHITECTURE.md` §1 is the map.
- **The repository is the source of truth — not conversation history.** A previous session's
  chat is gone and was never authoritative.
- Do not document unapproved ideas as doctrine, and do not overwrite settled doctrine merely
  to match the current implementation. **If code conflicts with approved doctrine, report the
  conflict** — in the mission report and in `DECISION_LOG.md`.
- **Do not edit old decisions to hide their history.** Mark them `SUPERSEDED` and cite the
  ruling that replaced them.

**Code.**

- Rule logic stays **deterministic**. No nondeterministic LLM call inside a deterministic
  rule path. Claude agents are for summarization, recommendation and drafting — always
  labelled, never load-bearing.
- One concern per module. New rules and new connectors are new files.
- Never weaken fail-closed authentication, CSRF protection, token expiry/revocation, or
  ownership checks for convenience.
- Never commit runtime secrets, logs containing secrets, rehearsal databases, evidence
  files, or backups.

**Tests.**

- The suite must stay at **0 failed / 0 skipped / 0 warnings**.
- Gated coverage (`cin_lite`, `dispatch`, `portal`) must not drop below its current figure.
- Do not skip, weaken, remove, or xfail a test to get green.

**Reporting.**

- **Do not claim a push occurred unless it was verified.**
- Report what happened, including what did not work.

---

## 8. Current build status (2026-08-25)

| | |
|---|---|
| Version | `0.1.0` |
| Suite | **3,696 passed** · 0 failed / 0 skipped / 0 warnings |
| Gated coverage | **94.74%** over `cin_lite` + `dispatch` + `portal` (floor 90%) |
| Ungated | `dispatch_launcher/` at 87.75% — Windows-only branches; see `docs/readiness/OPERATIONAL_PROOF.md` §2.1 |
| Laptop readiness | **UNVERIFIED** — see below |

**IMPLEMENTED:** the Spine lifecycle engine; loads, drivers, equipment, capacity,
milestones, evidence and POD; the Driver Portal; IFTA through finalization, exception
detection and receipt vision pre-fill; backup and restore; CSRF across mutating routes; the
connector boundary with eight connectors; rehearsal mode; the twenty-step operational-proof
system; the Dispatch Launcher and Control Center v1.

**IMPLEMENTED BUT NOT OPERATIONALLY PROVEN:** all of it. Every item above is software
behaviour verified by the suite. Nothing in this repository has been run on Mike's Windows
laptop.

**UNVERIFIED:** the fifteen first-start acceptance items in
`docs/readiness/LAUNCHER_PROOF_TEMPLATE.md`, and the twenty steps of the load proof in
`docs/readiness/OPERATIONAL_LOAD_PROOF_TEMPLATE.md`.

**Every external system is `UNCONFIGURED`.** No ELD, GPS, traffic, weather, load board,
mapping, accounting, scanner or Outlook client is connected.

**Dispatch does not know a driver's hours of service.** There is no ELD feed. Any surface
that implies otherwise is a defect.

**The next operational blocker** is stated at the end of
`docs/readiness/KNOWN_LIMITATIONS.md` and is kept current.

---

## 9. Where things are

| | |
|---|---|
| Start here | `CLAUDE.md` (this file) |
| Get Dispatch onto a laptop | `docs/operations/GET_DISPATCH_ONTO_YOUR_LAPTOP.md` — step one; there is no copy on Mike's machine |
| Start Dispatch | **Double-click `DISPATCH_START_HERE.cmd`.** Why that file and not `dispatch.bat`: `docs/readiness/LAUNCH_PATH.md` |
| First start, in detail | `DISPATCH_FIRST_START_GUIDE.md` |
| Architecture and the document map | `docs/architecture/DISPATCH_ARCHITECTURE.md` |
| Authority and boundaries | `docs/governance/DISPATCH_AUTHORITY_AND_BOUNDARIES.md` |
| Day-to-day operation | `docs/operations/DISPATCH_OPERATOR_GUIDE.md` |
| Backups, upgrades, recovery | `docs/maintenance/DISPATCH_MAINTENANCE_GUIDE.md` |
| What is proven, and what is not | `docs/readiness/OPERATIONAL_PROOF.md` |
| What is broken or missing | `docs/readiness/KNOWN_LIMITATIONS.md` |
| Every decision, in order | `DECISION_LOG.md` |
| Adding an external provider | `docs/connectors/PROVIDER_INSERTION.md` |

**Tech:** Python 3.11+ · SQLite (`sqlite3` stdlib, WAL, foreign keys enforced) · Flask ·
local filesystem · Claude API for the labelled non-deterministic helpers only.

**Commands:**

```bash
python -m pytest -q                       # the suite
python -m dispatch_launcher status        # what this machine is configured with
python -m dispatch_launcher start         # start Dispatch
python portal/app.py                      # start the portal directly
```
