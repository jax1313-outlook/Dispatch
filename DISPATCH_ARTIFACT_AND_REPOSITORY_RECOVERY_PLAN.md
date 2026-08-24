# DISPATCH_ARTIFACT_AND_REPOSITORY_RECOVERY_PLAN

**Phase 2 deliverable — Repository and ownership audit, plus Stage 0 recovery plan**
**Audit commit:** `37f4fd033e57c55f46dfd0568d3371e8473d683f`
**Status:** Findings and recommendations. No repository was restructured by this mission.

---

## 1. The eight elements the mission named, and what each actually is

| Element the mission names | What it actually is here | Reachable from this session |
|---|---|---|
| `/app` workspace | The **Jules builder's** container, now gone. Named in a committed log line, nothing more. | **No** |
| Git local repository inside `/app` | Did not exist in this session | **No** |
| GitHub remote | `github.com/jax1313-outlook/Dispatch` | Yes |
| GitHub branches | 55 remote heads | Yes |
| GitHub `main` | `37f4fd0` | Yes |
| Mike's local `D:\SANDBOX\Jules` folder | A Windows path | **No — see §2** |
| The running legacy portal | `/home/user/Jules` @ `fe35b13` — in-memory, unauthenticated | Source yes; running instance no |
| ZIP / tar recovery artifacts | None present in the workspace | n/a |

## 2. The `D:` drive — stated plainly, as the mission requires

**This environment cannot access Mike's Windows filesystem.**

- Platform is Linux (`Linux 6.18.44`). There is no `D:` drive concept.
- `mount` shows only two non-system mounts, both read-only squashfs skill images. No `drvfs`, no
  `cifs`, no `/mnt/d`, no Windows share.
- **No file was written to `D:\Dispatch Operations`, `D:\Archive`, `D:\Memory`, or
  `D:\SANDBOX\Jules` by this session or any session whose artifacts are visible here.**

