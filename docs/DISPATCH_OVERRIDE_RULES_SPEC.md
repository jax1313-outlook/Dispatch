# DISPATCH OVERRIDE RULES SPEC

Status: SPECIFICATION. Not implemented.

---

## 1. Why overrides exist

Because the operator knows things the profile does not.

A `hard_no` territory is a rule written in advance. The load that pays triple, positions
the truck for a week of good freight, or is a favour to a customer worth keeping is not a
failure of the rule — it is the reason a human is in the loop.

**An override is not the system being wrong. It is the human being in charge.**

The alternative — a system that cannot be overridden — teaches the operator to work around
it, and a system worked around is a system that no longer reflects reality.

## 2. What may be overridden

| Overridable | Not overridable |
|---|---|
| A blocking condition | The requirement to record the override |
| A filter exclusion | Human final authority |
| A recommendation | The prohibition on auto-accept |
| A sort position (pinning) | Provenance and no-fabrication |
| A dimension value, with a correction | The record of what the engine originally said |

The right column is short and it is fixed. Nothing in the profile, and no override, can
reach it.

## 3. What an override requires

Every override records five things:

```
override
  what          which condition, filter or recommendation
  original      what the engine said, preserved
  reason        why - required, free text, minimum length enforced
  who           the human
  when          timestamp
```

**The reason is mandatory.** Not a checkbox, not a dropdown. If overriding is frictionless
it becomes reflexive, and the blocking conditions stop meaning anything. A sentence is
enough; a sentence is also required.

**The original is preserved.** An overridden evaluation still shows what the engine
concluded. The override sits beside it, never on top of it.

## 4. Override requirement as a dimension

`Override Requirement` appears in the mission brief's dimension list. It is the
Evaluation's answer to: *what would a human have to accept to proceed with this?*

| Value | Meaning |
|---|---|
| `NONE` | Nothing to override; proceed normally |
| `SIMPLE` | A warning to acknowledge |
| `BLOCKING` | A blocking condition to override, with reason |
| `MULTIPLE` | More than one blocking condition |
| `NOT PERMITTED` | Cannot be overridden — see §5 |

Shown to the operator before they act, so the cost of proceeding is visible up front
rather than discovered halfway through.

## 5. Conditions that cannot be overridden — RESOLVED, and the list is empty

**Ruled by the operator, 30 August 2026.** An earlier draft proposed a `NOT PERMITTED` class:
conditions that exist, disqualify, and may never be overridden — endorsement not held, over
legal weight, over pallet positions, deadline passed.

**That class no longer exists**, because those conditions no longer reach the override stage.
The operator ruled that an impossibility is **filtered**: the load is not selected for
evaluation at all.

> *"If out of range — skip. The loads are not to be selected for evaluation."*
> *"These follow the same rule as weight and cube."* — of endorsements and deadlines

**A condition nobody may overrule never reaches the point of being overridden.** It never
entered the lane. See `DISPATCH_SCORING_ACCEPTANCE_CRITERIA.md` §1.

That removes a redundancy this specification carried: two mechanisms for impossibility, a
filter and an unoverrideable block, where one was enough.

### What remains overridable

Everything in the blocking stage, because everything left there is a **business judgement**:

| Overridable | Why |
|---|---|
| Below floor | A price judgement — he may take a thin load for a reason the engine cannot see |
| Broker on the avoid list | Business trust. Arrears get paid; the remedy is the USE list |
| Territory `hard_no` | A business judgement, and business judgements change |
| Operator hard stop | He set it; he may lift it |

**Every blocking condition is overridable, with a recorded reason.** There are no exceptions,
and that is now a property of the design rather than a list to maintain.

## 6. Configuration

```json
"override_rules": {
  "require_reason": true,
  "minimum_reason_length": 15,
  "_comment_not_permitted": "Deliberately absent. An impossibility is filtered before evaluation, so it never reaches an override. See DISPATCH_SCORING_ACCEPTANCE_CRITERIA.md section 1.",
  "expire_after_days": null,
  "warn_on_repeat_override": 3
}
```

`require_reason` is settable but **defaults on and should stay on**.

`warn_on_repeat_override` is the useful one: if the same condition has been overridden
three times, the profile is probably wrong. The system should say so — *"you have
overridden HARD-NO for TX three times; consider moving TX to expansion"* — rather than
keep blocking something the operator has repeatedly decided is fine.

**It counts overrides; it never draws a conclusion about a broker.** For the avoid list the
warning says the *list* may be out of date. It does not say the broker is now trustworthy, and
it must never be worded that way: **trust is not a program variable**, and a counter that
implies one is the same inference wearing arithmetic. Whether a broker belongs on that list is
formed by being paid or not being paid, which happens to a person and not in a database. See
`DISPATCH_SCORING_ACCEPTANCE_CRITERIA.md` §3.

That is the override log earning its keep: it turns friction into a signal that the policy
needs updating.

## 7. Overrides do not silently persist

An override applies to **one record, once**. It does not:

- change the profile
- apply to future loads matching the same pattern
- silently disable the condition

If the operator wants a rule changed, they change the profile — deliberately, in one
place, where they can see it. A system where overrides quietly accumulate into policy is a
system whose rules nobody can state.

## 8. Overrides and authority

An override changes **what the engine permits**. It never changes **who decides**.

Overriding a blocking condition on a load does not accept the load. It removes the
disqualification so the human can then decide. Two separate acts, both by the human, in
that order.
