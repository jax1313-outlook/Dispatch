# JOE WORKER IMPLEMENTATION PLAN
**Document ID:** 04_JOE_IMPLEMENTATION_PLAN.md / JOE_IMPLEMENTATION_PLAN.md
**Status:** BINDING IMPLEMENTATION PLAN
**Authority:** Mike Zachary / Dispatch Platform Doctrine

---

## 1. CURRENT STATE & MISSING COMPONENTS

### Current State
Joe is defined in Dispatch doctrine as the primary operational voice capture and driver communication assistant. Existing endpoints and templates support dictation capture and driver cockpit views.

### Missing Components
1. Dedicated `JoeWorker` class enforcing Constitution boundaries.
2. Direct handoff mechanism from Joe dictation parsing to `OpportunityCard` creation.
3. Configurable JSON settings in `config/workers/joe_config.json`.
4. Independent test suite in `tests/workers/test_joe.py`.

---

## 2. INTEGRATION POINTS & ENHANCEMENTS

### Integration Points
- **Module Path**: `dispatch operations/workers/joe/worker.py` & `dispatch/workers/joe/worker.py`
- **Config Path**: `dispatch operations/config/workers/joe_config.json`
- **Subsystem Interfaces**: `dispatch.opportunities.OpportunityPipeline`, `portal.routes.api_routes`, `portal.models.identity`.

### Required Enhancements
1. **Dictation Parsing Engine**: Parse free-form driver speech into structured fields (origin, destination, weight, equipment, rate, dates).
2. **Opportunity Card Ingestion**: Call `OpportunityPipeline.ingest_opportunities()` to create an `OpportunityCard` in `UNEVALUATED` state.
3. **70 MPH Cockpit Compliance**: Ensure all driver-facing prompts pass the 70 MPH Phone Call Test (arm's-length legibility, high contrast, minimal tap targets).
4. **Boundary Guard**: Fail-closed check ensuring Joe cannot commit loads, approve rates, or alter Constitutions.

---

## 3. TESTING APPROACH

`test_joe.py` will verify:
- Dictation capture correctly creates structured `OpportunityCard`.
- Joe worker respects constitutional boundaries (blocks commitment attempts).
- Handoff event is emitted cleanly to `INTELLIGENCE`.

---

## 4. REQUIRED FINAL QUESTION: LOAD MOVEMENT SUMMARY

In the context of Joe Worker:
- **Joe** receives driver voice input ("Picked up 40,000 lbs reefer in Atlanta for $2500").
- **Joe** creates the `OpportunityCard` (State 2 Possible Future).
- **Intelligence** scores the load.
- **Mike** commits the load on LOADS screen (State 1 Current Reality).
- **Publisher** generates rate confirmation and Outlook email draft.
- **Mike** reviews and sends email in Outlook.
- **Dispatch** executes load (POP/POD uploads).
- **Archive** closes and stores load permanently.
