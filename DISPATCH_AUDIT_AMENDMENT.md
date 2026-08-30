# DISPATCH_AUDIT_AMENDMENT

**Phase 6 deliverable — reassessment of every major conclusion in the whole-program audit.**
**Baseline:** commit `dd5d6c113a8fd2992bdcbcd7f3ef42c646e15d11` (11 deliverables, 2026-08-23)
**Amended by:** cross-repository evidence from 7 repositories and 67 branches, 2026-08-23

> **Rule applied throughout:** a finding is not weakened because another repository holds a more
> complete-looking object. Each such object was tested for whether it is **executable, connected,
> behaviorally tested, and doctrine-compliant** before any baseline conclusion was changed.

---

## Legend

**CONFIRMED** — new evidence supports it unchanged · **EXPANDED** — true, and larger or more
consequential than stated · **AMENDED** — materially wrong as stated, corrected here ·
**SUPERSEDED** — replaced by a different conclusion · **UNRESOLVED** — cannot be settled by
available evidence.

---

## 1. The fourteen conclusions the mission named

### 1.1 "718 disconnected lines" — **CONFIRMED and EXPANDED**

**Original:** `dispatch/capacity.py`, `opportunities.py`, `truck_arrangement.py` — 718 lines on
`main`, referenced by nothing outside themselves and their tests.

**Still true.** Re-verified at `37f4fd0`: the only inbound references remain
`opportunities.py:17-18`; no table, no route, no template, no service call.

**Expanded:** a further **827 lines** of the same package sit unmerged on
`harden-dispatch-dynamic-capacity-…` (`e75acb0`) — `CapacityState`, `CapacityDataMetadata`,
`StopRecord`, `StopSequenceEvaluation`, `DynamicCapacityEvaluation`, `project_capacity()`,
`evaluate_capacity()`. The disconnected body is **1,545 lines, not 718**, and the newer half is the
part that would have made it useful.

### 1.2 Dynamic Capacity maturity — **CONFIRMED**

**Original:** STRUCTURAL PROTOTYPE. **Unchanged.** The unmerged extension is also unwired, so it
raises the volume, not the maturity. It would still be a STRUCTURAL PROTOTYPE after recovery.

### 1.3 Truck Arrangement maturity — **CONFIRMED**

STRUCTURAL PROTOTYPE, 69 lines on `main`, +113 unmerged. Same reasoning.

**Related amendment — Stop Sequence:** the baseline called it *"a stop count, not a sequence."*
Correct for `main`. **A real `StopRecord` / `StopSequenceEvaluation.evaluate_sequence()` model
exists** on `e75acb0`. The gap is a delivery failure, not a design gap.

### 1.4 The third Opportunity state machine — **CONFIRMED, and the picture is worse**

**Original:** `opportunities.py:26-46` is a third state machine on `main` against BM-10, with no
Decision Log entry.

**Confirmed exactly.** And **expanded by a finding that inverts the significance**: the *sanctioned
second model* — the Spine work-item model BM-10 exists to protect — **was built, wired and tested,
and left on a branch**. `dispatch/spine/state.py` has 25 states and a 25-key transition table
matching Spine Specification §6, backed by 6 tables, initialized at `dispatch/db.py:422`, consumed
at `portal/routes/api.py:16-17`, inside a suite of **2,489 passing tests**.

**The unsanctioned third model shipped to `main`. The sanctioned second model did not.** See
**CF-04** — the most consequential decision in the register.

### 1.5 Optimistic verification defaults — **CONFIRMED, all ten**

Every OT-1 … OT-10 re-verified at `37f4fd0`, including `capacity.py:216`
`verified_by: str = "Mike Zachary"`, `capacity.py:244` `source: str = "ELD_LOG"`, and
`capacity.py:338`'s stale-tolerant feasibility return.

**Expanded, in both directions.** `e75acb0` adds `CapacityDataMetadata` (provenance) and
`PROHIBITED_AUTHORITY_STATUSES` — a builder was moving toward the same problem. **But the three
worst defaults are still present in that commit**, unfixed. Recovering it does not close OT-4, OT-5
or OT-6; ENG-01 and ENG-02 remain required.

