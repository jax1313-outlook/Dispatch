# Repository Recovery Inventory — 2026-09-05

**Authority: Mike Zachary.** Recovery and inventory operation only. Nothing in this directory
is a design proposal, a feature review, a refactor proposal, an archive recommendation, or a
judgement about what is important.

All fourteen repositories in the `jax1313-outlook` account were inventoried. None was skipped;
none was combined with another. Each has its own dossier with identical sections 1–10.

## Read in this order

1. **`MASTER_CAPABILITY_MATRIX.md`** — the final deliverable. Answers one question:
   *"What has actually been built?"* Every capability, its repository, its evidence, its
   status, its primary location.
2. **`MASTER_REPOSITORY_MATRIX.md`** — one row per repository: purpose, status, unique assets,
   capabilities, active/historical, cross references. Plus ecosystem totals, a timeline, and
   twelve findings that span repositories.
3. **The fourteen dossiers**, below.

## Dossiers

| Dossier | Repository | Shape |
|---|---|---|
| `DISPATCH_DOSSIER.md` | Dispatch | 459 files · 82,699 py LOC · 64 branches · 245 files off-`main` |
| `JOE_ASSISTANT_DOSSIER.md` | Joe-Assistant | 342 files · 34,000 py LOC · the only PROVEN capabilities |
| `HOLD_DOSSIER.md` | Hold | `main` 0 py LOC · `integration` 13,770 py LOC · never merged |
| `DISPATCH_OLD_DOSSIER.md` | Dispatch-Old | 3,906 py LOC · the only merged Manager · the only hosting config |
| `L2_INTELLIGENCE_AGENT_DOSSIER.md` | L2-intelligence-agent. | 2,006 py LOC · Intelligence department · private |
| `LIBRARY_DOSSIER.md` | Library | 875 py LOC · Library department |
| `PUBLISHER_DOSSIER.md` | Publisher | 872 py LOC · Publisher department |
| `CLAUDE_3_DOSSIER.md` | Claude-3 | docs only on `main` · 87 files on branches · prior recovery mission |
| `JULES_DOSSIER.md` | Jules | 717 py LOC · four-portal presentation layer |
| `CLAUDE_DOSSIER.md` | Claude | 252 py LOC · Spine prototype · Manager independent review |
| `CLAUDE_2_DOSSIER.md` | Claude-2 | 17 documents · no code · 3 h 39 min lifespan |
| `PREMIUM_LOGISTICS_PLATFORM_DOSSIER.md` | premium-logistics-platform- | 3 files · the only brand material |
| `ROUTE_RISK_DOSSIER.md` | Route-Risk | **empty** — 0 commits, 0 branches, 0 files |
| `SAM_DOSSIER.md` | SAM | **empty** — 0 commits, 0 branches, 0 files |

## Method

- Every repository cloned and read. `Jules`, `Route-Risk` and `SAM` were not attached to the
  session at start; they were added and cloned read-only.
- **Uniqueness** established by hashing every tracked file in all twelve non-empty
  repositories by git blob ID and comparing across repositories — 1,218 files compared.
- **Off-branch work** established by comparing every branch of every repository file-by-file
  against its default branch — 117 branches, 692 files found that exist on no default branch.
- **Cross-repository references** established by counting matching lines per term per repository.

## Two standing caveats

1. **No test suite was run.** Every test count in these documents is a static count of
   `def test_` functions. It is evidence that tests exist, not that they pass.
2. **`Dispatch/CLAUDE.md` §6: the repository test suite is evidence of software behaviour only.
   It is never operational proof.** The only capabilities recorded as PROVEN anywhere in this
   inventory are JOE's, measured on 2026-08-26 by running the program against live services.

## Where this lives

These documents are in `Dispatch` because `Dispatch/CLAUDE.md` §1 records Dispatch as the
**System of Record** for the ecosystem. They describe all fourteen repositories; no copy was
placed in the other thirteen.
