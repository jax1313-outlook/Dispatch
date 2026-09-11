# MERGE_RISK_ASSESSMENT.md

Authority: Mike Zachary. Assessed 2026-09-11.
Targets: the three bodies of unmerged work identified in `MASTER_CAPABILITY_MATRIX.md`.

**Assessment only.** Every merge below was performed in a throwaway worktree and abandoned.
Nothing was merged, committed to any target branch, or pushed. No recommendation is made about
whether to merge; this measures what would happen if you did, and what it would cost.

---

## Summary

| Target | Mechanical risk | Doctrinal risk | Verified state | Character of the problem |
|---|---|---|---|---|
| `Dispatch` → `joe-portal` | **HIGH** — 5 conflicts, 2 of them `add/add` on the connector boundary | **HIGH** — a naive resolution deletes the connector audit trail and un-registers authentication | Tests not run (suite needs main's fixtures) | **Not a merge. A reconciliation.** Two independent designs for the same governed boundary |
| `Hold` → `integration` | **NONE** — clean fast-forward, 0 conflicts, 0 deletions | **LOW** | **469 tests passed, 0 failed** — run for this assessment | The code is sound. The risk sits entirely outside git |
| `DISPATCH_FINAL_BLUEPRINT_v1.md` | **NONE** — a new file, nothing to conflict with | **HIGH** — mandates a Manager component that `CLAUDE.md` §5.6 forbids | n/a | A stale draft that contradicts settled doctrine |

The three are not variations of one problem. They need three different decisions.

---

## 1. `Dispatch` ← `joe-portal`

### Measured

| | |
|---|---|
| Merge base | `62af426`, **2026-08-03 11:52** |
| `main` HEAD | `3c03ab2`, 2026-08-31 |
| `joe-portal` HEAD | `02b0e75`, 2026-09-03 |
| Commits ahead of main | **48** |
| **Commits behind main** | **188** |
| Files changed on both sides | 9 |
| **Merge conflicts** | **5** (2 × `add/add`, 3 × content) |
| Test files | 96 on branch vs 136 on main |
| Test files deleted by the branch | **0** |

**The framing in the inventory was incomplete, and this correction matters.** `joe-portal` is not
48 commits of new work sitting on top of current `main`. It forked on **2026-08-03**, one day
after Dispatch's first commit, and is **188 commits behind**. Almost the entire freight platform
— the Spine, IFTA, the connector boundary, the Driver Portal, authentication — was built on
`main` *after* this branch left.

### The conflicts

```
CONFLICT (add/add)  dispatch/connectors/__init__.py
CONFLICT (add/add)  dispatch/connectors/registry.py
CONFLICT (content)  portal/models/publisher.py
CONFLICT (content)  portal/routes/__init__.py
CONFLICT (content)  portal/templates/base.html
```

### Why the connector conflict is not a normal conflict

Both sides independently built `dispatch/connectors/` — hence `add/add`. They share **no API
surface whatsoever**:

| | `main` | `joe-portal` |
|---|---|---|
| Files | 14 (`contract.py`, `boundary.py`, `audit.py`, `mock.py`, + 8 provider connectors) | 3 (`__init__`, `registry`, `outlook_mail`) |
| `registry.py` | 115 lines | 63 lines |
| API | `get(connector_id)`, `all_connectors()`, `status_board()`, `UnknownConnector` | `mail()`, `mail_status()`, `calendar_status()`, `status()` |
| Audit trail | `audit.py` — "one row for every attempt, including the refusals" (§6.8) | none |
| Fixed contract | `contract.py` + `boundary.py` | none |
| Design | registry of declared connectors, governed | probe-on-demand, never caches a `LIVE` |

Both honour the fixed truth vocabulary. Both are defensible designs. They are not compatible.

**Neither side calls the other's API.** Verified: no occurrence of `registry.get` /
`all_connectors` / `status_board` anywhere on the branch; no occurrence of `registry.mail` /
`mail_status` / `calendar_status` anywhere on main. So:

- **Keep `main`'s registry** → four branch call sites break immediately
  (`portal/cockpit.py:533`, `portal/routes/joe_api.py:423`, `portal/routes/joe_portal.py:545`,
  plus `tests/test_outlook_connectors.py`).
- **Keep the branch's registry** → deletes `contract.py`, `boundary.py`, `audit.py`, `mock.py`
  and all 8 provider connectors. That is a direct violation of `CLAUDE.md` §5.4 (*"a governed
  boundary with a fixed contract, an audit trail, and an honest status"*) and §7 (*never weaken*).

There is no correct side to take. The branch's `outlook_mail.py` — the ecosystem's only
Dispatch-side Outlook *implementation* — would have to be rewritten against main's connector
contract.

### The second trap

`portal/routes/__init__.py` on the branch registers: `pages`, `api`, `decisions`, `pipeline`,
`dispatch_api`, `joe_bp`, `joe_api`.

It does **not** register `auth_bp`, `driver_portal_bp` or `stakeholder_bp` — because they did
not exist when it forked. Taking the branch side of this file would silently remove
**login/logout, the Driver Portal and the stakeholder view** from the application. Under
`CLAUDE.md` §7 that is weakening fail-closed authentication.

This one is easy to resolve correctly (keep main's registrations, add joe's two). It is recorded
because it is exactly the kind of conflict a hurried resolution gets wrong, and the failure is
silent.

### What is not at risk

- The branch **deletes no tests**. The 59 main test files absent from it were added after the
  fork; a merge keeps them.
- **No Manager code** on the branch (`dispatch/manager/` is empty there).
- `dispatch/services.py`, `portal/models/sandbox.py`, `portal/routes/api.py` and
  `tests/test_booking.py` auto-merged cleanly.

### Character

This is a **reconciliation of two parallel architectures**, not a merge. The valuable content —
Driver Cockpit, mission and scheduling engines, booking board, arrival notices, the Outlook
implementation, 19 test files — is real. Landing it means deciding which connector design
governs, then porting one side onto the other.

**Unknown:** whether the branch's tests pass. They were not run — the branch's suite is 96 files
against main's 136, and the two expect different connector APIs, so a meaningful run requires
the reconciliation decision first.

---

## 2. `Hold` ← `integration`

### Measured

| | |
|---|---|
| Merge base | `484e40d` — **which is `main` HEAD** |
| Commits ahead | **75** |
| Commits behind | **0** |
| Files changed on both sides | **0** |
| Merge conflicts | **0** — `main` is a direct ancestor; this is a **fast-forward** |
| Change profile | 199 added · 7 modified · 14 renamed · **0 deleted** |
| Diff | 220 files, **+22,113** insertions, −59 deletions |

The 7 modified files are all documentation and schemas (`CONTRACT_REGISTER.md`,
`evidence_record.schema.json`, `DECISION_LOG.md`, four lane `NOTES.md`). Nothing is destroyed.

### Verified by running it

The integration branch was checked out and its suite executed:

```
469 passed in 7.16s
```

**0 failed, 0 errors.** This is the only test suite actually executed across this engagement,
and it passes clean. (Note: the inventory's static count of 428 `def test_` under-counts the
real total of 469, because of parametrisation.)

### Security check

- **No committed secrets.** Scanned for `sk-ant-` patterns, `api_key = "..."` literals, `.env`,
  credential and `.key` files across the branch. Nothing found.
- `docs/lanes/C/NOTES.md` records the practice explicitly: a real API key was supplied
  in-session, *"never written to any file (not the sandbox config, not `.env`, nothing
  committed) — used only as a transient environment variable… then discarded."* The scan
  corroborates that.

### One correction to the earlier inventory

The inventory reported that **only Joe-Assistant** had capabilities proven against a live
external service. That is not quite right. `Hold/docs/lanes/C/NOTES.md` Session 3 (2026-08-05)
records the vision extractor being **exercised live against the real Anthropic API**, which found
and fixed a real bug.

The precise limit matters: the image was **synthesised with Pillow**, because *"no real scanned
receipt existed in this build environment."* So it is live-API proof, not real-document proof.
Hold's OCR path has never seen an actual receipt.

### Character

**The mechanical risk is zero and the code is verified green.** The risk is entirely outside git,
and it is governance, not engineering:

- `Hold/README.md` states the repository is *"Sandbox configuration only, until Mike Zachary cuts
  over after merge 5,"* and that it is **not** the system of record.
- `docs/governance/APPROVAL_REGISTER.md` holds 14 approval items whose state this assessment did
  not evaluate.
- Merging `integration` → `Hold/main` is a different act from promoting Hold's code into
  `Dispatch`. The second is where the real architectural question sits — Hold's
  `src/dispatch/` tree is a **separate implementation** from Dispatch's `dispatch/` package, with
  its own IFTA engine alongside the one already in Dispatch.

**Unknown:** whether "merge 5" has occurred, and what the 14 approval items currently say.
Neither is recorded anywhere this assessment could reach.

---

## 3. `DISPATCH_FINAL_BLUEPRINT_v1.md`

### Measured

| | |
|---|---|
| Size | 1,133 lines, blob `ffb23f9` |
| Locations | 13, across 4 repositories; **0 default branches** |
| Branch tip | 2026-08-11 |
| Mechanical conflict | **None** — a new file; nothing to collide with |
| Would it break CI? | **No.** `tests/test_repository_doctrine.py` scans `*.py` and `portal/*.html` only |

### The actual risk

The Blueprint contains a full **"## 5. Manager Blueprint"** section — 45 Manager mentions,
including §5.9 and mandates such as *"Manager must never: approve on Mike's behalf…"*. It carries
**no disclaimer** that Manager was never built.

`Dispatch/CLAUDE.md` §5.6 states:

> **There is no Manager component in the current architecture. Do not create, restore,
> reference, or infer a Manager component, Manager agent, or Manager authority.**

Landing this document in Dispatch as-is introduces a governing artefact that mandates a component
current doctrine forbids. It would not fail a test — which makes it more dangerous, not less,
because nothing mechanical would catch it.

### It is also stale

Dated 2026-08-11, it predates at least these settled decisions in `DECISION_LOG.md`:

- **2026-08-21** — Build Matrix adopted; architectural adjudication (Spine ownership partitions,
  state models, load identity, Driver-First)
- **2026-08-21** — C3 status-change audit symmetry
- **2026-08-23** — W0-3 Portal adjudication; **CF-04** (*Opportunity advises; the Spine decides*)
- **2026-08-25** — **General Contractor Doctrine**

Its own header calls it a *"Final Blueprint Draft"* and states it *"does not authorize
deployment."*

### Character

Not a merge problem — a **doctrine-conflict problem**. `CLAUDE.md` §7 already prescribes the
handling: *"If code conflicts with approved doctrine, report the conflict"* and *"Do not edit old
decisions to hide their history. Mark them `SUPERSEDED` and cite the ruling that replaced them."*
This assessment reports it. What happens next is Mike's call.

Note that three repositories — `L2-intelligence-agent.`, `Library`, `Publisher` — were built
while recording this document as *"not found in any repo in scope."* Whatever is decided, those
three were built without their stated governing blueprint.

---

## What this assessment did not do

- **Did not merge anything.** All test merges ran in throwaway worktrees and were abandoned;
  nothing was committed to a target branch or pushed.
- **Did not run `joe-portal`'s tests.** A meaningful run requires the connector reconciliation
  decision first.
- **Did not run Dispatch's full suite.** Only `tests/test_repository_doctrine.py` (44 passed),
  earlier in this engagement.
- **Did not read the 14 approval items** in `Hold/docs/governance/APPROVAL_REGISTER.md`.
- **Did not assess the remaining 692-file off-main population** beyond these three targets.
- **Makes no recommendation.** Mike decides.
