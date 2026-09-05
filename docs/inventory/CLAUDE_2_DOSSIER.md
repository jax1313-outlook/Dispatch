# CLAUDE_2_DOSSIER.md

Repository inventory dossier. Authority: Mike Zachary.
Compiled 2026-09-05. Default branch `main` at `e681685`; both branches examined.

Recovery operation only. This dossier records what exists. It makes no design,
archive, cleanup, or refactor recommendation.

---

## SECTION 1 — REPOSITORY FACTS

| Fact | Value | How established |
|---|---|---|
| Repository name | `Claude-2` | `git remote get-url origin` |
| Repository URL | https://github.com/jax1313-outlook/Claude-2 | same |
| Visibility | Public | `list_repos` |
| Creation date (first commit) | 2026-08-10 09:09:36 -0400 | `git log --reverse` |
| Last commit date | 2026-08-10 12:48:29 -0400 (`e681685`, "Add files via upload") | `git log -1` |
| Last push | 2026-08-10T16:48:29Z | `list_repos` |
| **Lifespan** | **3 hours 39 minutes**, first commit to last | computed |
| Branch count | **2** — `main`, `claude/new-session-jwlb0v` | `git ls-remote --heads` |
| Commit count | **8** | `git rev-list --count HEAD` |
| Default branch | `main` | `git ls-remote` |
| Contributors | `jax1313-outlook` (8) — sole contributor, **no agent commits** | `git shortlog -sne` |
| README status | Present — `README.md` with a substantive purpose statement | `git ls-files` |
| Tracked files | 17 — **all markdown** | `git ls-files` |
| Python | **0** | `git ls-files '*.py'` |
| Markdown | 17 files, 3,819 lines | `wc -l` |
| Files unique to branches | **4** | branch scan |

Every commit message on `main` is a GitHub web-UI upload ("Add files via upload"). This
repository was assembled by hand through the browser, not by an agent or a local clone.

---

## SECTION 2 — PURPOSE

**Evidence source:** `README.md`, quoted at length because it is unusually explicit.

> # Claude-2
> ## Purpose
> Claude-2 is a clean architecture review and build-planning repository for the Dispatch
> platform.
>
> This repository exists to let Claude perform independent analysis, mapping, stress testing,
> and build-planning work against the current Dispatch architecture **without being contaminated
> by old drafts, retired concepts, or historical governance clutter.**
>
> ## Current Mission
> Use the current Dispatch documents to produce or review:
> - End-to-end program maps
> - Architecture stress tests
> - Build-readiness analysis
> - Dispatch Spine proposals
> - Portal flow analysis
> - Manager, Publisher, and Intelligence boundaries
> - MVP recommendations
> - Risks, blockers, and implementation sequencing
>
> ## Source of Truth
> Use only the current documents in this repository unless Mike explicitly supplies archived
> history.
> Start with:
> 1. `DISPATCH_CONSTITUTION_v2.md`
> 2. `CONTEXT_MASTER.md`
> 3. `ARCHITECTURE.md`

This is a **clean-room analysis workspace**, deliberately seeded with a curated document set and
nothing else. It is the second in a numbered series: `Claude` → `Claude-2` → `Claude-3`, each
created a short time after the last (2026-08-08, 2026-08-10 morning, 2026-08-10 afternoon).

---

## SECTION 3 — DIRECTORY MAP

Flat — 17 markdown files at the root, no directories, no code.

