# CLAUDE.md — Dispatch cold-start brief

> ## ⛔ READ BEFORE WORKING — THE GOVERNANCE PACKAGE
>
> **A session that has not read the governing document is not qualified to change this
> repository.** This block exists to end re-teaching. It is the standing duty named in
> `JOE_CONVERSATIONAL_MISSION.md` §1B.
>
> **Read these, in this order, in `docs/campaign/`:**
>
> | | Document | What it is |
> |---|---|---|
> | 1 | **`JOE_CONVERSATIONAL_MISSION.md`** | **The governing document.** Doctrine, roles, classes, phases, prohibitions, validation register. **Binding.** |
> | 2 | `CONOPS_v1.1.md` | Ratified operating architecture — node + tablet, degraded modes, session model, glossary |
> | 3 | `OPPORTUNITY_CAPTURE_PLAN.md` | The seventh contract and the walking-skeleton workflow |
> | 4 | `CODE_MISSION_MCP_SERVER.md` | The MCP server and brain-neutral instructions mission |
> | 5 | `CLAUDE_HARNESS_ACTIVATION.md` | **READ AND DO NOT BUILD.** Sealed envelope; nothing in it is authorized |
> | 6 | `CONOPS_EVALUATION.md` | Closed. Context for why v1.1 says what it says |
> | 7 | `CODE_EXECUTION_ORDER.md` | The active campaign order and its stop points |
>
> **On conflict:** the governing document wins. **Report the conflict; never resolve it
> silently.** Anything ambiguous is Class 3 — do the staff work, recommend, and hold.
>
> ### Who you are here
>
> **Code is the Staff Engineer.** Code builds, tests, maintains, verifies and stands watch over
> the machine that makes missions possible. **Code may never act as the co-driver and may never
> replace human command authority.**
>
> **Joe is the co-driver; Code is the engineer. Neither takes the other's hat.** Joe touches
> Mission Records. Code touches code, tests, contracts, adapters, infrastructure and reports —
> and does not read or write operational records except inside a migration, repair or
> verification mission the Owner explicitly authorized, reporting every touch.
>
> ### The three classes — confirmation matches consequence
>
> | Class | Meaning | Examples |
> |---|---|---|
> | **1 — Execute and report** | Low-risk, reversible, covered by direction | Run tests · health checks · doctrine scans · inventory · analyse · draft plans and reports |
> | **2 — Confirm, then execute** | Destructive or history-bearing | **Delete · force-push · rewrite history · schema migration · touch operational data.** State it first; execute on confirmation |
> | **3 — Recommend and hold** | Reserved to human command | **Change doctrine · change a ratified contract · add an endpoint beyond spec · add a vendor-locking dependency · anything outside mission intent.** Staff work, recommendation, Owner decides |
>
> *Precedent: the commit-endpoint removal — Code's engineering argument lost to doctrine,
> correctly.*
>
> ### The locked vocabulary
>
> **Status:** `LIVE` · `CONFIGURED` · `UNCONFIGURED` · `SIMULATED` · `UNAVAILABLE` · `MANUAL` ·
> `ABSENT` · `UNVERIFIED`
> **Result:** `PASS` · `FAIL`
> **Mission status, Joe's voice:** `ON TIME` · `DELAYED` · `AT RISK`
>
> **No other words for status.** `IMPLEMENTED` is not `OPERATIONALLY PROVEN`.
>
> ### The rules that bind every change
>
> - **Honest Reporting Rule.** No false success. No silent failure. Partial completion is
>   reported part by part.
> - **Contract-First / Vendor-Agnostic Rule.** Contracts, endpoints, data structures, workflow
>   objects, audit records and Mission Record schemas stay platform- and vendor-agnostic.
>   Vendors live only in adapters. Channels are named by nature — `CHAT`, `VOICE`,
>   `MISSIONSCREEN` — never by product. **The neutrality scan must pass after every change.**
> - **Doc/code equality.** A test asserts the contracts in code **equal** the spec — equality,
>   not sufficiency.
> - **Single Source of Truth.** Dispatch is the sole lifecycle and identity authority. No second
>   copy of operational truth.
> - **Rent-the-Trailer Rule.** The AI brain is rented. No in-house AI platform.
> - **ROGER control remains `UNVERIFIED`.** Do not implement without explicit Owner approval.
> - **No board automation, scraping, or session tooling of any kind, anywhere.**
>
> ### Standing prohibitions
>
> No AI/LLM built or hosted in-house · no auto-learning, self-modification or profile changes ·
> no second datastore of operational truth · no Class 2 action without completed read-back · no
> Class 3 action without an explicit Owner decision.

