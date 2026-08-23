# DISPATCH_CROSS_REPOSITORY_RECONCILIATION

**Continuation of the whole-program audit committed as `dd5d6c113a8fd2992bdcbcd7f3ef42c646e15d11`.**
That audit is the baseline. It is not discarded or restarted; it is amended where new evidence
requires — see `DISPATCH_AUDIT_AMENDMENT.md`.

**Date:** 2026-08-23 · **Authority:** Mike Zachary
**Production code changed: NO · Doctrine changed: NO · Branches merged: NO · Files removed: NO**

---

## 1. The headline

The baseline audit answered *"what is in the Dispatch repository?"* correctly. It asked the wrong
question. The right question was *"what did Mike's builders actually produce?"* — and the answer is
that **a large, tested, working body of Dispatch was built and never merged.**

| | Baseline audit said | Cross-repository evidence says |
|---|---|---|
| Repositories | 3 | **14 under `jax1313-outlook`** |
| Dispatch branches | "54 stale merged branches" | 55 heads, **31 with commits ahead of `main`** |
| The Spine in code | *"`spine` appears 0 times"* | **`dispatch/spine/` exists — 25 states, 6 tables, wired, tested — on an unmerged branch** |
| Driver write capability | *"exactly one control: Sign Out"* | **Built. Milestone stepping, POD upload, exception logging, fuel-receipt scan — unmerged** |
| CI coverage gate | "measures 14 %" | **Already fixed on an unmerged branch** (`--cov=cin_lite --cov=dispatch --cov=portal`) |
| Missing PIN-scope document | "exists in no repository" | **Found** — 177 lines, on an unmerged Jules branch |
| Governance homes | 3 | **5 distinct governing families** |

**Nothing in this reconciliation weakens a baseline finding about `main`.** Every finding about
what `main` contains today stands. What changes is the explanation: Dispatch is not an unfinished
program. It is a **finished-in-pieces program with a broken delivery path** — exactly the defect
the baseline audit named D-1 and OWN-01, now measured at its true size.

## 2. Repository state — Phase 1

### 2.1 The three named repositories

| | Dispatch | Jules | Claude-3 |
|---|---|---|---|
| Remote | `github.com/jax1313-outlook/Dispatch` | `.../Jules` | `.../Claude-3` |
| Default branch | `main` | `main` | `main` |
| `main` HEAD | `37f4fd033e57c55f46dfd0568d3371e8473d683f` | `d1dfc9ac` | `b7fc31d4` |
| Working branch here | `claude/dispatch-repo-context-reconcile-7mblbb` | same name | same name |
| Working-tree HEAD | `dd5d6c11` (audit baseline) | `fe35b13c` | `29e7ae09` |
| Working tree | clean | clean | clean |
| Remote heads | **55** | **7** | **5** |
| Branches ahead of `main` | **31** | 5 | 4 |

**Both Jules and Claude-3 `main` moved after the baseline audit was taken.** The baseline recorded
Jules at `fe35b13` and Claude-3 at `29e7ae0` — those were the checked-out branch tips, not `main`.
This is a correction to the baseline's Phase 1, and it matters: Claude-3's `main` now carries seven
recovery documents that did not exist in the tree the baseline inspected.

### 2.2 The eleven repositories the baseline never saw

`list_repos` returns **14** repositories. Four were inspected in this reconciliation; the mission
scoped three; the rest are named here and **not inspected**, which is stated rather than papered
over.

