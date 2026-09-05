# LIBRARY_DOSSIER.md

Repository inventory dossier. Authority: Mike Zachary.
Compiled 2026-09-05. Default branch `main` at `7e45527`; all 3 branches examined.

Recovery operation only. This dossier records what exists. It makes no design,
archive, cleanup, or refactor recommendation.

---

## SECTION 1 — REPOSITORY FACTS

| Fact | Value | How established |
|---|---|---|
| Repository name | `Library` | `git remote get-url origin` |
| Repository URL | https://github.com/jax1313-outlook/Library | same |
| Visibility | Public | `list_repos` |
| Creation date (first commit) | 2026-08-10 13:09:04 -0400 — **same second as `Claude-3` and `Jules`** | `git log --reverse` |
| Last commit date | 2026-08-11 13:27:34 -0400 (`7e45527`, "Build Library department to integration-ready status (#1)") | `git log -1` |
| Last push | 2026-08-11T17:27:35Z | `list_repos` |
| Branch count | **3** — `main`, `claude/dispatch-final-blueprint-v1-1vlkkc`, `claude/dispatch-tri-department-build-899qjm` | `git ls-remote --heads` |
| Commit count | **4** | `git rev-list --count HEAD` |
| Default branch | `main` | `git ls-remote` |
| Contributors | `jax1313-outlook` (4) — sole contributor | `git shortlog -sne` |
| README status | Present — `README.md` | `git ls-files` |
| Tracked files | 40 | `git ls-files` |
| Python | 13 files, **875 lines** | `wc -l` |
| Markdown | 26 files, 5,677 lines | `wc -l` |
| Files unique to branches | **22** (incl. `DISPATCH_FINAL_BLUEPRINT_v1.md`, `LIBRARY_INGESTION_RULE.md`, 16 stage designs) | branch scan |

---

## SECTION 2 — PURPOSE

**Evidence source:** `README.md`.

> # Dispatch Library
> Library department implementation for the Dispatch program (Level 1 Transport / Mike Zachary).
> This repo builds the **Library** link of the Intelligence → Library → Publisher dependency
> chain defined in `04_DISPATCH_SYSTEM_RELATIONSHIP_MATRIX.md`.

`README.md` records its own repurposing:

> Legacy note: this repo was previously used as "Repo-3", a document-only package for assembling
> `DISPATCH_FINAL_BLUEPRINT_v1.md`. That mission is separate from this repo's current role.
> …this repository's job is to build and test the Library department to integration-ready status.
> The governance documents mirrored at the repo root remain as load-bearing reference material;
> `src/` is new.

Status, verbatim:

> **Integration-ready candidate.** Not merged into Dispatch. Not deployed. Not
> production-promoted. See `MERGE_READINESS_REPORT.md` and `KNOWN_GAPS.md`. Mike decides on
> promotion.

What Library **is**, per `README.md`, is "current reusable truth and controlled production asset
storage (Constitution Section 7.4), **never as temporary workspace or automatic truth from
Archive or Intelligence**."

This is the middle link of the three sibling department repositories built in one campaign on
2026-08-11 (with `L2-intelligence-agent.` and `Publisher`).

---

## SECTION 3 — DIRECTORY MAP