---

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

**Dispatch is the System of Record and the Operational Authority.** Operational truth lives in
Dispatch; a plug-in's copy is a copy. Authority is over *operations*, never over Mike's decisions
(§4).

The physical shape of the program — what runs where, and what may assume connectivity — is
**§5A, the node and tablet architecture.** That is the current model and it is where a builder
should look first.

> **The General Contractor Doctrine was archived on 2026-09-07 — a failed idea, all of it.**
> Nothing was carried forward from it. The rules people associate with it — Single Source of
> Truth, *degradation is permitted, incapacity is not*, and *use the provider, own the interface*
> — were never its property. They are stated in **§5.1** and **§5.4** and stand there on their
> own, unchanged. The doctrine itself is in **§10.1**, as history.

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

### 5.6 Archive and Library are different things

**The Owner's L1-COS architecture recap, Section 8, carried into doctrine 2026-09-08:**

> **Archive stores completed history. Library stores approved reusable knowledge.**

Dispatch has both and the sentence appeared nowhere in this repository, which is how two stores
end up holding each other's contents.

| | |
|---|---|
| **Archive** — `D:\Archive`, `cin_lite/archive.py`, `docs/…/retention` | What **happened**. Closed loads, decisions taken, packets published, evidence. **Append-only and finished.** Nothing in it is a reference for the next load; it is the record that the last one occurred |
| **Library** — `portal/models/library.py`, the Company Library | What is **known and reusable**. Doctrine, rate policy, procedures, approved reference. **Curated, and edited when it changes** |

**The test is the tense.** A completed run belongs to the Archive. What that run *taught* belongs
to the Library — and moving it there is a deliberate act, never a side effect of closing a load.
That act is **Rule 16**, and it is the only door between them.

The roadmap the recap sets out — Broker, Customer, Location Intelligence, Operations and
Intelligence libraries, against Load, Decision, Publisher, Location and Broker history archives —
is **not built and not authorized.** It is parked in `D:\MD Files\EXPANSION_PARKING_LOT.md` with
a cost against it.

### 5.7 There is no Manager component

**There is no Manager component in the current architecture.** The concept was archived on
2026-09-07 and now lives in **§10.2** as history rather than as an active prohibition.

**The code guard did not move with it.** `TestNoManagerDoctrine` still forbids Manager modules,
authority, routing and tables from appearing in code. **Archiving a concept is not permission to
build it.**

### 5.8 THE MIKE RULE

Subsystems are deliberately kept standalone even where that duplicates a little code. A
subsystem that can be lifted out and run on its own is worth more than a subsystem that
shares a clever abstraction. Do not "clean up" duplication across subsystem boundaries
without a decision recorded in `DECISION_LOG.md`.

---

## 5A. The current architecture — node and tablet

**Ratified in `docs/campaign/CONOPS_v1.1.md`.** This is what Dispatch *is*, physically, and it
governs where code belongs.

**Dispatch operates as a node-and-terminal architecture.** The driver interacts with a tablet.
Dispatch operates from a laptop node. Joe is a Dispatch capability living on the node,
communicating with the driver through the tablet.

### The Dispatch Node

