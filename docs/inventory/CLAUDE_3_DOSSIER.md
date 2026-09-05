# CLAUDE_3_DOSSIER.md

Repository inventory dossier. Authority: Mike Zachary.
Compiled 2026-09-05. Default branch `main` at `bdf5f8f`; **all 6 branches examined**.

Recovery operation only. This dossier records what exists. It makes no design,
archive, cleanup, or refactor recommendation.

> **Read this first.** `main` holds 29 documents and no code. The branches hold **87 further
> files**, including `DISPATCH_FINAL_BLUEPRINT_v1.md` (1,133 lines), roughly 60 mission,
> design, review and reconciliation documents, and a 12-module Python package
> (`dispatch_build/`) with its own tests. None of it is on `main`.

---

## SECTION 1 — REPOSITORY FACTS

| Fact | Value | How established |
|---|---|---|
| Repository name | `Claude-3` | `git remote get-url origin` |
| Repository URL | https://github.com/jax1313-outlook/Claude-3 | same |
| Visibility | Public | `list_repos` |
| Creation date (first commit) | 2026-08-10 13:09:04 -0400 | `git log --reverse` |
| Last commit date (`main`) | 2026-08-24 00:57:41 -0400 (`bdf5f8f`, "Merge pull request #2 — record where the Dispatch implementation is") | `git log -1` |
| Last commit (any branch) | 2026-08-29 14:17:40 (`claude/dispatch-repo-context-reconcile-7mblbb`) | branch scan |
| Last push | 2026-08-29T14:18:04Z | `list_repos` |
| Branch count | **6** | `git ls-remote --heads` |
| Commit count (`main`) | **6** | `git rev-list --count HEAD` |
| Default branch | `main` | `git ls-remote` |
| Contributors | `jax1313-outlook` (4), `Claude <noreply@anthropic.com>` (2) | `git shortlog -sne` |
| README status | Present — `README.md` | `git ls-files` |
| Tracked files (`main`) | 29 — **all markdown** | `git ls-files` |
| Python (`main`) | **0** | `git ls-files '*.py'` |
| Markdown (`main`) | 29 files, 5,078 lines | `wc -l` |
| Files unique to branches | **87** | branch scan |

### Branches, measured

| Branch | Files | `.md` | `.py` | Python LOC | Tip |
|---|---|---|---|---|---|
| `main` | 29 | 29 | 0 | 0 | 2026-08-24 |
| `claude/dispatch-tri-department-build-899qjm` | 61 | 60 | 1 | 166 | 2026-08-14 |
| `claude/dispatch-jules-arch-review-i87dru` | 46 | 26 | **18** | **1,482** | 2026-08-19 |
| `claude/dispatch-final-blueprint-v1-1vlkkc` | 43 | 43 | 0 | 0 | 2026-08-11 |
| `claude/dispatch-repo-context-reconcile-7mblbb` | 29 | 29 | 0 | 0 | 2026-08-29 |
| `claude/e-ingestion-setup-bz23tm` | 28 | 28 | 0 | 0 | 2026-08-16 |

---

## SECTION 2 — PURPOSE

**Evidence source:** `README.md`.

> # Dispatch Repo-3
> This repository is the clean source-of-truth package for creating
> **DISPATCH_FINAL_BLUEPRINT_v1.md**.
>
> Repo-3 exists to move Dispatch from architecture review into final blueprint assembly.
> This repository is not an archive, not a sandbox, not a debate space, and not a history
> collection.

The blueprint was to cover: authority model, Portal, Manager, Publisher, Intelligence Analyst,
Library, Archive, Dispatch Spine, version doctrine, intelligence verification.

**The mission was completed — on a branch.** `DISPATCH_FINAL_BLUEPRINT_v1.md` exists at
1,133 lines on `claude/dispatch-final-blueprint-v1-1vlkkc`. It is not on `main`.

A second, later purpose is recorded in `DISPATCH_IMPLEMENTATION_STATUS.md` (added 2026-08-24):

