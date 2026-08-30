# DISPATCH CONFIDENCE MODEL SPEC

Status: SPECIFICATION. Not implemented.

---

## 1. What confidence measures

**How much Dispatch actually knows about this load.**

Not how good the load is. Not how strongly it fits. How much of what matters is
established fact rather than absence.

```
Score      ->  how well does it fit, on what we know
Confidence ->  how much do we know
```

Two independent questions. A load can fit superbly on four known facts while six others
are blank — high score, low confidence. That combination is the single most useful thing
this model produces, and no build in the lineage could express it.

## 2. The defect being corrected

**CONFIRMED.** v1.3.3 derived confidence from the score:

```python
conf = 'HIGH' if pts>=75 or pts<25 else 'MEDIUM'
```

This says: *I am confident when the score is extreme.* It is a statement about the
arithmetic, not about the evidence. A record with an unknown deadline, unknown weight,
unknown broker and unknown location could still report `HIGH` confidence by scoring below
25 — confident precisely where it knew least.

Confidence must measure evidence. Otherwise it is a second copy of the score.

## 3. Information completeness

Confidence is computed from a weighted count of facts known versus facts needed.

```
completeness = sum(weight of known fields) / sum(weight of required fields)
```

### Field weights

```json
"confidence_rules": {
  "critical": {
    "weight": 3,
    "fields": ["origin", "destination", "rate", "pickup_window", "delivery_window"]
  },
  "important": {
    "weight": 2,
    "fields": ["distance_miles", "weight_lbs", "equipment_required", "broker"]
  },
  "useful": {
    "weight": 1,
    "fields": ["commodity", "broker_history", "detention_history", "contact"]
  },
  "bands": { "high": 0.85, "medium": 0.60 },
  "critical_missing_caps_at": "LOW"
}
```

**Critical fields are the ones without which the load cannot be evaluated at all.** Missing
any one of them caps confidence at `LOW` regardless of the arithmetic — a load with no rate
is not 80% understood, whatever the other fields say.

### Bands

| Band | Completeness | Meaning |
|---|---|---|
| **HIGH** | ≥ 0.85, no critical missing | Enough is known to act on |
| **MEDIUM** | ≥ 0.60, no critical missing | Enough to judge, not to commit blind |
| **LOW** | below 0.60, or any critical field missing | Go and find out more |

## 4. What lowers confidence

| Cause | Effect |
|---|---|
| **An equipment specification is NOT CONFIGURED** | **caps the dimensions that need it at `UNKNOWN`** |
| A required field is `UNKNOWN` | reduces completeness by its weight |
| A critical field is missing | caps at `LOW` |
| A field is stale beyond its freshness window | treated as unknown |
| An adapter reported `UNAVAILABLE` | the fields it would have supplied are unknown |
| A `WARNING` condition fired | may lower by one band, configurable |

The `UNAVAILABLE` row is the link back to the adapter contract. A sweep that could not
reach the load board does not produce confidently-empty records; it produces records whose
missing fields are honestly marked unknown, and confidence falls accordingly.

## 5. What does NOT affect confidence

| Not a factor | Why |
|---|---|
| The score | That is fit, not knowledge — this is the v1.3.3 defect |
| The classification | Same reason |
| The recommendation | Downstream of confidence, not upstream |
| A blocking condition | A blocked load can be perfectly well understood |

That last row is worth stating plainly: knowing a load is disqualified is *knowledge*. A
California load with complete information is `DISQUALIFIED` with `HIGH` confidence. The
engine is very sure this one is a no.

## 5a. Missing equipment specifications

**CONFIRMED, 30 August 2026: the vehicle has not been purchased**, so payload, cube, pallet
positions and dimensions are `NOT CONFIGURED`.

A dimension that needs a missing specification **does not compute a number**. It reports
`UNKNOWN`, names the missing specification, and lowers confidence:

```
Operational Fit:  Strong
Confidence:       Low
Reason:           Cube capacity not configured.
```

This is the example the operator gave, and it is exactly the shape this model exists to
produce: **a real assessment of what is known, beside an honest statement of what is not.**

Note what it does *not* do — it does not refuse to evaluate, and it does not invent a
capacity so the arithmetic can proceed. Operational fit is still `Strong` on the facts that
are available. Confidence carries the gap.

## 6. Confidence never gates authority

Confidence informs the human. It does not decide for them.

| Forbidden | Why |
|---|---|
| Auto-accept above a confidence threshold | Confidence is not authority |
| Auto-decline below one | Same |
| Hide low-confidence records | The operator needs to see what is poorly understood |
| Treat `HIGH` confidence as permission | It is a measure of evidence, nothing more |

**High confidence means "I am sure about the facts." It never means "go ahead."**

## 7. Presentation

Confidence is shown with its reason, always naming what is missing:

```
Confidence: LOW - rate and delivery window unknown
Confidence: MEDIUM - broker history unknown
Confidence: HIGH - all required fields present
```

The reason is the useful half. `LOW` alone tells the driver nothing they can act on;
*"rate unknown"* tells them exactly which call to make.

## 8. Worked examples

| Case | Score | Confidence | Recommendation |
|---|---|---|---|
| Full data, good rate, in territory | 82 STRONG FIT | HIGH — all present | PURSUE |
| Good rate, no weight or broker history | 79 STRONG FIT | MEDIUM | REVIEW |
| Good rate, **no delivery window** | 76 STRONG FIT | **LOW** — critical missing | **REVIEW** |
| Poor rate, full data | 31 MARGINAL | HIGH | MONITOR |
| California, full data | 78 **DISQUALIFIED** | HIGH | DECLINE |

Row three is the one that matters. Under v1.3.3 it would have read `PURSUE` with `HIGH`
confidence, because 76 is above the threshold. Dispatch says: this looks strong, but you
do not know when it delivers — go and ask.