| Repository | Pushed | Inspected | Finding |
|---|---|---|---|
| `Dispatch` | 2026-08-23 | ✅ | Operational destination |
| `Claude-3` | 2026-08-22 | ✅ | Reviewer / architecture evidence |
| `Jules` | 2026-08-22 | ✅ | Builder evidence + presentation prototype |
| **`Route-Risk`** | 2026-08-19 | ✅ | **Completely empty. Zero commits.** A named department repository that was created and never used. |
| **`Publisher`** | 2026-08-11 | ✅ | Real package `src/dispatch_publisher/` — **590 lines**, 3 test files, own `DISPATCH_CONSTITUTION_v2.md` |
| **`Library`** | 2026-08-11 | ✅ | Real package `src/dispatch_library/` — **540 lines**, 5 test files, own `DISPATCH_CONSTITUTION_v3.md` |
| **`Hold`** | 2026-08-05 | ✅ | 68 files, **0 lines of Python** — a seeded construction repo carrying a **fourth constitutional family** (7 constitution/doctrine files + its own `DECISION_LOG.md` and `APPROVAL_REGISTER.md`) |
| **`Dispatch-Old`** | 2026-08-12 | ✅ | 86 files, `cin_lite`, `CONSTITUTION.md`, and `REPO_TO_DISPATCH_MAP.md` which maps the old department names onto Dispatch's |
| `SAM` | 2026-08-19 | ❌ | Govcon — separate program by doctrine (Research Scout stays separate) |
| `Gemini` | 2026-08-16 | ❌ | Not inspected |
| `L2-intelligence-agent.` | 2026-08-11 | ❌ | Private; not inspected |
| `Claude-2` | 2026-08-10 | ❌ | Not inspected |
| `Claude` | 2026-08-10 | ❌ | Not inspected |
| `Test-Grounds` | 2026-08-08 | ❌ | Not inspected |

**Dispatch's own code cites two of these by name.** `portal/models/library.py:39-41`:

> *"Matches `dispatch_library.models.RESERVED_SYSTEM_IDENTITIES` / `dispatch_publisher.models.RESERVED_SYSTEM_IDENTITIES` from the tri-department build."*

Those packages exist only in the `Library` and `Publisher` repositories. **The Dispatch codebase
carries a cross-repository citation to code no Dispatch checkout contains.**

## 3. What is unmerged in Dispatch — Phase 2/3

31 branches carry commits `main` does not. Counting commits overstates it: several were squash-merged
and their branches never deleted, so the content *is* on `main`. Classification is by **content**,
verified file by file.

### 3.1 Squash-merged — content already on `main`, branch not deleted (DUPLICATE)

`dispatch/conflict-notice-dedup-fix` (dedup loop present at `portal/models/conflict.py:72-79`) ·
`dispatch/intelligence-library-promote-route` (`/intelligence/promote` present in `api.py`) ·
`dispatch/portal-authentication-pin` (`identity.py` + gate present) ·
`dispatch/operational-intelligence-verification-labeling` ·
`claude/sandbox-source-type-filtering-hold` (`tests/test_sandbox_program_scoping.py` present) ·
`claude/pr-1-1-blueprint-girvb1` · `claude/dispatch-repo-verification-gjv4uv` ·
`feat-d-drive-bootstrap-…` (**0 additions, 0 deletions vs `main`** — a pure snapshot branch).

### 3.2 Historical / superseded — predates the current architecture (HISTORICAL)

`claude/ai-agent-collector-module-l6vpxl` · `claude/baseagent-abstract-interface-1xr9bn`
(cin_lite agent framework, Docker, metrics — 2026-07-28) · `claude/l2-cos-dispatch-refactor-c1ett1`
(`l2_cos/` package, the pre-Dispatch clone) · `claude/new-session-dzkxp4` · `portal-deploy` ·
`feature/init-hybrid-structure` and `claude/sdvosb-contract-opportunities-76rgtu` and
`claude/va-2026-541512-exec-summary-lpgno3` (all three carry the same `Hybrid/architecture/` document
set — the original hybrid CIN structure, June–July 2026).

### 3.3 Genuinely unmerged, genuinely useful (RECOVER CANDIDATE)

Detailed in `DISPATCH_RECOVERABLE_WORK_MATRIX.md`. Summary:

