# DISPATCH_BUILD_MATRIX

**Phases 14 and 15 — build order and builder recommendation**
**Audit commit:** `37f4fd033e57c55f46dfd0568d3371e8473d683f`
**Status:** Proposed. **This document does not supersede `DISPATCH_BUILD_MATRIX_v2`.**

### Relationship to the existing matrices

`DISPATCH_BUILD_MATRIX_v2` is the adopted register and its standing constraints BM-01 … BM-12 remain
in force. This document is the **audit's proposed successor**, produced under a mission that
required a file of this name. It becomes authoritative only if Mike says so in `DECISION_LOG.md`.
Until then, where the two disagree, **v2 wins**.

Carried forward unchanged from v2: BM-01 (no new architecture without review) · BM-02 (Manager stays
dormant) · BM-03 (no second calendar) · BM-04 (Portal is not a source of truth) · BM-05 (Website is
not a source of truth) · BM-06 (no judgment in deterministic partitions) · BM-07 (no invented
doctrine) · BM-08 (every assumption written down) · BM-09 (enumerate operator-visible changes) ·
BM-10 (**no third state authority**) · BM-11 (no identifier migration) · BM-12 (no scheduler or
overnight worker).

**Proposed additions, for Mike's decision:**

| # | Proposed constraint |
|---|---|
| **BM-13** | No mission merges. Each mission in the blueprint is approved, built, reviewed and accepted on its own. C2a must not become C2b; PORTAL-01 must not absorb PORTAL-02. |
| **BM-14** | No mission ships without its artifact chain complete: source, commit, remote branch, pull request, behavioral tests, **exact test output**, reviewer disposition, Mike's acceptance. A sandbox path is not delivery. |
| **BM-15** | No builder wires an unadjudicated model into the running system. `dispatch/capacity.py`, `dispatch/opportunities.py` and `dispatch/truck_arrangement.py` stay unwired until SPINE-01 is decided. |

---

## 1. Build order

| Stage | Gate — nothing in the stage starts until this holds | Missions |
|---|---|---|
| **0 · Artifact ownership and repository recovery** | — | OWN-04 (**immediately**), OWN-01, OWN-02, OWN-03, OWN-05 |
| **1 · Runtime and persistence stabilization** | OWN-01 and OWN-03 accepted | RUN-01, RUN-02, RUN-03, RUN-04, RUN-05, RUN-06, RUN-07, RUN-08, RUN-09 |
| **2 · Core Spine truth and state control** | Stage 1 accepted | SPINE-01 (decision), SPINE-02, SPINE-03, SPINE-04, SPINE-05 |
| **3 · Operational engine hardening** | SPINE-01 decided | ENG-01, ENG-02, ENG-03, ENG-04 |
| **4 · Portal wiring** | RUN-03 and RUN-04 accepted | PORTAL-01, PORTAL-02, PORTAL-03, PORTAL-04 |
| **5 · Outlook and external integrations** | The Outlook integration decision, which has not been made | none proposed |
| **6 · Operational pilot readiness** | Stages 0–2 accepted | PILOT-01, PILOT-02 |
| **7 · Scale readiness** | Stage 6 complete and stable | not scoped |

**Stage 0's rule, verbatim from the mission: no further build work until the complete accepted
codebase exists in a repository and branch Mike controls.** OWN-01 is the proof of that and is
unskippable. OWN-04 is the one exception to the ordering — a committed debugger PIN for an
unauthenticated app is fixed today, not in sequence.

## 2. Recommended first five, in order

1. **OWN-04** — delete the committed debugger PIN. Minutes.
2. **OWN-01** — Mike proves the program runs on his own machine. Everything else is theoretical until this passes.
3. **OWN-03** — Mike names which portal is Dispatch. Two products cannot both be maintained.
4. **RUN-01** — refuse to start on a default secret. Small, self-contained, closes the only BLOCKER in the Dispatch codebase.
5. **RUN-05** — backup and restore. No real load should be entered before one restore has been proven.

## 3. Builder recommendation by mission

Basis: the character of the work, and whether the mission has a reliable artifact-delivery path.

