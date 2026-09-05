# PUBLISHER_DOSSIER.md

Repository inventory dossier. Authority: Mike Zachary.
Compiled 2026-09-05. Default branch `main` at `7f19548`; both branches examined.

Recovery operation only. This dossier records what exists. It makes no design,
archive, cleanup, or refactor recommendation.

---

## SECTION 1 — REPOSITORY FACTS

| Fact | Value | How established |
|---|---|---|
| Repository name | `Publisher` | `git remote get-url origin` |
| Repository URL | https://github.com/jax1313-outlook/Publisher | same |
| Visibility | Public | `list_repos` |
| Creation date (first commit) | 2026-08-08 14:34:02 -0400 — **same second as `Claude` and `Joe-Assistant`** | `git log --reverse` |
| Last commit date | 2026-08-11 13:27:37 -0400 (`7f19548`, "Build Publisher department to integration-ready status (#1)") | `git log -1` |
| Last push | 2026-08-11T17:27:37Z | `list_repos` |
| Branch count | **2** — `main`, `claude/dispatch-tri-department-build-899qjm` | `git ls-remote --heads` |
| Commit count | **7** | `git rev-list --count HEAD` |
| Default branch | `main` | `git ls-remote` |
| Contributors | `jax1313-outlook` (7) — sole contributor | `git shortlog -sne` |
| README status | Present — **two**: `README.md` and `READ ME.md` | `git ls-files` |
| Tracked files | 26 | `git ls-files` |
| Python | 8 files, **872 lines** | `wc -l` |
| Markdown | 17 files, 2,917 lines | `wc -l` |
| Files unique to branches | **0** — the branch content is identical to `main` | branch scan |

The only repository of the fourteen whose non-default branch adds nothing.

---

## SECTION 2 — PURPOSE

**Evidence source:** `README.md`.

> # Dispatch Publisher
> Publisher department implementation… This repo builds the **Publisher** link of the
> Intelligence → Library → Publisher dependency chain… — the last link, consuming both upstream
> departments.

Its own renaming is recorded:

> Legacy note: this repo's prior README described it as "Test-Grounds". Per
> `07_DISPATCH_REPO_PLACEMENT_PLAN.md` ("Publisher Repo"), this repository's actual role is to
> build and test the Publisher department to integration-ready status. The Hold/Test-Grounds
> repo referenced by the Repo Placement Plan's promotion flow is a separate GitHub repo
> (`jax1313-outlook/Test-Grounds`), not this one.

Status, verbatim:

> **Integration-ready candidate.** Not merged into Dispatch. Not deployed. Not
> production-promoted. See `MERGE_READINESS_REPORT.md` and `KNOWN_GAPS.md`. Mike decides on
> promotion.

The governing constraint, stated in `README.md`:

> Publisher is a governed production assembly department: **it drafts, it never approves
> itself, and it never sends anything externally.**

That constraint is enforced by a dedicated test file, `tests/test_no_external_send.py`.

Third of the three sibling department repositories built in one campaign on 2026-08-11.

---

## SECTION 3 — DIRECTORY MAP

```
Publisher/
├── src/dispatch_publisher/       The Publisher department (5 modules, 872 LOC)
│   ├── models.py                 9 object types matching the shared contracts
│   ├── service.py                The assembly and gate machinery
│   ├── library_client.py         Duck-typed boundary to the Library repo (+ in-process stub)
│   ├── intelligence_client.py    Duck-typed boundary to the Intelligence repo (+ stub)
│   └── __init__.py
├── tests/                        3 files, 19 test functions
│   ├── test_models.py
│   ├── test_service.py
│   └── test_no_external_send.py  ← enforces "never sends anything externally"
├── docs/OBJECT_MODEL.md
├── KNOWN_GAPS.md
├── MERGE_READINESS_REPORT.md
└── (root) the numbered Dispatch governance set: 02_–08_ matrices,
        04_/05_ relationship + tri-department build command,
        DISPATCH_CONSTITUTION_v2, DISPATCH_CONTEXT_MASTER_v2,
        DISPATCH_AGENT_GOVERNANCE_LAW_v1, README, READ ME
```

Note: Publisher mirrors the **`02_`–`08_` numbered governance set** (as `Joe-Assistant` and
`L2-intelligence-agent.` do), not the Constitution-v3 doctrine set that `Library`, `Claude-3`
and `Jules` mirror. The two document families are distinct.

---

## SECTION 4 — CODE INVENTORY