```
Claude-2/                                        (main)
├── README.md                                    ← unique: the mission statement
├── DISPATCH_CONSTITUTION_v3.md                  v3 (README points to v2 — see note)
├── CONTEXT_MASTER.md  ARCHITECTURE.md  ARCHITECTURAL_DISPOSITION.md
├── COGNITIVE_FUNCTIONS.md
├── INTELLIGENCE_ANALYST.md  MANAGER.md  PUBLISHER.md
├── PORTAL_DESCRIPTION.md
├── DISPATCH_SPINE_OVERVIEW.md
├── DISPATCH_SPINE_SPECIFICATION_v1.md
├── DISPATCH_SPINE_SPEC_v1.md                    ← unique: a SECOND spine spec file
├── DISPATCH_DECISION_MATRIX.md
├── DISPATCH_FINAL_ARCHITECTURE_STRESS_TEST_PROMPT.md   ← unique
├── SUPERSESSION_MAP.md  REFINEMENT_ANALYST_REMOVAL.md
└── (branch adds)
    ├── DISPATCH_CONSTITUTION_v2.md              ← the version the README names
    ├── DISPATCH_CONSENSUS_MATRIX_RESULT.md              ← unique
    ├── DISPATCH_CONSENSUS_MATRIX_REVISED_RESULT.md      ← unique
    └── DISPATCH_FINAL_ARCHITECTURE_STRESS_TEST_RESULT.md ← unique
```

**Recorded discrepancy.** `README.md` instructs the reader to "Start with 1.
`DISPATCH_CONSTITUTION_v2.md`". That file is **not on `main`** — `main` carries
`DISPATCH_CONSTITUTION_v3.md`. `v2` exists on the `claude/new-session-jwlb0v` branch. A reader
following the README on `main` would not find the document it names. Recorded as fact.

**Recorded duplication.** Both `DISPATCH_SPINE_SPECIFICATION_v1.md` and
`DISPATCH_SPINE_SPEC_v1.md` are present. The first is shared with four other repositories; the
second is unique to Claude-2. Their contents were not diffed in this inventory.

---

## SECTION 4 — CODE INVENTORY

**None.** No applications, services, modules, APIs, routes, CLI tools, background services,
database models, contracts, adapters, connectors, tests, scripts, utilities or entry points.
17 markdown files and nothing else. No `.gitignore`, no CI.

This is the only repository of the fourteen with **no code and no non-markdown file of any kind**
apart from `premium-logistics-platform-` (which has a `.gitignore`).

---

## SECTION 5 — FUNCTIONAL CAPABILITIES

| Capability | Exists | Evidence | Primary files | Status |
|---|---|---|---|---|
| Curated clean-room doctrine set | Yes | 17 documents, README's "Source of Truth" section | root | DOCUMENTED |
| Architecture stress test — **the prompt** | Yes | `DISPATCH_FINAL_ARCHITECTURE_STRESS_TEST_PROMPT.md` | that file | DOCUMENTED |
| Architecture stress test — **the result** | Yes (branch) | `DISPATCH_FINAL_ARCHITECTURE_STRESS_TEST_RESULT.md` | branch `claude/new-session-jwlb0v` | COMPLETE on a branch; ABSENT from `main` |
| Consensus matrix — result and revision | Yes (branch) | `DISPATCH_CONSENSUS_MATRIX_RESULT.md`, `..._REVISED_RESULT.md` | branch | COMPLETE on a branch; ABSENT from `main` |
| Spine specification (two files) | Yes | `DISPATCH_SPINE_SPECIFICATION_v1.md` + `DISPATCH_SPINE_SPEC_v1.md` | those files | DOCUMENTED |
| Any software capability | **No** | no code of any kind | — | ABSENT by design |

---

## SECTION 6 — DOCUMENT INVENTORY

17 files on `main`, 4 more on the branch.

**Constitutions** — `DISPATCH_CONSTITUTION_v3.md` (`main`);
`DISPATCH_CONSTITUTION_v2.md` (branch — the one the README names).

**Architecture documents** — `ARCHITECTURE.md`, `ARCHITECTURAL_DISPOSITION.md`,
`CONTEXT_MASTER.md`, `DISPATCH_SPINE_OVERVIEW.md`, `PORTAL_DESCRIPTION.md`,
`COGNITIVE_FUNCTIONS.md`.

**Specifications** — `DISPATCH_SPINE_SPECIFICATION_v1.md`,
**`DISPATCH_SPINE_SPEC_v1.md`** (unique), `DISPATCH_DECISION_MATRIX.md`.