| Branch | Tip | Added vs `main` | What it is |
|---|---|---|---|
| **`stage13-testing-hold-review`** | `0e2096a` | **+9,175 lines, 44 new files** | A linear 14-commit chain covering **Stages 2–13**: governance import, Spine schemas, portal card levels, Security Foundation, Manager M4–M7, Archive Review Queue, CI coverage-gate fix. **2,489 tests pass, exit 0.** |
| **`jules-driver-transformation-missions-1-4-…`** | `afd6e00` | +491 lines, 1 new file | **Driver Transformation Missions 1–4** — milestone stepping, POD capture, exception logging, fuel-receipt scan, with an IDOR check |
| **`harden-dispatch-dynamic-capacity-…`** | `e75acb0` | +827 lines | *"Implement seven Dynamic Capacity architecture capabilities"* — `CapacityState`, `StopRecord`, `StopSequenceEvaluation`, `DynamicCapacityEvaluation`, `project_capacity`, `evaluate_capacity`, data-provenance metadata |
| **`jules-401783631158985267-177d2e11`** | `0eccd58` | +605 lines, 2 new files | Four commits after PR #110's merge: THE MIKE RULE duplication (`dispatch/email_delivery.py`, `dispatch/receipt_vision.py`), a **Route Risk ordering tie-break fix**, Mission Visibility Accessor |
| `dispatch-operational-intelligence-playbook-…` | `fbe0542` | +442 lines, 2 docs | Duplication/extraction action reports applying THE MIKE RULE |

## 4. What is unmerged in Jules

| Branch | Ahead | Content |
|---|---|---|
| `claude/dispatch-final-blueprint-v1-1vlkkc` | 43 | **+5,172 lines of design and reconciliation documents** — `DISPATCH_FINAL_BLUEPRINT_v1.md` (1,133 lines), `DISPATCH_INTEGRATED_BLUEPRINT_v1.md`, `DISPATCH_BLUEPRINT_DECISION_LOG.md`, and the Stage 4–13 build-design and reconciliation records. **These are the design counterparts to Dispatch's `stage*` code branches.** |
| `claude/dispatch-tri-department-build-899qjm` | 61 | **+6,558 lines** — including **`PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md` (177 lines)**, `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` (331), `DISPATCH_KNOWN_GAP_REPORT_v1.md`, completeness reviews for Intelligence/Library/Publisher, and `integration/cross_repo_walkthrough.py` (166 lines of actual tooling) |
| `claude/e-ingestion-setup-bz23tm` | 1 | The recovery document set (also merged to Claude-3 `main`) |
| `dispatch-presentation-layers-…`, `revert-2-…` | — | The presentation prototype, merged |

### 4.1 Four empty commits merged as work

`Jules` `main` merged PR #1 from `jules-13086465147654077201-fa7a7009`, containing four commits by
`google-labs-jules[bot]`:

```
56001f9  Architect Mode: Master Blueprint and Architectural Analysis Assembly     0 files changed
15d35fd  Architect Mode: Dispatch Completion and Deployment Blueprint Assembly    0 files changed
ab3d836  Architect Mode: Dispatch MVP Path to First Live Load Roadmap Assembly    0 files changed
db224d6  Architect Mode: Dispatch First Live Load Portal UI Walkthrough Assembly  0 files changed
```

`git diff --stat fe35b13 origin/main` on Jules returns **nothing**. Four commits claiming Blueprint,
Roadmap and Walkthrough assembly delivered **zero files**. This is the exact failure mode the
mission warns about: *do not treat a Jules completion statement as evidence of implementation.*

## 5. What is unmerged in Claude-3

| Branch | Ahead | Content |
|---|---|---|
| **`claude/dispatch-jules-arch-review-i87dru`** | **32** | `DISPATCH_DEPLOYMENT_BLUEPRINT.md` (**656 lines**) — §0 Driver-First Doctrine, §0b COMI Doctrine v1, **§0c Dispatch Momentum Doctrine**, §12–§22 build reports, and the **D1–D13 deployment decision register**. Plus `dispatch_build/` (**952 lines**, a parallel mini-implementation), `demo_first_live_load.py`, and 5 test files. |
| `claude/dispatch-final-blueprint-v1-1vlkkc`, `claude/dispatch-tri-department-build-899qjm`, `claude/e-ingestion-setup-bz23tm` | — | Identical SHAs to Jules — the same branches exist in both repositories |

