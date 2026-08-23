# DISPATCH_THREE_REPOSITORY_ARTIFACT_INVENTORY

**Phase 2 deliverable of the cross-repository reconciliation.**
**Baseline audit:** `dd5d6c113a8fd2992bdcbcd7f3ef42c646e15d11`
**Date:** 2026-08-23 · Nothing was modified, merged, or removed.

---

## 1. Scope and honesty note

The mission names three repositories. **Fourteen exist.** Four more were inspected because Dispatch's
own code and doctrine cite them by name; seven were not inspected and are listed as such. This
inventory covers **material artifacts** — the ones that decide a disposition — not every file. A
complete file-level inventory of 14 repositories was not attempted and is not claimed.

Blob column = `git rev-parse <ref>:<path>`, truncated to 12 hex characters. Every row is
reproducible from the commit and path given.

## 2. Repository-level inventory

| Repository | HEAD (`main`) | Heads | Ahead of main | Python LOC | Role | Disposition |
|---|---|---|---|---|---|---|
| **Dispatch** | `37f4fd03` | 55 | 31 branches | 22,193 | Operational destination | **AUTHORITATIVE** |
| **Jules** | `d1dfc9ac` | 7 | 5 branches | ~620 (prototype) | Builder evidence + presentation prototype | HISTORICAL + RECOVER (docs) |
| **Claude-3** | `b7fc31d4` | 5 | 4 branches | 952 (`dispatch_build/`) | Reviewer / architecture / doctrine | RECOVER (doctrine) |
| **Publisher** | `7f195486` | — | n/a | 590 (`src/dispatch_publisher/`) | Tri-department build | **DUPLICATE — ARCHIVE** |
| **Library** | `7e455279` | — | n/a | 540 (`src/dispatch_library/`) | Tri-department build | **DUPLICATE — ARCHIVE** |
| **Hold** | `484e40db` | — | n/a | **0** | Seeded construction repo; 4th constitution family | **HISTORICAL** |
| **Dispatch-Old** | `be6c593f` | — | n/a | `cin_lite` (86 files) | Predecessor; `REPO_TO_DISPATCH_MAP.md` | **HISTORICAL** |
| **Route-Risk** | *(none)* | 0 | n/a | 0 | — | **EMPTY — zero commits** |
| `SAM` | not inspected | — | — | — | Govcon — separate program by doctrine | UNVERIFIABLE |
| `Gemini`, `Claude`, `Claude-2`, `Test-Grounds`, `L2-intelligence-agent.` | not inspected | — | — | — | — | **UNVERIFIABLE** |

## 3. Material artifact inventory

