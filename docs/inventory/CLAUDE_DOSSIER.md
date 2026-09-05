# CLAUDE_DOSSIER.md

Repository inventory dossier. Authority: Mike Zachary.
Compiled 2026-09-05. Default branch `main` at `21be42a`; all 3 branches examined.

Recovery operation only. This dossier records what exists. It makes no design,
archive, cleanup, or refactor recommendation.

---

## SECTION 1 — REPOSITORY FACTS

| Fact | Value | How established |
|---|---|---|
| Repository name | `Claude` | `git remote get-url origin` |
| Repository URL | https://github.com/jax1313-outlook/Claude | same |
| Visibility | Public | `list_repos` |
| Creation date (first commit) | 2026-08-08 14:34:02 -0400 — **same second as `Publisher` and `Joe-Assistant`** | `git log --reverse` |
| Last commit date | 2026-08-10 08:57:21 -0400 (`21be42a`, "Merge pull request #1 from jax1313-outlook/claude/dispatch-program-map-proposal-gfeyei") | `git log -1` |
| Last push | 2026-08-10T12:57:21Z — **the oldest last-push of the fourteen** | `list_repos` |
| Branch count | **3** — `main`, `claude/dispatch-program-map-proposal-gfeyei`, `claude/dispatch-manager-architecture-review-ha8tm5` | `git ls-remote --heads` |
| Commit count | **17** | `git rev-list --count HEAD` |
| Default branch | `main` | `git ls-remote` |
| Contributors | `jax1313-outlook` (16), `Claude <noreply@anthropic.com>` (1) | `git shortlog -sne` |
| README status | Present — **contents are the single line `# Test-Grounds`** | `cat README.md` |
| Tracked files | 23 | `git ls-files` |
| Python | 5 files, **252 lines** (all under `proposal/spine_prototype/`) | `wc -l` |
| Markdown | 17 files, 2,322 lines | `wc -l` |
| Files unique to branches | **19** | branch scan |

---

## SECTION 2 — PURPOSE

**Evidence sources:** `README.md`, `DISPATCH_BUILD_PROPOSAL.md`,
`proposal/spine_prototype/README.md`, `DISPATCH_CLEAN_REPO_ROUND_2_MANIFEST.md`, branch names.

`README.md` in full is:

> `# Test-Grounds`

That is the whole file. `Publisher/README.md` records that the Publisher repository was *also*
previously described as "Test-Grounds", and names `jax1313-outlook/Test-Grounds` as a third,
separate repository. This repository still carries the name.

Purpose must therefore be read from contents. Three things are evident:

1. **A build proposal and a Spine prototype.** `DISPATCH_BUILD_PROPOSAL.md` plus
   `proposal/spine_prototype/` — described in its own README as "a first-pass, in-memory
   illustration of the Phase 0 Dispatch Spine skeleton proposed in `DISPATCH_BUILD_PROPOSAL.md`
   Section 9."
2. **A program map.** `DISPATCH_PROGRAM_MAP.md`, merged by the one pull request in the
   repository's history (branch `claude/dispatch-program-map-proposal-gfeyei`).
3. **A Manager architecture review** — branch `claude/dispatch-manager-architecture-review-ha8tm5`,
   carrying `INDEPENDENT_REVIEW_DISPATCH_MANAGER.md` and
   `INDEPENDENT_REVIEW_DISPATCH_MANAGER_ROUND_1.md` with a `round_1_source_materials/` folder.

The repository holds the **v2** doctrine family (`DISPATCH_CONSTITUTION_v2.md`,
`DISPATCH_CONTEXT_MASTER_v2.md`) — earlier than the v3 family in `Claude-2`, `Claude-3`,
`Library` and `Jules`.

---

## SECTION 3 — DIRECTORY MAP