A laptop in a ventilated Pelican case inside the truck. It owns **Mission Records, Mission Cards,
workflow, scheduling, COMI, Publisher, Library, Archive, Route Risk, Joe services, MCP services,
APIs and audit records.**

> **The node is the operational center of gravity. The node owns workflow and records.**

**Unattended recovery (R5):** the node must survive power loss without a keyboard — BIOS
auto-power-on, auto-login, services on boot, and a self-test reporting node status to the portal on
recovery. *A bad bump on I-10 costs seconds, not a roadside IT session.*

### The Driver Workstation

A cellular-enabled tablet. It owns **the phone, microphone, speaker, headset, camera, the Driver
Portal, the Mission Card display and the Joe interface.**

> **The tablet is not Dispatch. The tablet is the driver's workstation. The tablet is a portal into
> Dispatch.**

**Trust boundary (R9):** the tablet holds **no records and no standing secrets.** Portal sessions
authenticate to the node, expire, and are revocable from the node. **A stolen tablet is a hardware
loss, never a data loss.** `DISPATCH_JOE_TOKEN` never lives on the tablet.

### Connectivity is intermittent by default

The tablet provides the cellular link. The node treats internet as **intermittent by design** —
outbound work queues and retries honestly. Mission data lives on the node; internet is needed only
for external services.

| Connectivity | Dispatch (node) | Joe voice | Portal (tablet ↔ node) |
|---|---|---|---|
| **Online** | Full | Full | Full |
| **Offline** | **Full** — records, cards, workflow | **DOWN** — the rented brain is in the cloud | Full, by touch |

The portal shows Joe's state in locked vocabulary: **`JOE LIVE` / `JOE DOWN`.**

**Loss of internet never stops local operation.** It silences the co-driver's voice until signal
returns. A surface that stops working offline, or that hides the difference, is a defect.

### Records survivability (R8)

Nightly encrypted backup off-node whenever connectivity allows; the append-only audit ships more
often. Destination is the home NAS. **"Recoverable" and "Portable" are procedures, not adjectives**
— a restore test to a spare machine is part of the habit, not a claim.

### What this means for where code goes

- Anything that owns a record, a workflow or an audit entry belongs **on the node**.
- Anything that is a screen, a microphone or a speaker belongs **on the tablet** — and holds
  nothing.
- **No feature may assume connectivity.** Offline is the default case, not the error case.

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

### The Owner's design rules — numbered, and his

**These are Mike's, written in the L1-COS architecture recap and never carried into this
repository.** Rule 16 is quoted in two modules; **Rules 14 and 15 were quoted nowhere**, and
Rule 15 is the one that governs how a builder works. It was enforced for months only by the
Owner noticing a duplicate and saying so — twice in one afternoon on 2026-09-08, which is why
it is finally written down.

| | | |
|---|---|---|
| **Rule 14** | **Capture Once, Use Many** | *"The first trip gathers intelligence. The tenth trip consumes intelligence."* |
| **Rule 15** | **Reuse Before Create** | *"Expand existing roles before creating new layers."* |
| **Rule 16** | **Experience Becomes An Asset** | *"Convert operational experience into reusable company capability."* |

**Rule 15 in practice, because it is the one that gets broken.** Before writing anything new,
find what already does it. On 2026-09-08 Code copied eleven of the Mission Card's thirty-three
fields into JOE rather than asking Dispatch for the form, and built a printable capture sheet
for a form the New Mission screen already renders. **Both were caught by the Owner, not by the
program.** The guards that now exist — a test forbidding a second rendering of the Mission
Template, and one forbidding JOE to declare a field list — exist because a rule enforced by
somebody noticing is a rule that will be broken again.

**Doctrine.**