> **What this file is:** a pointer… so that someone reading its documents knows where the
> working system actually lives… **This repository holds** Specification and doctrine material
> only — 21 documents, no application code.

A third purpose is recorded in `RECOVERY_REPORT.md`: Claude-3 was used as the workspace for a
**prior recovery mission** over evidence at `D:\DISPATCH_AND_SAM_RECOVERY`.

---

## SECTION 3 — DIRECTORY MAP

`main` is flat — 29 markdown files at the root, no directories.

```
Claude-3/                       (main)
├── README.md
├── DISPATCH_CONSTITUTION_v3.md         Constitution (current version)
├── CONTEXT_MASTER.md  ARCHITECTURE.md  ARCHITECTURAL_DISPOSITION.md
├── COGNITIVE_FUNCTIONS.md  INTELLIGENCE_ANALYST.md  MANAGER.md  PUBLISHER.md
├── PORTAL_DESCRIPTION.md
├── DISPATCH_SPINE_OVERVIEW.md  DISPATCH_SPINE_SPECIFICATION_v1.md
├── DISPATCH_DECISION_MATRIX.md  DISPATCH_VERSION_DOCTRINE.md
├── ALERT_GOVERNANCE_DOCTRINE.md  ARCHIVE_REVIEW_POLICY.md
├── INTELLIGENCE_VERIFICATION_WORKFLOW.md
├── SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md
├── SUPERSESSION_MAP.md  REFINEMENT_ANALYST_REMOVAL.md
├── DISPATCH_REPO_MANIFEST_v3.md
├── DISPATCH_IMPLEMENTATION_STATUS.md   ← unique: pointer to where the code lives
├── DISPATCH_V0_BLUEPRINT.md            ← unique
├── DISPATCH_V0_BUILD_PLAN.md           ← unique
├── CLONE_MAP.md                        ← unique: recovered artifact → v0 stage map
├── RECOVERY_REPORT.md                  ← unique: prior recovery mission report
├── SOURCE_ARTIFACT_INDEX.md            ← unique
├── SURVIVES_EVOLVES_RETIRES.md         ← unique: classification of recovered material
└── OPEN_QUESTIONS_FOR_MIKE.md          ← unique: open decisions

(branches add)
├── DISPATCH_FINAL_BLUEPRINT_v1.md      1,133 lines — the mission deliverable
├── DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md   cited as authority by three other repos
├── LIBRARY_INGESTION_RULE.md           declared "not found in any repo in scope" elsewhere
├── ~55 further mission / design / review / reconciliation documents
├── dispatch_build/                     12 Python modules (on the jules-arch-review branch)
│   ├── models.py (218)  store.py (192)  cockpit.py (101)  sandbox.py (107)
│   ├── publisher.py (77)  trip_card.py (80)  email_helper.py (63)
│   ├── library.py (39)  archive.py (35)  accounting.py (33)  __init__.py (5)
├── demo_first_live_load.py (112)
├── integration/cross_repo_walkthrough.py + CROSS_REPO_WALKTHROUGH_REPORT.md
└── tests/  5 files: test_cockpit, test_communication_card, test_first_live_load,
                    test_hold_expiration, test_sandbox_program_scoping
```

---

## SECTION 4 — CODE INVENTORY

### On `main`
**None.** 29 markdown files, no application code, no tests, no CI.
`DISPATCH_IMPLEMENTATION_STATUS.md` states this directly: "Specification and doctrine material
only — 21 documents, no application code."

### On `claude/dispatch-jules-arch-review-i87dru` (1,482 Python LOC)

**Modules — `dispatch_build/` (12)**
| Module | LOC | Role |
|---|---|---|
| `models.py` | 218 | Domain objects |
| `store.py` | 192 | Persistence |
| `sandbox.py` | 107 | Sandbox / staging with program scoping |
| `cockpit.py` | 101 | Driver cockpit |
| `trip_card.py` | 80 | Trip card |
| `publisher.py` | 77 | Publisher |
| `email_helper.py` | 63 | Email drafting |
| `library.py` | 39 | Library |
| `archive.py` | 35 | Archive |
| `accounting.py` | 33 | Accounting |
| `__init__.py` | 5 | Package |

