# D: Drive Consolidation Roadmap

**Purpose:** bring the Dispatch program files scattered across Mike's local `D:` drive into
one canonical place, and from there into `jax1313-outlook/Dispatch`.

**Date:** 2026-09-04 · **Status:** Proposed. **No phase is authorized.**
**Hierarchy level:** 4 (Roadmap). Subordinate to the Dispatch Constitution, to approved
Decision Logs, and to architecture specifications. Where this document and any of those
conflict, this document is wrong.

---

## 0. What this document is, and what it is not

**I have never seen the `D:` drive.** No session has. It is a Windows path on Mike's
machine, unreachable from the Linux container every builder runs in. Any file list,
duplicate count or size estimate I produced would be invention, and invention about that
machine has already cost this program a full day.

**So this is a procedure for finding out, not an inventory.** Phase 1 is the discovery
step, and every phase after it is written against results that do not exist yet. The
numbers, names and decisions come from running it.

**One thing is already true and worth stating before anything else:** the tool for this job
already exists in this repository, is read-only by construction, and **has never been run.**
See §2.

---

## 1. What is actually known about `D:`

Everything below came from the launcher's own status output on Mike's machine on
2026-08-29, or from a mission statement he wrote. Nothing is inferred.

| Path | What it is | Source |
|---|---|---|
| `D:\Dispatch Operations\Current Workspace\PortalData` | Live database, PIN, sandbox JSON | launcher `status` |
| `D:\Dispatch Operations\Logs` | Runtime logs | launcher `status` |
| `D:\Archive` | `DISPATCH_ARCHIVE_ROOT` | launcher `status` |
| `D:\Archive\CIN` | Contract archive | launcher `status` |
| `D:\Memory` | `DISPATCH_MEMORY_ROOT` | launcher `status` |
| `D:\Sandbox` | Working material | **Mike, 2026-09-04** |
| `D:\Joe Assistant` | Working copy of the Joe repository | **Mike, 2026-09-04** |

**Two corrections from Mike, 2026-09-04, and one of them breaks a default in the tool.**

- The Joe working copy is **`D:\Joe Assistant`** — a space, not a hyphen. Every earlier
  document in this repository, including the Architecture Correction Directive and the gap
  analysis, writes it as `D:\Joe-Assistant`. Those are wrong.
- The sandbox root is **`D:\Sandbox`**, not `D:\Sandbox\Play Pen`.
  **`scripts/sandbox_survey.py:44` hard-codes `DEFAULT_SANDBOX_ROOT = r"D:\Sandbox\Play Pen"`.**
  Running the survey with no `--sandbox-root` would therefore point at a subfolder, or at a
  path that no longer exists, and report on the wrong scope while looking like it worked.
  **Always pass `--sandbox-root` explicitly** until that default is corrected — it is a
  one-line change and should be made before Phase 1b.

*(Read as `Sandbox`; Mike typed `Sanbox`. Path spelling is exact on Windows — if the folder
is genuinely spelled without the `d`, say so, because the survey will simply refuse a root
that does not resolve.)*

**That is the whole of what is known.** Whether these are all of it, whether they overlap,
what is inside any of them, and how much duplicates what is already in Git — all `UNKNOWN`.

The code lives at `C:\Dispatch\Dispatch2\Dispatch-main` and is an **extracted ZIP, not a git
checkout** — the launcher reports `Commit UNVERIFIED — this folder is not a git checkout`.
That matters in Phase 6.

---

## 2. The tool already exists

`dispatch/sandbox_survey/` — 1,975 lines across eight modules, with `scripts/sandbox_survey.py`
as the entry point and `docs/readiness/SANDBOX_SURVEY_PROCEDURE.md` as the written procedure.
It was built for exactly this and has never been pointed at a real folder.

**Its safety guarantee is structural rather than promised** (`safety.py`):

- **One writer, one root.** Nothing in the package writes to disk except
  `OutputWriter.write_text`, which refuses — by raising — any path outside the resolved
  output root.
- **Exclusive creation, never truncation.** The only file modes in the package are `"x"`
  and `"rb"`. No `"w"`, no `"a"`, no `"r+"`. No rename, move, merge or delete path exists —
  not behind a flag, not behind a prompt.
