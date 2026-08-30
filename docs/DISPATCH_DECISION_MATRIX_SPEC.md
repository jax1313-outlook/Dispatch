# DISPATCH DECISION MATRIX SPEC

Status: SPECIFICATION. Not implemented. State names are RECOMMENDATION, not final.

---

## 1. What the matrix is

The decision matrix is the table that turns an Evaluation into a **recommended action**,
and records what the **human** did with it. Two different things, deliberately in one
document, because the boundary between them is the thing most easily lost.

```
Evaluation  ->  Recommendation  ->  [ human ]  ->  Decision
                (the engine)                       (the record of authority)
```

The arrow into `Decision` passes through a person. There is no path around it.

## 2. Conditions

Four severities. Recovered and extended from v1.0.1, which had the mechanism but only one
condition in its catalogue.

| Severity | Disqualifies | Visible | Effect on confidence |
|---|---|---|---|
| **BLOCKING** | Yes | Always | none |
| **WARNING** | No | Always | may lower |
| **INFORMATIONAL** | No | Always | none |
| **UNKNOWN** | No | Always | lowers |

### Blocking catalogue

From the profile, not from code. Proposed starting set:

| Condition | Source |
|---|---|
| Deadline passed or under N hours | v1.0.1 (`under 5 days`) — the only one ever implemented |
| Territory tier `hard_no` | v1.3.3 tier, veto is new |
| Equipment not held | new |
| Endorsement not held (hazmat, tanker) | INFERRED from v1.0.1 risk string |
| **Over pallet capacity** | **new — nothing in the lineage tracked pallets** |
| Over weight limit | current Dispatch (today a 4-point deduction) |
| Exceeds available hours | current Dispatch (today a score band) |
| Operator hard stop | current Dispatch (today a 5-point deduction) |

**Four of these eight are currently point deductions, and two do not exist at all.**
That is the regression this specification exists to close.

The overweight check is worse than a deduction — it is **unreachable**. It tests
`weight > 45000`, and the operator's vehicle carries 10,000 lb. No load it can legally
haul will ever trip it. See `DISPATCH_SCORING_LINEAGE_AND_RECOVERY.md` §3, Defect D.

### The rule

```
A blocking condition disqualifies regardless of score.
A high score does not override a blocking condition.
Only a recorded human override clears one.
```

## 3. Recommendation matrix

What the rules support. Not what happens.

| Blocking | Band | Completeness | Recommended action |
|---|---|---|---|
| yes | any | any | **DECLINE** (override available) |
| no | STRONG FIT | HIGH | **PURSUE** |
| no | STRONG FIT | LOW | **REVIEW** — strong fit, too much unknown |
| no | POSSIBLE FIT | HIGH | **REVIEW** |
| no | POSSIBLE FIT | LOW | **REVIEW** |
| no | MARGINAL | any | **MONITOR** |
| no | POOR FIT | any | **DECLINE** |

The `STRONG FIT` + `LOW completeness` row is the one no build in the lineage could
express. v1.3.3 would have said `PURSUE` with `HIGH` confidence, because it derived
confidence from the score. A load that looks excellent on three known facts and has five
unknown ones is exactly the load that needs a human to look, not a recommendation to
commit.

Configurable via `recommendation_rules`. See `DISPATCH_RECOMMENDATION_MODEL_SPEC.md`.

## 4. Decision vocabulary

**Recovered from v1.3.1**, where it was enforced with validation on write:

```python
allowed = {"Pursue", "Monitor", "Decline", "Defer", "Undecided"}
```

### Mapping into Dispatch — RECOMMENDATION, not final

The mission brief asks for evaluation of how these map, and explicitly does not ask for
final state names.

| L1-COS | Dispatch meaning | Maps to | Commits |
|---|---|---|---|
| **Undecided** | Nothing decided yet | default on creation | no |
| **Monitor** | Watching this | GOLD `interested` → Brief | no |
| **Defer** | Ask me again later | needs a revisit date | no |
| **Decline** | Not this one | reason recorded | no |
| **Pursue** | Committing | GOLD `pursue` → Workspace → ACCEPT LOAD | **yes** |

### Rules

1. **Default is `Undecided`.** Recovered from v1.3.1's schema default. Nothing arrives
   pre-decided.
2. **Validated on write.** An unrecognised decision raises. Recovered from v1.3.1.
3. **A decision is a human act**, recorded with who and when.
4. **Only `Pursue` commits.** Everything else is reversible and free.
5. **`Decline` carries a reason.** Without it, declines teach nothing.
6. **`Defer` carries a date**, or it is a `Decline` wearing a friendlier word.

### Open question for Mike

`Monitor` and `Defer` are genuinely different — *watch this* versus *ask me later*.
Carrying both costs a control on the screen and a decision from the driver. Carrying one
loses a distinction v1.0.1 thought worth keeping.

Reduced cognitive load argues for one. The lineage argues for two. **This is your call.**

## 5. The three-way separation

Every row in every table above respects this, and it is the point of the whole document:

| | Produced by | Binds |
|---|---|---|
| **Classification** | the engine | nothing — a description of fit |
| **Recommendation** | the engine | nothing — a sentence |
| **Decision** | **the human** | the operator, and only after they act |

The engine may recommend `PURSUE` on every load on the screen. Until a person acts, no
load is pursued, nothing is booked, and the record says so.

## 6. What the matrix may never contain

- An `auto_accept` threshold
- An `auto_decline` threshold
- A confidence level above which the human is skipped
- Any rule that writes a `Decision` without a human act

These are absent by design, not by omission. A threshold that decides is a threshold that
can be edited to decide more.