### 1.6 Driver Portal write capability — **AMENDED**

**Original:** *"The Driver Portal has exactly one interactive control: Sign Out… Under Driver-First
Doctrine this is the largest gap in the program."*

**The first half stands for `main`. The diagnosis is wrong.**

`origin/jules-driver-transformation-missions-1-4-…` (`afd6e00`, 2026-08-22) implements **Driver
Transformation Missions 1–4**: 1-tap milestone progression, camera POD/evidence capture, dock
exception logging, vision fuel-receipt intake, native dialers and map navigation, a dual-layer
cockpit with a 7-day horizon — `portal/routes/driver_portal.py` +166, `driver_home.html` +235,
`tests/test_driver_portal.py` 144 lines. Writes route through `services.add_milestone()` and
`attach_evidence()`, so the M1 gate, the C3 audit, the extension allowlist and the SHA-256 checksum
all apply. `_verify_driver_load()` enforces driver-scoped access.

**Amended finding:** this is not an unbuilt feature. It is **a built feature that was never
delivered** — and it is essentially PORTAL-01 through PORTAL-04 of the baseline's own blueprint.

**Not softened:** the branch carries four real defects — silent `except Exception: pass` around the
milestone gate (a driver gets no feedback when a transition is refused, which fails the 70 MPH test
outright), the same in exception logging, **no driver scoping at all on the IFTA fuel-receipt
endpoint**, and an unguarded `float()`. **REPAIR CANDIDATE, not recover-as-is.**

### 1.7 Security defaults — **CONFIRMED**

S-1 (`"dispatch-dev-secret"` in two modules), S-2 (non-expiring, unrevocable tokens), S-3
(published `SECRET_KEY` default with a warning only), S-4 (no CSRF across 109 mutating routes), S-5
(no cookie flags) — **all re-verified at `37f4fd0`, all unchanged.**

**No repository contains a fix for any of them.** The Stage 7 security work is a *different* stack
(role/session/audit) and does not address S-1 … S-5; it also lacks the app-level gate entirely
(`grep -c "_require_authority_login" portal/app.py` → **0** on that branch). See **CF-03**.

**Jules findings J-1 … J-5 confirmed** against Jules `main` (`d1dfc9a`), whose tree is byte-identical
to the `fe35b13` the baseline inspected.

### 1.8 Backup and restore — **CONFIRMED, and now proven exhaustively**

**Original:** MISSING; *"a disk failure loses the business."*

**Confirmed across all seven inspected repositories.** No backup script, no restore procedure, no
export/import, on any branch of any of them. This is the only baseline BLOCKER for which the
cross-repository search produced **nothing at all**.

### 1.9 Governance fragmentation — **AMENDED, and materially worse**

**Original:** *"Governance lives in three repositories"*, with `DISPATCH_CONSTITUTION_v3.md` treated
as Dispatch's governing constitution.

**Two corrections.**

1. **It is five families, not three** — Dispatch's own, the Constitution v3 stack, the deployment
   blueprint's §0/§0b/§0c + D1–D13, Hold's seven-constitution lineage, and the Publisher/Library
   department doctrine.
2. **The Constitution v3 stack is explicitly NOT ADOPTED.** `DISPATCH_DEPLOYMENT_BLUEPRINT.md` §18
   records the instruction verbatim: *"`jax1313-outlook/Jules` is a sandbox artifact, not part of
   Dispatch's architecture… that document stack is explicitly out of scope here and not adopted."*
   The baseline's premise — that Dispatch's code is governed by a constitution held in Claude-3 —
   is **wrong**.

**What is actually true:** the doctrine Dispatch's code implements is
`DISPATCH_DEPLOYMENT_BLUEPRINT.md` (656 lines) — §0 Driver-First (LOCKED, with the 70 MPH test
verbatim), §0b COMI Doctrine v1 (LOCKED), §0c Dispatch Momentum Doctrine (LOCKED), and D1–D13.
D9, D10, D11, D12 and D13 are all implemented on `main` today. **It sits on an unmerged branch in a
third repository.**