| Repo | Path | Commit | Branch | Blob | Purpose | Equivalent elsewhere | Merged into Dispatch | Called by app | Tested | Disposition |
|---|---|---|---|---|---|---|---|---|---|---|
| Dispatch | `dispatch/services.py` | `37f4fd03` | main | `2f36f49c1e76` | Freight service layer | — | YES | YES | YES | AUTHORITATIVE |
| Dispatch | `dispatch/store.py` | `37f4fd03` | main | `15200bb3a770` | SQLite persistence, 26 tables | — | YES | YES | YES | AUTHORITATIVE |
| Dispatch | `dispatch/db.py` | `37f4fd03` | main | `1716378741fa` | Schema, WAL, migrations | — | YES | YES | YES | AUTHORITATIVE |
| Dispatch | `dispatch/capacity.py` | `37f4fd03` | main | `bc5727505022` | Dynamic Capacity model | — | YES | NO | YES | STRUCTURAL PROTOTYPE |
| Dispatch | `dispatch/opportunities.py` | `37f4fd03` | main | `292377dc2533` | Opportunity Card + 9-stage lifecycle | — | YES | NO | YES | STRUCTURAL PROTOTYPE |
| Dispatch | `dispatch/truck_arrangement.py` | `37f4fd03` | main | `5931b2e35ad6` | Cargo geometry | — | YES | NO | YES | STRUCTURAL PROTOTYPE |
| Dispatch | `portal/routes/driver_portal.py` | `37f4fd03` | main | `33eadfa14c9b` | Driver Portal (read-only) | — | YES | YES | YES | AUTHORITATIVE |
| Dispatch | `portal/routes/dispatch_api.py` | `37f4fd03` | main | `23207557e9ba` | 146 freight API routes | — | YES | YES | YES | AUTHORITATIVE |
| Dispatch | `portal/models/library.py` | `37f4fd03` | main | `1ef5ef9b7298` | Company Library | — | YES | YES | YES | AUTHORITATIVE |
| Dispatch | `route_risk/engine.py` | `37f4fd03` | main | `41f5537371f7` | Route Risk engine | — | YES | YES | YES | AUTHORITATIVE |
| Dispatch | `bootstrap_d_drive.py` | `37f4fd03` | main | `9e97d72ce433` | D: migration utility | — | YES | NO | YES | UNVERIFIABLE |
| Dispatch | `.github/workflows/ci.yml` | `37f4fd03` | main | `c6d13989116d` | CI | — | YES | YES | YES | AUTHORITATIVE |
| Dispatch | `dispatch/spine/state.py` | `0e2096ad` | stage13-testing-hold-review | `e994965fb43c` | Spine 25-state model + transitions | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `dispatch/spine/store.py` | `0e2096ad` | stage13-testing-hold-review | `a236bedab224` | Spine store | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `dispatch/spine/db.py` | `0e2096ad` | stage13-testing-hold-review | `69f64f188cac` | 6 Spine tables | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `dispatch/spine/models.py` | `0e2096ad` | stage13-testing-hold-review | `cadfa8677116` | WorkItem / PortalCard / events | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `dispatch/security/auth.py` | `0e2096ad` | stage13-testing-hold-review | `f0af3406a5f2` | Role/session/audit auth | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `dispatch/manager/staff_report.py` | `0e2096ad` | stage13-testing-hold-review | `d6e78b98eae1` | Manager staff report | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `portal/routes/manager.py` | `0e2096ad` | stage13-testing-hold-review | `44a7e8fcd032` | Manager page | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `docs/DISPATCH_CONSTITUTION_v3.md` | `0e2096ad` | stage13-testing-hold-review | `f980da24c493` | Constitution (imported) | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `docs/DISPATCH_FINAL_BLUEPRINT_v1.md` | `0e2096ad` | stage13-testing-hold-review | `ffb23f930028` | Final blueprint 1133 ln | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `docs/STAGE_STATUS.json` | `0e2096ad` | stage13-testing-hold-review | `eae76ff77bb6` | Stage gate status | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `tests/test_spine.py` | `0e2096ad` | stage13-testing-hold-review | `303265990969` | Spine tests | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `tests/test_security_foundation.py` | `0e2096ad` | stage13-testing-hold-review | `5558538b8661` | Security tests | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `tests/test_manager_foundation.py` | `0e2096ad` | stage13-testing-hold-review | `aab24a360f9d` | Manager tests | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `tests/test_archive_review_queue.py` | `0e2096ad` | stage13-testing-hold-review | `60e72360b410` | Archive queue tests | — | NO | YES (on branch) | YES | RECOVER CANDIDATE |
| Dispatch | `portal/routes/driver_portal.py` | `afd6e00e` | jules-driver-transformation… | `4a2a88d2643a` | Driver Portal + 4 write endpoints | portal/routes/driver_portal.py on main | NO | YES (on branch) | YES | REPAIR CANDIDATE |
| Dispatch | `portal/templates/driver_home.html` | `afd6e00e` | jules-driver-transformation… | `8364aa250674` | Driver cockpit UI | portal/routes/driver_portal.py on main | NO | YES (on branch) | YES | REPAIR CANDIDATE |
| Dispatch | `tests/test_driver_portal.py` | `afd6e00e` | jules-driver-transformation… | `ff398449d86b` | Driver portal tests | portal/routes/driver_portal.py on main | NO | YES (on branch) | YES | REPAIR CANDIDATE |
| Dispatch | `dispatch/capacity.py` | `e75acb09` | harden-dispatch-dynamic-capacity | `dd6f14a35864` | 7 more capabilities: StopRecord, evaluations, provenance | dispatch/capacity.py on main | PARTIAL | NO | YES | RECOVER CANDIDATE |
| Dispatch | `dispatch/store.py` | `0eccd580` | jules-401783631158985267 | `c95efbc6fd89` | Route Risk ORDER BY tie-break | dispatch/store.py on main | PARTIAL | YES | YES | RECOVER CANDIDATE |
| Jules | `app.py` | `d1dfc9ac` | main | `d5d224e9af54` | In-memory 3-portal prototype | — | NO | YES (standalone) | YES (own tests) | ARCHIVE |
| Jules | `dispatch_spine.py` | `d1dfc9ac` | main | `95f41e576829` | In-memory spine simulation | dispatch/spine/ on stage13 | NO | YES (standalone) | YES | ARCHIVE |
| Jules | `flask_app.log` | `d1dfc9ac` | main | `cadc0de704c7` | Committed log containing debugger PIN | — | NO | NO | NO | ARCHIVE — REMOVE |
| Jules | `PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md` | `4459f737` | claude/dispatch-tri-department-build | `6a6e0622c2a6` | The document identity.py cites | cited by 4 Dispatch files | NO | N/A | N/A | RECOVER CANDIDATE |
| Jules | `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` | `4459f737` | claude/dispatch-tri-department-build | `96cf69d1e335` | Object contracts cited as missing by reconciliation/ | cited by reconciliation/contracts.py | NO | N/A | N/A | RECOVER CANDIDATE |
| Jules | `DISPATCH_FINAL_BLUEPRINT_v1.md` | `950e5e21` | claude/dispatch-final-blueprint-v1 | `ffb23f930028` | 1133-line blueprint | docs/ copy on stage13 | NO | N/A | N/A | DUPLICATE |
| Jules | `integration/cross_repo_walkthrough.py` | `4459f737` | claude/dispatch-tri-department-build | `61fdfe1a163a` | Cross-repo walkthrough tool | — | NO | NO | UNKNOWN | RECOVER CANDIDATE |
| Claude-3 | `DISPATCH_DEPLOYMENT_BLUEPRINT.md` | `8a55c33a` | claude/dispatch-jules-arch-review | `2e2e5f381d2c` | §0/§0b/§0c doctrine + D1-D13 register — what the code follows | — | NO | N/A | N/A | AUTHORITATIVE (unmerged) |
| Claude-3 | `dispatch_build/models.py` | `8a55c33a` | claude/dispatch-jules-arch-review | `a6e438053caf` | Parallel mini-implementation | dispatch/models.py | NO | NO | YES | EXPERIMENTAL |
| Claude-3 | `RECOVERY_REPORT.md` | `b7fc31d4` | main | `5445975a96da` | Recovery analysis; names 13 repos | — | NO | N/A | N/A | RETAIN |
| Claude-3 | `SURVIVES_EVOLVES_RETIRES.md` | `b7fc31d4` | main | `0c8272ac7442` | Classification register | — | NO | N/A | N/A | RETAIN |
| Claude-3 | `DISPATCH_CONSTITUTION_v3.md` | `b7fc31d4` | main | `f980da24c493` | Constitution (G2) | identical in Jules and Library repo | NO | N/A | N/A | DUPLICATE — NOT ADOPTED |

