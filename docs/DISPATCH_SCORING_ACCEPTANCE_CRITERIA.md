# DISPATCH SCORING ACCEPTANCE CRITERIA

Status: ACCEPTANCE CRITERIA. Issued by the operator, 30 August 2026, and clarified the same
day. These are the categories the evaluation engine is built against and judged by.

**Architectural objective, in the operator's words:** *a policy change should alter
recommendations without altering scoring code.*

---

## 0. The critical rule

**The engine must not know:** Jacksonville · the operator's schedule · his detention value ·
his preferred territory · his reserve-capacity philosophy · his stop limits.

All of it belongs to the Policy Profile. Another operator may centre on Phoenix, Kansas City,
Dallas or Atlanta, or run nationally, with different equipment, rates and revenue goals. The
engine evaluates **categories**; policy supplies thresholds, limits, bonuses, penalties,
preferences, hard stops and weighting.

**The engine stays deterministic. The policy stays configurable.**

---

## 1. Hard stops — REJECT, whatever the score

Three categories can disqualify. A high score never overrides one.

**CONFIRMED, and it defines the two terms:**

> *"I take cube as size and weight as heft measured by scale. If they are out of range for
> equipment then they are no opportunity at all."*

| # | Category | Measures | Rule |
|---|---|---|---|
| 7 | **Cube** | **size** — the space the freight occupies | Out of range → **no opportunity at all** |
| 9 | **Weight** | **heft** — what it reads on a scale | Out of range → **no opportunity at all** |
| 8 | **Equipment compatibility** | what the equipment can do | *"If it does not fit I cannot take it."* |

Cube and weight are **two independent limits, not one**. Freight can be light and bulky, or
small and immensely heavy, and either alone disqualifies. A load at 40% of the weight limit can
still be cube-out.

**Weight is Moderate only *within* range.** Scoring how heavy a load is, once it fits, barely
matters. Exceeding the limit is not a heavy penalty — it is the same class of impossibility as
cube, and both are ceilings rather than deductions.

This is the defect that began the whole recovery: today a hard stop costs five points out of a
hundred, and the weight check tests `weight > 45000` on a vehicle that will carry a fraction of
that.

**Both limits are properties of the equipment**, so both live in the fleet profile — and both
are `UNCONFIGURED` until the van is bought.

### Open: reject-and-show, or filter-and-hide?

*"No opportunity at all"* could mean either. **RECOMMENDATION: show it, marked rejected, with
the number that disqualified it** — *"exceeds cube capacity by 40%"*.

The reason is a case that will happen: **a broker mis-types a dimension.** A load silently
filtered out for being 60 feet long, when the poster meant 6, is real freight the operator
never learns existed. Rejected-and-visible costs one line on a screen; filtered-and-hidden
costs a load, invisibly, and never announces itself.

Needs the operator's ruling — this is presentation, and presentation is his.

**Cube cannot be evaluated at all yet.** The van has not been purchased, so
`cube_capacity_ft3` is `UNCONFIGURED`. The most critical category is currently blind: it
reports `UNKNOWN` and lowers confidence rather than passing silently.

---

## 2. The categories

### 1 · Revenue Value — *benchmark only*

**CONFIRMED: "only as a goal/benchmark."** Gross revenue is an indicator, not a driver. Low
weight. Rate quality outranks it.

### 2 · Rate Quality — *high, and it should move the score hard*

**CONFIRMED: "score elevates significantly the higher the rate."**

Three levels — **Floor, Good, Excellent** — *"adjusted often, maybe weekly."*

Weekly adjustment settles the argument for externalisation on its own: a value that changes
weekly cannot live in code. Already in the Policy Profile as `money.rate_per_mile`.

### 3 · Capacity Fit — *high, and the hardest to build*

Fills an unused day · fits existing route plans · uses remaining capacity.

**CONFIRMED: the business model is repositioning to Jacksonville daily.**

**CONFIRMED, and it removes a dimension: "deadhead is not a factor."**

This is a real simplification. Deadhead scoring exists in `dispatch/scoring.py` today —
`compute_deadhead_miles`, and deadhead folded into effective rate-per-mile. If the truck
returns home every day regardless, the deadhead home is a **constant of the business model**,
not a variable of the load. Scoring it twice penalises loads for something that was going to
happen anyway.

> **Deadhead is retired as a scoring dimension.** It may still be *displayed* as a fact. It no
> longer moves the score.

### 4 · Revenue Opportunity

**Marked "no longer relevant" in the clarifications — but see §4, UNRESOLVED.** The
clarification numbering does not align cleanly with the category numbering, and category 6's
answer explicitly *keeps* the additional-stop case. Not actioned pending confirmation.

### 5 · Pickup Complexity — *high; pickups outrank deliveries*

**CONFIRMED: "the fewer stops the better."**

**CONFIRMED: "it is number of pickups that matter more. Limit should be 2 per day."**

**CONFIRMED: one stop taking the whole truck's capacity scores high.** A single-stop full load
is the ideal shape, not merely an acceptable one.

The limit of two is **policy**, not code.

### 6 · Delivery Complexity — *moderate*

**CONFIRMED: "the complicating factor is delivery times/distance."** Delivery count matters
less than the relationship between delivery windows and the distance between them — two
deliveries an hour apart with adjacent windows is a different load from two 200 miles apart
with overlapping ones.

**CONFIRMED, weekly basis: "adding a single stop for additional revenue and route fit within
capacity is a high score."** Capacity fit is assessed across the **week**, not only the day.

