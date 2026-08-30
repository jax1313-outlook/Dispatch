# DISPATCH RECOMMENDATION MODEL SPEC

Status: SPECIFICATION. Not implemented.

---

## 1. What a recommendation is

**A sentence, not an act.**

The engine may say `PURSUE`. Nothing moves. No broker is called, no load is booked, no
state advances. A recommendation is the engine explaining what its rules support, so the
human can decide faster — not instead of the human deciding.

## 2. Recommended actions

| Action | Means | Next step for the operator |
|---|---|---|
| **PURSUE** | Rules support committing | Accept the load, or not |
| **REVIEW** | Needs a human eye before anything | Look at what is unknown or mixed |
| **MONITOR** | Worth watching, not acting on | Leave it; revisit |
| **DECLINE** | Rules do not support it | Pass, or override |

Four, not five. v1.3.3 used `PURSUE / HOLD FOR STUDY / MONITOR / PASS`. `REVIEW` replaces
`HOLD FOR STUDY` because it says what the operator should *do*, and `DECLINE` replaces
`PASS` to match the decision vocabulary — the recommendation and the decision that follows
it should not use two different words for the same thing.

## 3. Inputs

A recommendation is derived from three things, never from score alone:

```
recommend(classification, conditions, completeness, profile) -> action + reason
```

| Input | Contributes |
|---|---|
| **Classification** | how well it fits |
| **Conditions** | whether it can be run at all |
| **Completeness** | whether enough is known to say either |

### Why not from score alone

**This is the correction to v1.3.3.** It computed all three of classification,
recommendation and confidence from a single number:

```python
cls  = 'HIGH VALUE MATCH' if pts>=75 else ...
rec  = 'PURSUE'          if pts>=75 else ...
conf = 'HIGH'            if pts>=75 or pts<25 else 'MEDIUM'
```

Three outputs that always agree carry no more information than one. If the score is high,
all three are high — so the operator learns nothing from seeing three fields.

Separating the inputs is what lets Dispatch say the useful thing: **strong fit, low
confidence, review before committing.**

## 4. Rules

1. **Blocking wins.** Any blocking condition recommends `DECLINE`, whatever the score.
2. **Low completeness cannot recommend `PURSUE`.** If too much is unknown, the honest
   recommendation is `REVIEW`. The engine does not recommend committing on facts it does
   not have.
3. **Every recommendation carries a reason**, in plain language, naming the deciding
   factor.
4. **Configurable**, from `recommendation_rules` in the profile.
5. **Never auto-executed.** No configuration may cause a recommendation to become an act.
6. **Stable.** The same evaluation recommends the same thing every time.

## 5. Configuration

```json
"recommendation_rules": {
  "pursue":  { "min_band": "STRONG FIT",   "min_completeness": "MEDIUM",
               "require_no_blocking": true },
  "review":  { "min_band": "POSSIBLE FIT" },
  "monitor": { "min_band": "MARGINAL" },
  "decline": { "default": true },
  "blocking_always_declines": true,
  "low_completeness_downgrades_to_review": true
}
```

`blocking_always_declines` and `low_completeness_downgrades_to_review` are settable to
`false` — an operator may want the engine to be more aggressive. Neither can cause an
action to be taken; they only change what sentence is printed.

## 6. Reason strings

A recommendation without a reason is an instruction, and the engine does not give
instructions.

| Recommendation | Reason names |
|---|---|
| PURSUE | the two or three strongest contributing dimensions |
| REVIEW | specifically what is mixed or unknown |
| MONITOR | why it is not worth acting on now |
| DECLINE | the blocking condition, or the weakest dimensions |

Examples:

```
PURSUE   "$4.20/mi, 40 miles deadhead, delivers 60 miles from home."
REVIEW   "Rate is strong but weight, broker history and delivery window are unknown."
MONITOR  "Fits the footprint but pays $2.60/mi, just above your floor."
DECLINE  "Delivers to CA - outside your operating footprint. Override available."
```

Written for a driver reading a phone at a truck stop. Short, specific, no jargon, and the
number that matters is in the sentence.

## 7. What a recommendation may never do

| Forbidden | Why |
|---|---|
| Set a decision | Decisions are human acts |
| Cross a gate | Gates are crossed by humans |
| Send, book, accept or reply | Not the engine's boundary |
| Claim an act occurred | Fact and Provenance doctrine |
| Be hidden from the operator | An invisible recommendation is a decision |

The last row matters more than it looks. If the engine recommends `DECLINE` and the
interface responds by not showing the load, the recommendation has silently become a
decision. Declined recommendations stay visible.
