# DISPATCH_CONFLICT_AND_AUTHORITY_REGISTER

**Cross-repository reconciliation — material conflicts, with authority determination.**
**Baseline audit:** `dd5d6c113a8fd2992bdcbcd7f3ef42c646e15d11`
**No conflict below was silently resolved.**

## Truth hierarchy applied

1. Mike Zachary's explicit accepted decisions → 2. Locked Dispatch Constitution and doctrine →
3. Accepted repository decision records → 4. Current operational implementation in Dispatch →
5. Behaviorally proven tests → 6. Unmerged reviewed implementation → 7. Experimental builder
implementation → 8. Completion reports and narrative claims.

---

## CF-01 · Where does Dispatch governance actually live?

| | |
|---|---|
| **Repositories** | Dispatch, Claude-3, Jules, Library, Publisher, Hold |
| **Files** | Five distinct governing families — see the reconciliation, §6 |
| **Competing versions** | **G1** `DISPATCH_DEPLOYMENT_BLUEPRINT.md` §0/§0b/§0c + D1–D13 (Claude-3, unmerged) · **G2** `DISPATCH_CONSTITUTION_v3.md` + 20 more (Claude-3 `main`, Jules `main`, Library repo — byte-identical) · **G3** Dispatch's own `DISPATCH_BUILD_MATRIX_v2`, `DRIVER_FIRST_DOCTRINE_v2`, `DECISION_LOG.md`, `CLAUDE.md` · **G4** Hold's `DISPATCH_BASE_CONSTITUTION_v1` + 6 more · **G5** `DISPATCH_CONSTITUTION_v2.md` (Publisher) / `v3` (Library) |
| **Observed behavior** | Dispatch's code implements **G1's** D9–D13 exactly. G3 governs the missions run in the Dispatch repository. G2 is cited by name in Dispatch source comments. G4 and G5 govern nothing that runs. |
| **Applicable doctrine** | G1 §18, verbatim: *"`jax1313-outlook/Jules` is a sandbox artifact, not part of Dispatch's architecture… that document stack is explicitly out of scope here and **not adopted**."* That sentence disqualifies **G2** — the family the baseline audit assumed was authoritative. |
| **Which appears authoritative** | **G1**, on hierarchy tier 1–2: it records Mike's explicit decisions and is marked LOCKED / Constitutional, and the code demonstrably implements it. **G3** is authoritative for build-mission governance and does not conflict with G1 except at CF-02. |
| **Why** | Tier 4 (current implementation) corroborates G1 and contradicts G2 — the code follows §0/§0b/§0c and the D-register, not the Constitution v3 stack. |
| **Mike decision required** | **YES** |
| **Recommended disposition** | Adopt **G1 + G3** as the governance home, land both in the Dispatch repository, and mark **G2, G4, G5** HISTORICAL with an explicit supersession record. **Do not delete them.** |

---

## CF-02 · Two registers both using D11, D12, D13

| | |
|---|---|
| **Repositories** | Dispatch, Claude-3 |
| **Files** | `DRIVER_FIRST_DOCTRINE_v2.md` (Dispatch `main`) vs `DISPATCH_DEPLOYMENT_BLUEPRINT.md` §6 (Claude-3, unmerged) |
| **Competing versions** | The deployment register defines **D11** = the Manufacturer → Shipper → Broker → Level 1 Transport legal-disclosure chain, **D12** = COMI Doctrine v1 (LOCKED), **D13** = Driver PIN Cards as a Library-managed asset. `DRIVER_FIRST_DOCTRINE_v2` relocates displaced Driver-First clauses into **D13, D14, D15**. |
| **Observed behavior** | Dispatch code cites `D11` (stakeholder disclosure, `portal/routes/stakeholder.py:4-6`), `D12`/COMI, and `D13` (driver PIN registry) — **all three in the deployment register's sense**. No code cites the v2 senses. |
| **Applicable doctrine** | The deployment register is tier 1–3; `DRIVER_FIRST_DOCTRINE_v2` is explicitly marked **PROPOSED**, not adopted. |
| **Which appears authoritative** | **The deployment register.** `DRIVER_FIRST_DOCTRINE_v2`'s D13/D14/D15 assignments collide with a live register. |
| **Why** | v2 was authored without sight of G1 — a direct consequence of CF-01. Its analysis stands; its numbering does not. |
| **Mike decision required** | **YES** |
| **Recommended disposition** | Adopt the **`DF-` prefix** already recommended in `DRIVER_FIRST_DOCTRINE_v2`: Driver-First clauses become `DF-1 … DF-15`, the deployment register keeps `D1 … D13`. This resolves the collision without renumbering either. **17 existing clause citations across 8 Dispatch files would need the prefix added.** |

