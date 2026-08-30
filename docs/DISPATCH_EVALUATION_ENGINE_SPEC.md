# DISPATCH EVALUATION ENGINE SPEC

Status: SPECIFICATION. Not implemented. No runtime behaviour is changed by this document.

---

## 1. What the engine is

The evaluation engine takes a Mission Record and a Policy Profile and returns an
**Evaluation**. It touches no network, calls no language model, reads no clock it was not
given, and writes nothing.

```
evaluate(record, profile, now, candidate_run=None) -> Evaluation
```

`candidate_run` is the run this opportunity would join. **Capacity is contextual:** a
two-pallet load is never over capacity by itself, only when added to what is already on a
particular day's run. The engine must therefore evaluate against **remaining** capacity,
not against an empty vehicle.

With `candidate_run=None` it falls back to the empty vehicle — the single-broker,
whole-truck case — so the model degrades correctly to the simple shape. See
`DISPATCH_LOAD_ARRANGEMENT_SPEC.md` §7a.

Deterministic and total: same three inputs, same output, always. `now` is passed in, never
read from the system clock inside the engine — otherwise the same record evaluates
differently on two machines and nothing can be tested.

## 2. The Evaluation

The engine's whole output. Every field is stored with the record.

```
Evaluation
  profile_version         which policy produced this
  evaluated_at            when
  admitted                bool   - did it pass FILTER
  filter_reason           why not, if not

  matched_vehicle         which vehicle in the fleet can take this, or none
  candidate_run           which run this was evaluated against, if any
  remaining_after         weight / cube / pallet left on that run if taken
  dimensions              the named dimensions, each with value + reason + origin
  conditions              blocking / warning / informational / unknown, each with reason
  disqualified            bool   - any BLOCKING condition fired
  disqualifying_conditions

  score                   0-100  - fit only, risk excluded
  classification          band name
  sort_key                how it orders in the list

  recommended_action      what the rules support
  recommendation_reason
  confidence              HIGH / MEDIUM / LOW
  confidence_reason

  reasons                 why it scored as it did
  risks                   what could go wrong
  missing_information     what was not known
```

Three separate outputs — classification, recommendation, confidence — never one number
wearing three hats.

## 3. Order of operations

The order is load-bearing. Changing it changes meaning.

```
1  NORMALISE     record -> engine vocabulary. No judgement.
2  FILTER        does this enter the decision lane at all?
3  CONDITIONS    blocking / warning / informational / unknown
4  DIMENSIONS    the named dimensions, each scored and explained
5  SCORE         combine dimensions into fit. Risk is NOT folded in.
6  CLASSIFY      bands - but BLOCKING wins first
7  RECOMMEND     from classification + conditions + profile rules
8  CONFIDENCE    from information completeness, NOT from score
9  SORT KEY      presentation order
```

### Vehicle matching happens at step 3

Capability conditions are evaluated against the **active fleet**, not against a single set
of numbers. A load is blocked on capability only when **no active vehicle can take it**.

```
for each active vehicle in profile.fleet:
    can it carry the pallets, the weight, the equipment, the endorsements?
if none can  -> BLOCKING, capability
if one can   -> matched_vehicle = that one
if several   -> matched_vehicle = the cheapest to run for this load
```

`matched_vehicle` is recorded on the Evaluation. Downstream, fuel and margin are computed
from **that vehicle's** cost per mile, so the same load can show a different margin
depending on which vehicle takes it.

With one vehicle this reads identically to a flat capability check. With three it is the
only correct rule, and it costs nothing to build it this way now — see
`DISPATCH_POLICY_PROFILE_SPEC.md` §4.8.

### Why conditions come before dimensions

A blocking condition is not a bad score — it is a disqualification. Evaluating it early
means the engine can state *"disqualified: outside operating footprint"* without the
operator having to interpret a number.

### Why score excludes risk