```
Library/
├── src/dispatch_library/       The Library department (8 modules, 875 LOC)
│   ├── taxonomy.py             The 15 Library collections — a CLOSED set
│   ├── models.py               LibraryObject, LibraryCandidate, PublisherRecipe
│   ├── registry.py             Versioned Object Registry with automatic supersession
│   ├── resolver.py             Object resolution
│   ├── ingestion.py            Human-gated ingestion
│   ├── recipes.py              Publisher recipes
│   ├── service.py              Integration surface
│   └── __init__.py
├── tests/                      5 files, 24 test functions
│   ├── test_taxonomy.py  test_registry_resolver.py  test_ingestion.py
│   ├── test_recipes.py   test_service.py
├── docs/OBJECT_MODEL.md        The object model specification
├── KNOWN_GAPS.md               Honest gap record
├── MERGE_READINESS_REPORT.md   Promotion assessment
└── (root) 22 mirrored doctrine documents — Constitution v3, ARCHITECTURE,
        CONTEXT_MASTER, MANAGER, PUBLISHER, INTELLIGENCE_ANALYST, SPINE spec,
        ALERT_GOVERNANCE, ARCHIVE_REVIEW_POLICY, VERSION_DOCTRINE,
        SUPERSESSION_MAP, DECISION_MATRIX, SECURITY spec, REPO_MANIFEST_v3,
        04_/05_ matrices, INTELLIGENCE_VERIFICATION_WORKFLOW, COGNITIVE_FUNCTIONS,
        ARCHITECTURAL_DISPOSITION, PORTAL_DESCRIPTION, REFINEMENT_ANALYST_REMOVAL
```

**Folder purposes** — `src/dispatch_library/` is the department. The root documents are the
mirrored governance set carried over from the repository's earlier "Repo-3" role and retained
deliberately as reference.

---

## SECTION 4 — CODE INVENTORY

### Applications / Entry points
None. This is a library package with no CLI, no HTTP surface and no daemon.

### Modules — `src/dispatch_library/` (8)
| Module | Role (per `README.md`) |
|---|---|
| `taxonomy.py` | The **15 Library collections**, a closed set: Constitution, Process, Operations, Compliance, Training, Reference, Templates, Company, Customer, Broker, Location_Intelligence, Route_Intelligence, Publisher_Parts, Security, Index |
| `models.py` | `LibraryObject` (current truth), `LibraryCandidate` (pending nomination — "field-compatible with the Intelligence repo's object of the same name"), `PublisherRecipe` |
| `registry.py` | Versioned Object Registry. "Adding a new `CURRENT` version of an `object_code` automatically supersedes the previous one; at most one `CURRENT` version can" exist |
| `resolver.py` | Object resolution |
| `ingestion.py` | Human-gated ingestion. `KNOWN_GAPS.md`: derived from `DISPATCH_CONSTITUTION_v3.md` §7.4 and the System Relationship Matrix Hard Rules, **not** from the missing `LIBRARY_INGESTION_RULE.md` |
| `recipes.py` | Publisher recipes |
| `service.py` | The integration surface consumed by `Publisher/src/dispatch_publisher/library_client.py` |

### APIs / Routes / CLI / Background services / Connectors
None.

### Database models
No database. `KNOWN_GAPS.md`: "**No persistent store.** `ObjectRegistry`/`CandidateQueue`/
`RecipeRegistry` are in-memory only. A Dispatch Spine-backed persistence layer is required
before this integrates with a running Manager/Portal."

### Contracts
`docs/OBJECT_MODEL.md`. `models.py`'s `LibraryCandidate` is declared field-compatible with
`L2-intelligence-agent.`'s object of the same name. `service.py` is the surface
`Publisher/library_client.py` duck-types against.

### Tests
5 files, **24 `def test_` functions**: `test_taxonomy`, `test_registry_resolver`,
`test_ingestion`, `test_recipes`, `test_service`. *Not run during this inventory.*

---

## SECTION 5 — FUNCTIONAL CAPABILITIES