```
Claude/                                   (main)
├── README.md                             "# Test-Grounds"
├── DISPATCH_BUILD_PROPOSAL.md            ← unique
├── DISPATCH_PROGRAM_MAP.md               ← unique
├── DISPATCH_CLEAN_REPO_ROUND_2_MANIFEST.md  ← unique
├── DISPATCH_CONSTITUTION_v2.md           v2 family
├── DISPATCH_CONTEXT_MASTER_v2.md         v2 family
├── CONTEXT_MASTER.md  ARCHITECTURE.md  ARCHITECTURAL_DISPOSITION.md
├── COGNITIVE_FUNCTIONS.md
├── INTELLIGENCE_ANALYST.md               ← unique variant
├── MANAGER.md  PORTAL_DESCRIPTION.md
├── DISPATCH_SPINE_OVERVIEW.md
├── SUPERSESSION_MAP.md  REFINEMENT_ANALYST_REMOVAL.md
└── proposal/spine_prototype/             ← unique: the third Spine implementation
    ├── README.md                         Scope and limits
    ├── state_registry.py                 WorkItem records and status transitions
    ├── validation.py                     Required-field / schema checks
    ├── routing.py                        Deterministic routing table
    ├── event_log.py                      Append-only event log
    └── demo.py                           Runnable demonstration

(branches add)
├── INDEPENDENT_REVIEW_DISPATCH_MANAGER.md            ← unique
├── INDEPENDENT_REVIEW_DISPATCH_MANAGER_ROUND_1.md    ← unique
├── round_1_source_materials/  (8 documents incl. DISPATCH_REFINEMENT_ROUND_1_MANIFEST.md)
├── READ ME.md
└── the 02_–08_ numbered governance set + DISPATCH_AGENT_GOVERNANCE_LAW_v1.md
```

---

## SECTION 4 — CODE INVENTORY

### Applications / Entry points
`proposal/spine_prototype/demo.py` — a runnable demonstration. Nothing else.

### Modules — `proposal/spine_prototype/` (5 files, 252 LOC)
| Module | Role (per its README) |
|---|---|
| `state_registry.py` | WorkItem records and status transitions |
| `validation.py` | Required-field / schema checks |
| `routing.py` | Deterministic routing table — "decides whether a work item needs a cognitive function or is purely mechanical" |
| `event_log.py` | Append-only event log |
| `demo.py` | Simulates where Manager reasoning / Publisher drafting / Intelligence analysis *would* be invoked, "by printing a placeholder instead of calling a model" |

### Declared scope and limits — quoted verbatim from `proposal/spine_prototype/README.md`

> **Scope and limits, read before touching:**
> - No network access, no database, no file storage — everything lives in memory for the length
>   of the `demo.py` run.
> - No cognitive functions are called…
> - No automation hook does anything beyond appending to the event log — none of them can take
>   an external action.
> - This is not wired to real Level 1 Transport data and must not be treated as a production
>   system, a deployed component, or an approval to deploy.
> - This is a recommendation/proposal artifact only. No action is authorized. Mike decides.

### APIs / Routes / CLI / Background services / Database / Connectors / Tests / CI
**None.** No test file, no `pytest.ini`, no CI workflow.

---

## SECTION 5 — FUNCTIONAL CAPABILITIES

| Capability | Exists | Evidence | Primary files | Status |
|---|---|---|---|---|
| Spine prototype: WorkItem state transitions | Yes | `state_registry.py` | that file | IMPLEMENTED — in-memory illustration only, per its own README |
| Validation (required fields / schema) | Yes | `validation.py` | that file | IMPLEMENTED — illustration only |
| Deterministic routing table | Yes | `routing.py` | that file | IMPLEMENTED — illustration only |
| Append-only event log | Yes | `event_log.py` | that file | IMPLEMENTED — illustration only |
| Runnable demo | Yes | `demo.py` | that file | IMPLEMENTED — prints placeholders where models would be called |
| Build proposal | Yes | `DISPATCH_BUILD_PROPOSAL.md` (§9 specifies the Phase 0 Spine skeleton) | that file | DOCUMENTED |
| Program map | Yes | `DISPATCH_PROGRAM_MAP.md`, merged via PR #1 | that file | DOCUMENTED |
| Manager architecture review | Yes (branch) | 2 independent-review documents + 8 source materials | branch `claude/dispatch-manager-architecture-review-ha8tm5` | DOCUMENTED |
| Persistence | **No** | its README: "everything lives in memory" | — | ABSENT by design |
| Cognitive function calls | **No** | its README: "No cognitive functions are called" | — | ABSENT by design |
| External actions | **No** | its README: "none of them can take an external action" | — | ABSENT by design |
| Tests | **No** | no test file exists | — | ABSENT |
| Production use | **No** | its README forbids it explicitly | — | ABSENT by design |

---

## SECTION 6 — DOCUMENT INVENTORY

17 markdown files on `main`; 19 further files on branches.

