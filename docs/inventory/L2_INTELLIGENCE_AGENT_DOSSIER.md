# L2_INTELLIGENCE_AGENT_DOSSIER.md

Repository inventory dossier. Authority: Mike Zachary.
Repository name on GitHub is `L2-intelligence-agent.` — **with a trailing period**.
Compiled 2026-09-05 from commit `9614780` (`origin/main`).

Recovery operation only. This dossier records what exists. It makes no design,
archive, cleanup, or refactor recommendation.

---

## SECTION 1 — REPOSITORY FACTS

| Fact | Value | How established |
|---|---|---|
| Repository name | `L2-intelligence-agent.` (trailing period is part of the name) | `git remote get-url origin` |
| Repository URL | https://github.com/jax1313-outlook/L2-intelligence-agent. | same |
| Visibility | **Private** — the only private repository of the fourteen | `list_repos` |
| Creation date (first commit) | **2026-07-27 10:36:15 -0400** — the oldest first commit in the ecosystem | `git log --reverse` |
| Last commit date | 2026-08-11 13:29:36 -0400 (`9614780`, "Build Intelligence department to integration-ready status (#2)") | `git log -1` |
| Last push | 2026-08-11T17:29:37Z | `list_repos` |
| Branch count | **3** — `main`, `claude/dispatch-tri-department-build-899qjm`, `jules-5236623337766230356-3cd9e666` | `git ls-remote --heads` |
| Commit count | **11** | `git rev-list --count HEAD` |
| Default branch | `main` | `git ls-remote` |
| Contributors | `jax1313-outlook` (10), `google-labs-jules[bot]` (1) | `git shortlog -sne` |
| README status | Present — **two**: `README.md` and `READ ME.md` | `git ls-files` |
| Tracked files | 84 | `git ls-files \| wc -l` |
| Python | 23 files, **2,006 lines** | `git ls-files '*.py'` + `wc -l` |
| Markdown | 35 files, 4,247 lines | same |

---

## SECTION 2 — PURPOSE

**Evidence source:** `README.md`.

> **Dispatch Intelligence** — Intelligence department implementation for the Dispatch program
> (Level 1 Transport / Mike Zachary). This repo builds the **Intelligence** link of the
> Intelligence → Library → Publisher dependency chain defined in
> `04_DISPATCH_SYSTEM_RELATIONSHIP_MATRIX.md`.

`README.md` also records its own renaming:

> Legacy note: this repo predates the current program name. "L2-COS" and "Read-Only Learning
> Sandbox" in earlier history are retired terminology (DISPATCH_CONSTITUTION_v3 Section 2) and
> no longer describe this repo's role or status.

And its status, verbatim:

> **Integration-ready candidate.** Not merged into Dispatch. Not deployed. Not
> production-promoted. See `MERGE_READINESS_REPORT.md` and `KNOWN_GAPS.md`. Mike decides on
> promotion.

Two layers, both **offline and deterministic — no LLM calls, no network, no third-party APIs**:

1. A deterministic analysis pipeline that reads one opportunity/document text file, classifies
   it, extracts facts, detects operational and government signals, flags 15+ risk conditions,
   and assigns routing labels from a fixed allowed set — "never an approval/decision label".
2. An object model and service layer producing the doctrine-required structured objects:
   Intelligence Finding, Operational Consideration, Special Requirement, Publisher Requirement,
   Library Candidate, Manager Decision Support Note.

This is one of **three sibling repositories** built to the same pattern in the same campaign
(with `Library` and `Publisher`), all reaching "integration-ready candidate" on 2026-08-11.

---

## SECTION 3 — DIRECTORY MAP

