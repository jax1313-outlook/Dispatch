# DISPATCH WORKER INTEGRATION PLAN
**Document ID:** 02_WORKER_INTEGRATION_PLAN.md / WORKER_INTEGRATION_PLAN.md
**Status:** BINDING INTEGRATION SPECIFICATION
**Authority:** Mike Zachary / Dispatch Platform Doctrine

---

## 1. OVERVIEW & SCOPE

This document specifies the exact integration map for Joe, Intelligence, and Publisher workers inside the existing Dispatch codebase.

Workers do not replace Dispatch architecture. Workers integrate inside existing subsystems:
- `Joe`: Interfaces with `dispatch/opportunities.py`, `portal/routes/`, and `portal/models/identity.py`.
- `Intelligence`: Interfaces with `dispatch/capacity.py`, `dispatch/scoring/`, `dispatch/spine/`, and `portal/routes/`.
- `Publisher`: Interfaces with `portal/models/publisher.py`, `portal/models/library.py`, `reconciliation/adapters/publisher_adapter.py`, and `dispatch/connectors/outlook_connector.py`.

---

## 2. WORKER INTEGRATION MAP

### 2.1 Joe Worker Integration
- **Location**: `dispatch operations/workers/joe/` & `dispatch/workers/joe/`
- **Inputs**: Voice dictation audio/text, Driver location/HOS status, Operator prompts.
- **Outputs**: `OpportunityCard` dict/instance in `UNEVALUATED` state.
- **Database Impact**: Writes to `OpportunityPipeline` store and Spine work item store (`save_opportunity`).
- **API Impact**: `/api/dictation`, `/api/joe/capture`, `/api/opportunities`.
- **UI Impact**: Dictation bar on LOADS screen, Joe Voice Cockpit modal on Driver Portal.
- **Records Touched**: `OpportunityCard`, `SpineWorkItem`.
- **Authority Boundary**: Cannot commit loads or write directly to State 1 Current Reality.

### 2.2 Intelligence Worker Integration
- **Location**: `dispatch operations/workers/intelligence/` & `dispatch/workers/intelligence/`
- **Inputs**: `OpportunityCard` from Joe, 6 Dynamic Capacity dimensions from `dispatch/capacity.py`, Calendar state.
- **Outputs**: Scored `OpportunityCard`, 6-Dimension Capacity Findings, Calendar Placement Recommendation.
- **Database Impact**: Updates `OpportunityCard` fields and Spine evaluation metadata.
- **API Impact**: `/api/opportunities/score`, `/api/capacity/evaluate`, `/api/calendar/recommend`.
- **UI Impact**: LOADS Screen scoring badges, Weight/Volume/Pallet/Time % gauges, Calendar proposed slots.
- **Records Touched**: `OpportunityCard`, `DynamicCapacityEvaluation`, `SpineWorkItem`.
- **Authority Boundary**: Stops at Mike's Commit Gate. May recommend, cannot commit.

### 2.3 Publisher Worker Integration
- **Location**: `dispatch operations/workers/publisher/` & `dispatch/workers/publisher/`
- **Inputs**: Committed `Mission Card` (`load_id`), Rate Confirmation Templates from Library, Archive Examples.
- **Outputs**: Rate Confirmation Packet (PDF/data), Outlook Draft Email payload.
- **Database Impact**: Writes to `portal/models/publisher.py` action queue, Library usage log.
- **API Impact**: `/api/publisher/generate_packet`, `/api/publisher/draft_email`.
- **UI Impact**: Control Center Publisher Action Queue, Outlook Draft Review panel.
- **Records Touched**: `MissionCard`, `PublisherAction`, `LibraryAsset`, `OutlookDraft`.
- **Authority Boundary**: Generates drafts and packets; requires human approval before sending email.

---

## 3. DATABASE & STORAGE IMPACT ANALYSIS

No worker creates a competing database or isolated source of truth. All worker persistence uses Dispatch's established stores:

```
[Dispatch Root / D:\Drive Storage]
   ├── portal/data/               --> Main portal operational SQLite / JSON store
   ├── dispatch/spine/store.py    --> Spine Work Item & Audit Event store
   ├── cin_lite/Archive/          --> Contract & Load Archive store
   └── dispatch operations/config/ --> Worker JSON configuration files
```

---

## 4. ONE CLICK COMMITMENT EXECUTION FLOW

When Mike clicks `COMMIT` on an approved opportunity:
1. `dispatch/spine/commitment.py::realize()` executes, creating/updating the committed load.
2. An event `COMMITMENT_REALIZED` is broadcast to the Worker Framework.
3. `PublisherWorker` automatically activates:
   a. Fetches active rate confirmation template from `reconciliation/adapters/library_adapter.py`.
   b. Generates PDF packet.
   c. Prepares draft email via `dispatch/connectors/outlook_connector.py`.
   d. Places draft in Outlook review queue and notifies Mike in Control Center.

Human authority is preserved: Mike clicked `COMMIT` once, the office work executed automatically, and the final email sits in Outlook waiting for human send confirmation.

---

## 5. REQUIRED FINAL QUESTION: LOAD MOVEMENT SUMMARY

A freight load moves from Joe Voice Capture to Archive via:
1. **Joe Capture**: Dictation → `OpportunityCard` (UNEVALUATED).
2. **Intelligence Analysis**: Dynamic capacity evaluation → Scored `OpportunityCard` + Calendar Recommendation.
3. **Mike Commit Gate**: Authenticated `COMMIT` click → Realized `Mission Card` (State 1 Current Reality).
4. **Publisher Assembly**: Library retrieval → Rate confirmation packet + Outlook draft email.
5. **Human Send Gate**: Mike reviews draft and sends email.
6. **Dispatch Operations**: Pickup → POP upload → Transit → Delivery → POD upload.
7. **Closeout & Archive**: Adjudication → Immutable `Archive Artifact`.
