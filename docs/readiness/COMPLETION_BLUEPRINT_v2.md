# Dispatch — Completion Blueprint v2

**Supersedes** `DISPATCH_COMPLETION_BLUEPRINT.md` (Phase 13, audit commit `37f4fd0`).
That document is **not** deleted and is **not** wrong — it is a plan written before anything
had run on the target machine. This one is written after.

**Date:** 2026-08-26 · **Status:** Proposed. **No mission here is authorized.**
Mike approves missions individually, never as a block. A mission may not be widened after
approval; one needing more than its stated scope stops and returns for a new approval.

Every mission carries the standing artifact rule: **source files, a commit, a remote branch, a
pull request, behavioural tests, exact test output, and Mike's acceptance or rejection.** A
completion report is not delivery. A list of test names is not verification.

---

## What v1 got right, and the one thing it got wrong

**Right:** the stage order. Runtime and persistence before Spine truth, Spine before portal
wiring, portal before integrations, integrations before a pilot. Nothing observed since has
disturbed that sequence.

**Wrong, and worth stating plainly:** v1 assumed the hard part was the code. Stages 0–5 are
substantially complete and the program still could not be started, signed into, or diagnosed
by its own operator. **Every defect that actually blocked use on 2026-08-25 was outside the
blueprint entirely** — a launcher nobody could find, no way to create a sign-in, an error page
that said nothing, windows that closed before they could be read.

That is the correction v2 carries: **a stage for the operator's experience of failure**, which
v1 had nowhere to put.

---

## Stage status against v1

Verified against the code on 2026-08-26, not asserted.

| v1 mission | State |
|---|---|
| **Stage 0** — artifact ownership, repository recovery | **Complete.** Delivery path proven; governance consolidated; portals adjudicated; debugger PIN removed |
| **RUN-01** refuse to start on a published secret | **Complete** — `InsecureConfigurationError` |
| **RUN-02** token expiry and revocation | **Complete** — `dispatch/tokens.py` |
| **RUN-03** session cookie policy | **Complete** |
| **RUN-04** CSRF on mutating routes | **Complete** — `portal/csrf.py` |
| **RUN-05** backup and restore | **Complete** — `scripts/dispatch_backup.py` |
| **RUN-06** label sample and test data | **NOT DONE. Now proven live** — see BLOCK-01 |
| **RUN-07** schema version and migration ledger | **Not done** |
| **RUN-08** storage under a WSGI server | **Not done** — still Flask's development server |
| **RUN-09** coverage gate | **Complete** |
| **Stage 2** — Spine truth and state control | **Substantially complete**; `loads.status` duplication remains open |
| **Stage 3** — engine hardening | **Complete** |
| **Stage 4** — portal wiring, driver POD/POP/lookup | **Complete in code, unexercised by a driver** |
| **Stage 5** — Outlook and external integrations | **Boundary complete; every connector `UNCONFIGURED`** |
| **Stage 6** — PILOT-01, one real load | **Not started.** Now the destination |

**Added since v1 and not in it:** the Dispatch Launcher and Control Center, first-run setup,
the sign-in PIN path, `[P] Reset PIN`, the connector boundary, rehearsal mode, the twenty-step
proof system, the crash page, and the repository-context document set.

---

## Stage A — Clear the operator's path

*Everything here is small, and every item is currently between Mike and using the program.*

### BLOCK-01 · Label the sample data (was RUN-06)
- **Problem, observed:** `/home` renders freight cards carrying a lane, a rate and a broker
  while `ACTIVE LOADS` reads 0. The four entries in `sandbox.json` are bundled samples. No
  marker exists anywhere in the code — `home.html` contains zero sample markers.
- **Doctrine:** `CLAUDE.md` §6 — *never represent sample data as live data.*
- **Scope:** mark sample-sourced records at the source, render a visible badge on every
  surface that displays one, and offer a one-click clear.
- **Mike's decision required first:** label the samples, or ship with none?
- **Builder:** Claude Code · **Reviewer:** Mike

### BLOCK-02 · Record the fifteen first-start acceptance items
- **Scope:** run each named command in `docs/readiness/LAUNCHER_PROOF_TEMPLATE.md` and write
  its real output beside the item.
- **The one that matters:** item 14 — Reset Session **refusing** while Dispatch is running.
  Untouched, and it is what prevents an orphaned server holding port 8080.
- **Builder:** **Mike.** Nobody else can produce this.

### BLOCK-03 · Home screen layout
- **Problem:** Mike's own first observation — some items belong on a second screen.
- **Scope:** await his answer on what belongs where; rebuild around it.
- **Blocked on:** Mike.

### BLOCK-04 · One copy of Dispatch
- **Problem, observed:** three copies existed; the broken one ran for seven hours. Each copy
  carries its own database.
- **Scope:** a startup check that warns when more than one Dispatch folder is present, and
  guidance on keeping exactly one.
- **Builder:** Claude Code

---

## Stage B — Prove one load, in rehearsal

### REH-01 · Run the twenty-step rehearsal
- `docs/readiness/OPERATIONAL_PROOF_PROCEDURE.md`. Fourteen steps automatable; **six are not,
  by design** — a human performs them or the proof is not operational.
- Records carry a permanent `REHEARSAL` tag and can never pass for a live mission.
- **Builder:** Mike, assisted. **Depends on:** BLOCK-01, BLOCK-02.

### REH-02 · Disposition the rehearsal findings
- Every point where Mike had to leave Dispatch, distrust a number, or guess becomes a mission.
- **Nothing beyond this stage is planned before it exists.**

---

## Stage C — One real load (was PILOT-01)

### PILOT-01 · One real revenue load, end to end, recorded
- Enter, assign, dispatch, milestone by milestone, evidence, delivery, rate confirmation,
  settlement, invoice, archive.
- **Every point where he had to leave Dispatch or distrust a number is written down.**
- **Depends on:** REH-01 passing. **Builder:** Mike. **Reviewer:** Mike.
- **This is the completion gate.** `CLAUDE.md` §2: *he uses it to run a load and gets paid.*

---

## Stage D — Only after a real load has run

Deliberately unplanned in detail. Naming these now would be inventing requirements before the
evidence exists.

- **RUN-07** schema version and migration ledger — needed once there is data worth migrating.
- **RUN-08** a real WSGI server — the development server is defensible for one local operator
  and is not what belongs on a VPS.
- **First connector.** Every external system is `UNCONFIGURED`. Outlook is the scheduling
  authority and the obvious first candidate; the boundary already exists.
- **The fuel, MPG and drive-speed constants** are defaults never checked against a real
  settlement. Replacing them with measurements from Level 1 Transport's own trucks is real
  work with real value.
- **`loads.status` versus the Spine** — two representations of lifecycle coexist.
- **`ROUTED_TO_MANAGER`** — a legacy state name under a No-Manager rule; persisted in the
  audit trail, so renaming rewrites history. Three options in
  `docs/architecture/DISPATCH_ARCHITECTURE.md` §7.1.

---

## What would make this blueprint wrong again

v1 was overtaken because it planned code and the obstacles were operational. The same could
happen here. The guard is the same one that caught it this time:

**Run it on the real machine, and believe what the operator reports over what the tests say.**

Four defects on 2026-08-25 were found in an afternoon of ordinary use. The suite — 3,822
tests, zero failures — found none of them, and could not have.