- Read existing repository doctrine before creating anything. Reuse and update rather than
  duplicate — **Rule 15.** `docs/architecture/DISPATCH_ARCHITECTURE.md` §1 is the map.
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
- ~~Never weaken fail-closed authentication, CSRF protection, token expiry/revocation, or
  ownership checks for convenience.~~ **SUPERSEDED 2026-09-07 by Owner ruling.** Security becomes
  a **plug-in module on the deferred list**, alongside Publisher, Library, Librarian and Archive:

  > *"At this point, my concept is an open application. So please disregard and move around, work
  > around, bypass whatever needs to be done on any security issue. We have serious things to build
  > without dealing with that at this point."*

  **Kept visible rather than deleted**, because the rule was right when written and will be right
  again. What replaced it, and the one condition that changes it back, are in
  `docs/DISPATCH_SECURITY_DEFERRAL.md`. **The short version: `PORTAL_HOST` is `127.0.0.1`, so
  "open application" means open *on this machine*. The day Phase 3 binds to the network for the
  tablet, this deferral must be re-read rather than inherited.**
- Never commit runtime secrets, logs containing secrets, rehearsal databases, evidence
  files, or backups.

**Tests.**

- **The suite has a known Windows baseline of 12 failures.** All are `WinError 1314` — the
  symlink-creation privilege Windows withholds — in `test_launcher`, `test_rehearsal_and_proof`
  and `test_sandbox_survey`. They are environmental, not defects, and they are the same twelve
  every run.

  **The rule is therefore: no new failures, and run the whole suite before pushing — not the files
  you touched.** On 2026-09-07 Code pushed two failing tests twice in one day by running targeted
  tests and reporting them as green. The old wording of this rule (`0 failed / 0 skipped /
  0 warnings`) was true on CI and false on this machine, and a rule that is false where the work
  happens gets ignored rather than obeyed.
- Gated coverage (`cin_lite`, `dispatch`, `portal`) must not drop below its current figure.
- Do not skip, weaken, remove, or xfail a test to get green.
- **THE TEST REALITY RULE.** *A test that builds its own precondition proves the logic and says
  nothing about whether the application can reach it.* Where a state matters, one test must arrive at it the way the screen
  does. This has now caused four defects: `artifacts_held` written only by tests, `rehearsal_badge`
  available to every template and called by six, `purge_session` implemented and called by nothing,
  and the entire Joe contract layer verified behind a login gate that `TESTING=True` switched off.

**Reporting.**

- **Do not claim a push occurred unless it was verified.**
- Report what happened, including what did not work.

---

## 8. What is proven, and where the status lives

**There is no status block in this file any more, and that is deliberate.**

The old §8 was headed *Current build status (2026-08-25)* and by 2026-09-07 four of its
statements were false — including *"Nothing in this repository has been run on Mike's Windows
laptop"*, which `docs/readiness/KNOWN_LIMITATIONS.md` §0 contradicts in its own title, and
*"there is no copy on Mike's machine"*, written in a file living on that machine.

A dated status block inside a binding doctrine file rots, because doctrine is re-read and status
is re-written and they do not keep the same schedule. That is the **Operator Document Rule**
(`docs/governance/OPERATOR_DOCUMENT_RULE.md`) applied to this file: *if the code changed, would
this be wrong?* Sections 1–7 — no. The status block — yes, and it was.

**Status now lives in one place:**

| | |
|---|---|
| **Where the program stands today** | `D:\MD Files\DISPATCH_CURRENT_STATE.md` |
| What is proven and what is not | `docs/readiness/OPERATIONAL_PROOF.md` |
| What is broken or missing | `docs/readiness/KNOWN_LIMITATIONS.md` |
| The first-start acceptance items | `docs/readiness/LAUNCHER_PROOF_TEMPLATE.md` |

### What stays here, because it is doctrine and not status

**IMPLEMENTED is not OPERATIONALLY PROVEN.**

- **IMPLEMENTED** — the code exists and the suite exercises it.
- **OPERATIONALLY PROVEN** — it has run **on Mike's machine** and evidence was recorded.

