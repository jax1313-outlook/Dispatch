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

## 1. Impossibility is a FILTER, not a score

**The principle, confirmed twice by the operator:** a condition the operator *cannot overrule*
removes the load from evaluation. It is not scored, not shown, and not offered as a decision.

A condition he *could* reasonably overrule — a business judgement — stays a blocking condition:
visible, disqualified, overridable with a recorded reason.

**CONFIRMED, and it defines the two terms:**

> *"I take cube as size and weight as heft measured by scale. If they are out of range for
> equipment then they are no opportunity at all."*

| Condition | Kind | Out of range |
|---|---|---|
| **Cube** — size, the space it occupies | physical | **Filtered. Not evaluated.** |
| **Weight** — heft, what the scale reads | physical | **Filtered. Not evaluated.** |
| **Equipment** cannot perform the load | physical | **Filtered. Not evaluated.** |
| **Endorsement not held** — hazmat, tanker | legal | **Filtered. Not evaluated.** |
| **Deadline already passed** | temporal | **Filtered. Not evaluated.** |
| *Pallet positions exceeded* | physical | *Filtered — by the principle. Confirm.* |

**CONFIRMED:** *"these follow the same rule as weight and cube"* — endorsements and deadlines.

Pallet positions are the same shape and are **not** separately ruled on: they are deck space,
as physical and as unoverruleable as cube. Included here by the principle, marked so it can be
corrected.

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

### RESOLVED: skip them. They are not selected for evaluation.

> *"If out of range — skip. The loads are not to be selected for evaluation."*

**This places physical fit at the FILTER stage, not the blocking stage**, and the distinction
is architectural rather than cosmetic. See `DISPATCH_FILTER_SCORE_SORT_SPEC.md`:

| | **FILTER** | **BLOCKING** |
|---|---|---|
| Asks | Is this a candidate at all? | Can this be run? |
| Result | Not shown by default | Shown, marked disqualified |
| Example | Cube, weight, equipment out of range | Below floor; broker on the avoid list |

Territory and floor compliance are **business judgements** — the operator may want to see one
and overrule it. Cube, weight and equipment are **physical facts about the vehicle**. There is
no judgement to exercise and no override that makes a load fit, so there is no reason to spend
his attention on it.

**The engine does not score what it cannot carry.**

### Filtering is recorded, never silent

A filtered load keeps its reason and stays retrievable — the operator can ask what was not
shown. That is a standing property of the filter stage, not a special provision for this
category.

**A filter that deletes would be a different thing entirely, and is forbidden.**

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

### 4 · Revenue Opportunity — **RETIRED**

**CONFIRMED: "retire, not relevant."**

Kept in the list as retired rather than deleted, so the numbering does not silently shift and
a future reader can see it was considered and dropped.

It is not a loss of capability: **category 6 already scores the case** — *"adding a single stop
for additional revenue and route fit within capacity is a high score."* Revenue opportunity was
a second name for something the delivery-complexity and capacity-fit categories were already
measuring, and two categories scoring one thing is double-counting.

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

### 7 · Cube Utilization — **FILTER**. See §1.

### 8 · Equipment Compatibility — **FILTER**. See §1.

### 9 · Weight Compatibility — *moderate within limits, filtered above*. See §1.

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

**And the operator goes further, which narrows this more than I expected:**

> *"This industry operates on all post data is trustworthy. It is also verified during
> negotiation process. Data changes will be made before commitment is formal."*

**Posted load data is trusted by default.** It is checked by a human during negotiation, and
corrections happen before anything is formal. The verification step this industry already has
is a conversation, not a scoring model.

**This retires most of `DISPATCH_CONFIDENCE_MODEL_SPEC.md`, and the correction is mine to
take.** That specification weighted every field of a posted load — rate, windows, weight,
broker history — and reported *"strong fit, low confidence"* when fields were missing. I called
that the most useful sentence the engine could produce. For this operation it is mostly noise:
it hedges data the operator will confirm by telephone anyway, and it would train him to ignore
a signal that fires on almost everything.

**What survives, and why it is different:**

| Survives | Retired |
|---|---|
| **Dispatch does not know its own equipment.** Cube capacity is `UNCONFIGURED`; the engine cannot evaluate a category and must say so. | Weighting a broker's posted fields and reporting a completeness percentage. |
| A field the engine needs and **cannot obtain** — a system gap. | A field the operator will obtain in the next phone call — a negotiation step. |