**`DISPATCH_DEPLOYMENT_BLUEPRINT.md` is the document Dispatch's code actually follows.** Its §0
states the Driver-First Doctrine and the 70 MPH test verbatim. Its D1–D13 register records the
decisions the codebase implements — D9 (Driver-First, LOCKED), D10 (email archive handling), D11
(the Manufacturer → Shipper → Broker → Level 1 Transport disclosure chain), D12 (COMI Doctrine,
LOCKED), D13 (Driver PIN Cards as a Library-managed asset). Every one of those is implemented on
Dispatch `main` today.

**It is on an unmerged branch in a third repository.**

## 6. Governance — Phase 5

Governance does not live in three places. It lives in **five distinct families**, and they do not
agree about which is authoritative.

| # | Family | Location | Status |
|---|---|---|---|
| **G1** | `DISPATCH_DEPLOYMENT_BLUEPRINT.md` §0/§0b/§0c + D1–D13 | Claude-3 `claude/dispatch-jules-arch-review-i87dru` — **unmerged** | **This is what the code implements.** Marked LOCKED / Constitutional. |
| **G2** | `DISPATCH_CONSTITUTION_v3.md`, `DISPATCH_SPINE_SPECIFICATION_v1.md`, `MANAGER.md`, `SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md` + 17 more | Claude-3 `main`, Jules `main`, **and the `Library` repo** — byte-identical | **Explicitly NOT ADOPTED.** §18 of G1 records the instruction verbatim: *"`jax1313-outlook/Jules` is a sandbox artifact, not part of Dispatch's architecture"*, and that this stack *"uses different vocabulary than what's already locked in real Dispatch (§0, §0b, D1-D12) — that document stack is explicitly out of scope here and not adopted."* |
| **G3** | Dispatch repo's own governance — `DISPATCH_BUILD_MATRIX_v1/v2`, `DRIVER_FIRST_DOCTRINE_v2`, `DISPATCH_OWNERSHIP_MATRIX_v1`, `DECISION_LOG.md`, `CLAUDE.md` | Dispatch `main` | Adopted for the missions it governs. **Written without sight of G1** — which is why `DRIVER_FIRST_DOCTRINE_v2` reassigns D13/D14/D15 while G1's register already uses D13. |
| **G4** | `DISPATCH_BASE_CONSTITUTION_v1`, `IFTA_CONSTITUTION_v1`, `LIBRARIAN_CONSTITUTION_v1`, `MANAGER_CONSTITUTION_v1`, `MEMORY_DOCTRINE_v1`, `RECEIPT_CONSTITUTION_v1` + `APPROVAL_REGISTER.md` + its own `DECISION_LOG.md` | `Hold` repo | A **fourth, independent constitutional lineage** the baseline audit never saw. Zero implementation in that repo. |
| **G5** | `DISPATCH_CONSTITUTION_v2.md` (Publisher repo), `DISPATCH_CONSTITUTION_v3.md` (Library repo), `DISPATCH_AGENT_GOVERNANCE_LAW_v1.md`, tri-department matrices | `Publisher`, `Library` repos | Department-local doctrine attached to 1,130 lines of unmerged package code |

**The document the baseline reported as missing everywhere — `PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md` — is in G-adjacent territory:** 177 lines, on Jules `claude/dispatch-tri-department-build-899qjm`. Dispatch's `portal/models/identity.py:5` cites it as "(Claude-3 repo)". It is in the **Jules** repo. That citation is wrong about the repository, and the document is real.

**This audit does not select the governance home.** That is a Mike-only decision; see
`DISPATCH_CONFLICT_AND_AUTHORITY_REGISTER.md`, conflict **CF-01**.

## 7. Workstream reconciliation — Phase 3