**Governance** — `SUPERSESSION_MAP.md`, `REFINEMENT_ANALYST_REMOVAL.md`.

**Department descriptions** — `MANAGER.md`, `PUBLISHER.md`, `INTELLIGENCE_ANALYST.md`.

**Prompts** — **`DISPATCH_FINAL_ARCHITECTURE_STRESS_TEST_PROMPT.md`** (unique). This is one of
only two standalone prompt files in the entire ecosystem; the other is
`Joe-Assistant/Governing_Inputs/LEVEL1_ASSISTANT_AGENT_CONFIG_v1.txt`.

**Research / analysis results (branch, all unique)** —
`DISPATCH_FINAL_ARCHITECTURE_STRESS_TEST_RESULT.md`, `DISPATCH_CONSENSUS_MATRIX_RESULT.md`,
`DISPATCH_CONSENSUS_MATRIX_REVISED_RESULT.md`.

**Decision logs / Roadmaps / Handoffs / Operational documents** — none.

---

## SECTION 7 — UNIQUE ASSETS

**3 of 17 `main` files are unique by content** — the lowest unique ratio of any repository in
the ecosystem (17.6%). The other 14 are byte-identical to copies in `Claude`, `Claude-3`,
`Library` and `Jules`. Four further unique files exist on the branch.

### 1. `DISPATCH_FINAL_ARCHITECTURE_STRESS_TEST_PROMPT.md` — and its result
The prompt is on `main`; **`DISPATCH_FINAL_ARCHITECTURE_STRESS_TEST_RESULT.md` is on the
branch**. Together they are a complete stress-test exercise: the question asked and the answer
produced. The prompt is one of only two standalone prompt artefacts in the ecosystem, and this
is the only prompt/result pair.

### 2. The consensus matrix results (branch)
`DISPATCH_CONSENSUS_MATRIX_RESULT.md` and `DISPATCH_CONSENSUS_MATRIX_REVISED_RESULT.md` — a
result and its revision. A consensus exercise recorded nowhere else. Neither is on `main`.

### 3. `DISPATCH_SPINE_SPEC_v1.md`
A second spine specification file, distinct from the `DISPATCH_SPINE_SPECIFICATION_v1.md` that
four other repositories share. Unique to this repository; contents not diffed here.

### 4. The README as a clean-room charter
The only document in the ecosystem that states a repository exists to work "**without being
contaminated by old drafts, retired concepts, or historical governance clutter**" and fixes a
reading order (Constitution → Context Master → Architecture). It is the clearest statement of the
clean-room method that produced the `Claude` → `Claude-2` → `Claude-3` series.

### 5. Hand-assembled provenance
All 8 commits are "Add files via upload" by `jax1313-outlook` — every file placed through the
GitHub web UI. The only repository of the fourteen with no agent-authored commit **and** no
local-clone commit. Its document set is therefore a record of exactly what Mike considered
current on 2026-08-10.

---

## SECTION 8 — CROSS-REPOSITORY REFERENCES

| Referenced entity | Occurrences | Representative files |
|---|---|---|
| Dispatch | 175 | throughout |
| Manager | 120 | `MANAGER.md`, README's "Manager, Publisher, and Intelligence boundaries" |
| Publisher | 102 | `PUBLISHER.md` |
| Library | 87 | doctrine documents |
| Jules | 10 | doctrine documents |
| Route Risk | 3 | doctrine documents |
| SAM | 3 | doctrine documents |
| COMI | 2 | doctrine documents |
| Joe / Mission Visibility | 0 | — |

**Series relationship.** `Claude` (2026-08-08, v2 doctrine), `Claude-2` (2026-08-10 09:09,
mixed v2/v3), `Claude-3` (2026-08-10 13:09, v3 doctrine). Claude-2's first commit is
**4 hours 21 minutes** before Claude-3's — the two were created the same day. Claude-2 carries
`DISPATCH_CONSTITUTION_v3.md`; `Claude-3` carries it too. Claude-2 is the hinge between the v2
and v3 families.