The distinction is **who can resolve it**. If the operator resolves it during negotiation, it
is not a confidence problem. If Dispatch cannot resolve it at all — an unconfigured vehicle, an
`UNAVAILABLE` adapter — it is, and it still reports `UNKNOWN` rather than guessing.

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

## 3. Two rules with no category — one answered, one open

### Return to home base — **not a category, and not a constraint**

**CONFIRMED:**

> *"It is not a restraint. It is business model. It is the same model used by tanker
> companies. All tanks are returned to home base. No different here."*

This answers a question I asked wrongly. I asked where the constraint should live; it is not a
constraint. **It is the shape of a day**, not a property of a load.

The difference is operational, not semantic:

| A constraint | A business model |
|---|---|
| Checked per load | Assumed for every day |
| Can be violated, flagged, overridden | Defines what a day *is* |
| Belongs in scoring | Belongs in the Capacity Plan |

Every Capacity Plan starts and ends at home base. Loads are evaluated *within* that frame; the
frame is not evaluated against them. **The engine never scores a load for returning home,
because every load returns home.**

This is the same reasoning that retired deadhead. If the truck comes home regardless, coming
home is a constant, and scoring a constant only adds noise.

### It is still policy, because it is not universal

A tanker fleet returns to base. A long-haul operator runs out for a week and sleeps in the
cab. Both are business models, and the engine must serve either — so the *pattern* is a Policy
Profile value that the Capacity Plan reads when it builds a day:

```json
"operating_pattern": "daily_return_to_base"
```

Not a score. Not a threshold. Not a toggle to be switched off mid-week. A statement of what
this business is, which the planner obeys when it lays out a day.

**Consequence:** `reserve_capacity.protect_return_home` was drafted as a boolean, which framed
the business model as an option. It should be the operating pattern instead.

### Broker trust — **not a category. Not the program's business.**

**CONFIRMED:**

> *"Trust is assumed until broken, and is not a program issue. It is a human issue."*

This closes the last gap, and it does so by removing the question rather than answering it.
**The engine does not assess trust.** It does not rate brokers, compute a reliability figure,
or decide who is dependable. That judgement is the operator's, formed the way such judgements
are actually formed — by being paid, or not.

**The avoid list is not a contradiction of this.** The list is a decision the operator has
already made; the engine merely honours it. Enforcing a human's recorded decision is mechanical.
Forming the judgement behind it is not, and the engine does neither the forming nor the
reviewing.

| The engine may | The engine may not |
|---|---|
| Refuse a load from a broker on the avoid list | Decide who belongs on the avoid list |
| Report that a broker settled and is now on USE | Score a broker's reliability |
| Warn that the same broker was overridden three times | Prefer a known broker over an unknown one |

**The fifteen categories are therefore complete.** Nothing is missing; the sixteenth was never
a category.

### CONFIRMED DEFECT: the engine scores broker trust today

`dispatch/scoring.py`, in `compute_score`:

```python
broker = load.get("broker_intelligence", "")
if broker:
    bl = broker.lower()
    if "reliable" in bl or "completed" in bl:
        score += 10
    elif "unknown" in bl or "no history" in bl:
        score += 3
```

Ten points of a hundred for a broker the engine believes is reliable, three for one it does not
recognise. That is the engine forming exactly the judgement the operator has ruled is his — and
it fails his rule in the specific direction that matters: **an unknown broker is penalised
seven points, when trust is supposed to be assumed until broken.**

It also decides by string-matching English prose, so a broker described as *"no history of
late payment"* scores as though they had no history at all.

**This comes out.** Broker reliability is not a scoring dimension. Whether a *replacement*
exists — a plain fact such as "first time with this broker" shown beside the load without a
number attached — is a presentation question, not a scoring one.

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

---

## 5. What this leaves in the blocking stage

With every impossibility moved to the filter, **blocking now holds only conditions the
operator might genuinely overrule**:

| Blocking condition | Why it is not a filter |
|---|---|
| **Below floor** | A price judgement. He may take a thin load for a reason the engine cannot see. |
| **Broker on the avoid list** | Business trust. Arrears get paid, and the remedy is the USE list. |
| **Territory `hard_no`** | A business judgement, and business judgements change. |

**Consequence for `DISPATCH_OVERRIDE_RULES_SPEC.md`:** its `not_permitted` list — conditions
that exist but may never be overridden — is now **empty by construction**. A condition nobody
may overrule never reaches the point of being overridden, because it never entered evaluation.

That is a simplification worth naming. The specification previously carried two mechanisms for
impossibility: a filter, and an unoverrideable block. One of them was redundant, and the
operator's ruling removed it.
