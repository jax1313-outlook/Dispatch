# DISPATCH_BLUEPRINT_TO_COMPLETION_v1

**Phase 7 deliverable — the completion blueprint, amended by cross-repository evidence.**
**Supersedes for planning purposes:** `DISPATCH_COMPLETION_BLUEPRINT.md` (baseline `dd5d6c1`).
That document remains valid; this one **re-scopes eight of its missions from "build" to "recover"**
and adds the recovery work it could not see.
**Status:** Proposed. **No mission here is authorized.** Mike approves individually.

---

## 1. What changed, and why the plan is now smaller

Eight baseline missions are no longer construction work:

| Baseline mission | Was | Now |
|---|---|---|
| RUN-09 fix the coverage gate | Build | **Recover 3 lines** — R-02a |
| PORTAL-01 driver POD capture | Build | **Recover + repair** — R-01 |
| PORTAL-02 driver proof-of-pickup | Build | **Recover + repair** — R-01 (same commit) |
| PORTAL-03 driver load lookup | Build | **Recover + repair** — R-01 (dual-layer cockpit) |
| PORTAL-04 Current Mission priority | Build | **Recover + repair** — R-01 (7-day horizon) |
| OWN-02 consolidate governance | Locate then move | **Located** — R-04, R-05, R-06 |
| (implicit) Archive retention | Not scoped | **Recover** — R-02c |
| (implicit) Stop Sequence model | Blocked | **Recover after adjudication** — R-07 |

**The remaining true gaps are four**, and no repository contains any of them:
**backup and restore · CSRF · token expiry and revocation · a proven delivery path to Mike's machine.**

## 2. Existing Dispatch implementation to RETAIN

Unchanged from the baseline's fourteen: the SQLite store and 26-table schema · the service layer ·
the M1 transition gate · the C3 audit helper · Route Risk with its injection contract · atomic JSON
writes · COMI routing · the three-namespace authentication model · `RESERVED_SYSTEM_IDENTITIES` ·
the stakeholder IDOR posture · `cin_lite` and its nine deterministic rules · the Operations Feed ·
the 2,817-test suite · the `DECISION_LOG` + walkthrough convention.

**Cross-repository evidence displaced none of them.** Where another repository holds a competing
implementation (auth, Library, Publisher, Spine-as-simulation), Dispatch's is newer, wired, or
better tested — or all three.

## 3. External-repository work to RECOVER

Detailed in `DISPATCH_RECOVERABLE_WORK_MATRIX.md`. Ready without a Mike decision: **R-02a** (CI
gate), **R-03** (Route Risk tie-break), **R-04** and **R-05** (the two cited documents).

## 4. Work requiring REPAIR before recovery

| Item | Repairs required |
|---|---|
| **R-01 Driver Transformation** | Surface refused transitions instead of `except Exception: pass` (two sites) · scope or remove the unscoped IFTA fuel-receipt endpoint · guard `float()` parsing · discard the branch's duplicate re-implementation of PR #111 |
| **R-03 Route Risk tie-break** | Write a new test against `main`'s post-M3 design; the branch's test targets a `_StubRouteRisk` that `main` does not have |
| **R-07 Dynamic Capacity extension** | ENG-01 and ENG-02 first — `verified_by="Mike Zachary"`, `source="ELD_LOG"`, and the stale-configuration feasibility path at `capacity.py:338` are all still present in `e75acb0` |
| **R-02b `dispatch/spine/`** | Rebase onto a `main` that has moved five merges; reconcile against the PIN gate the branch lacks |

## 5. Work to ARCHIVE