**The fragmentation finding is not weakened — it is sharpened.** The problem is not that the
constitution is in the wrong repository. It is that **the governing document has never been in any
repository's `main`.**

### 1.10 Coverage configuration — **AMENDED**

**Original:** CI measures 3,145 of 22,193 lines (14 %) because `--cov=cin_lite` overrides
`.coveragerc`; recommended as mission RUN-09.

**Still true of `main`. Already fixed elsewhere.** `stage13-testing-hold-review`'s
`.github/workflows/ci.yml` reads `--cov=cin_lite --cov=dispatch --cov=portal --cov-config=.coveragerc
--cov-fail-under=90`. RUN-09 is not work to be done; it is **three lines to be recovered** (R-02a).

### 1.11 Authentication-disabled HTTP tests — **CONFIRMED**

1,161 of 1,162 HTTP tests run with `TESTING=True`, which disables the gate; only
`TestDispatchPinAuthentication` exercises it with `LOGIN_DISABLED=False`.

**Independently corroborated** by `DISPATCH_DEPLOYMENT_BLUEPRINT.md` §… freight-core defect table,
which records a **Critical** finding whose root cause is stated as: *"Unnoticed because the whole
test suite runs with `TESTING=True`, which disables the gate outright."* A real bug — every decision
email redirecting reviewers to `/login` — reached production for exactly this reason. **The baseline
identified a live blind spot that has already cost the program once.**

### 1.12 Bootstrap D-drive proof — **CONFIRMED, independently corroborated, still UNRESOLVED**

Claude-3 `main`'s `RECOVERY_REPORT.md`, written by a different session about a different path,
reaches the identical conclusion: *"Not reachable, ever… no mount, network path, or credential that
reaches a user's local Windows machine. This is a hard environment boundary, not a permission that
could be granted."*

**Two independent sessions, two paths, one conclusion.** Status stays **UNRESOLVED** until Mike runs
it on Windows. No agent can close it. See **CF-10**.

### 1.13 The Jules portal — **CONFIRMED**

PLACEHOLDER OR SIMULATION. Jules `main` moved from `fe35b13` to `d1dfc9a`, but
`git diff --stat fe35b13 origin/main` is **empty** — the tree is unchanged. Every finding holds: no
persistence, no authentication, debugger PIN committed at `flask_app.log`, `0.0.0.0` bind, and POD
upload returning `"POD uploaded successfully"` with `"file_saved": "Simulated upload"` when no file
was posted.

**Expanded:** the four commits PR #1 merged — *"Master Blueprint and Architectural Analysis
Assembly"*, *"Completion and Deployment Blueprint Assembly"*, *"MVP Path to First Live Load Roadmap
Assembly"*, *"First Live Load Portal UI Walkthrough Assembly"* — **changed 0 files each.** Four
delivery claims, zero artifacts.

### 1.14 Mike-only decisions — **EXPANDED from five to nine**

The baseline named five. All five stand. Four more are added by cross-repository evidence:

| # | Decision | Source |
|---|---|---|
| 1 | Which portal is Dispatch | Baseline — **CONFIRMED** |
| 2 | Where governance lives | Baseline — **EXPANDED**, now five families (CF-01) |
| 3 | The Opportunity lifecycle against BM-10 | Baseline — **EXPANDED**, now also *"recover `dispatch/spine/`?"* (CF-04) |
| 4 | `/calendar` retire or rename | Baseline — **CONFIRMED** |
| 5 | The 402 protected conflict notices | Baseline — **CONFIRMED** |
| **6** | **Does BM-02 still hold now that Manager is built, wired and tested?** | **New — CF-05** |
| **7** | **`DF-` prefix to resolve the D11/D12/D13 collision** | **New — CF-02** |
| **8** | **Does THE MIKE RULE extend to `dispatch/email_delivery.py` and `dispatch/receipt_vision.py`?** | **New — R-08** |
| **9** | **What happens to the seven uninspected repositories** | **New — §3** |