### Applications / Entry points
None. A library package: no CLI, no HTTP surface, no daemon.

### Modules — `src/dispatch_publisher/` (5)
| Module | Role (per `README.md`) |
|---|---|
| `models.py` | `PublisherRequest`, `Workspace`, `ReadinessPacket`, `PartsInventory`, `MissingItemNotice`, `DraftReviewPackage`, `ArchiveHandoffPackage`, `VisibilityPackage`, `PODEvidenceBundle` — "matching `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` Section 5" |
| `service.py` | The governed assembly and gate machinery: request → workspace → readiness → inventory → review → approval → handoff. `KNOWN_GAPS.md`: "All `service.py` functions are pure/stateless, returning objects the caller must hold." |
| `library_client.py` | Duck-typed integration boundary to the Library repo, "without a hard package dependency"; ships an in-process stub for offline testing |
| `intelligence_client.py` | Same, for the Intelligence repo |

### APIs / Routes / CLI / Background services / Connectors
None.

### Database models
None. Stateless by design (`KNOWN_GAPS.md`).

### Contracts
`docs/OBJECT_MODEL.md`; the nine object types explicitly track
`DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` §5 — a document that lives on **Claude-3 branches**,
not in this repository.

### Adapters
`library_client.py` and `intelligence_client.py` — duck-typed, each with an in-process stub.
This is the ecosystem's clearest example of a cross-repository boundary held without a package
dependency.

### Tests
3 files, **19 `def test_` functions**. `tests/test_no_external_send.py` is a boundary test
asserting the department cannot send anything externally. *Not run during this inventory.*

---

## SECTION 5 — FUNCTIONAL CAPABILITIES

| Capability | Exists | Evidence | Primary files | Status |
|---|---|---|---|---|
| 9 Publisher object types | Yes | `docs/OBJECT_MODEL.md`; `tests/test_models.py` | `models.py` | IMPLEMENTED |
| Request → workspace | Yes | `tests/test_service.py` | `service.py` | IMPLEMENTED |
| Readiness packet | Yes | `ReadinessPacket` | `models.py`, `service.py` | IMPLEMENTED |
| Parts inventory | Yes | `PartsInventory` | those files | IMPLEMENTED |
| Missing-item notice | Yes | `MissingItemNotice` | those files | IMPLEMENTED |
| Draft review package | Yes | `DraftReviewPackage` | those files | IMPLEMENTED |
| Approval gate (never self-approves) | Yes | `README.md`: "it drafts, it never approves itself" | `service.py` | IMPLEMENTED |
| Archive handoff | Yes | `ArchiveHandoffPackage` | those files | IMPLEMENTED |
| Visibility package | Yes | `VisibilityPackage` | those files | IMPLEMENTED |
| POD evidence bundle | Yes | `PODEvidenceBundle` | those files | IMPLEMENTED |
| **No external send (enforced)** | Yes | `tests/test_no_external_send.py` | that test | IMPLEMENTED as a boundary test |
| Library integration boundary | Yes | duck-typed + stub | `library_client.py` | IMPLEMENTED — no live consumer connected |
| Intelligence integration boundary | Yes | duck-typed + stub | `intelligence_client.py` | IMPLEMENTED — no live consumer connected |
| **Content generation** (cover letters, technical narratives, form field values) | **No** | `KNOWN_GAPS.md`: "**No content-generation layer.** This repo builds the governed *assembly and gate* machinery… but does not draft actual document/packet text" | — | ABSENT |
| Persistent store | **No** | `KNOWN_GAPS.md`: "All `service.py` functions are pure/stateless" | — | ABSENT |
| Merged into Dispatch | **No** | `README.md` status line | — | not promoted |

---

## SECTION 6 — DOCUMENT INVENTORY

17 markdown files.

**Constitutions** — `DISPATCH_CONSTITUTION_v2.md`.

**Governance (the numbered set)** — `02_DISPATCH_AGENT_GOVERNANCE_LAW.md`,
`03_DISPATCH_AGENT_RELATIONSHIP_MATRIX.md`, `04_DISPATCH_CONTEXT_MASTER.md`,
`04_DISPATCH_SYSTEM_RELATIONSHIP_MATRIX.md`, `05_DISPATCH_AUTHORITY_MATRIX.md`,
`05_DISPATCH_TRI_DEPARTMENT_MATRIX_BUILD_COMMAND.md`, `06_DISPATCH_LEARNING_MATRIX.md`,
`07_DISPATCH_CONFLICT_MATRIX.md`, `08_DISPATCH_BUILD_VALIDATION_STANDARD.md`,
`DISPATCH_AGENT_GOVERNANCE_LAW_v1.md`, `DISPATCH_CONTEXT_MASTER_v2.md`.