```
L2-intelligence-agent./
├── src/dispatch_intel/        The Intelligence department (14 modules)
│   ├── normalization.py       Text normalization (incl. messy OCR)
│   ├── classifier.py          Document classification
│   ├── extractors.py          Fact extraction
│   ├── risk.py                15+ risk-condition flags
│   ├── routing.py             Fixed-set routing labels — never an approval label
│   ├── report_writer.py       Markdown + JSON report emission
│   ├── analyzer.py            Pipeline orchestration
│   ├── rules.py               Rule definitions
│   ├── models.py              The six doctrine objects
│   ├── store.py               IntelligenceStore (in-memory)
│   ├── service.py             Integration surface for Library / Publisher
│   ├── config.py, cli.py, __init__.py
├── tests/                     9 files, 33 test functions
├── examples/                  10 real-shape input samples across 6 source families:
│   ├── federal/               sample_federal.txt, sample_gsa.txt
│   ├── sam_gov/               sample_sam.txt
│   ├── state_local/           sample_state, sample_dot, sample_city_county, sample_port_agency
│   ├── fema_emergency/        sample_fema.txt
│   ├── load_board/            sample_load.txt
│   └── messy_ocr/             sample_messy.txt
├── reports/
│   ├── sample_outputs/        20 files — 10 .json + 10 .md, one pair per example
│   └── BUILD_VALIDATION_REPORT.md
├── test_inputs/               5 files nested 5 levels deep (see note below)
├── docs/                      ARCHITECTURE, USAGE, OBJECT_MODEL, LIMITATIONS,
│                              HUMAN_REVIEW_GUIDE, FUTURE_CONNECTORS
└── (root)                     Governance set: 01–08 numbered Dispatch documents,
                               DISPATCH_CONSTITUTION_v2, DISPATCH_CONTEXT_MASTER_v2,
                               DISPATCH_AGENT_GOVERNANCE_LAW_v1, MANAGER_DESCRIPTION_v2,
                               KNOWN_GAPS, MERGE_READINESS_REPORT, README, READ ME
```

**Note on `test_inputs/`.** The tree is `test_inputs/test_inputs/test_inputs/test_inputs/
test_inputs/` — five nested directories of the same name holding
`broker_test.txt`, `fema_test.txt`, `county_test.txt`, `sam_test.txt`. Recorded as observed.

---

## SECTION 4 — CODE INVENTORY

### Applications
Command-line analyzer only. No web application, no service daemon.

### Entry points
`python -m dispatch_intel` / `dispatch_intel.cli`. Per `README.md`, the CLI "calls both layers
on every `analyze`".

### Modules — `src/dispatch_intel/` (14)
| Module | Role |
|---|---|
| `normalization.py` | Normalizes input text, including messy OCR |
| `classifier.py` | Classifies the document |
| `extractors.py` | Extracts facts |
| `risk.py` | Flags 15+ risk conditions |
| `routing.py` | Assigns routing labels from a fixed allowed set |
| `rules.py` | Rule definitions |
| `analyzer.py` | Orchestrates the pipeline |
| `report_writer.py` | Emits the Markdown and JSON reports |
| `models.py` | The six doctrine objects |
| `store.py` | `IntelligenceStore` — **in-memory only** (`KNOWN_GAPS.md`) |
| `service.py` | `build_finding_from_analysis()`, `route_to_publisher()`, `route_to_library()` |
| `config.py` | Configuration |
| `cli.py` | CLI, `--summary`, JSON `intelligence_objects` section, batch tally |
| `__init__.py` | Package |

### APIs / Routes
None. There is no HTTP surface.

### CLI tools
`dispatch_intel.cli` — `analyze` with `--summary`; emits per-file JSON and Markdown reports and
a batch-level tally.

### Background services
None.

### Database models
No database. `models.py` defines six dataclass-style objects per
`DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` §3 (which lives in the Claude-3 repository):
**Intelligence Finding**, **Operational Consideration**, **Special Requirement**,
**Publisher Requirement**, **Library Candidate**, **Manager Decision Support Note**.

### Contracts
`service.py` is the declared integration surface for the Library and Publisher repositories.
`Publisher/src/dispatch_publisher/intelligence_client.py` is the matching duck-typed client on
the other side.

### Adapters / Connectors
None implemented. `docs/FUTURE_CONNECTORS.md` documents intended ones.

### Tests
9 files, **33 `def test_` functions**: `test_classifier`, `test_cli`, `test_extractors`,
`test_models`, `test_normalization`, `test_reports`, `test_risk`, `test_routing`, `test_service`.
Includes `test_cli.py::test_cli_wires_service_layer_into_json_report_and_summary`, added to close
an audit finding. *Not run during this inventory.*

### Scripts / utilities
None beyond the CLI.

---

## SECTION 5 — FUNCTIONAL CAPABILITIES