**Entry point** — `demo_first_live_load.py` (112 LOC), a first-live-load demonstration.

**Cross-repository harness** — `integration/cross_repo_walkthrough.py` plus
`integration/CROSS_REPO_WALKTHROUGH_REPORT.md`. This is the ecosystem's only executable
cross-repository walkthrough.

**Tests (5 files)** — `test_cockpit.py` (75), `test_communication_card.py` (59),
`test_first_live_load.py` (124), `test_hold_expiration.py` (67),
`test_sandbox_program_scoping.py` (95). *Not run during this inventory.*

`test_hold_expiration.py` is notable: `CLONE_MAP.md` records HOLD grace-period expiry as a
gap with "*No recovered equivalent found*" — this branch contains a test for it.

### APIs / Routes / CLI / Connectors / Database
None on any branch. `dispatch_build/store.py` is the only persistence layer.

---

## SECTION 5 — FUNCTIONAL CAPABILITIES

| Capability | Exists | Evidence | Primary files | Status |
|---|---|---|---|---|
| Doctrine corpus (v3 constitution + 18 doctrines) | Yes | 29 markdown files on `main` | root | DOCUMENTED |
| **Final Blueprint assembly** | Yes (branch) | `DISPATCH_FINAL_BLUEPRINT_v1.md`, 1,133 lines | branch `claude/dispatch-final-blueprint-v1-1vlkkc` | **COMPLETE on a branch; ABSENT from `main`** |
| Shared object contracts | Yes (branch) | `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` — cited as governing authority by `L2-intelligence-agent.`, `Library` and `Publisher` `KNOWN_GAPS.md` | branch | IMPLEMENTED as doctrine; consumers built against it |
| Recovery mission (inventory→classification→clone map→build plan) | Yes | `RECOVERY_REPORT.md`, `SOURCE_ARTIFACT_INDEX.md`, `CLONE_MAP.md`, `SURVIVES_EVOLVES_RETIRES.md`, `DISPATCH_V0_BUILD_PLAN.md` | `main` | COMPLETE |
| Implementation pointer | Yes | `DISPATCH_IMPLEMENTATION_STATUS.md` names `jax1313-outlook/Dispatch` `main` at `523ee32`, PR #116, merged 2026-08-24 | `main` | COMPLETE |
| Open-questions register | Yes | `OPEN_QUESTIONS_FOR_MIKE.md` | `main` | DOCUMENTED — decisions outstanding |
| `dispatch_build` prototype (cockpit, sandbox, trip card, publisher, library, archive, accounting) | Yes (branch) | 12 modules, 5 test files | branch `claude/dispatch-jules-arch-review-i87dru` | IMPLEMENTED on a branch; ABSENT from `main` |
| Cross-repository walkthrough | Yes (branch) | `integration/cross_repo_walkthrough.py` + report | branch | IMPLEMENTED on a branch |
| Tri-department build reconciliation | Yes (branch) | 60 documents incl. `TRI_DEPARTMENT_BUILD_RECEIPT_AND_QUALITY_AUDIT_v1.md` | branch `claude/dispatch-tri-department-build-899qjm` | COMPLETE on a branch |
| Application code on `main` | **No** | `DISPATCH_IMPLEMENTATION_STATUS.md` says so explicitly | — | ABSENT by design |
| Tests / CI on `main` | **No** | — | — | ABSENT |

---

## SECTION 6 — DOCUMENT INVENTORY

### On `main` (29)

**Constitutions** — `DISPATCH_CONSTITUTION_v3.md` (the current version; v2 lives in `Claude`,
`Joe-Assistant`, `L2-intelligence-agent.` and `Publisher`).