## 4. Dispatch branch inventory — all 31 branches ahead of `main`

Classified by **content**, not by commit count. A branch "1 ahead" whose content is already on
`main` was squash-merged and never deleted.

### 4.1 DUPLICATE — content is on `main` (8)
`dispatch/conflict-notice-dedup-fix` · `dispatch/intelligence-library-promote-route` ·
`dispatch/portal-authentication-pin` · `dispatch/operational-intelligence-verification-labeling` ·
`claude/sandbox-source-type-filtering-hold` · `claude/pr-1-1-blueprint-girvb1` ·
`claude/dispatch-repo-verification-gjv4uv` · `feat-d-drive-bootstrap-…` *(0 additions, 0 deletions
versus `main` — a snapshot)*

### 4.2 HISTORICAL — superseded by the current architecture (8)
`claude/ai-agent-collector-module-l6vpxl` · `claude/baseagent-abstract-interface-1xr9bn` ·
`claude/l2-cos-dispatch-refactor-c1ett1` · `claude/new-session-dzkxp4` · `portal-deploy` ·
`feature/init-hybrid-structure` · `claude/sdvosb-contract-opportunities-76rgtu` ·
`claude/va-2026-541512-exec-summary-lpgno3`

### 4.3 RECOVER / REPAIR CANDIDATE (5)
| Branch | Tip | +lines vs `main` | New files |
|---|---|---|---|
| `stage13-testing-hold-review` | `0e2096a` | **9,175** | 44 |
| `harden-dispatch-dynamic-capacity-…` | `e75acb0` | 827 | 0 |
| `jules-401783631158985267-177d2e11` | `0eccd58` | 605 | 2 |
| `jules-driver-transformation-missions-1-4-…` | `afd6e00` | 491 | 1 |
| `dispatch-operational-intelligence-playbook-…` | `fbe0542` | 442 | 2 |