---

## CF-03 · Two authentication stacks

| | |
|---|---|
| **Repositories** | Dispatch (`main` vs `stage13-testing-hold-review`) |
| **Files** | `portal/models/identity.py` + `portal/app.py` gate + `portal/models/driver_pin_registry.py` (on `main`) vs `dispatch/security/{auth,models,store,db}.py` + `portal/auth_helpers.py` + `portal/routes/security.py` (on the branch, 690 + 113 lines) |
| **Competing versions** | `main`'s is a fail-closed app-level PIN gate with three disjoint session namespaces and scrypt hashing. The branch's is a role/session/audit model with its own tables. |
| **Observed behavior** | `main`'s **operates and is tested**. The branch's has 275 test lines and passes there — but **`grep -c "_require_authority_login" portal/app.py` on that branch returns 0**: the branch has no app-level gate at all, and its own `/manager` route documents that viewing is deliberately ungated. |
| **Applicable doctrine** | `SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md` (G2 — not adopted, per CF-01) describes the branch's model. G1's D13 describes `main`'s. |
| **Which appears authoritative** | **`main`.** Tier 4 beats tier 6, the branch is 13 days older, and it lacks the gate. |
| **Mike decision required** | **NO** for the auth stack. **YES** if Mike wants the role and audit-event models harvested separately. |
| **Recommended disposition** | **Keep `main`'s.** Mark `dispatch/security/` SUPERSEDED. Optionally harvest `AuditEvent` and the role model into a separate, narrow mission. |

---

## CF-04 · Lifecycle authority — **ADJUDICATED 2026-08-23**

| | |
|---|---|
| **Repositories** | Dispatch (`main`, `stage13-…`), Jules |
| **Files** | `dispatch/spine/` (835 ln, branch) · `dispatch/opportunities.py` (297 ln, `main`) · `Jules/dispatch_spine.py` (395 ln, in-memory) |
| **Competing versions** | The branch's `dispatch/spine/state.py` has **25 states and a 25-key transition table** matching Spine Specification §6, with 6 tables (`work_items`, `events`, `portal_cards`, `audit_events`, `approval_events`, `conflict_events`) — the **work-item state model**. `opportunities.py` has a **separate 9-stage lifecycle** with its own transition table. Jules's is an in-memory simulation of the same concept. |
| **Observed behavior** | `dispatch/spine/` is **wired** (`dispatch/db.py:422`, `portal/routes/api.py:16-17`) and **tested** (`test_spine.py` passes within a 2,489-test green suite). `opportunities.py` is wired to **nothing**. Jules's stores nothing. |
| **Applicable doctrine** | **BM-10**: *"No mission may merge the load-status and work-item state models, replace either, or create a third state authority."* The adjudication established that load status and work-item state **coexist**. |
| **Which appears authoritative** | **`dispatch/spine/` is the legitimate second model** — it is the work-item model BM-10 protects, implemented to specification. **`dispatch/opportunities.py` is the third model BM-10 forbids**, and it is the one that is on `main`. |
| **Why** | The baseline audit flagged `opportunities.py` as a third state machine and was right. What it could not see is that the *second* model — the sanctioned one — was already built and left on a branch. **The wrong one shipped.** |
| **Mike decision required** | **ANSWERED.** |
| **Ruling, verbatim (2026-08-23)** | *"This is not a Spine-versus-Opportunity decision. Dispatch Spine shall become the authoritative lifecycle engine and single source of lifecycle truth. Dispatch Opportunity shall remain the authoritative opportunity-analysis, scoring, Dynamic Capacity, Scheduler, Route Risk, Special Requirements, and decision-support subsystem. Opportunity recommends. Spine records reality. Opportunity may request transitions. Spine owns transitions. Opportunity may not maintain a competing lifecycle authority. Scheduler, Dynamic Capacity, Route Risk, and Intelligence remain advisory systems and do not become lifecycle authorities."* |
| **Framing correction** | This register put CF-04 as *"Spine versus Opportunity."* **The ruling rejects that framing.** They are not competitors; they are different offices. Both are retained. |
| **Disposition** | Recover `dispatch/spine/` as the lifecycle engine. Strip Opportunity's competing lifecycle authority — eight surfaces, enumerated by line — and replace it with *requested* transitions Spine accepts or refuses. **`Filtered` and `Calendar Event` disappear**: §3 of the model shows neither was ever a lifecycle state. Nine alignment units, dependency-ordered, in `DISPATCH_CF04_LIFECYCLE_AUTHORITY_MODEL_v1.md`. |
| **Still open, and it gates one unit** | Whether *"single source of lifecycle truth"* absorbs `loads.status` (11 values, live, ~1,800 tests) or covers only the review/decision lifecycle. **Reading A (narrow) recommended** — see the model, §7. Blocks OPP-04 only. |