**The suite is evidence of software behaviour only.** It is never operational proof. A green run
says nothing about whether Dispatch starts on a Windows laptop, finds the `D:` drive, or keeps a
load across a restart.

Never represent sample data as live data · a requested action as a completed action · an interface
definition as a working integration · test success as operational deployment proof.

**The completion gate has not moved:** Mike runs a real load, end to end, on his own machine. Not
"the tests pass". Not "the feature is implemented".

---

## 8A. Doctrine ruled since 2026-09-05 — read these, they are binding

The campaign package in the block at the top of this file governs the JOE/MCP campaign. **These
govern Dispatch itself** and were ruled during the screen walk.

| Ruled | Doctrine | Where |
|---|---|---|
| 2026-09-06 | **Rehearsal data** — tagged at creation · visibly marked wherever displayed · never represented as live operational truth · must not silently contaminate financial reporting · may be viewed through an intentional mode or filter | `docs/DISPATCH_REHEARSAL_DATA_DOCTRINE.md` |
| 2026-09-06 | **The Operator Document Rule** — how to operate, configure, start, stop, test or validate a feature belongs in the repository; research, forensics, recovery, analysis, historical records and planning belong in `D:\MD Files` | `docs/governance/OPERATOR_DOCUMENT_RULE.md` |
| 2026-09-07 | **Security deferral** — security becomes a plug-in module on the deferred list; it must not delay the build | `docs/DISPATCH_SECURITY_DEFERRAL.md` |

### Vocabulary ruled 2026-09-06 — one word, not three

**The party who controls a load is the `Customer`.** Not broker, not shipper. Mike's reason, and it
is the operative one: *"I use Shipper/Broker synonymously, they are interchangeable, because I have
no idea which is booking the load."* Broker-versus-shipper is a distinction Dispatch was making
that the driver does not make.

**Display text on the Driver surfaces was changed. The stored field names were not** — 1,539
occurrences across 115 Python files, plus `broker_shipper`, `broker_contacts` and `broker_id` in
the schema. **Renaming those is one deliberate mission after the screen walk, never in passing.**
The register of every legacy name is `D:\AAA-Dispatch-Screen-Build\_SHARED\NAME_REGISTER.md`.

### The contracts are seven, not six

`POST /api/joe/opportunity` — Opportunity Capture — was ratified 2026-09-06 and built 2026-09-07.

**§8.1 of the governing document lists six.** The seventh is ratified in
`OPPORTUNITY_CAPTURE_PLAN.md` §2. The equality test in `tests/test_contract_neutrality.py` names
the source of each contract precisely, and a test holds that discrepancy visible so it is re-read
rather than tidied away.

---

## 9. Where things are

| | |
|---|---|
| Start here | `CLAUDE.md` (this file) |
| Get Dispatch onto a laptop | `docs/operations/GET_DISPATCH_ONTO_YOUR_LAPTOP.md` — **historical.** The working copy is `D:\Dispatch` and has been since 2026-09-05 |
| Start Dispatch | **Double-click `DISPATCH_START_HERE.cmd`.** Why that file and not `dispatch.bat`: `docs/readiness/LAUNCH_PATH.md` |
| First start, in detail | `DISPATCH_FIRST_START_GUIDE.md` |
| Architecture and the document map | `docs/architecture/DISPATCH_ARCHITECTURE.md` |
| Authority and boundaries | `docs/governance/DISPATCH_AUTHORITY_AND_BOUNDARIES.md` |
| Day-to-day operation | `docs/operations/DISPATCH_OPERATOR_GUIDE.md` |
| Backups, upgrades, recovery | `docs/maintenance/DISPATCH_MAINTENANCE_GUIDE.md` |
| Where things stand today | `D:\MD Files\DISPATCH_CURRENT_STATE.md` (outside the repository) |
| What remains, in order | `docs/readiness/COMPLETION_BLUEPRINT_v2.md` |
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