`dispatch/security/` (superseded by `main`'s gate) · `dispatch/manager/` (BM-02, unless lifted) ·
`dispatch_publisher/` and `dispatch_library/` (duplicates) · Jules's `app.py` + `dispatch_spine.py`
runtime (design may be harvested) · `dispatch_build/` (experimental) · `l2_cos/`,
`Hybrid/architecture/`, the cin_lite agent framework (historical) · the Constitution v3 stack
(G2 — explicitly not adopted) · Hold's constitution family (G4) · the empty `Route-Risk` repository ·
`Jules/flask_app.log` (**remove — it holds a live debugger PIN**).

## 6. Disconnected modules to CONNECT

| Module | Lines | Gate before connecting |
|---|---|---|
| `dispatch/opportunities.py` | 297 | **CF-04** — it is the third state model BM-10 forbids. Adjudicate before wiring, never after. |
| `dispatch/capacity.py` | 352 (+827 unmerged) | CF-04, then ENG-01/02 |
| `dispatch/truck_arrangement.py` | 69 (+113 unmerged) | Same |
| `reconciliation/` | 480 | Its contract document exists (R-05). Connect or archive — do not leave it ambiguous. |
| `dispatch/spine/` | 835 | **CF-04.** Recovering it *and* adjudicating `opportunities.py` is one decision, not two. |

## 7. Proven gaps still requiring new implementation

**Only four.** Each was searched for across all seven inspected repositories and found nowhere.

| Gap | Baseline mission | Evidence of absence |
|---|---|---|
| **Backup and restore** | RUN-05 | No backup script on any branch of any repository |
| **CSRF protection** | RUN-04 | `grep -rniE "csrf"` → zero, everywhere |
| **Token expiry and revocation** | RUN-02 | `make_stakeholder_token` is `HMAC(secret, "dispatch-stakeholder:" + load_id)` in every version found |
| **A proven delivery path to Mike's machine** | OWN-01 | Two independent sessions confirm the Windows filesystem is unreachable |

Plus the standing doctrine-blocked set, unchanged: Scheduler · Revenue Projection · capacity
projection · the Visual Capacity Board · Outlook integration · the reset function.

## 8. Mike-only decisions

Nine, listed in `DISPATCH_AUDIT_AMENDMENT.md` §1.14. **Four gate build work:**

| Decision | Gates |
|---|---|
| **CF-01** governance home | R-04, R-05, R-06, and OWN-02 |
| **CF-02** `DF-` prefix | Any Driver-First citation change |
| **CF-04** Spine vs Opportunity lifecycle | R-02b, R-07, and all Dynamic Capacity work |
| **CF-05** does BM-02 still hold | Whether 1,656 lines of Manager stay archived |

## 9. Safe parallel workstreams

These share no files and can proceed simultaneously once approved:

| Lane | Missions | Touches |
|---|---|---|
| **A · Delivery** | OWN-01, OWN-04, OWN-05, RUN-05 | Nothing in `portal/` or `dispatch/` |
| **B · Security hardening** | RUN-01, RUN-02, RUN-03 | `config.py`, `notifications.py`, `email_delivery.py` |
| **C · Recovery, ungated** | R-02a, R-03, R-04, R-05 | CI config, one SQL clause, two documents |
| **D · Driver** | R-01 + repairs | `driver_portal.py`, `driver_home.html` |
| **E · Governance** | CF-01, CF-02 adjudication | Documents only |

**Lane B and Lane D must not run in parallel with RUN-04 (CSRF)**, which rewrites every template and
all eight route modules. CSRF is a stop-the-world mission — schedule it alone.

## 10. Final integration order

```
STAGE 0  OWN-04 (today)  →  OWN-01  →  OWN-03  →  OWN-02/CF-01  →  OWN-05
STAGE 1  RUN-01 → RUN-05 → RUN-03 → RUN-02 → RUN-06 → RUN-07 → RUN-08
         ┌ R-02a, R-03, R-04, R-05 (ungated recovery — any time after OWN-01)
STAGE 1b └ RUN-04 CSRF — alone, nothing else in flight
STAGE 2  CF-04 adjudication → SPINE-02 (C1) → SPINE-03 (C2a) → SPINE-04 (C4) → SPINE-05
         └ then R-02b (spine), R-02c (archive queue), R-02d (card levels)
STAGE 3  ENG-01 → ENG-02 → R-07 → ENG-03 → ENG-04
STAGE 4  R-01 repairs → R-01 recovery  [requires RUN-03 + RUN-04]
STAGE 5  (blocked — Outlook decision not made)
STAGE 6  PILOT-01 → PILOT-02
STAGE 7  not scoped
```

**Dependency rules that must not be broken:**

1. **OWN-01 precedes everything.** Recovering 9,000 lines into a repository whose delivery path is
   unproven repeats the exact failure this audit is about.
2. **CF-04 precedes every capacity, opportunity and spine mission.** Wiring an unadjudicated model is
   how `opportunities.py` reached `main` in the first place.
3. **RUN-03 and RUN-04 precede R-01.** Driver write endpoints without CSRF and without session expiry
   would ship the program's first unauthenticated-adjacent write surface.
4. **ENG-01/ENG-02 precede R-07.** Recovering the extension first locks in `verified_by="Mike Zachary"`.
5. **RUN-05 precedes PILOT-01.** No real load is entered before one restore has been proven.