| Capability | Exists | Evidence | Primary files | Status |
|---|---|---|---|---|
| 15-collection taxonomy (closed set) | Yes | `README.md` lists all 15; `tests/test_taxonomy.py` | `taxonomy.py` | IMPLEMENTED |
| Library objects (current truth) | Yes | `docs/OBJECT_MODEL.md` | `models.py` | IMPLEMENTED |
| Library candidates (pending nomination) | Yes | field-compatible with Intelligence's object | `models.py` | IMPLEMENTED |
| Versioned Object Registry | Yes | `tests/test_registry_resolver.py` | `registry.py` | IMPLEMENTED |
| Automatic supersession (one `CURRENT` per `object_code`) | Yes | `README.md`; registry tests | `registry.py` | IMPLEMENTED |
| Object resolution | Yes | `tests/test_registry_resolver.py` | `resolver.py` | IMPLEMENTED |
| Human-gated ingestion | Yes | `tests/test_ingestion.py`; derived from Constitution §7.4 | `ingestion.py` | IMPLEMENTED |
| Publisher recipes | Yes | `tests/test_recipes.py` | `recipes.py` | IMPLEMENTED |
| Service integration surface | Yes | `tests/test_service.py`; consumed by `Publisher/library_client.py` | `service.py` | IMPLEMENTED — no live consumer connected |
| Persistent store | **No** | `KNOWN_GAPS.md` states it plainly | — | ABSENT |
| Live Archive integration | **No** | `KNOWN_GAPS.md`: "Superseded objects are marked `SUPERSEDED` but nothing writes them to an actual Archive department" | — | ABSENT — out of scope per System Relationship Matrix Phase 4 |
| Security sub-library behaviour | **No** | `KNOWN_GAPS.md`: the `Security` collection exists in the taxonomy but "no Security-department-specific behavior (credential handling, access control…) is implemented" | `taxonomy.py` | DOCUMENTED ONLY |
| Automatic truth from Archive or Intelligence | **No** (by design) | `README.md`: "never as… automatic truth from Archive or Intelligence" | `ingestion.py` | ABSENT by design |
| Merged into Dispatch | **No** | `README.md` status line | — | not promoted |

---

## SECTION 6 — DOCUMENT INVENTORY

26 markdown files.

**Constitutions** — `DISPATCH_CONSTITUTION_v3.md`.

**Architecture** — `ARCHITECTURE.md`, `ARCHITECTURAL_DISPOSITION.md`, `CONTEXT_MASTER.md`,
`DISPATCH_SPINE_OVERVIEW.md`, `PORTAL_DESCRIPTION.md`, `COGNITIVE_FUNCTIONS.md`.

**Specifications** — `docs/OBJECT_MODEL.md` (unique), `DISPATCH_SPINE_SPECIFICATION_v1.md`,
`SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md`, `DISPATCH_DECISION_MATRIX.md`,
`INTELLIGENCE_VERIFICATION_WORKFLOW.md`.

**Governance** — `ALERT_GOVERNANCE_DOCTRINE.md`, `ARCHIVE_REVIEW_POLICY.md`,
`DISPATCH_VERSION_DOCTRINE.md`, `SUPERSESSION_MAP.md`, `REFINEMENT_ANALYST_REMOVAL.md`,
`DISPATCH_REPO_MANIFEST_v3.md`, `04_DISPATCH_SYSTEM_RELATIONSHIP_MATRIX.md`,
`05_DISPATCH_TRI_DEPARTMENT_MATRIX_BUILD_COMMAND.md`.

**Department descriptions** — `MANAGER.md`, `PUBLISHER.md`, `INTELLIGENCE_ANALYST.md`.

**Gap and readiness records (unique)** — `KNOWN_GAPS.md`, `MERGE_READINESS_REPORT.md`.

**On branches (22 files)** — `DISPATCH_FINAL_BLUEPRINT_v1.md`, **`LIBRARY_INGESTION_RULE.md`**,
`DISPATCH_INTEGRATED_BLUEPRINT_v1.md`, `DISPATCH_BLUEPRINT_DECISION_LOG.md`,
`DISPATCH_REPO_RECONCILIATION_MATRIX_v1.md`, `DISPATCH_MANAGER_BUILDOUT_DESIGN_v1.md`,
`DISPATCH_STAGE_LAUNCH_PACKAGES_v1.md`, and 15 stage design/reconciliation documents
(stages 4, 6, 7, 8, 9, 10, 11, 12×5, 13).

---

## SECTION 7 — UNIQUE ASSETS

**16 of 40 files (40%) are unique by content** — the remaining 24 are the shared doctrine set
mirrored from Claude-3/Jules/Claude/Claude-2.