**Specifications** — `docs/OBJECT_MODEL.md` (unique).

**Gap and readiness records (unique)** — `KNOWN_GAPS.md`, `MERGE_READINESS_REPORT.md`.

**Handoffs** — `READ ME.md` (distinct from `README.md`).

**Decision logs / Roadmaps / Research reports / Prompts** — none.

---

## SECTION 7 — UNIQUE ASSETS

**11 of 26 files (42.3%) are unique by content.** The other 15 are the numbered governance set
shared with `Joe-Assistant` and `L2-intelligence-agent.`.

### 1. The only Publisher-department implementation in the ecosystem
`src/dispatch_publisher/` — 5 modules, 872 LOC, 19 tests. Two other things are called
"Publisher" and neither is this:
- `Dispatch/portal/models/publisher.py` with `/publisher/*` routes — a portal surface.
- `Dispatch-Old/cin_lite/publisher.py` (84 LOC) — the contract-pipeline publisher.

Neither implements the request→workspace→readiness→inventory→review→approval→handoff pipeline.

### 2. The 9 Publisher object types
`PublisherRequest`, `Workspace`, `ReadinessPacket`, `PartsInventory`, `MissingItemNotice`,
`DraftReviewPackage`, `ArchiveHandoffPackage`, `VisibilityPackage`, `PODEvidenceBundle`.
Declared to match `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` §5. This set exists in code nowhere
else. `VisibilityPackage` and `PODEvidenceBundle` are notable: Dispatch has Mission Visibility
and POD *records*, but not these packaging objects.

### 3. `tests/test_no_external_send.py` — a doctrine enforced as a test
The only test in the ecosystem that asserts a department **cannot send anything externally**.
`Hold` has comparable boundary tests (`test_no_tax_math`, `test_no_delete_sql`); this is the
external-send equivalent and it exists only here.

### 4. Duck-typed cross-repository clients with in-process stubs
`library_client.py` and `intelligence_client.py` — integration boundaries to two other
repositories held **without a hard package dependency**, each shipping a stub so the department
can be tested offline. The cleanest worked example of the independent-build pattern in the
ecosystem, and the pattern-mate of Dispatch's connector boundary.

### 5. `KNOWN_GAPS.md` — the most detailed missing-source record in the ecosystem
It names nine specific missing artefacts (`publisher_mvp.py`, `publisher_recipes.json`,
Publisher templates, Publisher Constitution Package, Legacy Publisher Emails 1–5,
`quality_control_statement.md`, `submission_email_template.md`,
`technical_narrative_template.md`, `Visibility_SOP.docx`) and states explicitly that **nothing
in the repo invents the content those documents would define** — recipe *types* are
doctrine-named, but "no specific packet field content, agency form layout, email copy, or SOP
procedure is fabricated."

### 6. `docs/OBJECT_MODEL.md` and `MERGE_READINESS_REPORT.md`
Publisher-specific.

### 7. Shared creation timestamp with `Claude` and `Joe-Assistant`
All three first commits are 2026-08-08 14:34:02 -0400 — the same second. Publisher's README
records that it, like `Claude`, was previously "Test-Grounds".

---

## SECTION 8 — CROSS-REPOSITORY REFERENCES

| Referenced entity | Occurrences | Representative files |
|---|---|---|
| Publisher | 242 | throughout |
| Library | 233 | `library_client.py`, `README.md` |
| Dispatch | 138 | governance set, `README.md` |
| Manager | 101 | `03_`/`05_` matrices |
| Route Risk | 1 | incidental |
| SAM / COMI / Mission Visibility / Joe / Jules | 0 | — |

**Named cross-repository dependencies.**
- `library_client.py` → `Library/src/dispatch_library/service.py`
- `intelligence_client.py` → `L2-intelligence-agent./src/dispatch_intel/service.py`
- `models.py` → `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` §5 — **on Claude-3 branches only**
- `KNOWN_GAPS.md` → `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` §1 (Claude-3 repo) for the
  cross-department missing-source report
- `README.md` → `07_DISPATCH_REPO_PLACEMENT_PLAN.md` ("Publisher Repo") — **not present in
  this or any other repository's default branch**
