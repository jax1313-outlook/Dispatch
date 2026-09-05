# HOLD_DOSSIER.md

Repository inventory dossier. Authority: Mike Zachary.
Compiled 2026-09-05. Default branch `main` at `484e40d`; **all branches examined**.

Recovery operation only. This dossier records what exists. It makes no design,
archive, cleanup, or refactor recommendation.

> **Read this first.** `Hold`'s default branch contains **no Python at all**. Its
> `integration` branch contains **13,770 lines of Python, 148 modules and 428 test
> functions**. A builder who read only `main` would conclude this repository is an empty
> scaffold. That conclusion would be wrong.

---

## SECTION 1 — REPOSITORY FACTS

| Fact | Value | How established |
|---|---|---|
| Repository name | `Hold` | `git remote get-url origin` |
| Repository URL | https://github.com/jax1313-outlook/Hold | same |
| Visibility | Public | `list_repos` |
| Creation date (first commit) | 2026-08-04 01:57:10 +0000 | `git log --reverse` |
| Last commit date (`main`) | 2026-08-04 02:46:59 +0000 (`484e40d`, "Add Lane A Launch Package") | `git log -1` |
| Last commit date (**any branch**) | **2026-08-05 03:48:01 +0000** (`integration`) | branch scan |
| Last push | 2026-08-05T03:48:17Z | `list_repos` |
| Branch count | **24** | `git ls-remote --heads` |
| Commit count (`main`) | **10** | `git rev-list --count HEAD` |
| Commit count (`integration`) | **85** | `git rev-list --count FETCH_HEAD` |
| Default branch | `main` | `git ls-remote` |
| Contributors | `Claude <noreply@anthropic.com>` (10) — **the only repository with no human-authored commits on `main`** | `git shortlog -sne` |
| README status | Present — `README.md` at root | `git ls-files` |
| Tracked files on `main` | 68 (39 `.md`, 17 `.gitkeep`, 11 `.json`, 1 `.gitignore`) | `git ls-files` |
| Tracked files on `integration` | **267** | branch scan |
| Python on `main` | **0 files, 0 lines** | `git ls-files '*.py'` |
| Python on `integration` | **148 files, 13,770 lines** | branch scan |
| Test functions on `integration` | **428** across 72 files | branch scan |

### Every branch, measured

| Branch | Files | Python files | Python LOC | Tip |
|---|---|---|---|---|
| `integration` | 267 | 148 | **13,770** | 2026-08-05 03:48 |
| `docs/ifta-clerk-blueprint-amendment-5` | 267 | 148 | 13,770 | 2026-08-05 03:47 |
| `build/mileage-entry-ui` | 267 | 148 | 13,770 | 2026-08-05 03:35 |
| `build/archive-package-evidence-refs` | 264 | 146 | 13,490 | 2026-08-05 03:16 |
| `build/ocr-fenced-json-fix` | 264 | 146 | 13,309 | 2026-08-05 02:51 |
| `build/ifta-clerk-payment-recommendation` | 264 | 146 | 13,239 | 2026-08-05 01:35 |
| `build/ifta-clerk-prepare-quarter` | 260 | 144 | 12,742 | 2026-08-05 01:05 |
| `build/ifta-clerk-review-dashboard` | 256 | 142 | 12,147 | 2026-08-05 00:36 |
| `docs/ifta-clerk-blueprint` | 243 | 135 | 11,142 | 2026-08-05 00:05 |
| `build/ifta-live-indicators` | 241 | 135 | 11,142 | 2026-08-04 23:44 |
| `build/ifta-worksheet-preview` | 237 | 133 | 10,598 | 2026-08-04 23:19 |
| `build/ifta-ui` | 245 | 136 | 10,869 | 2026-08-04 22:04 |
| `docs/pilot-run-2-report` | 233 | 132 | 10,199 | 2026-08-04 21:42 |
| `build/dispatch-shell` | 232 | 132 | 10,199 | 2026-08-04 21:38 |
| `docs/pilot-run-1-report` | 219 | 127 | 9,833 | 2026-08-04 21:12 |
| `build/dispatch-pilot` | 218 | 127 | 9,833 | 2026-08-04 21:05 |
| `amend/evidence-record-v1.1` | 210 | 121 | 9,208 | 2026-08-04 20:42 |
| `build/reports-fidelity-gate` | 210 | 121 | 9,151 | 2026-08-04 19:26 |
| `build/reports` | 208 | 120 | 8,972 | 2026-08-04 16:02 |
| `build/receipt-ifta` | 174 | 97 | 7,005 | 2026-08-04 15:17 |
| `build/manager-queue` | 125 | 51 | 3,172 | 2026-08-04 13:28 |
| `build/librarian-spine` | 105 | 37 | 2,095 | 2026-08-04 13:06 |
| **`main`** | **68** | **0** | **0** | 2026-08-04 02:46 |
| `claude/new-session-916rfj` | 68 | 0 | 0 | 2026-08-04 02:46 |