### 1. The only Library-department implementation in the ecosystem
`src/dispatch_library/` — 8 modules, 875 LOC, 24 tests. Three other things are called "Library"
in this ecosystem and none of them is this:
- `Dispatch/portal/models/library.py` — a portal surface for library records.
- `Dispatch-Old/cin_lite/library.py` (67 LOC) — approved reusable facts for the contract pipeline.
- `Joe-Assistant/library/assistant_library/` — a filesystem document search index for JOE.

None implements a versioned Object Registry, a closed collection taxonomy, or automatic
supersession.

### 2. The 15-collection closed taxonomy
Constitution, Process, Operations, Compliance, Training, Reference, Templates, Company,
Customer, Broker, Location_Intelligence, Route_Intelligence, Publisher_Parts, Security, Index.
Declared closed. This enumeration exists in code nowhere else.

### 3. Automatic supersession as running code
"Adding a new `CURRENT` version of an `object_code` automatically supersedes the previous one;
at most one `CURRENT` version can" exist. `SUPERSESSION_MAP.md` and
`DISPATCH_VERSION_DOCTRINE.md` state this as doctrine in five repositories; `registry.py` is
the only place it is **executed**.

### 4. `docs/OBJECT_MODEL.md`, `KNOWN_GAPS.md`, `MERGE_READINESS_REPORT.md`
Library-specific. `KNOWN_GAPS.md` is notable for recording exactly which source documents were
missing and stating that content **was not invented** in their absence.

### 5. `LIBRARY_INGESTION_RULE.md` — on a branch here, and recorded as missing on `main`
`KNOWN_GAPS.md` lists it under "Missing source material… Not found in any repo in scope",
and records that `ingestion.py` was therefore derived from `DISPATCH_CONSTITUTION_v3.md` §7.4
instead. The document exists on this repository's own
`claude/dispatch-tri-department-build-899qjm` branch, and on Claude-3 and Jules branches.
`KNOWN_GAPS.md` adds: "If that document surfaces later and specifies different ingestion
mechanics, this repo's `ingestion.py` should be reviewed against it." Recorded as fact.

### 6. A third copy of `DISPATCH_FINAL_BLUEPRINT_v1.md`
On `claude/dispatch-final-blueprint-v1-1vlkkc`, identical blob to Claude-3's and Jules'.
Not on `main`.

### 7. Shared creation timestamp with Claude-3 and Jules
All three first commits are 2026-08-10 13:09:04 -0400 — the same second. Library's README
records that it began as "Repo-3" before being repurposed.

---

## SECTION 8 — CROSS-REPOSITORY REFERENCES

| Referenced entity | Occurrences | Representative files |
|---|---|---|
| Library | 372 | throughout `src/` and docs |
| Dispatch | 293 | `README.md`, all doctrine documents |
| Publisher | 235 | `recipes.py`, `models.py` (`PublisherRecipe`), `PUBLISHER.md` |
| Manager | 154 | `MANAGER.md`, `KNOWN_GAPS.md` ("a running Manager/Portal") |
| Jules | 13 | branch names |
| Route Risk | 5 | `taxonomy.py` (`Route_Intelligence` collection) |
| SAM | 3 | doctrine documents |
| COMI / Mission Visibility / Joe | 0 | — |

**Named cross-repository dependencies.**
- `models.py`'s `LibraryCandidate` is declared **field-compatible with
  `L2-intelligence-agent.`'s object of the same name** — a deliberate cross-repository contract
  without a package dependency.
- `service.py` is the surface `Publisher/src/dispatch_publisher/library_client.py` duck-types
  against.
- `KNOWN_GAPS.md` cites `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` **§1 in the Claude-3
  repository** as the governing missing-source report.
- `README.md` cites `07_DISPATCH_REPO_PLACEMENT_PLAN.md` ("Library Repo") — a document **not
  present in this repository** and not found on `main` in any of the fourteen.