**Architecture documents** — `ARCHITECTURE.md`, `ARCHITECTURAL_DISPOSITION.md`,
`CONTEXT_MASTER.md`, `DISPATCH_SPINE_OVERVIEW.md`, `PORTAL_DESCRIPTION.md`,
`COGNITIVE_FUNCTIONS.md`.

**Specifications** — `DISPATCH_SPINE_SPECIFICATION_v1.md`,
`SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md`, `DISPATCH_DECISION_MATRIX.md`,
`INTELLIGENCE_VERIFICATION_WORKFLOW.md`.

**Governance / doctrine** — `ALERT_GOVERNANCE_DOCTRINE.md`, `ARCHIVE_REVIEW_POLICY.md`,
`DISPATCH_VERSION_DOCTRINE.md`, `SUPERSESSION_MAP.md`, `REFINEMENT_ANALYST_REMOVAL.md`,
`DISPATCH_REPO_MANIFEST_v3.md`.

**Department descriptions** — `MANAGER.md`, `PUBLISHER.md`, `INTELLIGENCE_ANALYST.md`.

**Roadmaps / build plans** — `DISPATCH_V0_BLUEPRINT.md`, `DISPATCH_V0_BUILD_PLAN.md`.

**Recovery documents (unique)** — `RECOVERY_REPORT.md`, `SOURCE_ARTIFACT_INDEX.md`,
`CLONE_MAP.md`, `SURVIVES_EVOLVES_RETIRES.md`, `DISPATCH_IMPLEMENTATION_STATUS.md`.

**Open questions** — `OPEN_QUESTIONS_FOR_MIKE.md`.

### On branches (~60 further documents)