**Shared files (14).** The doctrine set shared with `Claude`, `Claude-3`, `Library` and `Jules`.

---

## SECTION 9 — BUILT VS PLANNED

### Built In Code
**Nothing.** No code exists in this repository on any branch.

### Partially Built
Not applicable — no build was attempted.

### Documented Only
Everything: the constitution (v3 on `main`, v2 on the branch), context master, architecture,
architectural disposition, cognitive functions, spine overview and two spine specifications,
decision matrix, supersession map, refinement-analyst removal, and the Manager / Publisher /
Intelligence Analyst descriptions.

### Referenced But Missing
- **`DISPATCH_CONSTITUTION_v2.md`** — named by `README.md` as the first document to read, and
  **absent from `main`**. It is on the `claude/new-session-jwlb0v` branch.
- **The eight mission outputs listed in "Current Mission"** — end-to-end program maps,
  architecture stress tests, build-readiness analysis, Spine proposals, portal flow analysis,
  department boundaries, MVP recommendations, risks/blockers/sequencing. Of these, the stress
  test and the consensus matrix were produced (on the branch). The other six have no
  corresponding output file in this repository. Some were produced elsewhere:
  `Claude/DISPATCH_PROGRAM_MAP.md` (program map), `Claude/DISPATCH_BUILD_PROPOSAL.md` and
  `Claude/proposal/spine_prototype/` (Spine proposal), `Claude-3/DISPATCH_V0_BUILD_PLAN.md`
  (build planning).

### Unknown
- Why the stress-test result and both consensus-matrix results were never merged to `main`.
- Whether `DISPATCH_SPINE_SPEC_v1.md` and `DISPATCH_SPINE_SPECIFICATION_v1.md` differ in
  substance — **not diffed** in this inventory.
- Why the README names v2 while `main` carries v3.

---

## SECTION 10 — EXECUTIVE SUMMARY

**What is this repository?**

Claude-2 is a **clean-room architecture review and build-planning workspace** — the middle
member of the `Claude` → `Claude-2` → `Claude-3` series. Its README states its purpose plainly:
to allow independent analysis "without being contaminated by old drafts, retired concepts, or
historical governance clutter." It was assembled entirely by hand through the GitHub web UI —
all eight commits read "Add files via upload" — and its whole life ran **3 hours and 39 minutes**
on 2026-08-10, after which it was never touched again.

**What is actually implemented?**

No software of any kind, on any branch. Seventeen markdown documents on `main` and four more on
a branch. That is the entire repository. It contains no `.gitignore`, no tests, no CI, and no
non-markdown file.

What *was* produced is analysis. The `main` branch holds
`DISPATCH_FINAL_ARCHITECTURE_STRESS_TEST_PROMPT.md`; the branch holds its result, plus a
consensus matrix result and a revised consensus matrix result. Of the eight outputs the README's
"Current Mission" section asks for, two exist here (both on the branch) and three others were
produced in sibling repositories.

**What unique value does it contain?**

Its unique-content ratio is the lowest in the ecosystem — 3 of 17 files — because it is, by
design, a curated copy of a doctrine set that exists elsewhere. Its value is not in what it
duplicates but in four things.

First, the **stress-test prompt and its result** form the ecosystem's only complete
prompt-and-answer pair; the prompt is one of just two standalone prompt artefacts anywhere.
Second, the **consensus matrix result and its revision** record an exercise preserved nowhere
else. Third, `DISPATCH_SPINE_SPEC_v1.md` is a second, distinct spine specification found only
here. Fourth, and least obviously, its hand-assembled provenance makes its document set a
reliable record of **exactly which documents Mike considered current on 2026-08-10** — no agent
selected them.

Two discrepancies are recorded as fact: the README instructs a reader to start with
`DISPATCH_CONSTITUTION_v2.md`, which is not on `main`; and all three analysis results sit on an
unmerged branch.