### 4.4 CONFLICTED — same chain, earlier tips (10)
`stage2-documentation-import` · `stage3-blueprint-alignment` · `stage4-spine-schemas` ·
`stage5-portal-reconciliation` · `stage6-archive-review-queue` · `stage7-security-foundation` ·
`stage12-manager-foundation` · `stage12-manager-archive-wiring` · `stage12-manager-m7-policy-hook`
— all are ancestors of `stage13-testing-hold-review`; recovering the tip covers them.
Plus `arch-discoveries-update-…` and `jules-401783631158985267-…`'s merged portion.

## 5. Verification evidence for the recovery candidates

| Claim | Command | Result |
|---|---|---|
| The Stage 2–13 chain is real and passes | `pytest` on a detached worktree of `origin/stage13-testing-hold-review` | **`2489 passed in 298.48s`, exit 0** |
| Its own new tests pass | `pytest tests/test_spine.py tests/test_security_foundation.py tests/test_manager_foundation.py tests/test_archive_review_queue.py tests/test_version_doctrine.py` | **`160 passed in 38.81s`**, exit 0 |
| The Spine is wired, not shelved | `grep -rn "dispatch.spine"` outside `dispatch/spine/` and `tests/` | `dispatch/db.py:422` initializes the schema; `portal/routes/api.py:16-17` imports `WorkItem`, `create_work_item`, `create_approval_event` |
| The Spine matches the specification | `len(state.STATE_LIST)`, `len(state.ALLOWED_TRANSITIONS)` | **25 and 25** — Spine Specification §6 |
| Spine tables | `grep "CREATE TABLE" dispatch/spine/db.py` | `work_items`, `events`, `portal_cards`, `audit_events`, `approval_events`, `conflict_events` |
| The CI coverage gate is already fixed there | `grep cov .github/workflows/ci.yml` | `--cov=cin_lite --cov=dispatch --cov=portal --cov-fail-under=90` |
| Manager is wired there | `portal/routes/__init__.py` | `manager_bp` registered; `/manager` page + `/api/manager/policy-candidates` |
| The Jules "Architect Mode" commits are empty | `git diff-tree --name-only -r <sha>` on each | **0 files changed**, all four |
| Jules `main` gained nothing from PR #1 | `git diff --stat fe35b13 origin/main` | **empty output** |
| Claude-3 and Jules doctrine are byte-identical | `cmp` on 5 core documents | **IDENTICAL**, all five; `comm` shows Claude-3 has no file Jules lacks |
| `Route-Risk` is empty | `git clone` | *"You appear to have cloned an empty repository"* |
| `Hold` has no implementation | `find src -name '*.py' | xargs wc -l` | **0** |

## 6. Cross-repository citations found in Dispatch code

| Citing file | Cites | Where it actually is |
|---|---|---|
| `portal/models/identity.py:5`, `portal/app.py`, `portal/routes/auth.py`, `tests/test_portal.py` (10 citations) | `PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md` *"(Claude-3 repo)"* | **Jules**, branch `claude/dispatch-tri-department-build-899qjm` — the citation names the wrong repository |
| `portal/models/library.py:39-41` | `dispatch_library.models.RESERVED_SYSTEM_IDENTITIES`, `dispatch_publisher.models.RESERVED_SYSTEM_IDENTITIES` *"from the tri-department build"* | The **`Library`** and **`Publisher`** repositories |
| `reconciliation/contracts.py:3,35,71` | `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` | **Jules**, `claude/dispatch-tri-department-build-899qjm` (331 lines) |
| `portal/models/operations_feed.py:17` | *"the Jules sandbox's `PortalCard` (§18 of the blueprint)"* | **Claude-3**, `claude/dispatch-jules-arch-review-i87dru`, `DISPATCH_DEPLOYMENT_BLUEPRINT.md` §18 |

**Four independent cross-repository citations in production code and tests.** Not one of them
resolves inside a Dispatch checkout.
