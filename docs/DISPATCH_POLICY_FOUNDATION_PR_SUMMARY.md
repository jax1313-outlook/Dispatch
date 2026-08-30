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

**SCOPE CORRECTION, 30 August 2026.** `dispatch/capacity.py` already implements
`SEVERITY_BLOCKING`, physical dimensions including volume and pallets, a versioned asset
profile defaulting to `UNCONFIGURED`, and provenance on every specification. It is used by
`dispatch/opportunities.py`.

**The defect is that `dispatch/scoring.py` does not use any of it** — zero references. Two
capacity models exist and only one blocks. What follows is scoped to the scorer, and the
work is largely integration rather than construction.

`dispatch/scoring.py` treats a hard stop as a 5-point deduction out of 100:

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
| ~~8~~ | ~~What is the truck?~~ | **ANSWERED 30 Aug 2026 — see below** |

### Question 8 is answered, and it changed the specification

**CONFIRMED by the operator:** a **cargo van with trailer**, running courier and expedite
freight — and **it has not been purchased yet.** Payload, cube, pallet positions and
dimensions are all `UNCONFIGURED`. The operator's stated targets are 10,000 lb payload and
6 pallet positions; those are intent, never calculation inputs.

This exposed a fourth regression:

**`dispatch/scoring.py` is calibrated for a Class 8 tractor-trailer, which is not the
intended vehicle.** Its overweight guard tests `weight > 45000` — for a cargo van
operation, no load it could legally carry approaches that figure, so the guard cannot fire
on any realistic load.

**`dispatch/scoring.py` has no pallet or cube constraint.** `dispatch/capacity.py` does —
`PHYSICAL_DIMENSIONS = ["weight", "linear_feet", "volume", "pallets"]` — but the scorer
does not use it, which is the integration gap this package exists to close.

The July judgement was right and the later calibration was wrong: v1.3.3 targeted NAICS
492110 / 492210 and PSC R602 — couriers and local messengers — which is exactly a
cargo-van business.

### Follow-on questions this raises

| # | Question | Why it matters |
|---|---|---|
| ~~9~~ | ~~Payload or GVWR?~~ | **ANSWERED: payload.** Combined GVWR is materially higher, so the profile defaults to hours-of-service applying. Regulatory confirmation remains the operator's. |
| 10 | **What does fuel actually cost per mile?** | $0.62 implies ~6 mpg. Every margin figure is currently pessimistic. |
| 11 | **What are the real rate bands for this work?** | $2.50 / $4.00 / $5.50 are truckload numbers. Expedite and courier rates differ. |
| 12 | **Cube capacity of van and trailer?** | Two of three utilization ratios work without it; the third is guesswork. |
| 13 | **Accessorial rates** — detention/hour, layover, TONU, lumper, liftgate. | Every profitability figure. Detention on a multi-stop run can exceed the linehaul. |
| 14 | **Target margin** for the profit score. | Profit scoring has no reference point without it. |
| 15 | **Complexity tolerance** — how many stops before a load stops being worth it? | Complexity scoring bands. |
| ~~16~~ | ~~Resequenced after acceptance?~~ | **ANSWERED: yes** — stop order was never promised, time windows were. Not an override. |
| 17 | **What counts as "near" home base** for the end-of-day check? | The only parameter the close detection needs. |

### The Load Arrangement model changed the scope

The operator supplied a full Load Arrangement Data Model on 30 August 2026. It is
specified in `DISPATCH_LOAD_ARRANGEMENT_SPEC.md` and it added four things these
specifications did not have:

1. **Multi-stop is first-class** — ordered stops, types, windows, dwell, priority. This is
   the one item that reaches past Lane B into existing code: `dispatch/mission.py` assumes
   one pickup and one delivery. Recommended fix is minimal — phase becomes a property of
   the current stop rather than of the run — and it preserves the CURRENT-resolves
   doctrine unchanged.
2. **Three utilization ratios** — weight, cube, pallet. The binding constraint is whichever
   reaches 1.0 first, and being weight-out is a different situation from being cube-out.
3. **Accessorials** — detention, layover, TONU, lumper, liftgate, temp control. Every
   money figure in current Dispatch is linehaul-only, which is wrong for this work.
4. **Complexity as a dimension**, kept strictly separate from profit. *Is the extra money
   worth the extra hassle* is a question that only exists while the two are separate
   numbers.

It also resolved the Full / Heavy / Mixed capacity figures: 6 / 5 / 4 pallets all land on
the same 10,000 lb ceiling, so they are one weight limit at three pallet weights, capped at
6 positions by deck space — not three capacity rules.

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
