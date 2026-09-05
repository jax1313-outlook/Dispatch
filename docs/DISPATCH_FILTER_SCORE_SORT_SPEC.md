# DISPATCH FILTER / SCORE / SORT SPEC

Status: SPECIFICATION. Not implemented. No runtime behaviour is changed by this document.

---

## 1. Three questions, three stages

| Stage | Question | Output |
|---|---|---|
| **FILTER** | What enters the decision lane? | `admitted` + reason |
| **SCORE** | How well does it fit? | `0..100` + reasons |
| **SORT** | What appears first? | `sort_key` |

They are separate because they fail separately, and because merging them hides things from
the operator. A filter that scores is an invisible veto. A score that filters silently
discards work. A sort that scores makes its own order self-justifying.

---

## 2. FILTER

### Purpose

Decide what the operator is asked to look at. Filtering is about **relevance**, never
about quality.

### Rules

1. **Filtering is recorded, not silent.** Every filtered record keeps its reason and
   remains retrievable. The operator can always ask "what did you not show me?"
2. **Filters do not score.** A filter answers yes or no. It never contributes points.
3. **Filters are configurable.** From `filter_rules` in the profile.
4. **UNKNOWN does not filter out.** A record missing its destination is admitted with low
   completeness, not discarded. Discarding on unknown means the least-documented loads —
   often the ones needing attention — vanish.

### Filter rules

```json
"filter_rules": {
  "require_equipment_match": false,
  "exclude_expired": true,
  "exclude_states": [],
  "exclude_brokers": [],
  "minimum_revenue": 0,
  "maximum_deadhead_miles": null
}
```

`exclude_expired` is the one filter that should default on: a load whose window has closed
is not a decision, it is history.

### Filter is not blocking

Easy to confuse, and important.

| | FILTER | BLOCKING |
|---|---|---|
| Question | Is this relevant to me? | Can this be run at all? |
| Result | Not shown by default | Shown, marked disqualified |
| Visible | On request | Always |
| Override | Change the filter | Explicit recorded override |

A California load with a `hard_no` territory is **blocked**, not filtered — the operator
should see it, see why it is disqualified, and be able to override it deliberately. A load
from a broker the operator never works with is **filtered** — not worth the screen space.

---

## 3. SCORE

### Purpose

Express **degree of fit**, and nothing else.

### Rules

1. **Score measures fit. Risk is not subtracted from it.** Risk is reported alongside.
2. **Score never excludes.** A zero-scoring record is still shown if admitted.
3. **Score cannot rescue a blocked record.** 100 points plus a blocking condition is still
   disqualified.
4. **Every contribution carries a reason.** A score of 62 must decompose into the points
   that made it.
5. **Weights come from the profile.**
6. **Clamped to `0..100`.** Recovered from v1.0.1: `max(0, min(100, score))`.

### Weights

```json
"score_weights": {
  "operational_fit": 25,
  "financial_value": 30,
  "return_position_value": 20,
  "growth_potential": 15,
  "territory": 10
}
```

Weights sum to 100 so that a score reads as a percentage of achievable fit. If the operator
edits them to sum to something else, the engine normalises and says so.

Note what is **absent**: there is no `risk_penalty`. v1.0.1 had one (`-20`) and it is
deliberately not recovered — risk belongs in conditions, where it can be seen, not buried
in a number. This is the one place this specification knowingly departs from the lineage,
and the reason is stated here so the departure is not mistaken for an oversight.

### Classification bands

```json
"bands": [
  { "min": 75, "name": "STRONG FIT" },
  { "min": 45, "name": "POSSIBLE FIT" },
  { "min": 25, "name": "MARGINAL" },
  { "min": 0,  "name": "POOR FIT" }
]
```

Recovered from v1.0.1 and v1.3.3, which both used 75 / 45 / 25. Band **names** are
proposed, not final — v1.0.1's `NOT A FIT` for the bottom band is a poor name, because a
disqualified record and a low-scoring one are different things and should not share a
label.

**A disqualified record classifies as `DISQUALIFIED`, whatever its score.**

---

## 4. SORT

### Purpose

Decide what the operator sees first. Presentation only.

### Rules

1. **Sort never changes score, classification or recommendation.**
2. **Sort is configurable.**
3. **Disqualified records sort last by default**, and are not hidden.
4. **Sort is stable.** Equal keys keep a fixed order, so the list does not shuffle between
   refreshes. A list that reorders itself for no visible reason is a list the operator
   stops trusting.

### Sort rules

```json
"sort_rules": {
  "primary": "score",
  "direction": "desc",
  "disqualified_last": true,
  "tie_breakers": ["deadline_soonest", "deadhead_shortest", "record_id"],
  "pin_expiring_within_hours": 24
}
```

`record_id` is the final tie-breaker specifically to guarantee stability.

`pin_expiring_within_hours` is the one sort rule allowed to override score order —
something closing in six hours is worth seeing regardless of fit, because the *decision*
is urgent even when the load is mediocre. It is capped and configurable, and it is a sort
behaviour only: it changes nothing about the evaluation.

---

## 5. Worked example

A load: good rate, short deadhead, delivers to California (`hard_no`).

```
FILTER      admitted (no filter rule excludes it)
CONDITIONS  BLOCKING - outside practical operating footprint
DIMENSIONS  financial value HIGH ($4.10/mi)
            territory      HARD-NO LOCATION
            completeness   HIGH
SCORE       78  (fit is genuinely good)
CLASSIFY    DISQUALIFIED  <- blocking wins, band would have been STRONG FIT
RECOMMEND   DECLINE - blocking condition, override available
CONFIDENCE  HIGH - little is unknown
SORT        last (disqualified_last)
```

Under v1.3.3 this same load scored 70 and came back `POSSIBLE MATCH` /
`HOLD FOR STUDY`. Under current Dispatch it would score in the high 70s with no
disqualification at all.

The operator sees a strong-fitting load that they may not run, told plainly, with the
override in reach. That is the whole point of keeping the stages apart.
