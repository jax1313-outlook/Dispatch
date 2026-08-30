# DISPATCH POLICY FOUNDATION — PR SUMMARY

Status: SPECIFICATION PACKAGE. No code. No runtime change. No schema change.

---

## 1. What this package is

The first production-ready foundation for Dispatch evaluation: eight specifications
describing how Dispatch decides what to show, how well it fits, what to suggest, and how
sure it is — with the human keeping final authority throughout.

**It is specification only.** Nothing here is implemented. Nothing here changes how
Dispatch behaves today.

## 2. Files

| File | What it settles |
|---|---|
| `DISPATCH_POLICY_PROFILE_SPEC.md` | The single file holding every business judgement |
| `DISPATCH_EVALUATION_ENGINE_SPEC.md` | Inputs, outputs, order of operations, determinism |
| `DISPATCH_DECISION_MATRIX_SPEC.md` | Conditions, blocking, decision vocabulary |
| `DISPATCH_FILTER_SCORE_SORT_SPEC.md` | Three stages, kept apart |
| `DISPATCH_RECOMMENDATION_MODEL_SPEC.md` | What the rules support — a sentence, not an act |
| `DISPATCH_CONFIDENCE_MODEL_SPEC.md` | How much is actually known |
| `DISPATCH_OVERRIDE_RULES_SPEC.md` | When the human overrules the engine, and what is recorded |
| `DISPATCH_POLICY_PROFILE_EXAMPLES.md` | Four working profiles, zero lines of code changed |

## 3. What was deliberately excluded

Per the mission brief: no portals, no Driver View, no Stakeholder View, no JOE, no COMI,
no Route Risk, no Publisher. This is the evaluation foundation and nothing else.

## 4. The five stages

```
FILTER          what enters the decision lane
SCORE           how well it fits
SORT            what appears first
RECOMMENDATION  what the rules support
DECISION        what the human authorises
```

Kept separate throughout. Current `dispatch/scoring.py` merges score, risk and
recommendation into one integer, and has no filter stage at all.

## 5. Three corrections to the lineage

The lineage got a great deal right. These three it got wrong, and this package fixes them
rather than recovering them.

### 5.1 Confidence must measure evidence, not score

v1.3.3: `conf = 'HIGH' if pts>=75 or pts<25 else 'MEDIUM'`

Confidence derived from the score is a second copy of the score. Dispatch derives it from
**information completeness**, which lets the engine say *strong fit, low confidence* — the
most useful sentence it can produce, and one no build in the lineage could form.

### 5.2 A tier is not a veto

v1.3.3 scored `HARD-NO LOCATION` at −40 points. Its own reason text said *"manual override
only"*; nothing enforced it. A California load still classified as `POSSIBLE MATCH`.

Dispatch keeps the tiers and restores the veto from v1.3.1.

### 5.3 Risk does not belong inside the score

v1.0.1 had a `risk_penalty: -20`. Current Dispatch deducts for hard stops, overweight and
detention history. Both bury risk in a number where it cannot be seen.

Risk is reported alongside fit as conditions with severities. The operator sees *strong
fit, three risks* rather than a 70 that could mean anything.

## 6. The regression this closes

**CONFIRMED.** `dispatch/scoring.py` treats a hard stop as a 5-point deduction out of 100:

```python
op_risk = 10.0
if load.get("hard_stop"):
    op_risk -= 5
```

A load that cannot be run can score in the 90s and sort to the top of the list. Dispatch
had this solved on 13 July 2026 in v1.0.1, kept it through v1.3.1, and lost it in the
rewrite that produced v1.3.3 and GOLD.

Four of the seven proposed blocking conditions are currently point deductions.

## 7. Open questions — Mike's rulings needed

Implementation should not start on items 1–3 without answers.

| # | Question | Why it blocks |
|---|---|---|
| 1 | **What can never be overridden?** Proposed: endorsement not held, over legal weight, deadline passed. | A system that lets you override a hazmat endorsement you do not hold can help you break the law. |
| 2 | **Do `Monitor` and `Defer` both survive?** *Watch this* vs *ask me later*. | Reduced cognitive load says one. The lineage says two. Changes the state model. |
| 3 | **Which Master Constitution is authoritative?** v1.0.1 and v1.1 both carry `v1.0` and the files differ. | Two documents share a version number and disagree. |
| 4 | Territory tiers — still v1.3.3's July list? | Defaults |
| 5 | Rate floor $2.50, excellent $5.50 — still right? | Defaults |
| 6 | Fuel — what is it actually costing per mile now? | Defaults; $0.62 has a short shelf life |
| 7 | Reserve Capacity — what is the real rule, in your words? | Only you can state it; the keys are stubs |
| 8 | What is the truck? Equipment and endorsements. | **No build in the lineage records this.** All equipment matching is guesswork until answered. |

Question 8 is the one to answer first. It is the cheapest to answer and the most
foundational — every capability rule depends on it.

## 8. Not in this package, and why

| Absent | Reason |
|---|---|
| `auto_accept` / `auto_decline` | Human final authority is not configurable |
| A confidence threshold that skips the human | Confidence measures evidence, not permission |
| Any rule that writes a Decision | Decisions are human acts |
| A fabricating fallback | v1.0.1 shipped one against its own constitution |

These are absent by design. A threshold that decides is a threshold that can be edited to
decide more.

## 9. Recommended first implementation mission

**Stage 1 of `DISPATCH_AGGRESSIVE_BUILD_SEQUENCE.md`: the Policy Profile.**

Narrow, self-contained, no behaviour change:

1. Schema, loader, validator, defaults, versioning
2. Move the eight hard-coded constants out of `dispatch/scoring.py` into the profile
3. Tests: valid profile loads; malformed profile fails loudly and falls back to last
   known-good; same values in, same scores out

Exit condition: every business threshold in Dispatch lives in one editable file, and
`dispatch/scoring.py` produces **byte-identical output** to today.

Why first: every later stage needs somewhere to put its thresholds. Build evaluation first
and you hard-code twice.

Why not blocking conditions first, when they are the worse defect: blocking conditions
need a configurable catalogue to live in, and that catalogue is the profile. Building
blocking first means hard-coding the catalogue and moving it a week later.