---

## 10. Archived concepts — the What If box

**Owner ruling, 2026-09-07.** These were architecture once. **They are not now.** They are kept
here, named and dated, because a concept that is deleted comes back — someone reinvents it, or
finds a stray reference and assumes it is live.

**Nothing in this section authorizes code.** It is architectural history.

**The rule for everything in this box:** *do not build it, do not restore it, do not infer it from a
surviving reference — and do not delete the record of it either.*

---

### 10.1 The General Contractor Doctrine — ARCHIVED 2026-09-07

*Ruled `DECISION_LOG.md` 2026-08-25. Archived by Owner ruling 2026-09-07.*

It said:

> **Dispatch is the General Contractor, System of Record, and Operational Authority.**
>
> Dispatch coordinates core operational work and uses external wheels or optional plug-ins where
> appropriate. **Dispatch remains complete and operational without optional plug-ins.**

**Why it is archived.** *Owner ruling, 2026-09-07: "General Contractor was a failed idea. Meant all
of it to go."*

It described Dispatch as the coordinating centre of an ecosystem of optional plug-ins. The ratified
architecture is **node and tablet** (§5A) — a physical model of where records and workflow live, not
a contracting metaphor about what Dispatch presides over. The metaphor was doing no work the node
model does not do better, and it invited a shape the program never took.

**Nothing was carried forward. There are no survivors.**

An earlier draft of this section tried to rescue three clauses from it. That was wrong, and the
Owner said so. **Those rules were never the doctrine's property** — they have their own homes and
always did:

| Rule people associate with it | Where it actually lives |
|---|---|
| Single Source of Truth | **§5.1** and D4/D5 of the Driver-First Doctrine |
| *Degradation is permitted. Incapacity is not.* | **§5.4**, plug-in separation |
| *Use the provider; own the interface.* | **§5.4** and `docs/connectors/PROVIDER_INSERTION.md` |

They survive because they are independently true, **not** because anything of this doctrine
survives. Do not cite this section as their authority.

---

### 10.2 The Manager component — ARCHIVED 2026-09-07

*Never built. Named in planning. Prohibited from 2026-08-25. Archived by Owner ruling 2026-09-07.*

**There is no Manager component in the current architecture.** `docs/MANAGER.md` is the permanent
record of a capability that was named in planning and never built. It authorizes no code, no route,
no data model and no runtime behaviour.

**What changes with archiving, and what does not.** The concept moves from *prohibition* to
*history* — it is no longer an active rule a builder must be warned about, it is a thing that was
considered and set down.

**The code guard stays.** `TestNoManagerDoctrine` in `tests/test_repository_doctrine.py` still
forbids Manager modules, Manager authority, Manager routing and Manager-owned tables from appearing
in code. **Archiving a concept is not permission to build it.** If it is ever to be built, that is a
new Owner ruling and a new mission — not an inference from this box.

Manager work exists on an unmerged branch (866 lines plus 790 test lines), and a merged, running
Manager exists in `Dispatch-Old`. **Neither is authorized.** They are why the guard stays.

> ### `Dispatch-Old` — parts recovery only
>
> **Owner ruling, 2026-09-07:** *"Dispatch-Old was a working sandbox and should only be regarded
> for parts recovery only."*
>
> It is **not** a reference implementation, **not** a source of doctrine, and **not** evidence that
> something is authorized. That a thing runs there means it was tried, not that it was ruled.
>
> **Take a part from it only under an Owner-authorized mission, and say where the part came from.**
> Lifting behaviour out of a sandbox and into Dispatch without a ruling is how an archived concept
> comes back through the side door — which is exactly what the Manager guard above exists to stop.

---

### 10.3 How something enters or leaves this box

**Enters:** an Owner ruling, dated, with what replaced it named.
**Leaves:** an Owner ruling and a new mission. Never by a builder deciding a surviving reference
looks live.

---
