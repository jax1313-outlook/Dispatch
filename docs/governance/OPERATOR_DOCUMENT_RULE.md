# OPERATOR DOCUMENT RULE

**Status:** Doctrine · **Authority:** Mike Zachary · **Stated 2026-09-06**

---

## THE RULE, AS MIKE STATED IT

> Any document explaining how to **operate, configure, start, stop, test, or validate** a software
> feature belongs in the **repository**.
>
> **Historical analysis, recovery records, research, and planning** documents belong in
> `D:\MD Files`.

**The two categories, as he set them out on 2026-09-06:**

| REPOSITORY | `D:\MD Files` |
|---|---|
| Code | Research |
| Doctrine | Forensics |
| Specifications | Recovery |
| Operator Guides | Analysis |
| Walkthroughs | Historical Records |
| | Planning |

---

## WHY

**A document that explains how to work a feature has to change when that feature changes.** In the
repository that link is a diff — the same commit touches both, and a reviewer sees it. Outside the
repository the two drift apart silently.

**This was not theoretical when the rule was written.** On 2026-09-06 the settings screen printed
`setx DISPATCH_REHEARSAL_SESSION` while the walkthrough written an hour earlier said `set, never
setx`. Following the screen would have put every future start in rehearsal mode — including
PILOT-01, whose one real load would then have been recorded as a test. **It was caught because Mike
pasted the output**, not because anything checked. Had both documents been versioned together, the
contradiction would have been visible in the diff that created it.

The reverse case is just as clear. An ecosystem forensic inventory does not change when the code
changes. Versioning it alongside the code implies a relationship that does not exist, and the
repository fills with material nobody reads.

---

## THE TEST

Ask: **if the code changed, would this document be wrong?**

- **Yes** → repository, `docs/`.
- **No** → `D:\MD Files`.

A document describing *what happened* is never made wrong by a later commit. A document describing
*what to type* is.

---

## WHERE THINGS LIVE

**In the repository**

| | |
|---|---|
| `docs/operations/` | How to operate the software — `DISPATCH_OPERATOR_GUIDE.md`, `GET_DISPATCH_ONTO_YOUR_LAPTOP.md`, `MIKE_WALKTHROUGH.md`, `MIKE_REHEARSAL_MODE.md` |
| `docs/readiness/` | How to prove it works — proof templates, `KNOWN_LIMITATIONS.md`, launch path |
| `docs/governance/` | The rules, including this one |
| `docs/` | Doctrine and specifications |

**In `D:\MD Files`**

Ecosystem inventories and matrices · recovery findings and corrections · the roadmap and plan index ·
decision briefs · email and design analysis · the current-state summary.

**In `D:\AAA-Dispatch-Screen-Build`**

The tab walk working area. Never in git — Mike's narrations, observations and decisions, backed up to
the vault instead. The finished `<TAB>.md` for each screen crosses into the repository when that tab
is done.

---

## APPLIED 2026-09-06

**Moved into `docs/operations/`:** `MIKE_WALKTHROUGH.md` (the acceptance items) and
`MIKE_REHEARSAL_MODE.md` (turning rehearsal mode on and off).

**Pointer stubs left in `D:\MD Files`** so a remembered path still leads somewhere. Nothing deleted.

**Reviewed and left in `D:\MD Files`:** all 24 remaining documents. `MIKE_ACTION_LIST.md` was the
only close call — it tells Mike what to do, but what it holds are *decisions and authorizations*,
not instructions for operating a feature. A code change does not make it wrong. It stays, and points
at the walkthrough for the parts that are operator steps.

## APPLIED IN REVERSE, 2026-09-06

The rule cuts both ways, and had only been run one direction. All 57 repository documents were
checked against the `MD Files` categories. **Six fitted them. Mike moved two.**

**Moved out to `D:\MD Files`:**

| Was | Now | Why |
|---|---|---|
| `docs/readiness/RECON.md` | `RECON_2026-08-24.md` | Reconnaissance from 2026-08-24 against a branch that no longer leads the work. **Referenced by nothing** |
| `docs/readiness/STATUS_2026-08-26.md` | `STATUS_2026-08-26.md` | A dated status report, and stale — it says zero loads and the database has held loads since |

Both carry a banner recording where they came from and why. Nothing was altered below it.

**Two citations were repointed, and they were wrong in substance, not only in path.** `CLAUDE.md`
and `DISPATCH_ARCHITECTURE.md` both described `STATUS_2026-08-26.md` as *"where things stand
today"* — of a document eleven days stale. Both now point at
`D:\MD Files\DISPATCH_CURRENT_STATE.md`. **That is the argument for the rule in one example:** a status
record kept beside the code gets cited as if it were current, and nothing in a repository makes a
date go stale loudly.

**Left in place, with reasons:**

| Document | Why it stays |
|---|---|
| `DISPATCH_GOLD_RECOVERY_FINDINGS.md` · `DISPATCH_COMPONENT_RECOVERY_REGISTER.md` · `DISPATCH_SCORING_LINEAGE_AND_RECOVERY.md` | They read as forensics, but they are cited **as the reasoning behind current specifications** — closer to specification support than to history. `SCORING_LINEAGE` alone is cited by six repository documents |
| `readiness/COMPLETION_REPORT.md` | Referenced by `tests/test_repository_doctrine.py`. Moving it breaks a test, which makes it a code change rather than a filing change. **Decide it on its own** |
| `DISPATCH_POLICY_FOUNDATION_PR_SUMMARY.md` | Genuinely borderline. The name says historical, the content calls itself a specification package. The **title** is the misleading part — one for the rename mission |

---

---

## A NOTE FOR THE RENAME MISSION

`MIKE_WALKTHROUGH.md` and `MIKE_REHEARSAL_MODE.md` are named for one operator. Dispatch is being
built for owner-operators plural, and a customer opening `docs/operations/` should not find a
document named after someone else.

**Not renamed now** — no renaming in passing until the tab walk is finished. Logged in the name
register.
