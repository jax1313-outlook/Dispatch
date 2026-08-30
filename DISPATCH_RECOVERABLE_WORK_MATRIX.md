# DISPATCH_RECOVERABLE_WORK_MATRIX

**Phase 4 deliverable of the cross-repository reconciliation.**
**Baseline audit:** `dd5d6c113a8fd2992bdcbcd7f3ef42c646e15d11`
**Nothing was copied into Dispatch. Nothing was merged. This is a candidate list.**

---

## 0. The exclusion test, applied first

The mission bars recovery of work that manufactures human approval, turns unknown into verified,
creates a competing state machine, duplicates an accepted implementation, violates Driver-First
Doctrine, unseats Outlook as scheduling truth, adds a source of operational truth, or lacks an
operational owner. **Every candidate below was tested against all eight bars, and four bodies of
work failed and are excluded** — see §6. Existence of code was never treated as a reason to recover it.

---

## R-01 · Driver Transformation Missions 1–4 — **the highest-value recovery in the program**

| | |
|---|---|
| **Source** | Dispatch `origin/jules-driver-transformation-missions-1-4-12863749728267333928` |
| **Exact commit** | `afd6e00` (parent `0f2d3e5`, the PR #110 merge) |
| **Files** | `portal/routes/driver_portal.py` (+166), `portal/templates/driver_home.html` (+235), `tests/test_driver_portal.py` (new, 144 lines), `portal/routes/dispatch_api.py` (+18) |
| **Why useful** | It closes the baseline audit's single largest gap. The Driver Portal on `main` has exactly one interactive control (Sign Out). This branch adds four write paths: 1-tap milestone progression, camera POD/evidence capture, dock exception logging, and vision fuel-receipt intake — plus a dual-layer cockpit with a 7-day horizon. **This is PORTAL-01, PORTAL-02, PORTAL-03 and PORTAL-04 of the baseline blueprint, already built.** |
| **Test evidence** | `tests/test_driver_portal.py`, 144 lines, on the branch. Not run against `main` — the branch is based on `0f2d3e5` and `main` has moved 5 merges since. |
| **Dependencies** | `cin_lite.agents.receipt_vision` (present on `main`); `services.add_milestone`, `attach_evidence`, `open_exception`, `add_ifta_fuel_purchase` (all present on `main`) |
| **Conflict risk** | **HIGH on the file, LOW on the substance.** The branch also re-implements the whole of PR #111 (M1, M3, M-A, C3, all walkthrough reports, `DECISION_LOG.md`). That half is already on `main` and must be discarded, not merged. Cherry-pick the four files, never the commit. |
| **Doctrine compatibility** | **Strong.** Milestone writes go through `services.add_milestone()`, so the M1 transition gate and the C3 audit both apply. POD goes through `attach_evidence()`, so the extension allowlist, size cap and SHA-256 checksum all apply. `_verify_driver_load()` enforces driver-scoped access. Directly serves Driver-First §0 and the 70 MPH test. |
| **Destination** | `portal/routes/driver_portal.py`, `portal/templates/driver_home.html`, `tests/test_driver_portal.py` |
| **Repair required before recovery** | **YES — four defects, all real:** |

1. **Silent refusal.** `driver_step_milestone` wraps `add_milestone()` in `except Exception: pass`. A driver taps "Picked Up", the M1 gate refuses the transition, and **nothing is shown**. The refusal card is raised internally and the driver is redirected as though it worked. `flash` is imported and never used. This defeats the whole point of M1 and fails the 70 MPH test — a driver at speed cannot tell whether the tap registered.
2. **Same pattern** in `driver_log_exception`.
3. **`driver_fuel_receipt` has no driver scoping at all.** It is the only write endpoint on the branch with no `_verify_driver_load()` and no load association — any authenticated driver can inject arbitrary rows into the company IFTA fuel ledger. **IFTA is a tax filing.** This must be scoped and reviewed before recovery.
4. **`float(gallons_val)` is unguarded** — a non-numeric form value raises and returns 500.

| | |
|---|---|
| **Recommended disposition** | **REPAIR CANDIDATE — recover after repair, not before.** Fix all four, keep everything else. |
| **Mike decision required** | **NO** for the recovery itself (it implements approved blueprint missions). **YES** for whether the fuel-receipt endpoint belongs on the driver surface at all. |

---

## R-02 · The Stage 2–13 chain — **the largest body of unmerged work**

| | |
|---|---|
| **Source** | Dispatch `origin/stage13-testing-hold-review` |
| **Exact commit** | `0e2096a`, tip of a linear 14-commit chain from `c2b70f7` (IFTA Phase 7, PR #81, 2026-08-10/11) |
| **Size** | **+9,175 lines vs `main`, 44 new files** |
| **Test evidence** | **`2489 passed in 298.48s`, exit 0**, run in a detached worktree on this machine. Its own new suites: **`160 passed in 38.81s`**, exit 0. |
| **Contents** | `dispatch/spine/` (835 ln — 25 states, 25-key transition table, 6 tables, wired at `dispatch/db.py:422` and `portal/routes/api.py:16-17`) · `dispatch/security/` (690 ln — role, session, audit) · `dispatch/manager/` (866 ln, 8 modules) · `docs/` governance import including `DISPATCH_CONSTITUTION_v3.md`, `DISPATCH_SPINE_SPECIFICATION_v1.md`, `SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md`, `DISPATCH_FINAL_BLUEPRINT_v1.md` (1,133 ln) · Archive Review Queue · Portal card levels + Version Doctrine display · **the CI coverage-gate fix** · 1,874 lines of new tests |
| **Conflict risk** | **HIGH.** The base is 13 days and five merges old. `main` has since gained the PIN authentication gate (absent from this branch — `grep -c _require_authority_login portal/app.py` → **0**), M1, M3, M-A, C3, and the Dynamic Capacity package. This will not merge; it must be recovered **piece by piece**. |
| **Doctrine compatibility** | **Mixed — see below. This is not one recovery, it is five.** |

**Split into five independent recoveries:**

| # | Piece | Lines | Disposition | Reason |
|---|---|---|---|---|
| **R-02a** | **CI coverage-gate fix** (`.github/workflows/ci.yml`) | 3 | **RECOVER — trivial, do it first** | Exactly the baseline's RUN-09. `--cov=cin_lite --cov=dispatch --cov=portal`. One-line change, zero doctrine surface. |
| **R-02b** | **`dispatch/spine/`** | 835 + `tests/test_spine.py` | **RECOVER after adjudication** | It implements the **work-item state model** the adjudication already blessed as coexisting with load status — *not* a third model. 25 states matching Spine Specification §6 exactly. But it is a second persistence root, so BM-10 and the source-of-truth boundary must be checked explicitly by Mike. |
| **R-02c** | **Archive Review Queue** (`portal/models/archive.py` +75, `tests/test_archive_review_queue.py` 259 ln) | ~334 | **RECOVER CANDIDATE** | Age-based, portal-archive only. Fills the baseline's D-6 finding (no retention policy is implemented). Owner exists: Archive. |
| **R-02d** | **Portal card levels + Version Doctrine display** (Stage 5) | ~290 | **RECOVER CANDIDATE** | Additive display; corroborates `operations_feed.py`'s existing 0–5 taxonomy. |
| **R-02e** | **`dispatch/security/` (Stage 7) and `dispatch/manager/` (Stage 12)** | 1,556 | **DO NOT RECOVER AS-IS — see §6** | Fails the exclusion test. |

---

## R-03 · Route Risk ordering tie-break

| | |
|---|---|
| **Source** | Dispatch `origin/jules-401783631158985267-177d2e11`, commit **`28b5e65`** |
| **File** | `dispatch/store.py`, `list_route_risk_events()` |
| **Change** | `ORDER BY created_at DESC` → `ORDER BY created_at DESC, rowid DESC` |
| **Why useful** | `main`'s query has **no tie-break**. `created_at` is second-precision, so two events recorded in the same second return in undefined order. This is the exact ambiguity that forced two of my own M3/C3 tests to be rewritten as membership assertions rather than ordering assertions. The fix makes "latest" deterministic. |
| **Test evidence** | `tests/test_route_risk.py` on the branch adds `test_fallback_stub_adapter_multiple_events`. **That test targets a `_StubRouteRisk` adapter that does not exist on `main`** — the branch's `dispatch/route_risk.py` is a different implementation from `main`'s post-M3 injection design. **Only the `store.py` one-liner is recoverable; the test is not.** |
| **Dependencies** | None |
| **Conflict risk** | **LOW** — one clause in one query |
| **Doctrine compatibility** | Full |
| **Repair required** | **YES** — a new test must be written against `main`'s actual design (two events forced into the same second via direct SQL, asserting the deterministic winner) |
| **Mike decision required** | **NO** |

---

## R-04 · `PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md`

| | |
|---|---|
| **Source** | Jules `origin/claude/dispatch-tri-department-build-899qjm` |
| **Exact commit** | `4459f73` (branch tip) |
| **Size** | 177 lines |
| **Why useful** | The baseline audit reported this document as **MISSING from every repository**. It is not missing. **Ten citations across four Dispatch files** point at it — `portal/models/identity.py:5`, `portal/app.py`, `portal/routes/auth.py`, `tests/test_portal.py` — and they name the wrong repository ("Claude-3 repo"; it is in Jules). |
| **Conflict risk** | **NONE** — a document with no code equivalent in Dispatch |
| **Doctrine compatibility** | It **is** the doctrine those citations claim to follow |
| **Destination** | Dispatch, wherever OWN-02's governance home lands |
| **Repair required** | Only the citation text, which currently names the wrong repository |
| **Mike decision required** | **NO** to recover the file. **YES** on where governance lives (CF-01). |

---

## R-05 · `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md`

| | |
|---|---|
| **Source** | Jules `origin/claude/dispatch-tri-department-build-899qjm`, 331 lines |
| **Why useful** | `reconciliation/contracts.py` cites it **three times** (lines 3, 35, 71) — including *"Mirrors DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md Section 4.1 field-for-field"* — and Claude-3's own recovery report singles out that module for *"deliberately conservative adapters that refuse to fabricate fields Dispatch's existing data can't support, citing the missing `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` by name."* The contract exists; the code that mirrors it cannot be reviewed without it. |
| **Conflict risk** | NONE |
| **Repair required** | NO |
| **Mike decision required** | NO |

---

## R-06 · `DISPATCH_DEPLOYMENT_BLUEPRINT.md` — **the doctrine the code actually follows**

| | |
|---|---|
| **Source** | Claude-3 `origin/claude/dispatch-jules-arch-review-i87dru`, commit `8a55c33`, 656 lines |
| **Why useful** | It carries **§0 Driver-First Doctrine (LOCKED)** with the 70 MPH test verbatim, **§0b COMI Doctrine v1 (LOCKED)**, **§0c Dispatch Momentum Doctrine (LOCKED)**, §12–§22 build reports, and the **D1–D13 deployment decision register**. D9, D10, D11, D12 and D13 are all implemented on Dispatch `main` today. This is the source of the authority the Dispatch repository has been operating under without holding. |
| **Conflict risk** | **HIGH — governance, not code.** Its D13 ("Driver PIN Cards are a Library-managed asset") collides with `DRIVER_FIRST_DOCTRINE_v2`'s reassignment of D13/D14/D15. See **CF-02**. |
| **Doctrine compatibility** | It **is** the doctrine — but adopting it as Dispatch's governance home is a Mike decision, not a recovery |
| **Repair required** | The D-numbering collision must be resolved first |
| **Mike decision required** | **YES — CF-01 and CF-02** |

---

## R-07 · Seven additional Dynamic Capacity capabilities

| | |
|---|---|
| **Source** | Dispatch `origin/harden-dispatch-dynamic-capacity-18425064352509625141`, commit **`e75acb0`** |
| **Size** | +827 lines across `dispatch/capacity.py` (+378), `dispatch/truck_arrangement.py` (+113), `tests/test_architecture_discoveries.py` (+356) |
| **Adds** | `CapacityState` enum, `APPROVED_EVALUATION_STATUSES`, `PROHIBITED_AUTHORITY_STATUSES`, `CapacityDataMetadata` (provenance), `StopRecord`, `StopSequenceEvaluation.evaluate_sequence()`, `DynamicCapacityEvaluation`, `project_capacity()`, `evaluate_capacity()` |
| **Why useful** | It is the **real Stop Sequence model** the baseline found missing (`main` has only a stop *count*), and `PROHIBITED_AUTHORITY_STATUSES` plus `CapacityDataMetadata` look like a direct answer to the baseline's optimistic-default findings OT-1 … OT-6. |
| **Conflict risk** | **BLOCKED, not risky.** It extends a package that is unwired, unadjudicated, and carries a third state machine against BM-10. |
| **Repair required** | **YES** — the baseline's ENG-01 and ENG-02 defects (`verified_by="Mike Zachary"` as a default, `source="ELD_LOG"` with no ELD, the stale-configuration feasibility path at `capacity.py:338`) are **still present** in this commit and must be fixed. |
| **Mike decision required** | **YES — SPINE-01 must be decided first.** Recovering this before the lifecycle adjudication would deepen a governance breach, not close one. |

---

## R-08 · THE MIKE RULE duplication modules

| | |
|---|---|
| **Source** | Dispatch `origin/jules-401783631158985267-177d2e11` — `dispatch/email_delivery.py`, `dispatch/receipt_vision.py` (both absent from `main`) |
| **Why useful** | PR #110 merged Phases 1–3 of the extraction; four commits after it did not merge. Under THE MIKE RULE these standalone copies exist deliberately so `dispatch/` owns its own transport and vision paths rather than importing `cin_lite`'s. |
| **Conflict risk** | **MEDIUM** — duplicating a module that works is a maintenance cost; THE MIKE RULE says that cost is intended. Needs Mike to confirm the rule still applies here. |
| **Repair required** | Verify against `main`'s current `cin_lite` equivalents before recovery |
| **Mike decision required** | **YES** — does THE MIKE RULE extend to these two modules? |

---

## 6. Explicitly NOT recommended for recovery

Recorded with reasons, so nobody later mistakes omission for oversight.

| Work | Location | Bar it fails |
|---|---|---|
| **`dispatch/manager/` (866 lines, 8 modules) + `portal/routes/manager.py`** | `stage13-…` | **Violates BM-02** — "No mission reactivates, redesigns, or wires Manager." It registers a `manager_bp`, adds a `/manager` page and an API route. It also states in its own docstring that *"Viewing what Manager prepared is not gated by login in this build"* — an explicit auth carve-out. BM-02 postdates the branch, so this was not a violation when written; **recovering it now would be.** *Recoverable only if Mike lifts BM-02, and then only with the login carve-out removed.* |
| **`dispatch/security/` (690 lines)** | `stage13-…` | **Duplicates an accepted implementation.** `main` already has a working, fail-closed PIN gate with three disjoint session namespaces and scrypt hashing, built later and on a newer base. Two auth stacks is one too many. *The role and audit-event models inside it may be worth harvesting separately; the auth stack is not.* |
| **`dispatch_publisher/` (590 ln), `dispatch_library/` (540 ln)** | `Publisher`, `Library` repos | **Duplicates accepted implementations.** `portal/models/publisher.py` and `portal/models/library.py` operate today. The tri-department reconciliation on the Jules branch reached the same conclusion against Dispatch's real code. |
| **Jules `app.py` + `dispatch_spine.py` (~620 ln)** | Jules `main` | **Adds a competing source of operational truth** and **manufactures an operational record** — POD upload returns `"POD uploaded successfully"` with `"file_saved": "Simulated upload"` when no file was posted. The *presentation design* may be harvested; the runtime must not be. |
| **`dispatch_build/` (952 ln)** | Claude-3 `claude/dispatch-jules-arch-review-i87dru` | **Duplicates an accepted implementation** — a parallel mini-model of what `dispatch/models.py` and `dispatch/store.py` already do. EXPERIMENTAL. |
| **`l2_cos/`, `Hybrid/architecture/`, `cin_lite/agents/base.py` framework** | Old Dispatch branches | **Superseded.** June–July 2026, predating the current architecture. |
| **The four "Architect Mode" commits** | Jules `main` | **Nothing to recover — zero files changed, all four.** |

## 7. Recovery order

Dependency-ordered. Each is its own approval.

| Order | Item | Gate |
|---|---|---|
| 1 | **R-02a** CI coverage gate | None — 3 lines |
| 2 | **R-03** Route Risk tie-break | None — 1 clause + a new test |
| 3 | **R-04**, **R-05** the two cited documents | None to copy; CF-01 to place |
| 4 | **R-01** Driver Transformation | Repair the four defects first |
| 5 | **R-06** deployment blueprint / doctrine | **CF-01 + CF-02 — Mike** |
| 6 | **R-02c**, **R-02d** Archive queue, card levels | Standard review |
| 7 | **R-02b** `dispatch/spine/` | **CF-04 — Mike** |
| 8 | **R-08** MIKE RULE modules | **Mike confirms the rule** |
| 9 | **R-07** Dynamic Capacity extension | **SPINE-01 decided, then ENG-01/02 repairs** |