---

## CF-05 · Manager: dormant by standing bar, wired on a branch

| | |
|---|---|
| **Repositories** | Dispatch (`main` vs `stage12-*`/`stage13-*`), Claude-3, Jules, Hold |
| **Files** | `dispatch/manager/` (866 ln, 8 modules) + `portal/routes/manager.py` + `portal/templates/manager.html` + `tests/test_manager_foundation.py` (790 ln) vs **nothing on `main`**. Doctrine in four places: `docs/MANAGER.md` (Dispatch), `MANAGER.md` (Claude-3/Jules/Library), `MANAGER_CONSTITUTION_v1.md` (Hold), `DISPATCH_MANAGER_BUILDOUT_DESIGN_v1.md` (Jules branch, 481 ln). |
| **Observed behavior** | On `main`, Manager is **absent**. On the branch it is **fully wired**: blueprint registered, page served, `/api/manager/policy-candidates` exposed, 790 lines of passing tests. |
| **Applicable doctrine** | **BM-02**, adopted 2026-08-21: *"No mission reactivates, redesigns, or wires Manager."* The branch is dated 2026-08-10/11 — **it predates the bar and did not violate it.** |
| **Which appears authoritative** | **BM-02** (tier 3, and later in time). Manager stays dormant. |
| **Mike decision required** | **YES** — BM-02 was written when Manager was believed unbuilt. It is built, wired and tested. Mike may reasonably want to reconsider the bar now that the cost of the decision is known. |
| **Recommended disposition** | **Leave BM-02 in force and leave Manager on the branch.** Record explicitly that 866 lines + 790 test lines exist and are recoverable if the bar is lifted. If Mike does lift it, the `/manager` login carve-out must be removed first — the module's own docstring states viewing is deliberately ungated. |

---

## CF-06 · `PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md` — cited to the wrong repository

| | |
|---|---|
| **Repositories** | Dispatch, Jules |
| **Files** | 10 citations across `portal/models/identity.py:5`, `portal/app.py`, `portal/routes/auth.py`, `tests/test_portal.py` — all naming *"(Claude-3 repo)"*. The document is 177 lines on **Jules** `claude/dispatch-tri-department-build-899qjm`. |
| **Observed behavior** | A reviewer following the citation into Claude-3 finds nothing. The baseline audit concluded it was MISSING. |
| **Which appears authoritative** | The document is real; **the citations are wrong** about where it lives. |
| **Mike decision required** | **NO** |
| **Recommended disposition** | Recover the document (R-04) and correct the 10 citations to point at its landing place. |

---

## CF-07 · Four empty commits merged as delivered work