`bootstrap_d_drive.py` (added in commit `d0dfdc0`, merged in PR #115) declares those four paths as
its defaults. It is a **plausible utility that has never been proven against a real target**: its
four tests (`tests/test_bootstrap_d_drive.py`, 83 lines) exercise `copy_tree_safe` against
`tmp_path` directories. Nothing in the repository demonstrates a successful copy onto a Windows
volume, and nothing could, from Linux.

**Classification of "Mike's D: drive was updated": UNVERIFIABLE — and, as far as this workspace
shows, FALSE.** Treat `bootstrap_d_drive.py` as untested-in-target code until Mike runs it on the
Windows host and reports the result.

## 3. Dispatch repository state

```
branch   claude/dispatch-repo-context-reconcile-7mblbb  (restarted from origin/main)
HEAD     37f4fd033e57c55f46dfd0568d3371e8473d683f
status   clean — 0 modified, 0 staged, 0 untracked tracked-path entries
remote   origin  https://github.com/jax1313-outlook/Dispatch  (fetch and push)
```

- **Commits present locally and not on GitHub: 0.**
- **Commits on `origin/main` and not in the working tree: 0.**
- **Files present only locally: 0** (ignored paths excluded: `portal/data/`, `cin_lite/Archive/`,
  `__pycache__/`).
- **Files present only on GitHub: 0.**

The prior consolidation branch was fully merged as PR #111 (`748f821`). Three further merges landed
on `main` afterwards, from a different builder:

| Merge | PR | Content |
|---|---|---|
| `f898b5b` ← `8374a0f`, `2b9d3d8`, `f4da3dc` | #113 | Seven architecture documents; `dispatch/capacity.py`, `dispatch/opportunities.py`, `dispatch/truck_arrangement.py`; `tests/test_architecture_discoveries.py` |
| `b7e0611` ← `ac92424` | #114 | Dynamic Capacity hardening (`NEEDS_REVIEW` / `INSUFFICIENT_DATA` paths) |
| `37f4fd0` ← `d0dfdc0` | #115 | `bootstrap_d_drive.py`, `run_bootstrap_d_drive.bat`, `tests/test_bootstrap_d_drive.py` |

Net since `748f821`: **17 files, +1,859 / −2 lines.**

## 4. Branch hygiene — 55 remote heads

`git ls-remote --heads origin | wc -l` → **55**. The overwhelming majority are merged feature
branches that were never deleted (`claude/archive-reference-wiring`, `claude/driver-pin-registry`,
`claude/operations-feed`, `claude/stakeholder-portal`, and so on).

This is not a defect in the code, but it is a defect in **ownership legibility**: Mike cannot look
at the branch list and tell what is live. Recommended (Mike's call, not executed here): delete
merged branches, keep `main` plus any branch with unmerged commits.

## 5. The three-repository split — the central ownership problem

| Repository | Holds | Problem |
|---|---|---|
| **Dispatch** | All 22,193 lines of production code, all tests, CI | Does not contain its own constitution |
| **Claude-3** | 21 governance documents, **no code at all** | Doctrine with no implementation to bind |
| **Jules** | A **byte-identical superset** of Claude-3's 21 documents (verified with `cmp` on the Constitution, Spine Specification, Manager, Architecture and Supersession Map — all IDENTICAL; Claude-3 has no file Jules lacks) **plus** a separate, unauthenticated, in-memory Flask app | Two portals now claim to be Dispatch; Claude-3 is a strict duplicate with nothing of its own |

Concrete consequence, from code: `portal/models/identity.py:5` cites
`PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md (Claude-3 repo)`. That document is **not in
Claude-3**, and not in Jules. A reviewer following the citation finds nothing.

**Neither Claude-3 nor Jules has any automated test of the Dispatch code they claim to govern.**
Jules's single test file covers only Jules's own in-memory app.

## 6. Where the program departs from the target source-control model

Target: `working artifact → git commit → GitHub branch → pull request → review → approved merge →
local operational copy`.

| # | Departure | Evidence | Severity |
|---|---|---|---|
| D-1 | **The last link does not exist.** There is no proven path from an approved merge to Mike's machine. | §2 — no `D:` access; `bootstrap_d_drive.py` never run against a real target | **BLOCKER for ownership** |
| D-2 | **Review is not real.** PRs #113/#114/#115 merged with no human reviewer disposition recorded, and no `DECISION_LOG.md` entry — breaking the repository's own convention that every governed change gets a walkthrough report and a log entry. | `DECISION_LOG.md`'s last entry is C3 (verified by `tail`); the three post-#111 merges added seven doctrine-shaped documents and 718 lines of new engine code with no log entry and no walkthrough report | **HIGH** |
| D-3 | **Doctrine is not source-controlled with the code it governs.** | §5 | **HIGH** |
| D-4 | **A second implementation exists outside the model.** The Jules app has its own repo, its own routes, its own state model, no tests against Dispatch, no auth. | `/home/user/Jules/app.py`, `dispatch_spine.py` | **HIGH** |
| D-5 | **Operational data has no home in the model at all** — correctly so (it is gitignored), but nothing else fills the gap: no backup, no export, no restore procedure. | `.gitignore:19` `portal/data/`; no backup script in the repository | **HIGH** |
| D-6 | Branch list does not reflect live work. | §4 | MEDIUM |
| D-7 | CI proves less than it appears to: the 90 % coverage gate measures `cin_lite` only. | `.github/workflows/ci.yml` passes `--cov=cin_lite`, overriding `.coveragerc`'s `source = cin_lite, dispatch` | MEDIUM |

## 7. Stage 0 recovery plan — artifact ownership and repository recovery

These are the actions that must complete before any further build work. Each is a decision for
Mike; none were executed by this mission.

### R-0.1 Decide which portal is Dispatch
**One** of `Dispatch/portal/` and `Jules/` is the product. The other is archived. They cannot both
be maintained: they have different state models, different auth postures, and no shared tests.
**Recommendation: Dispatch/portal/.** It has the persistence, the authentication, the 26-table
schema, and 2,817 tests. Jules has the better-looking driver screen and nothing behind it.
*Authority required: Mike. Data-preservation concern: none — Jules stores nothing.*

### R-0.2 Consolidate governance into the Dispatch repository
Move the 21 documents from Claude-3/Jules into `Dispatch/governance/`, with a `SUPERSESSION_MAP.md`
that states which version is current. Locate or re-author
`PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md`, or amend the citations that reference it — **10 citations across 4 files**: `portal/models/identity.py`, `portal/app.py`, `portal/routes/auth.py`, `tests/test_portal.py`.
*Authority required: Mike. Dependency: R-0.1.*

### R-0.3 Prove the delivery path to Mike's machine
Mike runs, on Windows, in this order: `git clone` → `pip install -e .` → `cin-portal-init-admin` →
`python portal/app.py` → log in → create one load → stop the app → restart → confirm the load is
still there. Report the result. **Until this is done, "Mike owns Dispatch" is unproven.**
*Authority required: Mike executes personally. This cannot be delegated to any builder.*

### R-0.4 Establish a backup and restore procedure for `portal/data/`
The SQLite database and eleven JSON stores are the entire operational record and are deliberately
untracked. A documented copy-out/copy-in procedure, and one proven restore, are required before any
real load is entered.
*Authority required: Mike approves the procedure; a builder may write it.*

### R-0.5 Retire the branch backlog and restore the review record
Delete merged branches. Add `DECISION_LOG.md` entries for PRs #113–#115 recording what was accepted
and by whom, or mark those merges as unreviewed.
*Authority required: Mike.*

### R-0.6 Purge test residue from `portal/data/`
Six JSON files totalling ~336 KB in this workspace are test and probe output. They must not travel
to Mike's machine and be mistaken for operations. Note that `conflicts.json` holds unresolved
notices, which the Archive Review Policy classifies as protected — **deletion is Mike's call, not a
builder's.**
*Authority required: Mike.*