| Mission | Lane | Why |
|---|---|---|
| OWN-01 Prove delivery | **Human — Mike, personally** | It is a proof about Mike's machine. No agent can perform it and no agent's report can substitute. |
| OWN-02 Consolidate governance | **Claude Code** | Mechanical, high-citation-fidelity, must not paraphrase doctrine. |
| OWN-03 Adjudicate the portals | **Human — Mike** | An ownership decision, not an engineering one. |
| OWN-04 Remove debugger PIN | **Claude Code** | Trivial and urgent. |
| OWN-05 Restore review record | **Claude Code drafts, Mike dispositions** | An agent must never record its own approval. |
| RUN-01 Secret refusal | **Claude Code** | Small, security-sensitive, needs the test suite intact. |
| RUN-02 Token expiry | **Claude Code** | Cryptographic detail; existing tests must not be weakened. |
| RUN-03 Cookie policy | **Claude Code** | Config-local. |
| RUN-04 CSRF | **Claude Code** | Touches every template and all 8 route modules — needs the whole suite as a safety net and a careful exemption list. Largest blast radius in Stage 1. |
| RUN-05 Backup/restore | **Claude Code builds, Mike proves** | The code is straightforward; the acceptance is Mike restoring on Windows. |
| RUN-06 Label samples | **Claude Code** | Small. |
| RUN-07 Schema version | **Claude Code** | Must not disturb the existing idempotent migrations. |
| RUN-08 Storage dirs under WSGI | **Claude Code** | Two lines. |
| RUN-09 Coverage gate | **Claude Code** | CI config; must set the threshold to the measured value, not an aspiration. |
| SPINE-01 Lifecycle adjudication | **Claude Code drafts the mapping; Mike decides** | BM-07 — no builder invents doctrine. |
| SPINE-02 C1 duplicate state | **Claude Code** | Well-specified, approved design, medium regression risk across two display paths. |
| SPINE-03 C2a calendar | **Claude Code, after Mike picks retire-or-rename** | Reasoning-light, decision-gated. |
| SPINE-04 C4 replay guards | **Claude Code** | The largest of the corrective missions; the ledger-not-outbox test discipline is subtle and matters. |
| SPINE-05 No-op audit | **Claude Code** | One line plus test updates. |
| ENG-01 … ENG-04 | **Claude Code** | Deterministic rule work inside a decided model. |
| PORTAL-01 … PORTAL-04 | **Claude Code** | Portal construction against an existing service layer, with security implications (driver scoping) that need the suite. |
| PILOT-01 One real load | **Human — Mike** | The whole point is what Mike notices. |
| PILOT-02 Disposition | **Mike, with Claude Code drafting** | — |

### Lanes deliberately not recommended, and why

- **Jules — not recommended for any mission in this blueprint.** This is not a judgment about
  capability. It is that Jules's delivered artifact in this program is an unauthenticated,
  non-persistent app that reported `"POD uploaded successfully"` for uploads that never happened,
  ran with the Werkzeug debugger exposed, and committed its debugger PIN. Separately, the three PRs
  merged into Dispatch after #111 added 718 lines of unwired engine code and a third state machine
  with no Decision Log entry and no walkthrough report. **The mission's own rule applies: do not
  recommend a builder unless the mission includes a reliable artifact-delivery path.** That path is
  what OWN-01, OWN-02 and OWN-05 exist to build. Once it exists and Jules's work runs through it —
  branch, PR, behavioral tests, exact output, reviewer disposition — this recommendation should be
  revisited on evidence rather than on this history.
- **Gemini — not recommended, for lack of evidence either way.** No Gemini-produced artifact exists
  in this program to assess. Recommending it now would be novelty, which the mission forbids.
- **Copilot-guided manual implementation** — appropriate if Mike wants to work through RUN-03,
  RUN-06 or RUN-08 himself to build familiarity with the codebase. Not required.
- **Human developer required** — none of these missions needs one. OWN-01 and PILOT-01 need *Mike*,
  which is different: they are proofs about his environment and his operation.

## 4. What is still blocked, and by what

| Item | Blocked by | Kind |
|---|---|---|
| Visual Capacity Board (C2b) | Reserve Capacity Doctrine | Doctrine — hard |
| Capacity projection (M10) | Reserve Capacity Doctrine, Jacksonville Repositioning Doctrine | Doctrine — hard |
| Any scheduler or overnight worker | BM-12 and Overnight Operations Doctrine | Doctrine plus standing bar |
| Outlook integration, either direction | The integration decision has not been made | Decision |
| Reset function | The protected set is drafted and not adopted | Doctrine |
| Manager reactivation | BM-02 | Standing bar |
| Wiring Dynamic Capacity | SPINE-01, then BM-15 if adopted | Decision |
| Driver-First citation prefixing | Numbering approval | Sequence |
| Operating constants register (M9) | Two live discrepancies remain unresolved: radius 500 in code vs 250–260 in the corpus; card threshold 90 in config vs 85 in the corpus | Doctrine |
| Revenue Projection | No doctrine, no owner | Doctrine |
| Receivable tracking and collections | **No owner assigned** — a stop condition under ONT-07 | Adjudication |
| IFTA report generation ownership | **No owner assigned** | Adjudication |

## 5. Amendment

Amended only by Mike Zachary, in `DECISION_LOG.md`, in his own words.