**This is the correction to current Dispatch.** `compute_score()` today deducts points for
hard stops, overweight and detention history, which produces a single number meaning
"fit, minus some risk, minus some position penalty". That number cannot be explained,
because two loads scoring 70 may have nothing in common.

Fit and risk are reported side by side. The operator sees *"strong fit, three risks"* —
which is what they actually need to know.

## 4. Dimensions

Each dimension returns `value`, `reason`, and `origin` (SOURCE / DERIVED / HUMAN /
UNKNOWN). Never a bare number.

| Dimension | Question | Lineage |
|---|---|---|
| **Operational Fit** | Can this truck do this load? | new (equipment, weight, HOS) |
| **Financial Value** | What does it pay after cost? | current Dispatch `compute_economic_opportunity` |
| **Growth Potential** | Does it open something? | v1.3.3 `growth()` |
| **Return Position Value** | Where does it leave me? | current Dispatch `compute_position_impact`, `compute_tomorrow_position_risk` |
| **Mission Risk** | What could go wrong? | current Dispatch `compute_route_risk`, `compute_hos_risk` |
| **Information Completeness** | How much do I actually know? | **new** |
| **Utilization** | How full does this leave the van — weight, cube, pallets? | operator model, 30 Aug 2026 |
| **Service Risk** | Tight windows, high dwell, appointment vs FCFS | operator model, 30 Aug 2026 |
| **Complexity** | Stops, handling, compatibility — how hard is this day? | operator model, 30 Aug 2026 |

**Complexity never folds into profit.** The question an owner-operator actually asks is
*"is the extra money worth the extra hassle"*, and that question only exists while the two
are separate numbers. Merge them and the engine will keep recommending loads that pay well
and cost the operator their evening.

See `DISPATCH_LOAD_ARRANGEMENT_SPEC.md` for the load, stop and cargo structure these three
dimensions read from.

**Dimensions are never collapsed into one unexplained score.** They are stored separately,
displayed separately, and each carries its own reason.

The mission brief lists these plus `Recommended Action`, `Confidence`, `Reasons`, `Risks`,
`Missing Information` and `Override Requirement` — those are Evaluation fields rather than
dimensions, and appear in §2.

## 5. Rules the engine obeys

1. **No network, no model, no clock.** Anything time-dependent is passed in.
2. **No writes.** The engine returns an Evaluation; the caller stores it.
3. **No state changes.** The engine never advances a status or crosses a gate.
4. **Total.** Every input produces an Evaluation, including a nearly-empty record — that
   one comes back with low completeness, `UNKNOWN` dimensions, and low confidence.
5. **No exceptions for missing data.** Missing is a value, not an error.
6. **Explainable.** Every number has a reason string. An unexplainable score is a defect.
7. **Re-evaluation is additive.** A new Evaluation attaches to the record; it does not
   overwrite the one the human saw when they decided.

## 6. What the engine may not do

| Forbidden | Why |
|---|---|
| Decide, approve, accept, book | Human final authority |
| Send anything | Not its boundary |
| Advance a state or cross a gate | Gates are crossed by humans |
| Fabricate a missing value | See Fact and Provenance doctrine |
| Silently drop a record | Filtering is recorded with a reason |
| Read the system clock | Breaks determinism and testability |
| Call a language model | Breaks determinism |

## 7. Testability

The engine's determinism is what makes it testable, so the tests are stated here as part
of the specification:

- **Fixture-driven.** A record plus a profile plus a fixed `now`, with an expected
  Evaluation. No mocks needed — there is nothing to mock.
- **Doctrine tests, not implementation tests.** `test_blocking_condition_cannot_be_outvoted`
  asserts that a record with a blocking condition and a 100-point fit is still
  disqualified. That test should be written before the code and will fail today.
- **Both directions.** Every guard is tested for firing when it should *and* not firing
  when it should not. A guard only tested one way is a guard that may be permanently on.