### 7 · Cube Utilization — **HARD STOP**. See §1.

### 8 · Equipment Compatibility — **HARD STOP**. See §1.

### 9 · Weight Compatibility — *moderate within limits, hard stop above*. See §1.

Distinct from cube: cube is the space it takes, weight is what the scale reads. Either alone
disqualifies.

### 10 · Accessorial Value — *high, and it inverts the usual sign*

**Relevant: detention, driver assist, wait time.** Lumper is not used at this scale.

**CONFIRMED: "driver assist with cargo van and trailer are assumed."** It is the normal case,
not a surcharge-triggering exception.

**CONFIRMED, and it inverts standard freight logic: "detention is free money even if it is
3 hours."**

Most systems treat detention risk as a penalty. Here it is not. At the operator's own
opportunity-cost formula the detention rate is set to make waiting worth its lost capacity, so
a load likely to sit is **not** a worse load.

> **Detention risk does not reduce the score.** A category that penalised it would be arguing
> with the accessorial policy that exists to make it whole.

**CONFIRMED, and this is a capacity rule hiding in a money answer:**

> *"If shipper warns about possible detention and accepts rate then that is a dedicated day to
> that load even if there is no detention."*

A warned-detention load **consumes the whole day's capacity at acceptance**, whether or not the
detention occurs. That is not scoring — it is an allocation against the Capacity Plan, and it
changes what else can be booked that day. See `DISPATCH_CAPACITY_PLAN_DOCTRINE.md`.

Detention rates come from the Company Library, never from code — see
`DISPATCH_ACCESSORIAL_POLICY_DOCTRINE.md`.

### 11 · Floor Compliance — *critical*

**CONFIRMED: "floor or above is all that matters."**

That is a clean rule and it resolves the ambiguity in the original wording, which offered both
*"reduces recommendation substantially"* **and** *"becomes Not Recommended"*. Offering both is
the v1.3.3 trap — a tier that reads as a veto and behaves as a penalty.

**Below floor is disqualifying by default**, with the option to configure it as a heavy penalty
instead. One or the other, chosen in policy, never both.

### 12 · Route Risk — *high, and it can cancel a day*

Consumes Route Risk intelligence: severe weather, flooding, closures, hurricanes, major
disruptions.

**CONFIRMED: "because of the severe weather we have in our area, turning back or not moving can
be a factor to cancel the day or days."**

Route Risk therefore acts at **two levels**: it scores a load, and it can invalidate a whole
Capacity Plan. The second is not a scoring output — it is a reason to reopen a locked day under
the BOOK IT DANO rule, in the opposite direction from a better opportunity.

**CONFIRMED: "this should be covered in our Rate Confirmation template."** Weather-related
turn-back terms belong in the customer-facing document, not only in the engine.

### 13 · Mission Feasibility — *high*

**CONFIRMED: "we must operate on all committed loads as if information is accurate."**

**This narrows the Confidence Model, and the operator is right.**
`DISPATCH_CONFIDENCE_MODEL_SPEC.md` derives confidence from information completeness, which
would hedge a *committed* load for a missing broker-history field. That is second-guessing an
agreement.

> Confidence measures what is **unknown about an opportunity**. It does not second-guess a
> **commitment already made**. A committed load is treated as accurate unless proven otherwise.

### 14 · Territory Alignment

Policy determines home base, preferred territory, avoid territory and repositioning philosophy.

**Do not hardcode Jacksonville.** The Jacksonville-centred operation is *policy*.

`dispatch/scoring.py` currently hardcodes `_HOME_BASE = "Jacksonville, FL"`. The Policy Profile
PR moves it to `identity.home_base`.

### 15 · Overall Recommendation

**CONFIRMED: "the decision matrix is designed to make a recommendation. The score total IS that
recommendation."**

Output vocabulary — the operator's words, adopted over the earlier draft:

```
Strong Match  ·  Recommended  ·  Review Required  ·  Not Recommended
```

**Human authority remains final. The score provides a recommendation, not authority.**

---

## 3. Missing from the fifteen

Two rules the operator has already given elsewhere have no category, and would otherwise live
nowhere:

**Broker trust.** The avoid list is a blocking condition — nonpayment, *"I would simply work
for free."* It is not among the fifteen. Either it becomes a category or it is a standing
blocking condition outside them; it cannot be neither.

**Return to home base.** *"Every day starts and ends at home base"* is stated as a hard
constraint, not a preference. Category 14 mentions "repositioning philosophy", which
understates it. With deadhead retired as a dimension, this is the constraint that replaces it.

---

## 4. UNRESOLVED — not guessed

**The clarification numbering does not align with the category numbering.** The answers run
1–15, but from roughly item 7 onward they track categories 5–13 — pickups answered at 7,
cube at 9, equipment at 10, accessorials at 11, floor at 12, route risk at 13, feasibility
at 14.

Everything recorded above is placed by **content**, not by number, and each is quoted so it can
be checked.

Two items are genuinely unclear and are **not** actioned:

| Item | Question |
|---|---|
| *"4. no longer relevant"* | Which is retired? Category 4 (Revenue Opportunity) contradicts the answer at item 6, which keeps the additional-stop case explicitly. |
| ~~*"8. As long as cube size and limit is not exceeded, medium factor"*~~ | **RESOLVED.** Cube is size; weight is heft on a scale. Both are hard stops when out of range for the equipment; both are moderate within it. |

Per the Fact and Provenance doctrine, an unclear instruction is recorded as unresolved rather
than resolved by assumption.