- **`tests/test_sandbox_survey.py` asserts this by parsing the package's own source**, so
  the guarantee breaks only if someone deletes a test that is watching.

**What one run emits**, timestamped so a second run can never overwrite a first:

`SANDBOX_FILE_INVENTORY` (csv + md) · `SANDBOX_KNOWLEDGE_MAP` ·
`DISPATCH_RESEARCH_CANDIDATES` · `POSSIBLE_DUPLICATES` ·
`GOVERNANCE_AND_DOCTRINE_CANDIDATES` · `MIKE_DECISION_CANDIDATES` ·
`SENSITIVE_MATERIAL_REPORT` · `PROPOSED_FOLDER_STRUCTURE` ·
`PROPOSED_ORGANIZATION_ACTIONS` · `sandbox_survey.json`

**`PROPOSED_ORGANIZATION_ACTIONS` is a proposal the tool cannot execute.** It has no code
path that could.

---

## 3. Standing rules this operation runs under

These are Mike's, already in force, and they constrain every phase below.

**On the Sandbox, verbatim:**

> The first pass is read-only. Under no circumstances may any file in the Sandbox be moved,
> renamed, deleted, overwritten, deduplicated, converted, archived, uploaded, committed to
> Git, or treated as accepted doctrine. Open files read-only. Do not execute any script,
> notebook, or binary found in the Sandbox. Do not follow links or fetch external resources
> referenced in Sandbox files.

> For sensitive material, record the path and category only — never copy contents into any
> report.

**On what may never reach Git** (`CLAUDE.md` §7): runtime secrets, logs containing secrets,
rehearsal databases, evidence files, backups.

**Therefore, before any phase runs, four of the seven known roots are excluded from Git by
rule, not by judgement:**

| Path | Disposition | Why |
|---|---|---|
| `D:\Dispatch Operations\Current Workspace\PortalData` | **NEVER to Git** | Live database, PIN hash, operational data |
| `D:\Dispatch Operations\Logs` | **NEVER to Git** | Runtime logs; may contain secrets |
| `D:\Archive`, `D:\Archive\CIN` | **NEVER to Git** | Evidence store |
| `D:\Memory` | **NEVER to Git** | Evidence and library store |

They still get surveyed — knowing what is in them matters — but the survey output about
them is a catalogue, not a migration list. **Backing them up is a separate job with its own
tooling** (`scripts/dispatch_backup.py`), and it is not this roadmap.

**What is actually in scope for Git:** `D:\Sandbox`, `D:\Joe Assistant`, and
anything the survey finds that is source, specification, doctrine or documentation.

---

## Phase 1 — Discover

**Nothing moves. Nothing is decided. The drive is only read.**

**1a — Dry run, one root at a time.**

```
python scripts\sandbox_survey.py --sandbox-root "D:\Sandbox" --dry-run
```

Dry run creates no folder and writes no file. It prints what it would produce. **Run this
first on every root**, and read the output before running anything for real.

**1b — Real run, same roots.** Drop `--dry-run`. The tool creates exactly one folder —
`<root>\Dispatch` — and writes its reports there. That folder is the only structural change
this phase makes anywhere.

**1c — Repeat for each root**, including the four excluded ones. A catalogue of what is in
the evidence stores is worth having even though none of it is going to Git.

**1d — Copy the report folders off the drive** and attach them here. They are the input to
every phase that follows. **They contain paths and categories, never file contents** — the
sensitive-material rule is enforced by the tool, not by the person running it.

**Exit criterion:** one `SANDBOX_FILE_INVENTORY` per root, and a `POSSIBLE_DUPLICATES`
report that says how much of this is the same thing several times.

**Builder:** Mike runs it. **Nobody else can** — the drive is on his machine.

---

## Phase 2 — Adjudicate

**Reading the reports, deciding what each thing is. Still nothing moved.**

The survey sorts files into candidate piles. Every pile needs a ruling, and the rulings are
Mike's:

| Report | The question it asks |
|---|---|
| `GOVERNANCE_AND_DOCTRINE_CANDIDATES` | Is this doctrine? If so, does it agree with the Constitution? |
| `MIKE_DECISION_CANDIDATES` | Does this record a decision that should be in `DECISION_LOG.md`? |
| `DISPATCH_RESEARCH_CANDIDATES` | Is this research worth keeping, or is it working-out? |
| `POSSIBLE_DUPLICATES` | Which copy is canonical? |
| `SENSITIVE_MATERIAL_REPORT` | Does this need to stay off Git entirely? |

**The Conflict Rule applies throughout.** Any document found on `D:` that contradicts the
Dispatch Constitution is reported — statement, document, location, impact — and not
reconciled by a builder.

**Expect the constitution question to surface here.** Eleven constitution documents exist
across the reachable repositories already; `D:` may hold more. **Which document is the
Dispatch Constitution is currently unresolved** (`DECISION_LOG.md` 2026-09-04) and this
phase will make that worse before it makes it better, because it will find more candidates.

**Exit criterion:** every file in the inventory carries a disposition — **keep · supersede ·
historical · never-to-Git · discard**. No file is unclassified.

**Builder:** Mike decides. Claude Code can draft the classification and explain each
proposal.

---

## Phase 3 — Reconcile against what is already in Git

**Before anything is staged, find out how much of it is already here.**

Dispatch already holds 431 tracked files, 89 of them Markdown. Jules holds 41. Claude-3
holds 29. Joe-Assistant holds 342. **Much of what is on `D:` is likely a copy of something
already in one of them** — that is how the drive came to look like this.

For each file marked *keep* in Phase 2:

1. Does a file of that name already exist in Dispatch? Compare content, not name.
2. If it exists and differs — **which is newer, and which is right?** Those are different
   questions and the answer to the second one is Mike's.
3. If it exists identically — the `D:` copy is a duplicate. Nothing to migrate.
4. If it does not exist — it is a genuine candidate for the repository.

**Do not skip step 2 by taking the newer file.** The gap analysis found a governing ruling
living on an unmerged branch inside a section marked NOT AUTHORITATIVE. Recency is not
authority.

**Exit criterion:** a list of files that exist **only** on `D:` and are wanted in Git —
which is the actual migration set, and will be far smaller than the inventory.

---

## Phase 4 — Stage

**A clean staging folder, not the live workspace.**

Copy the migration set into a fresh folder — `D:\Dispatch Staging` or similar — leaving the
originals untouched. This is the first phase in which anything is copied, and it copies
**out of** the Sandbox rather than moving anything within it, which keeps the read-only rule
intact.

Two reasons the staging folder is separate:

- **The originals stay put until the migration is proven.** If something goes wrong at
  Phase 6, nothing has been lost.
- **A staging folder can be inspected as a unit** before it becomes a commit.

**Exit criterion:** a folder containing exactly the files intended for the repository, in the
structure they will occupy, and nothing else.

---

## Phase 5 — Structure

**Decide where each file lands, using the layout the repository already has.**

Dispatch's existing structure is the answer to most of this and should not be reinvented:

| Kind | Destination |
|---|---|
| Doctrine, constitutions, authority documents | `docs/governance/` |
| Architecture and specifications | `docs/architecture/` |
| Operational procedure | `docs/operations/` |
| Readiness, status, proof | `docs/readiness/` |
| Decisions | appended to `DECISION_LOG.md`, never a new log |
| Source code | the module it belongs to |
| Historical material | kept, marked `SUPERSEDED`, **never deleted** |

**The rule against editing history applies to imports too.** A document arriving from `D:`
that supersedes one already in the repository does not replace it — the old one is marked
and the new one cites it.

**Exit criterion:** `PROPOSED_FOLDER_STRUCTURE` reconciled with the repository's real layout,
and every staged file assigned a destination path.

---

## Phase 6 — Land

**One branch, one pull request, reviewed as a unit.**

1. **Make Mike's Dispatch folder a real git checkout first.** It is currently an extracted
   ZIP, which is why the launcher reports `Commit UNVERIFIED` and why three copies of
   Dispatch once existed. A ZIP cannot be updated — only replaced. **This is a prerequisite,
   not a nice-to-have**, and it is the fix for gap G-40.