- `README.md` → **`jax1313-outlook/Test-Grounds`**, named as a separate GitHub repository in the
  promotion flow. **It is not in the account listing.** `Claude-3/RECOVERY_REPORT.md`
  independently names `Test-Grounds` (with `Jules-2` and `Jules-3`) as a working instance of the
  promotion pipeline. None of the three exists today.

---

## SECTION 9 — BUILT VS PLANNED

### Built In Code
9 Publisher object types · the governed assembly and gate pipeline (request → workspace →
readiness → parts inventory → missing-item notice → draft review → approval → archive handoff) ·
visibility package · POD evidence bundle · duck-typed Library and Intelligence clients with
in-process stubs · a boundary test asserting no external send · 19 test functions.

### Partially Built
- **Integration** — both clients exist and are stubbed; neither upstream repository is merged or
  deployed, so nothing is connected.

### Documented Only
The 11 mirrored governance documents; recipe *types* named in doctrine
(`Constitution/PUBLISHER.md`) without the templates that would fill them.

### Referenced But Missing
`KNOWN_GAPS.md` names all of these as not found in any repo in scope:
`publisher_mvp.py` (a Publisher MVP prototype), `publisher_recipes.json`, Publisher templates,
the Publisher Constitution Package, Legacy Publisher Emails 1–5, `quality_control_statement.md`,
`submission_email_template.md`, `technical_narrative_template.md`, `Visibility_SOP.docx`.
This inventory did not find any of them on any branch of any of the fourteen repositories.

Also referenced and absent: **`jax1313-outlook/Test-Grounds`** (named as a real repository);
`07_DISPATCH_REPO_PLACEMENT_PLAN.md`; a persistent store; a content-generation layer.

### Unknown
- Whether the 19 test functions pass — **not run** during this inventory.
- Whether `Test-Grounds` was renamed to this repository or to `Claude` (both READMEs record a
  "Test-Grounds" past; `Claude/README.md` is still literally `# Test-Grounds`), or deleted.

---

## SECTION 10 — EXECUTIVE SUMMARY

**What is this repository?**

Publisher is the **Publisher department** of the Dispatch program — the last link of the
Intelligence → Library → Publisher chain, consuming both upstream departments. It was previously
called "Test-Grounds" (as was the `Claude` repository, whose README still reads `# Test-Grounds`).
It has 7 commits, 26 files, 872 lines of Python, and is the only repository of the fourteen whose
non-default branch adds nothing to `main`. Untouched since 2026-08-11.

**What is actually implemented?**

The governed assembly and gate machinery of a production department: nine object types
(`PublisherRequest`, `Workspace`, `ReadinessPacket`, `PartsInventory`, `MissingItemNotice`,
`DraftReviewPackage`, `ArchiveHandoffPackage`, `VisibilityPackage`, `PODEvidenceBundle`) and a
stateless service implementing request → workspace → readiness → inventory → review → approval →
handoff. Two duck-typed clients reach the Library and Intelligence repositories without a package
dependency, each shipping an in-process stub. Nineteen test functions cover it, one of which
exists solely to assert that the department cannot send anything externally.

What it does **not** do is draft anything. `KNOWN_GAPS.md` is explicit: there is no
content-generation layer — no cover letters, technical narratives or form field values — because
the templates and prototype that would define them were not found, and the repository did not
invent them. It is stateless, unmerged, undeployed and not production-promoted.

**What unique value does it contain?**

Two-fifths of its files are unique. It is the **only Publisher-department implementation in the
ecosystem** — Dispatch's `/publisher` routes and Dispatch-Old's `cin_lite/publisher.py` are
different things — and its nine object types, including `VisibilityPackage` and
`PODEvidenceBundle`, exist in code nowhere else. `tests/test_no_external_send.py` is the only
test anywhere that enforces the no-external-send boundary. And its duck-typed clients with
in-process stubs are the ecosystem's cleanest worked example of holding a cross-repository
boundary without coupling.

Its `KNOWN_GAPS.md` is the most detailed missing-source record in the ecosystem, naming nine
specific artefacts that could not be found and stating plainly that their content was not
fabricated. This inventory searched all fourteen repositories, on every branch, and found none of
the nine. It also confirms that `jax1313-outlook/Test-Grounds` — named in this repository's README
as a separate GitHub repository in the promotion flow, and named again in
`Claude-3/RECOVERY_REPORT.md` — does not exist in the account.