**Constitutions** — `DISPATCH_CONSTITUTION_v2.md`.

**Architecture** — `ARCHITECTURE.md`, `ARCHITECTURAL_DISPOSITION.md`, `CONTEXT_MASTER.md`,
`DISPATCH_CONTEXT_MASTER_v2.md`, `DISPATCH_SPINE_OVERVIEW.md`, `PORTAL_DESCRIPTION.md`,
`COGNITIVE_FUNCTIONS.md`, **`DISPATCH_PROGRAM_MAP.md`** (unique).

**Proposals** — **`DISPATCH_BUILD_PROPOSAL.md`** (unique),
**`proposal/spine_prototype/README.md`** (unique).

**Governance** — `SUPERSESSION_MAP.md`, `REFINEMENT_ANALYST_REMOVAL.md`,
**`DISPATCH_CLEAN_REPO_ROUND_2_MANIFEST.md`** (unique).
On branches: the `02_`–`08_` numbered set and `DISPATCH_AGENT_GOVERNANCE_LAW_v1.md`.

**Department descriptions** — `MANAGER.md`, **`INTELLIGENCE_ANALYST.md`** (a unique variant —
this repository's copy differs in content from every other repository's file of that name).

**Reviews (branches, unique)** — `INDEPENDENT_REVIEW_DISPATCH_MANAGER.md`,
`INDEPENDENT_REVIEW_DISPATCH_MANAGER_ROUND_1.md`, plus `round_1_source_materials/` holding
`DISPATCH_REFINEMENT_ROUND_1_MANIFEST.md`, `ARCHITECTURE.md`, `COGNITIVE_FUNCTIONS.md`,
`CONTEXT_MASTER.md`, `INTELLIGENCE_ANALYST.md`, `MANAGER.md`, `PORTAL_DESCRIPTION.md`,
`REFINEMENT_ANALYST_REMOVAL.md`.

**Handoffs** — `READ ME.md` (branch).

**Decision logs / Roadmaps / Research reports / Operational documents / Prompts** — none.

---

## SECTION 7 — UNIQUE ASSETS

**12 of 23 files (52.2%) are unique by content**, plus 19 files on branches.

### 1. `proposal/spine_prototype/` — the third Spine implementation in the ecosystem
252 LOC across 5 files. The ecosystem contains **three unrelated Spine implementations**:
| Where | Nature | Persistence |
|---|---|---|
| `Dispatch/dispatch/spine/` | The lifecycle authority: `state.transition()` / `store.apply_transition()` | SQLite (WAL, FK) |
| `Jules/dispatch_spine.py` | Consequence-level model (Levels 0–5), Portal Cards | in-memory |
| `Claude/proposal/spine_prototype/` | WorkItem registry, validation, routing table, event log | in-memory |

None is a copy of another. This one is distinguished by its **deterministic routing table**
that classifies a work item as needing a cognitive function or being purely mechanical — a
decision the other two do not make — and by its **append-only event log**.

### 2. `DISPATCH_BUILD_PROPOSAL.md`
The proposal the prototype illustrates (its §9 specifies the Phase 0 Spine skeleton). Unique.

### 3. `DISPATCH_PROGRAM_MAP.md`
Merged via the repository's only pull request. Unique.

### 4. `DISPATCH_CLEAN_REPO_ROUND_2_MANIFEST.md`
A repository-hygiene manifest from a "Round 2" clean-up. Unique.

### 5. The Manager independent review (on a branch)
`INDEPENDENT_REVIEW_DISPATCH_MANAGER.md` and `..._ROUND_1.md` with an 8-document
`round_1_source_materials/` folder. **The only independent architectural review of Manager
anywhere in the ecosystem** — distinct from Claude-3's `MANAGER_ORCHESTRATION_REVIEW_v1.md`
(a completeness review) and from Hold's `MANAGER_CONSTITUTION_v1.md` (law).

### 6. `round_1_source_materials/` — a preserved review snapshot
Eight documents captured as they stood for Round 1, with their own manifest
(`DISPATCH_REFINEMENT_ROUND_1_MANIFEST.md`). The only frozen point-in-time doctrine snapshot in
the ecosystem; every other repository carries live copies.

### 7. A unique `INTELLIGENCE_ANALYST.md`
This repository's copy is byte-different from the copies in `Claude-2`, `Claude-3`, `Library`
and `Jules` — an earlier or divergent version of the same document.

