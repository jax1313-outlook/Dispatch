# INTELLIGENCE WORKER IMPLEMENTATION PLAN
**Document ID:** 05_INTELLIGENCE_IMPLEMENTATION_PLAN.md / INTELLIGENCE_IMPLEMENTATION_PLAN.md
**Status:** BINDING IMPLEMENTATION PLAN
**Authority:** Mike Zachary / Dispatch Platform Doctrine

---

## 1. PRE-COMMIT LIFECYCLE & INTEGRATION

The Intelligence Worker owns the pre-commit evaluation lifecycle. It collects opportunity data, evaluates dynamic capacity across 6 physical and temporal dimensions, scores freight opportunities, recommends calendar placement, and presents alternatives to Mike.

### LOADS & Scoring Integration
- **Module Path**: `dispatch operations/workers/intelligence/worker.py` & `dispatch/workers/intelligence/worker.py`
- **Integrations**: `dispatch.capacity.DynamicCapacityEngine`, `dispatch.scoring.scoring_engine`, `dispatch.opportunities.OpportunityPipeline`.

### 6 Dynamic Capacity Dimensions
1. **Physical Capacity**: Truck/trailer weight (lbs), volume (cu ft), door dimensions, deck height.
2. **Time Capacity**: Hours of Service (HOS) clock, drive time remaining, loading/unloading window buffer.
3. **Position Capacity**: Deadhead mileage, origin proximity, destination positioning for next load.
4. **Reserve Capacity**: Buffer for unexpected detention, weather delay, or maintenance.
5. **Cargo Arrangement**: Pallet layout, weight distribution across axles, trailer load arrangement plan.
6. **Stop Sequence**: Multi-stop routing logic, appointment window order, geographic progression.

---

## 2. RECOMMENDATION FLOW & COMMIT BOUNDARY

### Recommendation Flow
1. Consume `OpportunityCard` in `UNEVALUATED` state.
2. Evaluate 6 capacity dimensions against active fleet data in `dispatch/capacity.py`.
3. Compute consumption % metrics:
   - Weight Consumption %
   - Volume Consumption %
   - Pallet Consumption %
   - Time Consumption %
4. Generate calendar placement recommendation.
5. Present card with score badge and recommendation string:
   > `"This is a recommendation only. No action is authorized. Mike decides."`

### Commit Boundary
- The Intelligence Worker **stops at Mike Zachary**.
- The worker cannot commit loads, accept offers, or advance state to Current Reality.
- Only Mike's authenticated action on the LOADS screen triggers commitment.

---

## 3. TESTING APPROACH

`test_intelligence.py` will verify:
- Dynamic capacity evaluation calculates accurate consumption metrics.
- Recommendation string is attached to every evaluated opportunity.
- Stop condition at Mike's commit gate is strictly enforced.

---

## 4. REQUIRED FINAL QUESTION: LOAD MOVEMENT SUMMARY

In the context of Intelligence Worker:
- **Joe** captures dictation into an `OpportunityCard`.
- **Intelligence** evaluates the 6 capacity dimensions, scores the opportunity, and recommends calendar placement.
- **Mike** commits the load on LOADS screen (State 1 Current Reality).
- **Publisher** generates rate confirmation and Outlook email draft.
- **Mike** reviews and sends email in Outlook.
- **Dispatch** executes load (POP/POD uploads).
- **Archive** closes and stores load permanently.