`DISPATCH_FINAL_BLUEPRINT_v1.md` · `DISPATCH_INTEGRATED_BLUEPRINT_v1.md` ·
`DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` · `LIBRARY_INGESTION_RULE.md` ·
`DISPATCH_BLUEPRINT_DECISION_LOG.md` · `DISPATCH_MASTER_BUILD_SEQUENCE_v1.md` ·
`DISPATCH_CODE_LINEAGE_MAP_v1.md` · `DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md` ·
`DISPATCH_REPO_RECONCILIATION_MATRIX_v1.md` · `DISPATCH_DEPARTMENT_RECONCILIATION_v1.md` ·
`DISPATCH_KNOWN_GAP_REPORT_v1.md` · `DISPATCH_MERGE_READINESS_REPORT_v1.md` ·
`DISPATCH_MAIN_SYNC_SAFETY_REPORT_v1.md` · `DISPATCH_EXISTING_ASSET_PROOF.md` ·
**Deployment set:** `DISPATCH_DEPLOYMENT_BLUEPRINT.md`, `DISPATCH_DEPLOYMENT_CRITICAL_PATH_v1.md`,
`DISPATCH_DEPLOYMENT_STATUS_REPORT_v1.md`, `DISPATCH_END_TO_END_DEPLOYMENT_PLAN_v1.md`,
`DISPATCH_FIRST_REAL_DEPLOYMENT_READINESS_REVIEW_v1.md`,
`DISPATCH_FIRST_LIVE_LOAD_GAP_ANALYSIS.md`, `DISPATCH_PROMOTION_PLAN_FIRST_LIVE_LOAD.md` ·
**Archive set:** `ARCHIVE_AUTHORITY_AND_OWNERSHIP_REPORT_v1.md`,
`ARCHIVE_DEAD_SECTION_VALIDATION_MISSION_v1.md`,
`DISPATCH_ARCHIVE_ARCHITECTURE_REVIEW_{FINDINGS,MISSION}_v1.md` ·
**Integration-bridge set:** `DISPATCH_INTEGRATION_BRIDGE_{INVESTIGATION,MISSION,SCOPE}_v1.md`,
`DISPATCH_INTEGRATION_RECONSTRUCTION_v1.md`,
`DISPATCH_INTEGRITY_AND_DEPLOYMENT_VERIFICATION_MISSION_v1.md` ·
**Stage designs (16):** `DISPATCH_STAGE4_SPINE_SCHEMA_DESIGN_v1`, `STAGE6_ARCHIVE_BUILD_DESIGN_v1`,
`STAGE6_ARCHIVE_IFTA_RECONCILIATION_v1`, `STAGE6_OBJECT_FLOW_SCOPING_v1`,
`STAGE7_SECURITY_FOUNDATION_DESIGN_v1`, `STAGE7_SECURITY_RECONCILIATION_v1`,
`STAGE8_VERSION_DOCTRINE_RECONCILIATION_v1`, `STAGE9_VERIFICATION_WORKFLOW_RECONCILIATION_v1`,
`STAGE10_ALERT_GOVERNANCE_RECONCILIATION_v1`, `STAGE11_MVP_INTEGRATION_RECONCILIATION_v1`,
`STAGE12_MANAGER_BUILD_DESIGN_v1`, `STAGE12_MANAGER_ARCHIVE_WIRING_DESIGN_v1`,
`STAGE12_MANAGER_M4_MIRROR_DESIGN_v1`, `STAGE12_MANAGER_M4_M6_BUILD_DESIGN_v1`,
`STAGE12_MANAGER_M7_POLICY_HOOK_DESIGN_v1`, `STAGE13_TESTING_HOLD_REVIEW_BUILD_DESIGN_v1`,
`DISPATCH_STAGE_LAUNCH_PACKAGES_v1` ·
**Department reviews:** `INTELLIGENCE_COMPLETENESS_REVIEW_v1`,
`INTELLIGENCE_APPROVAL_CHAIN_REVIEW_v1`, `LIBRARY_COMPLETENESS_REVIEW_v1`,
`PUBLISHER_COMPLETENESS_REVIEW_v1`, `MANAGER_ORCHESTRATION_REVIEW_v1`,
`SYNC_ENGINE_AUTHORITY_AND_BOUNDARY_REVIEW_v1`,
`TRI_DEPARTMENT_BUILD_RECEIPT_AND_QUALITY_AUDIT_v1`,
`DISPATCH_TRI_DEPARTMENT_MATRIX_BUILD_RECONCILIATION_v1`,
`DISPATCH_COPILOT_ARTIFACT_REFERENCE_REVIEW_v1` ·
**Scopes:** `STAGE_1_INTELLIGENCE_LIBRARY_PUBLISHER_LINK_SCOPE_v1`,
`STAGE_2_PUBLISHER_PROPOSAL_WRITER_BRIDGE_SCOPE_v1`,
`PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1`,
`PRESENTATION_LAYER_CONSOLIDATION_SCOPE_v1`,
`OPERATIONAL_INTELLIGENCE_VERIFICATION_LABELING_SCOPE_v1`,
`DISPATCH_MANAGER_BUILDOUT_DESIGN_v1`,
`DISPATCH_INTELLIGENCE_FINAL_INTEGRATION_LAUNCH_PACKAGE_v1`,
`DISPATCH_INTELL_LIBRARY_PUBLISHER_BUILD_PACKAGE_v1` ·
`BUILD_REPORT.md` · `integration/CROSS_REPO_WALKTHROUGH_REPORT.md`.

---

## SECTION 7 — UNIQUE ASSETS

**8 of 29 `main` files are unique by content; 87 further files exist only on branches.**
The other 21 `main` files are byte-identical to copies in `Claude`, `Claude-2`, `Library` and
`Jules` — the shared doctrine set.

### 1. `DISPATCH_FINAL_BLUEPRINT_v1.md` — located, on no default branch anywhere

1,133 lines. Identical blob `ffb23f9` in **13 places across four repositories**, and on **no
default branch**:

| Repository | Branch | Path |
|---|---|---|
| `Claude-3` | `claude/dispatch-final-blueprint-v1-1vlkkc` | `DISPATCH_FINAL_BLUEPRINT_v1.md` |
| `Library` | `claude/dispatch-final-blueprint-v1-1vlkkc` | `DISPATCH_FINAL_BLUEPRINT_v1.md` |
| `Jules` | `claude/dispatch-final-blueprint-v1-1vlkkc` | `DISPATCH_FINAL_BLUEPRINT_v1.md` |
| `Dispatch` | 10 `stage*` branches | `docs/DISPATCH_FINAL_BLUEPRINT_v1.md` |

Its own header reads: *"Status: Final Blueprint Draft — Built From Repo-3 Source of Truth…
This document does not authorize deployment… **Mike Zachary is final authority. Mike decides.**"*

This matters beyond Claude-3: `L2-intelligence-agent./KNOWN_GAPS.md` records
`DISPATCH_FINAL_BLUEPRINT_v1.md` as **"not found in any repo in scope"**, and the Library and
Publisher repositories were built without it. It was there — one branch away.

### 2. `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` — an authority cited by three repositories, held on a branch
`L2-intelligence-agent.`, `Library` and `Publisher` all cite this document, by name and section,
as the contract their object models implement. It exists only on Claude-3 branches.

### 3. `LIBRARY_INGESTION_RULE.md` — declared missing elsewhere, present here
`Library/KNOWN_GAPS.md` lists `LIBRARY_INGESTION_RULE.md` under "Missing source material…
Not found in any repo in scope", and records that Library's `ingestion.py` was therefore derived
from the constitution instead. The document exists on Claude-3 branches.

### 4. The prior recovery mission's output (on `main`)
- **`RECOVERY_REPORT.md`** — the report of a recovery over `D:\DISPATCH_AND_SAM_RECOVERY`.
  Records that the local path "was never directly reachable" from a cloud container, and that
  recovery proceeded instead from 13 GitHub repositories plus a user-uploaded
  `E-Ingestion.zip` (21.5 MB, ~600 files).
- **Its headline finding**, quoted: *"the recovered material splits cleanly into two different
  programs that have been developed together, under overlapping names, since the beginning"* —
  Dispatch (freight) and CIN/CIN-Lite/Hybrid/Micro-CIN/SDVOSB (government contracting) — and
  *"Most of what was recovered is CIN/SDVOSB material and is not Dispatch v0 material."*
- **`CLONE_MAP.md`** — maps each stage of the v0 workflow
  (SWEEP→FIT→ROUTE→SCORE→AVAILABLE LOADS→SANDBOX→DECISION→COMMIT→HOLD→DELETE;
  ACTIVE LOAD→POD→INVOICE→PAYMENT→ARCHIVE) to the specific recovered artifact implementing it,
  with a coverage verdict for each. It identifies `Dispatch/dispatch/scoring.py` as *"the single
  most complete, ready-to-clone piece of the entire recovery"* and names SWEEP (no load-board
  adapter) and HOLD/DELETE (no timed expiry) as the genuine gaps.
- **`SOURCE_ARTIFACT_INDEX.md`**, **`SURVIVES_EVOLVES_RETIRES.md`**,
  **`DISPATCH_V0_BLUEPRINT.md`**, **`DISPATCH_V0_BUILD_PLAN.md`**.

