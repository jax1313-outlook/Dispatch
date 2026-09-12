# COMMIT TRANSACTION TRACE
**Document ID:** COMMIT_TRANSACTION_TRACE.md
**Status:** VERIFIED & TRACED
**Authority:** Mike Zachary / Dispatch Platform Doctrine

---

## 1. LITERAL COMMIT TRANSACTION TRACE

Below is the exact step-by-step trace of the `COMMIT` transaction in the Dispatch platform:

```
[LOA01: Human Action]
Mike Zachary clicks COMMIT on LOADS screen
  │
  ▼
[LOA02: Opportunity Pipeline]
dispatch.opportunities.OpportunityPipeline.request_commitment(opportunity_id, human_actor="Mike Zachary")
  ├─ Validates human_actor is not empty or a reserved system identity.
  ├─ Calls card.request_transition("approved", actor_id="Mike Zachary", actor_type="human_authority").
  └─ Creates ApprovalEvent(action="APPROVE_LOAD_PURSUIT", new_state="MIKE_APPROVED") in Spine store.
  │
  ▼
[LOA03: Spine State Transition]
dispatch.spine.store.apply_transition(work_item_id, "MIKE_APPROVED")
  └─ Spine Work Item state updated to MIKE_APPROVED.
  │
  ▼
[LOA04: Commitment Realization]
dispatch.opportunities.OpportunityPipeline.realize_commitment(opportunity_id, actor_id="Mike Zachary")
  ├─ Invokes dispatch.spine.commitment.realize(work_item_id, actor_id="Mike Zachary", opportunity=card.to_dict()).
  ├─ Verifies work item is in MIKE_APPROVED and carries valid human approval event.
  ├─ Calls dispatch.services.create_load() -> Writes load into State 1 Current Reality.
  ├─ Calls dispatch.services.confirm_rate() -> Locks negotiated rate and distance.
  ├─ Updates card.linked_load_id = load["load_id"] (preserving single Opportunity identity).
  └─ Emits AuditEvent(action="REALIZED_COMMITMENT").
  │
  ▼
[LOA05: Downstream Activation]
Publisher Worker activated
  ├─ Consumes committed Mission Card data.
  ├─ Queries portal.models.library for approved company assets.
  ├─ Creates Publisher Action in portal.models.publisher.create_action().
  └─ Prepares Outlook Email Draft payload (status: DRAFT_READY_FOR_HUMAN_REVIEW).
```

---

## 2. ONE RECORD / ONE IDENTITY PROOF

- **Identity Continuity**: The `opportunity_id` (e.g. `OPP-7C921445`) remains the single primary identity throughout analysis, commitment, execution, closeout, and archive.
- **Role of `linked_load_id`**: When Spine realizes commitment, `linked_load_id` is assigned the State 1 Current Reality load reference ID. This is a technical correlation key, not a duplicate business record. Commitment changes state on the same underlying freight load.

---

## 3. CAPACITY CONSUMPTION & CALENDAR FIXATION

- **Calendar Fixation**: Upon commitment, proposed calendar slot becomes fixed placement in State 1. `OutlookConnector` is notified with authorization reference `APPROVE_LOAD_PURSUIT`.
- **Capacity Consumption**: Weight, volume, pallets, and drive hours are formally locked into State 1 active fleet capacity, subtracting from available daily capacity.