---

## 2. Baseline conclusions not in the mission's list, also reassessed

| Baseline conclusion | Verdict | Note |
|---|---|---|
| `/app` does not exist; it was the Jules builder's container | **CONFIRMED** | Unchanged |
| The freight engine is sound; 14 subsystems RETAIN | **CONFIRMED** | Cross-repo evidence adds nothing that displaces any of them |
| 2,817 tests pass, exit 0 | **CONFIRMED** | Re-run not required; `main` unchanged at `37f4fd0` |
| 37 of 2,817 tests are constant-only (1.3 %) | **CONFIRMED** | |
| `test_bootstrap_d_drive.py` is MISLEADING | **CONFIRMED** | |
| "54 stale merged branches" | **AMENDED** | 55 heads, **31 ahead of `main`**; by content, 8 duplicate, 8 historical, 5 recoverable, 10 chain-ancestors |
| Claude-3 is *"a strict, byte-identical subset of Jules with nothing of its own"* | **AMENDED** | True of the tree inspected. Claude-3 `main` is now `b7fc31d` and carries 7 recovery documents Jules lacks, plus a unique 32-commit branch holding the program's governing doctrine |
| `PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md` is MISSING | **AMENDED** | **Found** — 177 lines, Jules `claude/dispatch-tri-department-build-899qjm`. The 10 citations name the wrong repository (CF-06) |
| `reconciliation/` is orphaned dead code | **CONFIRMED, with context** | Still called by nothing. Its cited contract, `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md`, **exists** (331 lines, Jules branch) — the module was written against a real specification, not an imagined one |
| Three repositories | **AMENDED** | **Fourteen.** Four more inspected; seven not |
| Scheduler MISSING | **CONFIRMED** | No repository contains one |
| Revenue Projection MISSING | **CONFIRMED** | No repository contains one |
| Librarian role MISSING | **AMENDED** | `LIBRARIAN_CONSTITUTION_v1.md` exists in `Hold`; `dispatch_library` (540 ln) exists in `Library`. **Doctrine and code both exist; neither is in Dispatch, and the Library *function* is implemented separately in `portal/models/library.py`** |
| Archive has no retention policy implemented | **AMENDED** | An **Archive Review Queue** exists — `portal/models/archive.py` +75, `tests/test_archive_review_queue.py` 259 lines, unmerged on `stage6`/`stage13` |
| No `dispatch.db` exists in the workspace | **CONFIRMED** | |
| Only three live integrations | **CONFIRMED** | No repository adds one |

---

## 3. What remains UNRESOLVED

| # | Item | Why it cannot be settled here |
|---|---|---|
| U-1 | The `D:` drive delivery path | Hard environment boundary. Only Mike can close it. |
| U-2 | Seven uninspected repositories — `SAM`, `Gemini`, `Claude`, `Claude-2`, `Test-Grounds`, `L2-intelligence-agent.` (private), and any not returned by `list_repos` | Out of the mission's three-repository scope. **This audit does not claim completeness across all fourteen**, and no conclusion here should be read as covering them. |
| U-3 | Whether the Stage 2–13 chain can be recovered onto today's `main` without regression | The chain is 13 days and five merges stale. It passes **on its own base** (2,489 tests, exit 0). Whether each piece rebases cleanly is only knowable by attempting it, which this mission is barred from doing. |
| U-4 | Whether any live stakeholder token has been issued | Determines whether RUN-02's token-format change is safe. Only Mike knows. |

---

## 4. The one-sentence amendment

**The baseline audit's account of what is in `main` survives intact; its account of *why* does not.**
Dispatch is not a program whose hard parts were never built. It is a program whose hard parts were
built repeatedly, in six repositories, by three builders, and delivered once — which makes the
baseline's own **OWN-01** (prove the path from an approved merge to Mike's machine) not the
housekeeping item it looked like, but **the single defect that explains every other one.**
