# CORRECTIONS.md

Corrections to the repository recovery inventory, recorded rather than silently applied.

`Dispatch/CLAUDE.md` §7 requires that history not be edited to hide it. The inventory's own
`CLAUDE.md` §1 sets the pattern — a wrong statement is *"Corrected here rather than quietly
overwritten."* This file follows that rule: each correction names what was originally said, what
is now known, and what established it.

---

## C-01 · "Only Joe-Assistant has been proven against a live service"

**Issued** 2026-09-05 · **Corrected** 2026-09-11

**What the inventory said.** That `Joe-Assistant` was the only repository in the ecosystem with
capabilities proven against live external services, and — in `MASTER_REPOSITORY_MATRIX.md`
finding 12 — that *"No repository has been operationally proven except `Joe-Assistant`."*

**Why it was wrong.** It was too strong. `Hold/docs/lanes/C/NOTES.md` Session 3 (2026-08-05)
records the vision extractor being exercised **live against the real Anthropic API**, a run that
found and fixed a real bug. The inventory read Hold's `main` branch and its branch *file lists*;
it did not read that lane note, which sits on the `integration` branch.

**What is now recorded.** Two repositories carry live-service proof. `Joe-Assistant` carries it
broadly, and is the only one proven against a live *Microsoft* service. `Hold` carries exactly
one such proof, with a limit its own note states plainly: the receipt image was **synthesised
with Pillow**, because *"no real scanned receipt existed in this build environment."* It is
live-API proof, not real-document proof — Hold's OCR path has never seen an actual receipt.

**How it was established.** Read directly from `docs/lanes/C/NOTES.md` on `Hold`'s `integration`
branch during the merge-risk assessment, 2026-09-11.

**Amended in.** `MASTER_CAPABILITY_MATRIX.md` · `MASTER_REPOSITORY_MATRIX.md` (findings 12–13) ·
`HOLD_DOSSIER.md` (§5 capability row, §7.11) · `JOE_ASSISTANT_DOSSIER.md` §7.2 · `README.md` ·
the findings report, both web and Word.

---

## C-02 · Hold's `integration` test count, and whether it passes

**Issued** 2026-09-05 · **Corrected** 2026-09-11

**What the inventory said.** That `Hold`'s `integration` branch held **428 test functions**, and
recorded under Unknowns: *"Whether the 428 test functions pass — not run during this inventory."*

**Why it was incomplete.** 428 was a static count of `def test_` statements. The real collected
total is higher because of parametrisation, and the suite had not been executed.

**What is now recorded.** The branch was checked out and its suite run on 2026-09-11:
**469 passed, 0 failed.** This is the only test suite actually executed across the engagement.
The Unknown is resolved, not merely restated.

**How it was established.** `python -m pytest -q` on a throwaway worktree of
`Hold/integration`, during the merge-risk assessment.

**Amended in.** `HOLD_DOSSIER.md` (§1, §3, §4, §7, §9, §10) · `MASTER_REPOSITORY_MATRIX.md` ·
`MASTER_CAPABILITY_MATRIX.md` · the findings report, both web and Word.

---

## C-03 · How far `joe-portal` has diverged

**Issued** 2026-09-05 · **Corrected** 2026-09-11

**What the inventory said.** That `Dispatch`'s `joe-portal` branch was *"48 commits ahead of
`main`"* and carried the newest work in the ecosystem.

**Why it was incomplete.** Both halves are true and, stated alone, they mislead. The branch is
also **188 commits behind `main`**, because it forked on **2026-08-03** — one day after
Dispatch's first commit. Nearly the entire freight platform (the Spine, IFTA, the connector
boundary, the Driver Portal, authentication) was built on `main` *after* this branch left.
"48 commits ahead" reads as a small, current branch. It is a month-old fork.

**What is now recorded.** 48 ahead **and 188 behind**, forked 2026-08-03. The merge cost was
then measured: 5 conflicts, two of them `add/add` on `dispatch/connectors/`, where both sides
independently built a connector registry sharing no API surface.

**How it was established.** `git merge-base`, `git rev-list --count` both directions, and a test
merge in a throwaway worktree, 2026-09-11. Full detail in `MERGE_RISK_ASSESSMENT.md` §1.

**Amended in.** `DISPATCH_DOSSIER.md` (§3, §9, §10) · `MASTER_CAPABILITY_MATRIX.md` ·
`MASTER_REPOSITORY_MATRIX.md` timeline · the findings report, both web and Word.

---

## What was *not* corrected

These stand unchanged, and are restated here so the corrections above are not read as broader
than they are:

- **692 files exist on no default branch.** Unchanged.
- **`Hold`'s `main` contains zero Python.** Unchanged.
- **`DISPATCH_FINAL_BLUEPRINT_v1.md` exists in 13 places and on no default branch.** Unchanged.
- **Manager runs as tested code in three places.** Unchanged.
- **`Route-Risk` and `SAM` are empty.** Unchanged.
- **`Dispatch/CLAUDE.md` §8 — nothing in Dispatch has ever run on Mike's laptop.** Unchanged;
  C-01 concerns `Hold`, not `Dispatch`.
- **No Dispatch test suite was run** beyond `tests/test_repository_doctrine.py` (44 passed).
  Unchanged.
