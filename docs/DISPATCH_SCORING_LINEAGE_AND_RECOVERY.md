# DISPATCH SCORING LINEAGE AND RECOVERY

Status: FINDINGS + RECOMMENDATION. No runtime behaviour is changed by this document.

---

## 1. Why this document exists

Scoring is where every governance principle either holds or quietly fails. A veto that is
really a penalty, a threshold that is really a constant, a recommendation that is really a
decision — none of these announce themselves. They look like working code.

This traces what the lineage learned about scoring, what it lost, and where current
Dispatch stands.

## 2. The lineage of the score

### v1.0.1 — the constitutional model (13 Jul 08:10)

Externalised weights, an explicit veto, and a four-band classification.

```python
def classify(score: int, risks: list[str]) -> str:
    if any(r.startswith("BLOCKING") for r in risks):
        return "NOT A FIT"          # veto — evaluated before any band
    if score >= 75: return "HIGH-VALUE MATCH"
    if score >= 45: return "POSSIBLE MATCH"
    if score >= 25: return "LOW-VALUE / HIGH-COMPETITION"
    return "NOT A FIT"
```

Weights lived in `config/scoring_rules.json`. Score clamped `0..100`. Reasons and risks
accumulated as separate lists and were stored, not discarded.

Only **one** blocking condition was ever implemented:
`"BLOCKING: deadline is under 5 days or already passed"`. The *mechanism* was general; the
*catalogue* was one item. Dispatch inherits the mechanism and must write the catalogue.

### v1.1 → v1.3.1 — carried forward unchanged

The veto, the vocabulary and the external config survived three more builds. v1.3.1 still
has the veto at `app.py:87`, byte-for-byte the same idea. v1.1 removed the fabrication
fallback. v1.3 added reset. v1.3.1 added PSC.

### v1.3.3 — richer dimensions, weaker veto (13 Jul 14:31)

v1.3.3 added the best territory model in the lineage and, in the same rewrite, **lost the
veto**.

```python
if st in r['hard_no']:
    return -40, 'HARD-NO LOCATION', f'{st} is outside current practical operating footprint; manual override only.'
```

`-40` is a penalty, not a veto. The reason text says *"manual override only"* and nothing
enforces it. Worked example, from v1.3.3's own weights:

```
priority NAICS 492110  +35
PSC R602               +25
SDVOSB set-aside       +25
keyword hits           +25
HARD-NO location       -40
                       ----
                        70  →  POSSIBLE MATCH  →  recommend HOLD FOR STUDY
```

A California opportunity survives as a possible match. The words are severe; the
arithmetic is not.

v1.3.3 also introduced, for the first time, the separation Dispatch now needs:

```python
cls  = 'HIGH VALUE MATCH' if pts>=75 else 'POSSIBLE MATCH' if pts>=45 else ...
rec  = 'PURSUE' if pts>=75 else 'HOLD FOR STUDY' if pts>=45 else 'MONITOR' if pts>=25 else 'PASS'
conf = 'HIGH' if pts>=75 or pts<25 else 'MEDIUM'
```

Classification, recommendation and confidence as **three separate outputs**. That is the
right shape. The flaw is that all three derive from the same single number — see §4.

### GOLD — workflow gained, judgement not restored

GOLD inherited the post-rewrite scoring and added the human gates and the Publisher. It
did not restore the veto, the vocabulary or the external config.

## 3. Where current Dispatch stands

`dispatch/scoring.py` is a well-built module with three structural defects inherited from
nowhere — they are new.

### Defect A — no blocking condition exists

**CONFIRMED.** A hard stop is a five-point deduction:

```python
op_risk = 10.0
if load.get("hard_stop"):
    op_risk -= 5
score += max(op_risk, 0)
```

A load with `hard_stop=True`, a good rate and a short deadhead scores in the 90s and sorts
to the top. Nothing in the module can disqualify anything. This is a regression against a
capability the lineage had on 13 July.

### Defect B — business policy is hard-coded

**CONFIRMED.** `_HOME_BASE`, `_OPERATING_RADIUS_MILES`, `_FUEL_COST_PER_MILE`,
`_RATE_PER_MILE_FLOOR / _GOOD / _EXCELLENT`, `_WEIGHT_LIMIT_LBS`,
`_HOURS_AVAILABLE_DEFAULT` are module constants. v1.0.1 externalised its equivalents in
July.

### Defect C — the stages are merged

**CONFIRMED.** `compute_score()` folds fit, risk and position into one integer.
`compute_economic_opportunity()` returns a recommendation word (`Strong`, `Good`,
`Acceptable`, `Below floor`) from inside the scoring module. There is no filter stage at
all.

### What current Dispatch does better than the lineage

Credit where due. `dispatch/scoring.py` produces **named, explainable dimensions** that
L1-COS never had — position impact, return-home requirement, tomorrow's position risk, HOS
risk, route risk, deadhead miles, fuel estimate. Each returns a sentence a driver can read.

That is the raw material for the multi-dimensional model in
`DISPATCH_EVALUATION_ENGINE_SPEC.md`. The dimensions are already there. They are simply
being collapsed into one number at the end.

## 4. The recovery

**RECOMMENDATION.** Combine the three sources rather than choosing between them.

| Take | From |
|---|---|
| Blocking veto, evaluated before bands | v1.3.1 |
| Decision vocabulary, validated | v1.3.1 |
| Externalised weights and thresholds | v1.0.1 / v1.3.1 |
| Tiered territory with status + reason | v1.3.3 |
| Growth potential, recommended action, confidence as separate outputs | v1.3.3 |
| Named driver-legible dimensions | current Dispatch |
| Human gates and artifacts | GOLD |

And fix what none of them got right:

**Do not derive classification, recommendation and confidence from one number.**

v1.3.3 computed all three from `pts`, which means confidence was a restatement of the
score rather than a measure of how much was actually known. A record missing its deadline,
its weight and its broker history should not report `HIGH` confidence merely because the
points landed above 75.

Confidence measures **information completeness**, not fit. See
`DISPATCH_CONFIDENCE_MODEL_SPEC.md`.

## 5. Migration constraint

The recovery must not silently rescore history. Any record already evaluated keeps the
score, classification and profile version it was evaluated under. Re-evaluation produces a
new evaluation attached to the same Mission Record — it does not overwrite the one the
human saw when they decided.