### 8. The oldest-quiet repository
Last pushed 2026-08-10T12:57:21Z; no repository has been quiet longer.

### 9. The `# Test-Grounds` README
A surviving trace of the "Test-Grounds" naming that `Publisher/README.md` and
`Claude-3/RECOVERY_REPORT.md` both refer to. Recorded as fact.

---

## SECTION 8 — CROSS-REPOSITORY REFERENCES

| Referenced entity | Occurrences | Representative files |
|---|---|---|
| Dispatch | 176 | throughout |
| Manager | 130 | `MANAGER.md`, the independent reviews (branch), `demo.py` placeholder |
| Library | 99 | doctrine documents |
| Publisher | 80 | doctrine documents, `demo.py` placeholder |
| COMI | 3 | doctrine documents |
| SAM | 3 | doctrine documents |
| Route Risk | 3 | doctrine documents |
| Jules / Joe / Mission Visibility | 0 | — |

**Notable.** `demo.py` names Manager, Publisher and Intelligence as the three cognitive
functions whose invocation points it simulates — the clearest compact statement in code of the
three-department model that `L2-intelligence-agent.`, `Library` and `Publisher` later built.

**Shared files (11).** The doctrine set shared with `Claude-2`, `Claude-3`, `Library` and
`Jules`.

---

## SECTION 9 — BUILT VS PLANNED

### Built In Code
An in-memory Spine prototype: WorkItem state registry, validation, a deterministic routing
table, an append-only event log, and a runnable demo. 252 lines.

### Partially Built
Nothing. The prototype's own README declares it complete as an illustration and forbids reading
it as anything more.

### Documented Only
`DISPATCH_BUILD_PROPOSAL.md`, `DISPATCH_PROGRAM_MAP.md`,
`DISPATCH_CLEAN_REPO_ROUND_2_MANIFEST.md`, the v2 doctrine family, and (on a branch) the Manager
independent review with its Round 1 source materials.

### Referenced But Missing
- **Everything the prototype stands in for** — network, database, file storage, cognitive
  functions, automation hooks with real effects. All are named in its README and none exists,
  by design.
- **`jax1313-outlook/Test-Grounds`** — this repository's README still carries the name; a
  separate repository of that name is asserted by `Publisher/README.md` and
  `Claude-3/RECOVERY_REPORT.md`, and is not in the account listing.

### Unknown
- Whether `demo.py` runs — **not executed** during this inventory. There are no tests.
- Whether this repository or `Publisher` is the "Test-Grounds" the other documents mean, or
  whether both were renamed from a third.

---

## SECTION 10 — EXECUTIVE SUMMARY

**What is this repository?**

`Claude`'s README consists of the single line `# Test-Grounds`, and that is the most honest
description available: it is a proving ground. Created 2026-08-08 in the same second as
`Publisher` and `Joe-Assistant`, it went quiet on 2026-08-10 and has been the longest-untouched
repository of the fourteen since. It carries the **v2** doctrine family, earlier than the v3
family that `Claude-2`, `Claude-3`, `Library` and `Jules` carry.

**What is actually implemented?**

252 lines of Python in `proposal/spine_prototype/` — a WorkItem state registry, a validation
layer, a deterministic routing table, an append-only event log, and a runnable `demo.py`. Its
own README is unusually careful about what it is not: no network, no database, no file storage,
no cognitive-function calls, no automation hook capable of an external action, not wired to real
Level 1 Transport data, and "a recommendation/proposal artifact only. No action is authorized.
Mike decides." There are no tests and no CI.

**What unique value does it contain?**

Just over half its files are unique. Its principal holding is the **third of the ecosystem's
three unrelated Spine implementations** — the others being Dispatch's SQLite-backed lifecycle
authority and Jules' in-memory consequence-level engine. This one is distinguished by a
deterministic routing table that classifies each work item as needing a cognitive function or
being purely mechanical, and by an append-only event log; neither of the other two does that.
Its `demo.py` is also the clearest compact statement in code of the three-department model —
Manager, Publisher, Intelligence — that three later repositories were built to implement.

On a branch it holds the **only independent architectural review of Manager anywhere in the
ecosystem**, in two rounds, together with `round_1_source_materials/` — an eight-document
frozen snapshot of the doctrine as it stood for that review, with its own manifest. No other
repository preserves a point-in-time doctrine snapshot; all the rest carry live copies.
