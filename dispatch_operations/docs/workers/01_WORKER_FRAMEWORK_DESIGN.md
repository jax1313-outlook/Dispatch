# DISPATCH WORKER FRAMEWORK DESIGN
**Document ID:** 01_WORKER_FRAMEWORK_DESIGN.md / WORKER_FRAMEWORK_DESIGN.md
**Status:** BINDING GOVERNANCE AND ARCHITECTURE
**Authority:** Mike Zachary / Dispatch Platform Doctrine

---

## 1. EXECUTIVE SUMMARY & PRINCIPLES

The Dispatch Worker Framework governs bounded, rule-constrained operational workers designed to reduce owner/operator cognitive load while preserving absolute human authority.

Dispatch is an operational freight platform used by a real truck owner/operator running Level 1 Transport equipment. Workers are **not** autonomous AI employees, generic agents, or CRM bots. Workers act inside defined Constitutions with fixed capabilities, explicit boundaries, and deterministic handoff gates.

### Core Governance Directives
1. **The Mike Rule / Human Authority Boundary**: Only Mike Zachary commits freight loads, accepts financial rates, or authorizes external execution. Workers may analyze, recommend, draft, prepare, assemble, and route, but may **never** commit or send communications without human approval.
2. **70 MPH Test**: Every interface, communication, and decision surface must be clear, arm's-length legible, and immediately actionable by a driver operating at highway speeds.
3. **One Identity, Dual State**: `Opportunity Card` and `Mission Card` represent the exact same core business object. Human commitment changes state (from State 2 Possible Future to State 1 Current Reality); commitment never creates duplicate objects.
4. **One Load, One Record, One Click**: After human commitment (`COMMIT`), downstream workers automatically retrieve assets, assemble packets, and generate Outlook drafts without unnecessary manual intervention, while preserving the human send gate.

---

## 2. WORKER REGISTRY & IDENTITY MODEL

The Worker Registry manages worker instantiation, capability validation, and lifecycle tracking.

### Worker Identity Definitions

| Worker ID | Name | Core Purpose | Identity Boundary |
|---|---|---|---|
| `JOE` | Joe Voice & Communication Worker | Voice dictation capture, driver interaction, load intent extraction, routing. | Creates Opportunity Cards; may NOT commit loads or own dispatch workflow. |
| `INTELLIGENCE` | Pre-Commit Freight Intelligence Worker | Dynamic capacity evaluation, load scoring, calendar placement recommendations. | Recommends pre-commit options; stops strictly at Mike's commitment gate. |
| `PUBLISHER` | Commitment Package Publisher Worker | Document packet production, library asset retrieval, Outlook email draft generation. | Generates rate confirmation packets and email drafts; requires human send approval. |

### Reserved Identities & Attribution Rule
`RESERVED_SYSTEM_IDENTITIES` (`{"PUBLISHER", "SYSTEM", "AUTOMATION", "INTELLIGENCE", "LIBRARY", "JOE"}`) may never be recorded as approving or verifying a commitment or policy change. Only authenticated human actions (Mike Zachary) produce `MIKE_APPROVED` or `VERIFIED` statuses.

---

## 3. WORKER LIFECYCLE & CAPABILITIES MODEL

Every worker transitions through a strict state lifecycle:
`CREATED` → `INITIALIZED` → `ACTIVE_EVALUATION` → `HANDOFF_READY` → `HANDOFF_COMPLETED` (or `HALTED` / `ESCALATED`).

### Worker Capabilities Matrix

| Capability | JOE | INTELLIGENCE | PUBLISHER |
|---|---|---|---|
| Voice & Dictation Capture | **YES** | NO | NO |
| Opportunity Card Creation | **YES** | NO | NO |
| 6-Dimension Capacity Scoring | NO | **YES** | NO |
| Calendar Placement Recommendation | NO | **YES** | NO |
| Load Commitment / State Transition | **NEVER** | **NEVER** | **NEVER** (Mike Only) |
| Rate Confirmation Packet Generation | NO | NO | **YES** |
| Library Asset & Archive Retrieval | NO | NO | **YES** |
| Outlook Draft Email Preparation | NO | NO | **YES** |
| Autonomous Email Dispatch | **NEVER** | **NEVER** | **NEVER** (Mike Only) |

---

## 4. RELATIONSHIP & HANDOFF MODEL

Workers operate in a linear, bounded pipeline:
`JOE` → `INTELLIGENCE` → `MIKE (Human Commit Gate)` → `PUBLISHER` → `DISPATCH` → `ARCHIVE`

### Deterministic Handoff Principles
1. Workers do not invent workflow or recipient lists.
2. Every handoff produces a verifiable `HandoffEvent` record carrying SHA-256 checksums, timestamps, source state, and target state.
3. If an anomaly, unconfigured asset, or boundary breach occurs, the worker enters `HALTED` or `NEEDS_REVIEW` state and escalates to human review.

---

## 5. REQUIRED FINAL QUESTION: END-TO-END LOAD LIFECYCLE

### Journey of One Freight Load: From Joe Voice Capture to Archive

Below is the step-by-step operational path showing how a freight load moves through the Dispatch codebase:

```
[1. Joe Voice Capture]
       ↓ (Dictation parsed into Opportunity Card)
[2. Intelligence Worker]
       ↓ (6-Dimension Dynamic Capacity scoring & Calendar recommendation)
[3. Mike Commit Gate]
       ↓ (Human authenticated COMMIT click -> State 1 Current Reality)
[4. Publisher Worker]
       ↓ (Library asset retrieval, Rate Confirmation PDF, Outlook draft generated)
[5. Human Review & Send Gate]
       ↓ (Mike clicks Send in Outlook)
[6. Active Dispatch Execution]
       ↓ (Pickup -> POP upload -> Transit -> Delivery -> POD upload)
[7. Closeout & Archive]
       ↓ (Financial adjudication & Immutable Archive Artifact created)
```

#### Detailed Stage Breakdown:

1. **Joe Voice Capture**
   - **Worker**: `JOE`
   - **Trigger**: Driver speaks dictation via voice input or API endpoint (`/api/dictation` or `/api/joe/capture`).
   - **Business Object**: Creates `Opportunity Card` in `UNEVALUATED` state.
   - **Database Update**: Saved in `OpportunityPipeline` store and Spine work item repository.
   - **State Transition**: `DRAFT` → `UNEVALUATED`.
   - **Handoff**: `JOE` passes Opportunity Card folder to `INTELLIGENCE`.

2. **Intelligence Analysis & Recommendation**
   - **Worker**: `INTELLIGENCE`
   - **Trigger**: Receipt of `UNEVALUATED` Opportunity Card.
   - **Action**: Evaluates 6 Dynamic Capacity dimensions (Physical, Time, Position, Reserve, Cargo Arrangement, Stop Sequence), runs Scoring Engine, calculates consumption % metrics (Weight, Volume, Pallet, Time), recommends calendar placement.
   - **Business Object**: Updates `Opportunity Card` with score and recommendations.
   - **Database Update**: Persisted in `dispatch/opportunities.py` & `dispatch/capacity.py`.
   - **State Transition**: `UNEVALUATED` → `EVALUATED` / `RECOMMENDED`.
   - **Handoff**: `INTELLIGENCE` presents Card on LOADS Screen / Calendar for Mike Zachary.

3. **Human Authority Commitment Gate (Mike Zachary)**
   - **Worker**: `MIKE` (Human Operator - sole authority)
   - **Trigger**: Mike reviews Card and performs authenticated `COMMIT` action.
   - **Action**: `dispatch/spine/commitment.py::realize()` verifies `MIKE_APPROVED` state and approval event.
   - **Business Object**: Opportunity Card becomes Committed `Mission Card` (`load_id` preserved).
   - **Database Update**: Core load created via `dispatch/services.py::create_load()`, rate confirmed via `confirm_rate()`.
   - **State Transition**: `RECOMMENDED` → `COMMITTED` / `DISPATCHED` (State 1 Current Reality).
   - **Handoff**: One-Click Commitment event triggers `PUBLISHER`.

4. **Publisher Document & Communication Generation**
   - **Worker**: `PUBLISHER`
   - **Trigger**: Receipt of Committed Mission Card event.
   - **Action**: Consumes `Mission Card`, queries `reconciliation/adapters/library_adapter.py` for rate confirmation templates, incorporates past `reconciliation/adapters/archive_adapter.py` examples, builds rate confirmation packet, generates draft email via `dispatch/connectors/outlook_connector.py`.
   - **Business Object**: Produces `Publisher Packet` & `Outlook Email Draft`.
   - **Database Update**: Action recorded in `portal/models/publisher.py`.
   - **State Transition**: `COMMITTED` → `PACKET_GENERATED` / `DRAFT_READY`.
   - **Handoff**: `PUBLISHER` routes email draft to Outlook for Mike's final review.

5. **Human Review & Email Send Gate**
   - **Worker**: `MIKE` (Human Operator)
   - **Trigger**: Outlook Draft notification in Control Center / Outlook.
   - **Action**: Mike inspects draft email and attached rate confirmation PDF, then clicks `SEND`.
   - **State Transition**: `DRAFT_READY` → `COMMUNICATION_SENT`.
   - **Handoff**: Active freight movement begins.

6. **Active Dispatch Operations (Pickup, POP, Delivery, POD)**
   - **Worker**: Dispatch Engine & Driver Cockpit
   - **Action**:
     - Pickup at Origin → Driver uploads Proof of Pickup (`POP` / BOL with SHA-256 hash).
     - Transit → GPS/milestone updates recorded.
     - Arrival at Destination → Driver uploads Proof of Delivery (`POD`).
   - **Business Object**: `Mission Record` updated with evidence files.
   - **Database Update**: Saved in `portal/data` evidence store and load record.
   - **State Transition**: `COMMUNICATION_SENT` → `IN_TRANSIT` → `DELIVERED` → `POD_VERIFIED`.
   - **Handoff**: Handoff to Closeout & Archive.

7. **Closeout & Archive**
   - **Worker**: Reconciliation & Archive Engine
   - **Action**: Verifies all required artifacts (POP, POD, Rate Confirmation, Settlement), closes load financially and operationally, generates immutable Archive Artifact.
   - **Business Object**: `Archive Artifact` stored in `cin_lite/Archive` and `D:\Archive\CIN`.
   - **Database Update**: Immutable archive entry saved via `portal/models/archive.py`.
   - **State Transition**: `POD_VERIFIED` → `CLOSED` → `ARCHIVED`.