| Capability | Exists | Evidence | Primary files | Status |
|---|---|---|---|---|
| Text normalization (incl. messy OCR) | Yes | `examples/messy_ocr/sample_messy.txt` + its report pair | `normalization.py`, `tests/test_normalization.py` | IMPLEMENTED |
| Document classification | Yes | 6 source families covered by examples | `classifier.py`, `tests/test_classifier.py` | IMPLEMENTED |
| Fact extraction | Yes | 10 sample report pairs | `extractors.py`, `tests/test_extractors.py` | IMPLEMENTED |
| Risk detection (15+ conditions) | Yes | `README.md`; `tests/test_risk.py` | `risk.py` | IMPLEMENTED |
| Routing labels (fixed set) | Yes | `README.md`: "never an approval/decision label" | `routing.py`, `tests/test_routing.py` | IMPLEMENTED — advisory only, consistent with Dispatch `CLAUDE.md` §4 |
| Report generation (JSON + Markdown) | Yes | 20 committed sample outputs | `report_writer.py`, `tests/test_reports.py` | IMPLEMENTED |
| Six doctrine objects | Yes | `docs/OBJECT_MODEL.md`; `tests/test_models.py` | `models.py` | IMPLEMENTED |
| Service layer → Publisher / Library | Yes | `route_to_publisher()`, `route_to_library()`; `tests/test_service.py` | `service.py` | IMPLEMENTED — no live consumer connected |
| CLI wiring of the service layer | Yes | Fixed after an external audit finding; dedicated regression test | `cli.py` | IMPLEMENTED |
| Persistent store | **No** | `KNOWN_GAPS.md`: "**No persistent store.** `IntelligenceStore` is in-memory only." | `store.py` | ABSENT |
| LLM / network / third-party APIs | **No** (by design) | `README.md`: "both offline/deterministic — no LLM calls, no network access, no third-party APIs" | — | ABSENT by design |
| Connectors | **No** | `docs/FUTURE_CONNECTORS.md` is forward-looking | — | DOCUMENTED ONLY |
| Merged into Dispatch | **No** | `README.md`: "Not merged into Dispatch. Not deployed. Not production-promoted." | — | UNVERIFIED / not promoted |

---

## SECTION 6 — DOCUMENT INVENTORY

35 markdown files.

**Constitutions** — `01_DISPATCH_CONSTITUTION.md`, `DISPATCH_CONSTITUTION_v2.md`.

**Governance documents** (the numbered Dispatch set) —
`02_DISPATCH_AGENT_GOVERNANCE_LAW.md`, `03_DISPATCH_AGENT_RELATIONSHIP_MATRIX.md`,
`04_DISPATCH_CONTEXT_MASTER.md`, `04_DISPATCH_SYSTEM_RELATIONSHIP_MATRIX.md`,
`05_DISPATCH_AUTHORITY_MATRIX.md`, `05_DISPATCH_TRI_DEPARTMENT_MATRIX_BUILD_COMMAND.md`,
`06_DISPATCH_LEARNING_MATRIX.md`, `07_DISPATCH_CONFLICT_MATRIX.md`,
`08_DISPATCH_BUILD_VALIDATION_STANDARD.md`, `DISPATCH_AGENT_GOVERNANCE_LAW_v1.md`,
`DISPATCH_CONTEXT_MASTER_v2.md`, `MANAGER_DESCRIPTION_v2.md`.

**Architecture documents** — `docs/ARCHITECTURE.md`.

**Specifications** — `docs/OBJECT_MODEL.md` (the six objects and the
`PARTIALLY_VERIFIED` default), `docs/FUTURE_CONNECTORS.md`.

**Decision logs** — none.

**Roadmaps** — `05_DISPATCH_TRI_DEPARTMENT_MATRIX_BUILD_COMMAND.md` is the build command this
repository was executed against.

**Research / validation reports** — `reports/BUILD_VALIDATION_REPORT.md`,
`MERGE_READINESS_REPORT.md`.

**Gap records** — `KNOWN_GAPS.md`, `docs/LIMITATIONS.md`.

**Operational documents** — `docs/USAGE.md`, `docs/HUMAN_REVIEW_GUIDE.md`.

**Handoffs** — `READ ME.md` (distinct from `README.md`).