### 5. `DISPATCH_IMPLEMENTATION_STATUS.md`
A pointer document recording that the working system lives in `jax1313-outlook/Dispatch` at
`main` `523ee32` (PR #116, merged 2026-08-24), and that this repository holds no application
code. It states explicitly: *"Nothing in this repository was edited, superseded, retired or
adopted by adding it."* A near-copy exists in `Jules`.

### 6. `OPEN_QUESTIONS_FOR_MIKE.md`
The only standing register of decisions awaiting Mike anywhere in the ecosystem.

### 7. `dispatch_build/` — a 12-module prototype on a branch
Cockpit, sandbox with program scoping, trip card, publisher, library, archive, accounting,
models, store, email helper — 1,482 LOC with 5 test files and a `demo_first_live_load.py`.
Includes `test_hold_expiration.py`, testing the HOLD grace-period behaviour that `CLONE_MAP.md`
records as having no recovered equivalent.

### 8. `integration/cross_repo_walkthrough.py`
The ecosystem's only executable cross-repository walkthrough, with its report.

### 9. The 16 stage-design documents and 5 Manager stage designs
`DISPATCH_STAGE12_MANAGER_*` (build, archive wiring, M4 mirror, M4–M6, M7 policy hook) — the
design counterparts to Dispatch's unmerged `stage12-manager-*` code branches.

---

## SECTION 8 — CROSS-REPOSITORY REFERENCES

| Referenced entity | Occurrences (`main`) | Representative files |
|---|---|---|
| Dispatch | 381 | throughout |
| Library | 124 | `CLONE_MAP.md`, `LIBRARY_COMPLETENESS_REVIEW_v1.md` (branch) |
| Publisher | 129 | `PUBLISHER.md`, `PUBLISHER_COMPLETENESS_REVIEW_v1.md` (branch) |
| Manager | 135 | `MANAGER.md`, 5 `STAGE12_MANAGER_*` designs (branch) |
| SAM | 29 | `RECOVERY_REPORT.md`, `SURVIVES_EVOLVES_RETIRES.md` |
| Jules | 19 | `CLONE_MAP.md`, branch `claude/dispatch-jules-arch-review-i87dru` |
| Route Risk | 8 | `CLONE_MAP.md` (cites `Dispatch/dispatch/scoring.py` route risk) |
| COMI / Mission Visibility / Joe | 0 | — |

**Explicit named references to other repositories' files** (this is the most
cross-repository-aware repository in the ecosystem — `CLONE_MAP.md` alone cites files in three
others by path):
- `Dispatch/dispatch/acquisition.py`, `models.py` (`LOAD_SOURCES`, `LOAD_STATUSES`,
  `EVIDENCE_TYPES`, `POD_STATUSES`), `scoring.py` (`_HOME_BASE`, `_OPERATING_RADIUS_MILES`,
  `_KNOWN_DISTANCES`, `_lookup_distance`), `portal/models/sandbox.py`,
  `portal/routes/dispatch_api.py`, `portal/templates/{queues,search,dispatch,rate_confirmation_print}.html`,
  `cin_lite/pending.py`, `cin_lite/acquisition.py`
- `Hold/contracts/queue_item.schema.json`, `Hold/docs/reference/DISPATCH_BUILD_BLUEPRINT_v1.md`,
  `Hold/docs/governance/DISPATCH_BASE_CONSTITUTION_v1.md`
- `Hybrid/architecture/system_overview.md`

**Repositories named in `RECOVERY_REPORT.md` that are NOT in the account listing:**
`Jules-2`, `Jules-3`, `Test-Grounds`. Also named as recovered codebases with no repository of
their own: `hybrid_v1`, `hybrid-operator` (Next.js UI), `Micro-CIN` / "CIN-Tell",
the `cin-hybrid` runtime. `Publisher/README.md` independently names
`jax1313-outlook/Test-Grounds` as "a separate GitHub repo". None of the three appear in
`list_repos`.

