# DISPATCH DETERMINISTIC CHASSIS

Status: DOCTRINE. No runtime behaviour is changed by this document.
Recovered from the L1-COS v1 lineage (v1.0 / v1.0.1 / v1.1 / v1.3 / v1.3.1 / v1.3.3 / v1.3.2 GOLD).

---

## 1. The one rule

**The engine is deterministic. The operator owns the policy. The human owns the decision.**

Same inputs, same policy profile, same outputs. Every time. If a result cannot be
reproduced from the record and the profile alone, it is not part of the chassis.

## 2. Five stages, never collapsed

The single most expensive mistake available to this system is to merge these into one
number. They answer five different questions and they fail in five different ways.

| Stage | Question | Owns | May not |
|---|---|---|---|
| **FILTER** | What enters the decision lane at all? | Inclusion | Rank anything |
| **SCORE** | How well does it fit? | Degree of fit | Exclude anything |
| **SORT** | What does the human see first? | Presentation order | Change score or fit |
| **RECOMMENDATION** | What action do the rules support? | A suggested action | Bind anyone |
| **DECISION** | What did the human authorise? | The record of authority | Be produced by the engine |

### Why they must stay apart

- A **filter** that scores becomes an invisible veto. The operator cannot see what was
  removed, and cannot tell a low score from an exclusion.
- A **score** that filters silently discards work. `NOT A FIT` must be a *classification*
  the human can look at, not a deletion.
- A **sort** that changes score makes the list order self-justifying.
- A **recommendation** that decides removes the human. See §4.
- A **decision** produced by the engine is a fabricated authority. It does not exist.

### CONFIRMED regression in current Dispatch

`dispatch/scoring.py` collapses stages. `compute_score()` mixes fit, risk and position
into one 0-100 integer, and `compute_economic_opportunity()` returns a recommendation
string (`Strong`, `Good`, `Acceptable`, `Below floor`) from inside the scoring module.

This is the condition the lineage already solved and then lost. See
`DISPATCH_SCORING_LINEAGE_AND_RECOVERY.md`.

## 3. Blocking conditions are not scores

Recovered from v1.0.1 `l1_cos/app.py:197`, still present unchanged in v1.3.1 `app.py:87`:

```python
if any(r.startswith("BLOCKING") for r in risks):
    return "NOT A FIT"
```

The veto is evaluated **before** the score bands and **cannot be outvoted by points**.

Dispatch must support four severities:

| Severity | Effect |
|---|---|
| **BLOCKING** | Disqualifies regardless of score. Human override required and recorded. |
| **WARNING** | Does not disqualify. Must be shown. May reduce confidence. |
| **INFORMATIONAL** | Shown. No effect on fit. |
| **UNKNOWN** | A missing fact, not a good one. Reduces confidence. Never scores as zero risk. |

**A high score does not override a blocking condition.** This is not a preference. A load
that cannot legally or physically be run does not become runnable at 95 points.

### CONFIRMED regression in current Dispatch

`dispatch/scoring.py:compute_score()` treats a hard stop as a **5-point deduction** out of
100 (`op_risk -= 5`). A load carrying `hard_stop=True` can still score in the 90s and sort
to the top of the list. There is no veto anywhere in the module.

## 4. Recommendation is not authority

The engine may say `PURSUE`. That is a sentence, not an act. Nothing moves until a human
acts on it, and the record stores *who* acted and *when* — never *that the system decided*.

Inherited directly from current Dispatch doctrine and from the JOE authority model:
**the system may recommend; it may not approve, decide, or state that an action has been
taken.**

## 5. Human interest is not commitment

Recovered from GOLD. GOLD separated two gates that everything before it had merged:

- `interested = 1` — the human is looking at this. Creates a Brief. Commits nothing.
- `pursue = 1` — the human is committing. Creates a Workspace.

Marking interest must remain free. If interest costs something, the operator stops
marking interest, and the system loses its most useful signal.

## 6. UNKNOWN is a first-class value

Recovered from v1.3.3 `score_location()`, which returns an explicit
`UNKNOWN LOCATION` state with its own reason string rather than defaulting to a
neutral or favourable value.

Everywhere in Dispatch: a fact that is not known is `UNKNOWN`. It is displayed, it lowers
confidence, and it never silently becomes `False`, `0`, or `no risk`.

## 7. Determinism boundary

Inside the chassis: rules, thresholds, arithmetic, table lookups, configuration.
Outside the chassis: language models, network calls, anything time-dependent that is not
passed in as an input.

Non-deterministic helpers may **describe** what the chassis produced. They may not
produce it.

---

## Related

- `DISPATCH_CONFIGURABLE_BUSINESS_POLICY_DOCTRINE.md` — who owns the thresholds
- `DISPATCH_FACT_AND_PROVENANCE_DOCTRINE.md` — where facts come from
- `DISPATCH_SCORING_LINEAGE_AND_RECOVERY.md` — what was lost and when
- `DISPATCH_STATE_TRANSITION_RULES.md` — the gates