**Prompts** — none.

---

## SECTION 7 — UNIQUE ASSETS

**68 of 84 files (81.0%) have content found in no other repository.**

1. **The only Intelligence-department implementation in the ecosystem** —
   `src/dispatch_intel/` (14 modules, 2,006 LOC). Dispatch has
   `portal/models/intelligence.py` and `/intelligence/*` routes, but that is a portal surface
   for holding and promoting intelligence records; it is not this analysis pipeline. No other
   repository contains a classifier, extractor set, risk-flag engine or routing labeller.
2. **The 10-example corpus across six source families** — `examples/federal/` (2),
   `sam_gov/`, `state_local/` (4), `fema_emergency/`, `load_board/`, `messy_ocr/`. Real-shape
   solicitation and load text found nowhere else. The `messy_ocr` sample in particular is the
   only OCR-degradation fixture in the ecosystem.
3. **20 committed sample outputs** — `reports/sample_outputs/`, a `.json` and `.md` pair for
   each example. These are executed results, not templates: a record of what the pipeline
   actually produced.
4. **The six doctrine objects as code** — `models.py` implementing Intelligence Finding,
   Operational Consideration, Special Requirement, Publisher Requirement, Library Candidate and
   Manager Decision Support Note. The `Library` repository's `LibraryCandidate` is documented as
   "field-compatible with the Intelligence repo's object of the same name" — this repository
   holds the origin definition.
5. **A named Manager object in code** — `Manager Decision Support Note` is produced by
   `models.py`/`service.py`. This is the only *object-level* Manager artefact in a working
   pipeline outside `Dispatch-Old/cin_lite/manager.py`. Recorded as fact.
6. **`docs/HUMAN_REVIEW_GUIDE.md`** — the ecosystem's only guide written for the human doing
   the reviewing rather than for the builder.
7. **`MANAGER_DESCRIPTION_v2.md`** — a Manager description document unique to this repository.
8. **`01_DISPATCH_CONSTITUTION.md`** — the `01_`-numbered constitution, unique here.
9. **Oldest first commit in the ecosystem** (2026-07-27), and the only **private** repository.
10. **A `jules-*` branch** (`jules-5236623337766230356-3cd9e666`) — one of only four
    repositories carrying Jules-bot branch history.

---

## SECTION 8 — CROSS-REPOSITORY REFERENCES

| Referenced entity | Occurrences | Representative files |
|---|---|---|
| Dispatch | 221 | `README.md`, `docs/ARCHITECTURE.md`, all numbered governance documents |
| Library | 284 | `service.py::route_to_library`, `models.py` (`LibraryCandidate`), `KNOWN_GAPS.md` |
| Publisher | 237 | `service.py::route_to_publisher`, `models.py` (`PublisherRequirement`) |
| Manager | 130 | `MANAGER_DESCRIPTION_v2.md`, `models.py` (Manager Decision Support Note), `03_`/`05_` matrices |
| SAM / SAM.gov | 32 | `examples/sam_gov/sample_sam.txt`, `reports/sample_outputs/sample_sam_report.*` |
| Jules | 1 | branch `jules-5236623337766230356-3cd9e666` |
| Route Risk | 2 | incidental |
| COMI / Mission Visibility / Joe | 0 | — |

**Named cross-repository dependencies.**
- `KNOWN_GAPS.md` cites `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` **§1 and §3 in the Claude-3
  repository** as the governing object contract — a live dependency on Claude-3.
- `KNOWN_GAPS.md` cites `TRI_DEPARTMENT_BUILD_RECEIPT_AND_QUALITY_AUDIT_v1.md` **in Claude-3**
  as the external audit that found the CLI/service-layer defect.
- `README.md` cites `04_DISPATCH_SYSTEM_RELATIONSHIP_MATRIX.md` for the
  Intelligence → Library → Publisher chain.
- `Publisher/src/dispatch_publisher/intelligence_client.py` is the matching client in the
  Publisher repository.

---

## SECTION 9 — BUILT VS PLANNED

### Built In Code
Text normalization including messy OCR · document classification across six source families ·
fact extraction · 15+ risk-condition flags · fixed-set routing labels · JSON and Markdown report
writing · the six doctrine objects · a service layer routing to Publisher and Library ·
a CLI wiring both layers with `--summary` and a batch tally · 33 test functions · 20 executed
sample outputs.

