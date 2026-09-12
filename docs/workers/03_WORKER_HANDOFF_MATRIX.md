# DISPATCH WORKER HANDOFF MATRIX
**Document ID:** 03_WORKER_HANDOFF_MATRIX.md / WORKER_HANDOFF_MATRIX.md
**Status:** BINDING WORKFLOW MATRIX
**Authority:** Mike Zachary / Dispatch Platform Doctrine

---

## 1. WORKFLOW PIPELINE OVERVIEW

The Dispatch worker pipeline moves a freight load through six deterministic handoff stages:

`Joe` → `Intelligence` → `Mike (Commit Gate)` → `Publisher` → `Dispatch Execution` → `Archive`

---

## 2. COMPREHENSIVE HANDOFF SPECIFICATION MATRIX

| Stage Transition | Trigger | Input | Output | Record Updated | Authority Boundary |
|---|---|---|---|---|---|
| **1. Joe → Intelligence** | Voice dictation completed or API dictation submitted | Raw dictation text / audio stream | Structured `OpportunityCard` (state: `UNEVALUATED`) | `OpportunityPipeline` store, Spine Work Item | Joe creates candidate; cannot evaluate capacity or score. |
| **2. Intelligence → Mike** | Ingestion of `UNEVALUATED` Opportunity Card | `OpportunityCard` + Fleet Capacity Data + Calendar | Scored `OpportunityCard` + Calendar Recommendation | `OpportunityCard` metadata, Spine Evaluation Record | Intelligence recommends; stops at Mike's Commit Gate. |
| **3. Mike → Publisher** | Authenticated `COMMIT` click by Mike Zachary | Scored `OpportunityCard` + Approval Event | Realized `Mission Card` (State 1 Current Reality) | Spine Work Item (`MIKE_APPROVED`), Load Record created | ONLY Mike commits. System never infers commitment. |
| **4. Publisher → Human Review** | Commitment event notification (`COMMITMENT_REALIZED`) | Realized `Mission Card` + Library Assets | Rate Confirmation PDF Packet + Outlook Email Draft | `PublisherAction` record, Outlook Draft Queue | Publisher generates packet/email; cannot send email autonomously. |
| **5. Human Review → Dispatch** | Mike clicks `SEND` in Outlook / Control Center | Outlook Email Draft + Rate Confirmation Packet | Sent Rate Confirmation + Active Dispatch Load | Load Status (`DISPATCHED`), Communication Audit Log | ONLY Mike authorizes outbound email transmission. |
| **6. Dispatch → Archive** | Load delivery completed & POD uploaded | Driver POD/POP evidence files + Load Record | Verified Load Record + Complete Evidence Package | Load Status (`DELIVERED` / `POD_VERIFIED`) | Driver provides proof; system verifies integrity. |
| **7. Closeout → Archive** | Financial settlement & operational closeout | Verified Load Record + Settlement Data | Immutable `Archive Artifact` | `cin_lite/Archive` store, Portal Archive Record | Final closeout seals the load record permanently. |

---

## 3. HANDOFF ANOMALY & STOP CONDITIONS

If any transition encounters invalid data or a boundary violation, the handoff runner enforces fail-closed behavior:

1. **Unconfigured Physical Asset**: Yields `NEEDS_REVIEW` or `INSUFFICIENT_DATA` rather than guessing capacity.
2. **Missing Approval Event**: `dispatch/spine/commitment.py` raises `CommitmentNotAuthorized`.
3. **Reserved Identity Attempt**: System identities (`PUBLISHER`, `SYSTEM`, etc.) are blocked from human approval fields.
4. **Unverified Evidence**: Uploads without SHA-256 checksum or invalid extensions are refused.

---

## 4. REQUIRED FINAL QUESTION: END-TO-END HANDOFF PATH

Every freight load traverses the handoff matrix in strict order:
- **Joe** captures dictation into an `OpportunityCard`.
- **Intelligence** scores capacity and recommends calendar slot.
- **Mike** reviews on LOADS screen and commits load.
- **Publisher** fetches Library template and prepares rate confirmation PDF + Outlook email draft.
- **Mike** reviews Outlook draft and sends.
- **Dispatch Engine** tracks pickup (POP) and delivery (POD).
- **Archive Engine** closes load and writes immutable archive artifact.
