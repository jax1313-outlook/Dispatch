# DISPATCH AGGRESSIVE BUILD SEQUENCE

Status: RECOMMENDATION. A proposed order of work. Nothing here is implemented.

---

## 1. The rule that sets the order

**Build the thing that makes the next thing safe to build.**

Not the most visible thing, not the easiest thing. The lineage shows what happens
otherwise: GOLD built an excellent workflow on top of an evaluation model that had
already lost its veto, and the workflow could not tell that anything was wrong.

## 2. Sequence

### Stage 0 — Foundation (Lane B specifications)

**Status: this PR.** Specifications only, no code.

Produces the policy profile, evaluation engine, decision matrix, filter/score/sort,
recommendation, confidence and override specifications.

Exit condition: Mike has read them and the open questions in
`DISPATCH_POLICY_FOUNDATION_PR_SUMMARY.md` are answered.

---

### Stage 1 — The policy profile

**First code. Nothing else can be built correctly before it.**

- Profile schema, loader, validator, defaults
- Profile versioning, stamped onto evaluations
- Migrate the hard-coded constants out of `dispatch/scoring.py` into the profile

Exit condition: every business threshold in Dispatch is editable in one file, and a
malformed profile fails loudly rather than partially applying.

Why first: every later stage needs somewhere to put its thresholds. Building evaluation
first means hard-coding twice.

---

### Stage 2 — Blocking conditions

**The single most consequential recovery.**

- Severity ladder: BLOCKING / WARNING / INFORMATIONAL / UNKNOWN
- Blocking evaluated **before** any band, and unable to be outvoted by points
- The blocking catalogue, from the profile — not from code
- Override path, with the override recorded

Exit condition: a load with a hard stop cannot classify as anything but disqualified,
regardless of score, and the operator can see exactly which condition fired.

Why second: today `hard_stop` costs 5 points out of 100. Everything built on top of
scoring inherits that defect until it is fixed.

---

### Stage 3 — Stage separation

- A real FILTER stage — currently there is none
- SCORE stops carrying recommendation words
- A SORT stage that cannot alter score
- Dimensions preserved separately, not collapsed

Exit condition: the five stages exist as five things, each testable alone.

---

### Stage 4 — Dimensions

- Tiered territory with status and reason (from v1.3.3)
- Growth potential, return position value
- Information completeness
- Keep the existing driver-legible dimensions — they are good and they already work

Exit condition: an evaluation returns the full dimension set from the mission brief, with
reasons, risks and missing information stored alongside.

---

### Stage 5 — Recommendation and confidence

- Recommendation derived from bands **and** blocking state, via profile rules
- Confidence derived from **information completeness**, not from the score

Exit condition: a record with a strong score and three missing facts reports high fit and
**low** confidence. That combination is the whole point, and no build in the lineage could
express it.

---

### Stage 6 — Decision vocabulary and state

- Recover validated decision vocabulary
- Settle the state names (open question — see `DISPATCH_STATE_TRANSITION_RULES.md` §9)
- Default `Undecided`, validation on write

---

### Stage 7 — Gates and artifacts

Out of scope for Lane B. Interested → Brief, Pursue → Workspace, Publisher, artifact and
workspace creation, duplicate protection, run history, `ensure_column` recovery paths.

---

### Stage 8 — Presentation

The portal, Driver View, Stakeholder View, JOE narration. Explicitly excluded from the
foundation work. Presentation shows what the chassis produced; it does not produce
anything.

## 3. What "aggressive" means here

It does not mean skipping stages. It means:

- **No placeholder that fabricates.** A stage that is not built reports UNAVAILABLE.
- **Each stage ships working, not staged behind a flag.**
- **Tests are written against the doctrine**, not against the implementation. A test that
  asserts a hard stop cannot score above the disqualification line will fail today and
  pass at Stage 2. That is the correct order.
- **No presentation work borrows from a later stage.** The temptation at Stage 8 is to
  compute something in the template because the engine does not provide it yet. That is
  how the stages merged the first time.

## 4. What must not move earlier

| Do not build early | Why |
|---|---|
| Portal / Driver View / Stakeholder View | Presentation of an unfinished chassis hardens the wrong shape |
| JOE integration | JOE describes what the chassis produced. Nothing to describe yet. |
| Publisher | Artifacts of an evaluation that will change |
| COMI / Route Risk expansion | Depend on dimensions from Stage 4 |

## 5. Dependency, in one line

```
profile -> blocking -> stage separation -> dimensions -> recommendation + confidence
        -> decision vocabulary -> gates + artifacts -> presentation
```

Each arrow is a real dependency. Reversing any one of them means building something twice.