The entire build happened in ~26 hours on 2026-08-04–05 and **was never merged to `main`**.

---

## SECTION 2 — PURPOSE

**Evidence source:** `README.md`.

> **Hold** — Construction repository for Dispatch Matrix Group 1 (Librarian, Manager,
> Receipt/IFTA, and Reports lanes). Seeded per `DISPATCH_HOLD_SEED_PACKAGE_v1`.
>
> A clean, intentionally-empty-at-seed construction repository. No build session touches
> production `D:\` roots. Sandbox configuration only, until Mike Zachary cuts over after
> merge 5.

`README.md` states what it is **not**:

> - **Not** a clone of the live Dispatch system.
> - **Not** the system of record. Archive is (per `CONSTITUTION.md` Articles III/VIII)…
> - **Not** authorized to hold production config. `config/dispatch.config.json` must never
>   exist here before cutover.

And where its law lives:

> `CONSTITUTION.md` (Level 1 Transport Inc. master constitution) is supreme law for all
> governed development work… maintained outside this repository… and is not duplicated here.

The "intentionally-empty-at-seed" language describes `main`. It does not describe the
repository, because the construction it was seeded for **happened**, on 22 branches.

---

## SECTION 3 — DIRECTORY MAP

### `main` (the seed — 68 files, no code)

```
Hold/
├── config/          config.schema.json, sandbox.config.json
├── contracts/       8 JSON Schemas + CONTRACT_REGISTER.md
├── docs/
│   ├── governance/  7 constitutions + APPROVAL_REGISTER
│   ├── reference/   11 audit / blueprint / review documents
│   ├── decisions/   DECISION_LOG.md
│   ├── lanes/A..D/  NOTES.md each; A also has LANE_A_LAUNCH_PACKAGE_v1
│   └── HOLD_PRE_BUILD_v1.md
├── library_seed/    Constitutions/ (7 mirrors), Vocabulary/, Templates/, RateTables/
├── src/dispatch/    common/ evidence/ ifta/ queue/ receipt/ reports/ — ALL .gitkeep ONLY
├── tests/           conformance/ fixtures/ golden/ lane_a..d/ stubs/ — ALL .gitkeep ONLY
└── tools/           .gitkeep ONLY
```

### `integration` (the build — 267 files, 13,770 py LOC)

The same tree, filled in:

```
src/dispatch/
├── common/      audit.py  config.py  db.py  hashing.py  ids.py
├── evidence/    index.py  interface.py
├── ifta/        app.py  db.py  exceptions.py  live_indicators.py  mileage.py
│                package.py  rates.py  readonly.py  worksheet.py
├── ifta_clerk/  app.py  dashboard.py  prepare.py  readonly.py  recommend.py
├── receipt/     address.py  db.py  dedup.py  intake.py  router.py  units.py
│                validators.py  vocabulary.py
│                extraction/vision.py
│                parsers/{common,csv_parser,statement_parser}.py
├── reports/     app.py  dates.py  db.py  queries.py  readonly.py  rendering.py
│                snapshot.py  templates_engine.py
├── queue/       app.py  store.py
├── shell/       app.py
└── pilot/       intake.py
tools/           init_roots.py  init_pilot.py  seed_library.py
                 mileage_worksheet.py  export_audit_rolls.py
tests/           72 files, 428 test functions — lane_a, lane_b, lane_c, lane_d,
                 conformance, golden/{ifta,receipts}, ifta_clerk, ifta_ui,
                 shell, pilot, fixtures, stubs