- `README.md` cites `04_DISPATCH_SYSTEM_RELATIONSHIP_MATRIX.md` for the dependency chain.

---

## SECTION 9 — BUILT VS PLANNED

### Built In Code
15-collection closed taxonomy · `LibraryObject` / `LibraryCandidate` / `PublisherRecipe` ·
versioned Object Registry with automatic supersession and a single-`CURRENT` invariant ·
object resolver · human-gated ingestion · Publisher recipes · a service integration surface ·
24 test functions.

### Partially Built
- **Integration** — `service.py` exists and is tested; `Publisher`'s client duck-types against
  it; the two repositories are independently built and neither is merged.
- **Ingestion** — implemented from the Constitution rather than from the governing ingestion
  rule, which was believed missing. `KNOWN_GAPS.md` flags it for review if that rule surfaces.
  It has since been located on branches (§7.5).

### Documented Only
- **Security sub-library** — the collection exists in the taxonomy; no Security-specific
  behaviour is implemented. `KNOWN_GAPS.md` records Security as a separate Dispatch concern.
- The 22 mirrored doctrine documents.

### Referenced But Missing
`KNOWN_GAPS.md` names these as not found in any repo in scope:
`LIBRARY_INGESTION_RULE.md` (**located on branches by this inventory**), a "Library Department
Core Object Model" document, "Operational Memory Systems in Organizations", and
`publisher_recipes.json`. Also referenced and absent from `main` anywhere:
`07_DISPATCH_REPO_PLACEMENT_PLAN.md`. Also absent: a persistent store; a live Archive department.

### Unknown
- Whether the 24 test functions pass — **not run** during this inventory.
- Whether `ingestion.py` agrees with the now-located `LIBRARY_INGESTION_RULE.md`; the two were
  not compared in this inventory.

---

## SECTION 10 — EXECUTIVE SUMMARY

**What is this repository?**

Library is the **Library department** of the Dispatch program — the middle link of the
Intelligence → Library → Publisher chain. It began life as "Repo-3", a document-only package for
assembling the Final Blueprint (it was created in the same second as `Claude-3` and `Jules`),
and was repurposed on 2026-08-11 to build the Library department. It has 4 commits, 3 branches,
40 files and 875 lines of Python, and has not been touched since.

**What is actually implemented?**

A governed store of "current reusable truth": a closed 15-collection taxonomy; `LibraryObject`,
`LibraryCandidate` and `PublisherRecipe`; a versioned Object Registry that automatically
supersedes the previous `CURRENT` version of an `object_code` and permits at most one; a
resolver; a human-gated ingestion path; a recipe registry; and a service surface for Publisher
and Intelligence to integrate against. 24 test functions cover it.

It has no persistent store — the registry, candidate queue and recipe registry are all in
memory. It has no Archive integration: objects are marked `SUPERSEDED` and nothing writes them
anywhere. The `Security` collection exists in the taxonomy with no Security-specific behaviour
behind it. It is not merged into Dispatch, not deployed, not production-promoted.

**What unique value does it contain?**

Two-fifths of its files are unique. It holds the **only Library-department implementation in the
ecosystem** — three other things are named "Library" (Dispatch's portal model, Dispatch-Old's
`cin_lite/library.py`, Joe-Assistant's document index) and none of them implements a versioned
registry, a closed collection taxonomy, or supersession. Its **15-collection closed taxonomy**
exists in code nowhere else, and its `registry.py` is the only place in the ecosystem where the
supersession doctrine — stated as prose in `SUPERSESSION_MAP.md` and
`DISPATCH_VERSION_DOCTRINE.md` across five repositories — actually runs.

Its `KNOWN_GAPS.md` is also unusually valuable as a record: it names exactly which source
documents were missing when the build ran and states that their content **was not invented**.
This inventory located one of them, `LIBRARY_INGESTION_RULE.md`, on this repository's own
unmerged branch — `KNOWN_GAPS.md` had already written the instruction for that case: review
`ingestion.py` against it.