2. Branch from current `main`.
3. Commit the staged files in coherent groups — doctrine separately from source, and each
   group with a message that says where the files came from and why they were kept.
4. Open one pull request. **Do not squash the groups**; a reviewer needs to see doctrine
   arriving separately from code.
5. Full suite green before merge: 0 failed / 0 skipped / 0 warnings.

**Exit criterion:** merged, and the `D:` originals still untouched.

---

## Phase 7 — Steady state, so this does not happen again

**The consolidation is worthless if the drive refills.**

1. **One canonical location per kind of thing.** Dispatch is canonical for Dispatch doctrine
   and code. Joe-Assistant is canonical for Assistant doctrine. `D:` holds runtime data —
   database, logs, archive, memory — and **nothing that belongs in Git**.
2. **Working copies carry pointers, not doctrine.** The pattern already works: Jules and
   Claude-3 each carry `DISPATCH_IMPLEMENTATION_STATUS.md` naming the repository, path and
   commit it was written against. Staleness becomes visible instead of silent.
3. **The `D:\Joe Assistant` working copy is the specific risk.** A fourth maintained copy of
   doctrine with no stated precedence is the mechanism that produced this drive's current
   state — it is structurally the same as the three-copies-of-Dispatch failure that cost
   seven hours. Either it becomes a git checkout that can be pulled, or it stops holding
   doctrine.
4. **Re-run the survey quarterly.** It is read-only and cheap. A drive that has quietly
   refilled is worth knowing about before it becomes a day.

---

## What could go wrong, and what to do about it

| Risk | Mitigation |
|---|---|
| **A secret reaches Git** | The exclusion table in §3 is by rule, not judgement. `SENSITIVE_MATERIAL_REPORT` is read before Phase 4, and Phase 4 copies an explicit list rather than a folder. |
| **The live database is disturbed** | `PortalData` is surveyed and never staged. **Stop Dispatch before surveying it** — a survey reading a database mid-write gets a torn read, and WAL means the file on disk is not the whole story. |
| **A duplicate is landed as new** | Phase 3 exists for this and must not be skipped. |
| **A superseded document overwrites a current one** | Phase 5's rule: mark, cite, never replace. |
| **The originals are lost** | Nothing is moved or deleted at any phase. Phase 4 copies. |
| **A found document contradicts the Constitution and gets silently reconciled** | Conflict Rule: report the four fields, do not resolve. |
| **The drive is disconnected mid-run** | `D:` is external. The survey writes only at the end of a run and refuses to overwrite; a lost drive means an incomplete run, not a corrupted one. Re-run. |

---

## What this needs from Mike, before Phase 1

1. **Are the seven roots in §1 the whole of it?** If there are other folders on `D:` holding
   Dispatch material, name them — the survey only looks where it is pointed.
2. **Correct the survey's hard-coded default** before Phase 1b —
   `scripts/sandbox_survey.py:44` still says `D:\Sandbox\Play Pen`. One line.
3. **Which document is the Dispatch Constitution?** Still unresolved, and Phase 2 will find
   more candidates rather than fewer.
4. **May Phase 1 run at all?** It is read-only and structurally incapable of modifying its
   input — but it is his drive, and the standing rule says the first pass is read-only, not
   that it is authorized.

---

## Honest assessment of scale

**Unknown, and I am not going to estimate it.** The inventory does not exist. What can be
said:

- **Phase 1 is hours, not days**, and most of that is the drive reading.
- **Phase 2 is the expensive one**, because it is judgement and it is Mike's, and the
  duplicate count will decide whether that is an afternoon or a week.
- **Phases 3–6 scale with what survives Phase 2**, which is usually a small fraction of what
  goes in.

**The single most useful thing that could happen next is Phase 1a** — one dry run, one root,
read-only, no commitment. It converts every `UNKNOWN` in this document into a number.

---

*Nothing in this document is accepted doctrine or a Mike decision. No phase is authorized.
Where this roadmap and the Dispatch Constitution conflict, the Constitution wins.*