| | |
|---|---|
| **Repositories** | Jules |
| **Files** | None — that is the finding |
| **Competing versions** | `56001f9`, `15d35fd`, `ab3d836`, `db224d6` by `google-labs-jules[bot]`, titled *"Architect Mode: Master Blueprint and Architectural Analysis Assembly"*, *"…Completion and Deployment Blueprint Assembly"*, *"…MVP Path to First Live Load Roadmap Assembly"*, *"…First Live Load Portal UI Walkthrough Assembly"*. Merged into Jules `main` as PR #1. |
| **Observed behavior** | `git diff-tree --name-only -r` on each: **0 files.** `git diff --stat fe35b13 origin/main`: **empty.** |
| **Applicable doctrine** | Tier 8 — completion reports and narrative claims are the lowest tier of evidence. |
| **Which appears authoritative** | **Nothing.** There is no artifact. |
| **Mike decision required** | **NO** — but it is the clearest available evidence for how much weight to give a completion statement. |
| **Recommended disposition** | Record and move on. Nothing to recover, nothing to archive. |

---

## CF-08 · A department repository that is completely empty

| | |
|---|---|
| **Repositories** | `Route-Risk` |
| **Observed behavior** | `git clone` → *"You appear to have cloned an empty repository."* **Zero commits**, last "pushed" 2026-08-19. |
| **Competing versions** | Route Risk is meanwhile **implemented, durable and tested** inside Dispatch (`route_risk/` + `dispatch/route_risk.py` + 20 tests). |
| **Which appears authoritative** | **Dispatch's implementation.** The repository is a name with nothing behind it. |
| **Mike decision required** | **NO** |
| **Recommended disposition** | Archive or delete the empty repository so it stops implying a parallel implementation exists. |

---

## CF-09 · Dispatch code depends on packages in other repositories

| | |
|---|---|
| **Repositories** | Dispatch, Library, Publisher |
| **Files** | `portal/models/library.py:39-41` cites `dispatch_library.models.RESERVED_SYSTEM_IDENTITIES` and `dispatch_publisher.models.RESERVED_SYSTEM_IDENTITIES` *"from the tri-department build"*. Those packages exist only in the `Library` (540 ln) and `Publisher` (590 ln) repositories. |
| **Observed behavior** | Dispatch's own constant is **hard-coded to match**, not imported — so nothing breaks. But the invariant is maintained by a comment across a repository boundary, with no test anywhere that would catch a divergence. |
| **Which appears authoritative** | **Dispatch's copy** (tier 4), consistent with THE MIKE RULE. |
| **Mike decision required** | **NO** |
| **Recommended disposition** | Keep Dispatch's copy, archive the two packages, and either drop the cross-repo citation or restate it as historical provenance. |

---

## CF-10 · The `D:` drive — corroborated, still UNRESOLVED

| | |
|---|---|
| **Repositories** | Dispatch, Claude-3 |
| **Files** | `bootstrap_d_drive.py` (Dispatch `main`, PR #115) vs Claude-3 `main`'s `RECOVERY_REPORT.md` |
| **Observed behavior** | The baseline audit found no Windows filesystem reachable and no proof the utility ever ran against a real target. **Claude-3's recovery report independently reports the same boundary** for a different path: *"Not reachable, ever, from this session: the local path `D:\DISPATCH_AND_SAM_RECOVERY`… This session runs in an isolated cloud container with no mount, network path, or credential that reaches a user's local Windows machine. This is a hard environment boundary, not a permission that could be granted."* |
| **Which appears authoritative** | Both agree. **Two independent sessions, two different paths, same conclusion.** |
| **Mike decision required** | **NO** — but the proof (baseline OWN-01) is his to perform |
| **Status** | **UNRESOLVED** until Mike runs it on the Windows host and reports the result. No agent can close this. |

---

## Summary

| Conflict | Mike decision required | Status |
|---|---|---|
| CF-01 governance home | **YES** | Open |
| CF-02 D-numbering collision | **YES** | Open |
| CF-03 two auth stacks | NO | Resolved — `main` wins |
| CF-04 lifecycle authority | ANSWERED | **ADJUDICATED 2026-08-23** — one sub-question open (`loads.status` scope) |
| CF-05 Manager wired on a branch vs BM-02 | **YES** | Open |
| CF-06 wrong-repository citation | NO | Resolved — recover and correct |
| CF-07 four empty commits | NO | Resolved — nothing exists |
| CF-08 empty Route-Risk repo | NO | Resolved — archive it |
| CF-09 cross-repo package citation | NO | Resolved — keep Dispatch's copy |
| CF-10 `D:` drive | NO | **UNRESOLVED** — only Mike can close it |