### Partially Built
- **Service-layer integration** — `route_to_publisher()` and `route_to_library()` exist and are
  tested, but no live consumer is connected; the three sibling repositories are independently
  built and unmerged.
- **Verification status** — `KNOWN_GAPS.md` records that the default `PARTIALLY_VERIFIED` is
  "a conservative, documented scaffold choice… not a doctrine claim", because the tuning material
  for verification thresholds was not found.

### Documented Only
- `docs/FUTURE_CONNECTORS.md` — connectors named, none implemented.
- The numbered governance set (`01_`–`08_`) — doctrine mirrored here, implemented elsewhere or
  nowhere.

### Referenced But Missing
`KNOWN_GAPS.md` states plainly, under "Missing source material", that these were
**not found in any repo in scope**:
- `DISPATCH_FINAL_BLUEPRINT_v1.md` — the blueprint that Claude-3 and Jules were both created to
  produce. **It was not in scope when this repository was built, but it does exist.** It is
  present on 13 unmerged branches across four repositories (identical blob
  `ffb23f9`, 1,133 lines) and on **no default branch anywhere**. See
  `CLAUDE_3_DOSSIER.md` §7 and `MASTER_REPOSITORY_MATRIX.md`.
- `INTELLIGENCE_VERIFICATION_WORKFLOW.md`-adjacent tuning material for verification thresholds.

Also referenced and absent: a persistent store; any live Archive department.

### Unknown
- Whether the 33 test functions currently pass — **the suite was not run** during this inventory.
- Whether the two non-`main` branches carry work absent from `main`; branch contents were not diffed.
- Why the repository name ends in a period.

---

## SECTION 10 — EXECUTIVE SUMMARY

**What is this repository?**

`L2-intelligence-agent.` is the **Intelligence department** of the Dispatch program — the first
link of the Intelligence → Library → Publisher chain. It carries the oldest first commit in the
ecosystem (2026-07-27) and is the only private repository of the fourteen. It was formerly named
"L2-COS" and "Read-Only Learning Sandbox"; its README records that terminology as retired. It is
one of three sibling repositories (with `Library` and `Publisher`) built to the same command in
one campaign, all declared "integration-ready candidate" on 2026-08-11 and none merged since.

**What is actually implemented?**

A working, entirely offline, entirely deterministic analysis pipeline: 2,006 lines across 14
modules that read one opportunity or document, normalize it (including degraded OCR), classify
it, extract facts, flag 15+ risk conditions, and assign routing labels from a fixed set that
"never" includes an approval or decision label. On top sits an object layer producing the six
doctrine objects — Intelligence Finding, Operational Consideration, Special Requirement,
Publisher Requirement, Library Candidate, Manager Decision Support Note — and a service layer
that routes them toward Publisher and Library. 33 test functions, and 20 committed sample
outputs proving the pipeline against 10 real-shape inputs from six source families.

It has no persistent store (in-memory only), no HTTP surface, no connectors, no LLM calls and no
network access — the last three by explicit design. It is not merged into Dispatch, not deployed
and not production-promoted; its README says Mike decides on promotion.

**What unique value does it contain?**

81% of its files exist nowhere else. It holds the ecosystem's **only Intelligence analysis
pipeline** — Dispatch's `/intelligence` routes are a portal surface for records, not this
engine. It holds the **origin definition of the six shared doctrine objects**, which the Library
repository explicitly declares field-compatibility with. It holds a **10-example corpus across
six source families with 20 executed output pairs** — the only such evidence set in the
ecosystem, including its only OCR-degradation fixture. And it holds `docs/HUMAN_REVIEW_GUIDE.md`,
the only document written for the human reviewer rather than the builder.

Its `KNOWN_GAPS.md` also supplies a lead that reaches beyond this repository: it records that
`DISPATCH_FINAL_BLUEPRINT_v1.md` — the document both Claude-3 and Jules exist to produce — was
"not found in any repo in scope". This inventory located it. The blueprint exists, 1,133 lines,
as an identical blob on **13 unmerged branches across four repositories** and on **no default
branch anywhere**. It was therefore invisible to a builder reading `main`, which is why this
repository was built without it.