docs/ifta-clerk/ 12 documents (blueprint + 5 feature note/walkthrough pairs)
docs/lanes/A..D/ launch package + NOTES + walkthrough report per lane
docs/pilot/      pilot notes + 2 run reports
docs/website/    3 documents
```

**Lane structure.** The four lanes named in `README.md` map to the four test directories:
Lane A (Librarian), Lane B (Manager), Lane C (Receipt/IFTA), Lane D (Reports).

---

## SECTION 4 — CODE INVENTORY

### On `main`
**None.** Every `src/`, `tests/` and `tools/` directory holds only a `.gitkeep`.

### On `integration`

**Applications** — four Flask-style `app.py` surfaces: `src/dispatch/ifta/app.py`,
`ifta_clerk/app.py`, `reports/app.py`, `queue/app.py`, plus `shell/app.py` (the shell that
hosts them).

**Entry points** — `src/dispatch/shell/app.py`; five CLI tools under `tools/`.

**Modules (148 Python files)** grouped by lane:
| Package | Modules | Role |
|---|---|---|
| `common/` | `audit`, `config`, `db`, `hashing`, `ids` | Shared foundation: audit trail, config, SQLite, content hashing, ID generation |
| `evidence/` | `index`, `interface` | Evidence indexing and its interface |
| `ifta/` | `app`, `db`, `exceptions`, `live_indicators`, `mileage`, `package`, `rates`, `readonly`, `worksheet` | IFTA engine: mileage, rates, worksheet, exceptions, live indicators, read-only enforcement |
| `ifta_clerk/` | `app`, `dashboard`, `prepare`, `readonly`, `recommend` | IFTA Clerk: review dashboard, prepare-this-quarter, payment recommendation |
| `receipt/` | `address`, `db`, `dedup`, `intake`, `router`, `units`, `validators`, `vocabulary`, `extraction/vision`, `parsers/{common,csv_parser,statement_parser}` | Receipt intake: OCR/vision extraction, CSV and statement parsing, deduplication, unit and address normalization, validation against a controlled vocabulary |
| `reports/` | `app`, `dates`, `db`, `queries`, `readonly`, `rendering`, `snapshot`, `templates_engine` | Reports: query layer, template engine, rendering, snapshots, read-only enforcement |
| `queue/` | `app`, `store` | Manager queue |
| `shell/` | `app` | Hosting shell |
| `pilot/` | `intake` | Pilot intake |

**CLI tools** — `tools/init_roots.py`, `init_pilot.py`, `seed_library.py`,
`mileage_worksheet.py`, `export_audit_rolls.py`.

**Contracts** — 8 JSON Schemas, present on **both** `main` and `integration`:
`audit_entry.schema.json`, `config.schema.json`, `evidence_record.schema.json`,
`expense_record.schema.json`, `expense_vocabulary.schema.json`, `fuel_record.schema.json`,
`mileage_record.schema.json`, `queue_item.schema.json`, registered in
`contracts/CONTRACT_REGISTER.md`. Conformance tests bind code to schema
(`tests/conformance/test_audit_entry_conformance.py`).

**Database models** — SQLite via `common/db.py`, with per-package `db.py` in `ifta/`,
`receipt/` and `reports/`.

**Adapters / Connectors** — `receipt/extraction/vision.py` (OCR/vision) and the parser set.
No external service connectors.

**Tests** — 72 files, **428 `def test_` functions**, `pytest.ini`, `requirements.txt`,
`tests/conftest.py`. Lane-partitioned, plus conformance and golden-file suites
(`tests/golden/ifta/`, `tests/golden/receipts/`). Named tests include
`test_no_tax_math.py`, `test_no_delete_sql.py`, `test_readonly_enforcement.py`,
`test_ifta_position_display_only.py`, `test_fidelity_gate.py`, `test_fixture_conformance.py`
— boundary tests that enforce doctrine, not just behaviour. *Not run during this inventory.*

---

## SECTION 5 — FUNCTIONAL CAPABILITIES

Status is given for `integration`, with `main` noted separately.

| Capability | Exists | Evidence | Primary files | Status |
|---|---|---|---|---|
| Receipt intake | Yes (branch) | `tests/lane_c/` (25 files) | `receipt/intake.py`, `router.py` | IMPLEMENTED on `integration`; ABSENT on `main` |
| OCR / vision extraction | Yes (branch) | `docs/governance/OCR_VISION_EXTRACTION_DOCTRINE_v1.md`; branch `build/ocr-fenced-json-fix` | `receipt/extraction/vision.py` | IMPLEMENTED on `integration`; ABSENT on `main` |
| Receipt parsing (CSV, statement) | Yes (branch) | `tests/golden/receipts/` | `receipt/parsers/` | IMPLEMENTED on `integration` |
| Receipt deduplication | Yes (branch) | `receipt/dedup.py` | that file | IMPLEMENTED on `integration` |
| Controlled expense vocabulary | Yes (both) | `library_seed/Vocabulary/expense_vocabulary.v1.json` + schema | `receipt/vocabulary.py` | Schema on `main`; code on `integration` |
| IFTA engine (mileage, rates, worksheet) | Yes (branch) | `tests/golden/ifta/`, `tests/lane_c/` | `ifta/{mileage,rates,worksheet,package}.py` | IMPLEMENTED on `integration`; ABSENT on `main` |
| IFTA exceptions | Yes (branch) | `ifta/exceptions.py` | that file | IMPLEMENTED on `integration` |
| IFTA live indicators | Yes (branch) | branch `build/ifta-live-indicators`; `docs/ifta-clerk/LIVE_INDICATORS_WALKTHROUGH_REPORT_v1.md` | `ifta/live_indicators.py` | IMPLEMENTED on `integration` |
| IFTA UI | Yes (branch) | branch `build/ifta-ui`; `docs/ifta-ui/DISPATCH_IFTA_UI_LAUNCH_PACKAGE_v1.md`; `tests/ifta_ui/` | `ifta/app.py` | IMPLEMENTED on `integration` |
| **IFTA Clerk** (dashboard, prepare-quarter, payment recommendation) | Yes (branch) | 12 documents in `docs/ifta-clerk/`; `tests/ifta_clerk/` | `ifta_clerk/{dashboard,prepare,recommend}.py` | IMPLEMENTED on `integration`; **exists nowhere else in the ecosystem** |
| Mileage entry UI | Yes (branch) | branch `build/mileage-entry-ui`; `docs/ifta-clerk/MILEAGE_ENTRY_NOTES_v1.md` | `ifta/mileage.py`, `tools/mileage_worksheet.py` | IMPLEMENTED on `integration` |
| Reports (queries, templates, rendering, snapshots) | Yes (branch) | `tests/lane_d/` (15 files) incl. `test_fidelity_gate.py` | `reports/*` | IMPLEMENTED on `integration`; ABSENT on `main` |
| Reports fidelity gate | Yes (branch) | branch `build/reports-fidelity-gate`; `docs/lanes/D/FIDELITY_GATE_REPORT_v1.md` | `tests/lane_d/test_fidelity_gate.py` | IMPLEMENTED on `integration` |
| **Manager queue** | Yes (branch) | branch `build/manager-queue`; `contracts/queue_item.schema.json`; `tests/lane_b/` | `queue/{app,store}.py` | IMPLEMENTED on `integration` — one of only three Manager implementations in the ecosystem |
| **Librarian spine** | Yes (branch) | branch `build/librarian-spine`; `tests/lane_a/`; `docs/governance/LIBRARIAN_CONSTITUTION_v1.md` | `evidence/`, `common/` | IMPLEMENTED on `integration` |
| Evidence records | Yes (branch) | `contracts/evidence_record.schema.json`; branch `amend/evidence-record-v1.1` | `evidence/{index,interface}.py` | IMPLEMENTED on `integration` |
| Archive package evidence refs | Yes (branch) | branch `build/archive-package-evidence-refs` | `ifta/package.py`, `evidence/index.py` | IMPLEMENTED on `integration` |
| Audit trail / audit rolls | Yes (branch) | `contracts/audit_entry.schema.json`; conformance test | `common/audit.py`, `tools/export_audit_rolls.py` | IMPLEMENTED on `integration` |
| Read-only enforcement (doctrinal) | Yes (branch) | `tests/lane_d/test_readonly_enforcement.py`, `test_no_delete_sql.py` | `*/readonly.py` | IMPLEMENTED on `integration` |
| "No tax math" boundary | Yes (branch) | `tests/lane_d/test_no_tax_math.py` | that test | IMPLEMENTED on `integration` |
| Dispatch shell | Yes (branch) | branch `build/dispatch-shell`; `tests/shell/` | `shell/app.py` | IMPLEMENTED on `integration` |
| Dispatch pilot | Yes (branch) | branch `build/dispatch-pilot`; 2 pilot run reports; `tests/pilot/` | `pilot/intake.py` | IMPLEMENTED on `integration` |
| Library seed | Yes (both) | `library_seed/` | Constitutions, Vocabulary, Templates, RateTables | IMPLEMENTED |
| Production `D:\` access | **No** (by design) | `README.md`: "No build session touches production `D:\` roots." | `config/sandbox.config.json` only | ABSENT by design |
| Freight operations (loads, drivers, POD, settlement) | **No** | no such module on any branch | — | ABSENT |

---

## SECTION 6 — DOCUMENT INVENTORY

39 markdown files on `main`; ~60 on `integration`.

**Constitutions (7)** — `docs/governance/`: `DISPATCH_BASE_CONSTITUTION_v1.md`,
`IFTA_CONSTITUTION_v1.md`, `LIBRARIAN_CONSTITUTION_v1.md`, `MANAGER_CONSTITUTION_v1.md`,
`RECEIPT_CONSTITUTION_v1.md`, `REPORTS_CHARTER_v1.md`, `MEMORY_DOCTRINE_v1.md`.
Each is **mirrored byte-identically** into `library_seed/Constitutions/`.
`integration` adds `OCR_VISION_EXTRACTION_DOCTRINE_v1.md`.
The master `CONSTITUTION.md` is deliberately **not** in this repository (`README.md`).

**Governance** — `docs/governance/APPROVAL_REGISTER.md` — described in `README.md` as the
"single source of truth for the 14 approval items."

**Decision logs** — `docs/decisions/DECISION_LOG.md`.

**Architecture / reference (11)** — `docs/reference/`:
`DISPATCH_ARCHITECTURE_AUDIT_v1`, `DISPATCH_BOUNDARY_AUDIT_v1`, `DISPATCH_BUILD_BLUEPRINT_v1`,
`DISPATCH_BUILD_MATRIX_AUDIT_v1`, `DISPATCH_FINAL_PRECODING_REVIEW_v1`,
`DISPATCH_HOLD_IMPACT_AND_BRIEFS_v1`, `DISPATCH_HOLD_SEED_PACKAGE_v1`,
`DISPATCH_MATRIX_EXECUTION_PACKAGE_v1`, `DISPATCH_MEMORY_AUDIT_v1`,
`DISPATCH_RECEIPT_WORKFLOW_AUDIT_v1`, `DISPATCH_REPORTS_DESIGN_REVIEW_v1`, plus a `README.md`.

**Specifications** — `contracts/CONTRACT_REGISTER.md` + 8 JSON Schemas;
`config/config.schema.json`.

**Roadmaps / launch packages** — `docs/lanes/{A,B,C,D}/LANE_*_LAUNCH_PACKAGE_v1.md`
(A on `main`; B, C, D on `integration`), `docs/HOLD_PRE_BUILD_v1.md`,
`docs/ifta-ui/DISPATCH_IFTA_UI_LAUNCH_PACKAGE_v1.md`.

**Walkthrough / build reports (`integration` only)** —
`docs/lanes/{A,B,C,D}/WALKTHROUGH_REPORT_v1.md`, `docs/lanes/D/FIDELITY_GATE_REPORT_v1.md`,
and in `docs/ifta-clerk/`: `IFTA_CLERK_BLUEPRINT_v1` plus NOTES/WALKTHROUGH pairs for
Live Indicators, Payment Recommendation, Prepare This Quarter, Review Dashboard, Worksheet
Preview Mode, and Mileage Entry.

**Operational reports (`integration` only)** — `docs/pilot/DISPATCH_PILOT_NOTES_v1.md`,
`DISPATCH_PILOT_RUN_1_REPORT_v1.md`, `DISPATCH_PILOT_RUN_2_REPORT_v1.md`.

**Lane notes** — `docs/lanes/{A,B,C,D}/NOTES.md`.

**Prompts / handoffs** — none.

---

## SECTION 7 — UNIQUE ASSETS

**51 of 68 `main` files (75%) are unique.** Counting `integration`, essentially all 148
Python modules are unique — no other repository contains any of them.

### 1. A complete Receipt/IFTA/Reports build that exists on no default branch anywhere
13,770 lines of Python, 148 modules, 428 test functions, built in ~26 hours on 2026-08-04–05
across 22 branches, **never merged**. `main` has zero Python. This is the single largest body
of work in the ecosystem that is invisible from a default-branch reading.

### 2. The IFTA Clerk — unique in the ecosystem
`src/dispatch/ifta_clerk/` (5 modules: `dashboard`, `prepare`, `recommend`, `readonly`, `app`)
with 12 supporting documents including a blueprint and five NOTES/WALKTHROUGH pairs.
Dispatch has an IFTA subsystem; it has **no clerk-facing review dashboard,
prepare-this-quarter workflow, or payment recommendation engine**. Nothing comparable exists
elsewhere.

### 3. The 8 JSON Schemas and `CONTRACT_REGISTER.md`
`audit_entry`, `config`, `evidence_record`, `expense_record`, `expense_vocabulary`,
`fuel_record`, `mileage_record`, `queue_item`. **The only formal machine-readable data
contracts in the ecosystem.** Dispatch expresses its contracts as Python dataclasses and a
connector protocol; nowhere else is there a JSON Schema set with a register and conformance
tests binding code to it.

### 4. The 7-constitution governance set
`DISPATCH_BASE_CONSTITUTION_v1`, `IFTA_CONSTITUTION_v1`, `LIBRARIAN_CONSTITUTION_v1`,
`MANAGER_CONSTITUTION_v1`, `RECEIPT_CONSTITUTION_v1`, `REPORTS_CHARTER_v1`,
`MEMORY_DOCTRINE_v1` — each mirrored into `library_seed/Constitutions/`. These per-worker
constitutions exist only here. `MANAGER_CONSTITUTION_v1.md` is the only Manager *constitution*
in the ecosystem.

### 5. `APPROVAL_REGISTER.md` — the 14 approval items
Described by `README.md` as the single source of truth for them. No equivalent elsewhere.

### 6. The 11 `docs/reference/` audits
Architecture Audit, Boundary Audit, Build Blueprint, Build Matrix Audit, Final Pre-coding
Review, Hold Impact and Briefs, Hold Seed Package, Matrix Execution Package, Memory Audit,
Receipt Workflow Audit, Reports Design Review. A distinct audit body from Dispatch's.

### 7. Doctrine-enforcing boundary tests
`test_no_tax_math.py`, `test_no_delete_sql.py`, `test_readonly_enforcement.py`,
`test_ifta_position_display_only.py`, `test_fidelity_gate.py`. Tests that assert what the
system must *not* do. Dispatch has `tests/test_repository_doctrine.py`; this is a different
and larger set of the same idea.

### 8. Two executed pilot run reports
`docs/pilot/DISPATCH_PILOT_RUN_1_REPORT_v1.md` and `RUN_2`. Records of the system being run.

### 9. `OCR_VISION_EXTRACTION_DOCTRINE_v1.md`
The only OCR/vision governance document in the ecosystem. Dispatch has receipt-vision *code*
(`cin_lite/agents/receipt_vision.py`) with no governing doctrine document.

### 10. The only repository with no human-authored commit on `main`
All 10 `main` commits are authored by `Claude <noreply@anthropic.com>`.

---

## SECTION 8 — CROSS-REPOSITORY REFERENCES

| Referenced entity | Occurrences (`main`) | Representative files |
|---|---|---|
| Dispatch | 320 | `README.md`, all `docs/reference/DISPATCH_*` audits, `docs/governance/DISPATCH_BASE_CONSTITUTION_v1.md` |
| Library / Librarian | 137 | `LIBRARIAN_CONSTITUTION_v1.md`, `library_seed/`, Lane A |
| Manager | 99 | `MANAGER_CONSTITUTION_v1.md`, `contracts/queue_item.schema.json`, Lane B, branch `build/manager-queue` |
| Publisher | 45 | governance documents |
| SAM | 7 | governance documents |
| COMI / Route Risk / Mission Visibility / Joe / Jules | 0 | — |

**Named external dependencies.**
- `CONSTITUTION.md` — the Level 1 Transport master constitution, declared supreme law and
  **explicitly maintained outside this repository** ("Copilot Workspace/Constitution per
  `CONTEXT_MASTER.md` §13"). Not present in any of the fourteen repositories.
- Production `D:\` roots — named and deliberately not touched.
- `config/dispatch.config.json` — named and forbidden to exist before cutover. It does not exist.

**Shared files.** 22 files are byte-identical to files in `Dispatch`,
`L2-intelligence-agent.`, `Library` and `Publisher` — the mirrored governance set.

---

## SECTION 9 — BUILT VS PLANNED

### Built In Code (on `integration`, not on `main`)
Receipt intake, routing, dedup, address and unit normalization, validators, controlled
vocabulary · OCR/vision extraction · CSV and statement parsers · IFTA mileage, rates,
worksheet, package, exceptions, live indicators, read-only enforcement · IFTA UI ·
**IFTA Clerk** review dashboard, prepare-this-quarter, payment recommendation · mileage
entry UI · Reports queries, dates, rendering, snapshots, template engine, fidelity gate ·
Manager queue · Librarian spine · evidence index and interface · shared audit, config, db,
hashing, ids · Dispatch shell · pilot intake · 5 CLI tools · 428 test functions including
golden-file and conformance suites · 8 JSON Schemas with conformance tests.

### Built In Code (on `main`)
Nothing. 8 JSON Schemas, 2 config schemas, 39 documents, and a `.gitkeep` skeleton.

### Partially Built
- **The merge itself.** `README.md` says "Sandbox configuration only, until Mike Zachary cuts
  over after merge 5." `integration` exists and was never merged to `main`. No document in the
  repository records why.

### Documented Only
- **The 14 approval items** in `APPROVAL_REGISTER.md`.
- **Cutover to production `D:\` roots** — described, deliberately not performed.
- `docs/website/` (3 documents on `integration`) — no website code.

### Referenced But Missing
- **`CONSTITUTION.md`** — declared supreme law over all governed development work, stated to
  live outside this repository. **It is not in any of the fourteen repositories.**
- `config/dispatch.config.json` — named, forbidden, absent (correctly).
- `DISPATCH_HOLD_SEED_PACKAGE_v1` is present as a reference document; the seeding it describes
  was performed.

### Unknown
- Whether the 428 test functions pass — **not run** during this inventory.
- Whether the two pilot runs (`RUN_1`, `RUN_2`) were executed against sandbox or real data.
  The reports were not read line-by-line in this inventory.
- Why `integration` was never merged. No decision record exists.
- What "merge 5" refers to; the phrase appears in `README.md` without a referent in-repo.

---

## SECTION 10 — EXECUTIVE SUMMARY

**What is this repository?**

Hold is the **construction repository for Dispatch Matrix Group 1** — the Librarian, Manager,
Receipt/IFTA and Reports lanes — seeded deliberately empty so that no build session would
touch production `D:\` roots before Mike cut over. It is the only repository whose `main`
branch has no human-authored commit.

**What is actually implemented?**

This is where a default-branch reading fails. `main` holds 68 files, 39 of them documents,
17 of them `.gitkeep` placeholders, and **zero lines of Python**. Its `integration` branch
holds **267 files, 148 Python modules, 13,770 lines of code and 428 test functions** — a
working receipt-and-IFTA system with OCR/vision extraction, CSV and statement parsers,
deduplication, a full IFTA engine (mileage, rates, worksheet, packaging, exceptions, live
indicators), an **IFTA Clerk** with a review dashboard, a prepare-this-quarter workflow and a
payment-recommendation engine, a Reports lane with a fidelity gate, a Manager queue, a
Librarian spine, an evidence index, a hosting shell, a pilot intake, five CLI tools, and
golden-file and schema-conformance test suites. It was built across 22 branches in roughly 26
hours on 2026-08-04 and 05, and **none of it was ever merged**. Nothing in the repository
records why.

**What unique value does it contain?**

Three holdings are singular. First, the **IFTA Clerk** — a clerk-facing review dashboard,
prepare-this-quarter workflow and payment-recommendation engine with twelve supporting
documents. Dispatch has an IFTA subsystem but nothing resembling this clerk layer, and no
other repository has any of it. Second, the **8 JSON Schemas with a contract register and
conformance tests** — the only formal machine-readable data contracts anywhere in the
ecosystem. Third, the **seven per-worker constitutions** (Base, IFTA, Librarian, Manager,
Receipt, Reports, Memory), each mirrored into a library seed, plus the `APPROVAL_REGISTER.md`
holding the fourteen approval items — governance that exists in no other repository, including
the ecosystem's only Manager *constitution* and only OCR/vision extraction doctrine.

Alongside these: eleven reference audits, four lane launch packages with walkthrough reports,
two executed pilot run reports, and a set of doctrine-enforcing boundary tests
(`test_no_tax_math`, `test_no_delete_sql`, `test_readonly_enforcement`) that assert what the
system must not do.

One dependency is recorded as missing everywhere: `CONSTITUTION.md`, the Level 1 Transport
master constitution that `README.md` declares supreme law over all governed development work,
is stated to live outside this repository — and it is not in any of the fourteen.