**Non-repository sources named:** `D:\DISPATCH_AND_SAM_RECOVERY` (unreachable),
`E-Ingestion.zip` (21.5 MB, ~600 files, delivered through chat),
`C:\USERS\JAX13\ONEDRIVE - LEVEL 1 TRANSPORT INC (1)\COPILOT WORKSPACE\E-INGESTION\`,
`Email intake system.docx`.

---

## SECTION 9 — BUILT VS PLANNED

### Built In Code
On `main`: **nothing**. On `claude/dispatch-jules-arch-review-i87dru`: the 12-module
`dispatch_build/` package, a first-live-load demo, a cross-repository walkthrough harness, and
5 test files — 1,482 lines.

### Partially Built
- **The Final Blueprint** — written in full (1,133 lines) and never merged to any default branch.
- **The stage sequence** (stages 4–13) — designs written here; code written on Dispatch's
  `stage*` branches; neither merged.

### Documented Only
The doctrine corpus (constitution v3, spine specification, security specification, decision
matrix, alert governance, archive review policy, version doctrine, verification workflow,
Manager / Publisher / Intelligence Analyst descriptions), the V0 blueprint and build plan, all
16 stage designs, the deployment set, the archive set, the integration-bridge set, and all
department completeness reviews.

### Referenced But Missing
- **`Jules-2`, `Jules-3`, `Test-Grounds`** — named in `RECOVERY_REPORT.md` (and Test-Grounds in
  `Publisher/README.md`) as real repositories in the promotion path. Not in the account listing.
- **`hybrid_v1`, `hybrid-operator`, `Micro-CIN`/"CIN-Tell"** — named as recovered codebases;
  no repository holds them. (Fragments of `cin-hybrid` survive on three Dispatch branches.)
- **`D:\DISPATCH_AND_SAM_RECOVERY`** — the original evidence location; recorded as permanently
  unreachable from a cloud session.
- **`E-Ingestion.zip`** — used by the prior mission, not committed to any repository.
- **SWEEP** and **HOLD/DELETE** — `CLONE_MAP.md` records both as having no recovered
  equivalent. (A `test_hold_expiration.py` exists on a branch here.)

### Unknown
- Why `DISPATCH_FINAL_BLUEPRINT_v1.md` was never merged to any `main`.
- Whether the `dispatch_build/` tests pass — **not run** during this inventory.
- Whether `Jules-2`, `Jules-3` and `Test-Grounds` were deleted, renamed, or never created.

---

## SECTION 10 — EXECUTIVE SUMMARY

**What is this repository?**

Claude-3 — "Dispatch Repo-3" — was created as the clean source-of-truth package for assembling
`DISPATCH_FINAL_BLUEPRINT_v1.md`. It later became the workspace for a prior recovery mission
over `D:\DISPATCH_AND_SAM_RECOVERY`. Its `main` branch holds 29 markdown documents and no code;
its six branches hold 87 further files.

**What is actually implemented?**

On `main`, no software at all — `DISPATCH_IMPLEMENTATION_STATUS.md` says so in its own words.
What is implemented is a doctrine corpus (constitution v3, spine specification, security
specification, decision matrix, alert governance, archive review policy, version doctrine) and,
crucially, the completed output of a prior recovery mission: a recovery report, a source
artifact index, a survives/evolves/retires classification, a v0 blueprint and build plan, and a
clone map that traces every stage of the target workflow to the artifact that already
implements it. On one branch there is also a working 12-module prototype (`dispatch_build/`,
1,482 lines) with a first-live-load demo, a cross-repository walkthrough harness, and five test
files.

**What unique value does it contain?**

Its `main` holds the ecosystem's only prior recovery analysis — including the finding that the
whole body of work is **two programs sharing one history**, Dispatch (freight) and
CIN/SDVOSB (government contracting), and that most of what was recovered belongs to the second.
`CLONE_MAP.md` names `Dispatch/dispatch/scoring.py` as the single most reusable recovered
artifact and identifies SWEEP and HOLD/DELETE as the real gaps. `OPEN_QUESTIONS_FOR_MIKE.md`
is the only standing register of decisions awaiting Mike anywhere.

Its branches hold three documents that other repositories were built without and recorded as
missing. **`DISPATCH_FINAL_BLUEPRINT_v1.md` exists** — 1,133 lines, identical in thirteen
places across four repositories, and on no default branch anywhere;
`L2-intelligence-agent./KNOWN_GAPS.md` records it as "not found in any repo in scope".
**`DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md`** — cited by name and section as the governing
object contract by three separate repositories — likewise exists only on a branch here. And
**`LIBRARY_INGESTION_RULE.md`**, which `Library/KNOWN_GAPS.md` also records as not found in any
repository in scope, is here too.

Finally, it names three repositories — `Jules-2`, `Jules-3` and `Test-Grounds` — as working
instances of the promotion pipeline. None of them exists in the account today.