| Workstream | Began | Changed | Merged | Isolated | Operates now | Disconnected | Disposition |
|---|---|---|---|---|---|---|---|
| **Dynamic Capacity** | Dispatch PR #113 | PR #114 hardening; `e75acb0` adds 7 more capabilities | Two commits | `e75acb0` (+827) | Nothing — unwired | All 352 lines | RECOVER after adjudication |
| **Truck Arrangement** | PR #113 | `e75acb0` (+113) | Base only | The extension | Nothing | All 69 lines | Same as above |
| **Stop Sequence** | PR #113 as a *count* | `e75acb0` adds `StopRecord`, `StopSequenceEvaluation` | Count only | The real sequence model | Nothing | All | RECOVER after adjudication |
| **Opportunity lifecycle** | PR #113 | — | Yes, to `main` | — | Nothing — unwired | All 297 lines | **CONFLICTED** — third state model, BM-10 |
| **Score** | `dispatch/scoring.py` | Stable | Yes | — | **Operates**, advisory | — | RETAIN |
| **Scheduler** | Never built | — | — | — | Nothing | — | Blocked on Outlook decision |
| **Intelligence** | `cin_lite/` | Tri-department build produced a separate package | cin_lite yes | Tri-department | **cin_lite operates** | Tri-department package | ARCHIVE the duplicate |
| **Route Risk** | `route_risk/` | M3 durability; `28b5e65` ordering fix | M3 yes | The tie-break fix | **Operates**, durable | `Route-Risk` repo is **empty** | RECOVER the tie-break |
| **Driver Portal** | `driver_pin_registry` + read-only home | **Missions 1–4 built** | **Read half only** | **All write capability** | Read-only | Milestone/POD/exception/fuel | **RECOVER — top priority** |
| **Operations Portal** | `portal/` | Stage 5 card levels; Stage 12 Manager page | Base yes | Stage 5/12 additions | **Operates** | Card-level display, Manager page | Partial recover |
| **Stakeholder Portal** | PR #99 | — | Yes | — | **Operates** | — | RETAIN; token lifecycle still open |
| **Authentication** | `dispatch/portal-authentication-pin` | Stage 7 built a *second, different* auth stack | PIN gate yes | `dispatch/security/` (690 lines) | **PIN gate operates** | Stage 7 stack | **CONFLICTED — CF-03** |
| **Security** | Freight-core defect fixes | Stage 7 Security Foundation | Hardening yes | Stage 7 | Hardening operates | Role/audit/session model | Partial recover |
| **Library** | `portal/models/library.py` | `Library` repo built `dispatch_library` (540 ln) | Portal model yes | The package | **Portal model operates** | The package | ARCHIVE the duplicate |
| **Archive** | `cin_lite/archive.py`, `portal/models/archive.py` | Stage 6 Archive Review Queue (+259 tests) | Base yes | Review queue | **Operates** | Review queue | RECOVER candidate |
| **Publisher** | `portal/models/publisher.py` | `Publisher` repo built `dispatch_publisher` (590 ln) | Portal model yes | The package | **Portal model operates** | The package | ARCHIVE the duplicate |
| **COMI** | D12, `comi_routing.py` | — | Yes | COMI context doc | **Operates** | Doctrine document | RETAIN |
| **Synchronization** | `sync/` | — | Yes | — | Launcher only | — | RETAIN |
| **Bootstrap / D-drive** | PR #115 | — | Yes | — | **Never run against a real target** | — | **UNVERIFIABLE — unchanged** |
| **Persistence** | `dispatch/db.py`, 26 tables | Stage 4 added 6 Spine tables | 26 yes | Spine 6 | **26 operate** | Spine schema | RECOVER candidate |
| **Backup / restore** | Never built anywhere | — | — | — | **Nothing** | — | **Still MISSING — no repository has it** |
| **Outlook boundaries** | Doctrine only | — | — | — | Nothing, correctly | — | Blocked on decision |
| **Governance** | Five families | Continuously | G3 only | G1, G2, G4, G5 | G3 governs missions | **G1 governs the code and is unmerged** | **CF-01** |

## 8. What this changes about the baseline

Fully itemised in `DISPATCH_AUDIT_AMENDMENT.md`. In one sentence:

**The baseline's description of `main` was accurate; its diagnosis of the program was not.** The
program's problem is not that the work was never done. It is that **the work was done four times, in
four places, and delivered once.**
