# DISPATCH_SPINE_SPECIFICATION_v1.md

**Document Type:** Deterministic Runtime Specification  
**Program:** Dispatch  
**Owner:** Mike Zachary / Level 1 Transport  
**Status:** Build-Readiness Specification Draft  
**Authority:** Mike Zachary remains final authority  

---

## 1. Purpose

The Dispatch Spine is the deterministic runtime backbone of Dispatch.

The Spine exists to make routine system behavior reliable, auditable, and boring. The Spine handles state, routing mechanics, validation, queues, scoring formulas, event records, audit records, storage behavior, and approved automation hooks.

The Spine does not reason. The Spine does not approve. The Spine does not replace Manager. The Spine does not replace Portal. The Spine does not replace Mike.

---

## 2. Core Rule

The Dispatch Spine handles deterministic execution.

Cognitive functions handle reasoning, interpretation, drafting, and judgment support only when deterministic logic is insufficient.

All business authority remains with Mike Zachary.

---

## 3. Spine Responsibilities

The Spine owns these deterministic functions:

- work item creation
- work item state tracking
- allowed state transitions
- routing table execution
- queue assignment
- required field validation
- schema validation
- scoring formula execution
- event logging
- audit logging
- Portal card generation triggers
- approval event recording
- conflict event recording
- Archive handoff triggers
- Library candidate routing
- approved automation hooks

---

## 4. Spine Non-Responsibilities

The Spine must not:

- approve anything
- submit anything externally
- book a load
- sign a document
- certify compliance
- decide rates
- decide legal sufficiency
- decide government pursuit
- invent missing facts
- interpret business meaning beyond deterministic rules
- replace Manager reasoning
- replace Intelligence analysis
- replace Publisher drafting
- replace Portal visibility
- replace Mike authority

---

## 5. Work Item Schema

A work item is the base unit of Dispatch work.

Minimum fields:

- work_item_id
- created_at
- updated_at
- source_type
- source_id
- current_state
- priority
- consequence_level
- assigned_function
- required_action
- source_confidence
- due_date
- related_files
- source_refs
- validation_status
- scoring_status
- cognitive_status
- portal_card_id
- final_disposition

Example:

```json
{
  "work_item_id": "uuid",
  "created_at": "2026-08-10T00:00:00Z",
  "updated_at": "2026-08-10T00:00:00Z",
  "source_type": "government_opportunity",
  "source_id": "SAM-EXAMPLE-001",
  "current_state": "CREATED",
  "priority": "MEDIUM",
  "consequence_level": 2,
  "assigned_function": "Intelligence Analyst",
  "required_action": "Analyze opportunity requirements",
  "source_confidence": "SOURCE_PRESENT",
  "due_date": null,
  "related_files": [],
  "source_refs": [],
  "validation_status": "PENDING",
  "scoring_status": "NOT_REQUIRED",
  "cognitive_status": "NOT_STARTED",
  "portal_card_id": null,
  "final_disposition": null
}
```

---

## 6. State List

Approved initial state list:

- CREATED
- VALIDATION_PENDING
- VALIDATION_FAILED
- VALIDATED
- SCORING_PENDING
- SCORED
- COGNITIVE_REVIEW_PENDING
- COGNITIVE_REVIEW_COMPLETE
- ROUTING_PENDING
- ROUTED_TO_MANAGER
- ROUTED_TO_INTELLIGENCE
- ROUTED_TO_PUBLISHER
- ROUTED_TO_LIBRARY_REVIEW
- ROUTED_TO_ARCHIVE
- PORTAL_CARD_PENDING
- PORTAL_CARD_CREATED
- WAITING_FOR_MIKE
- MIKE_APPROVED
- MIKE_REJECTED
- MIKE_REQUESTED_REVISION
- DEFERRED
- CONFLICT_RAISED
- CONFLICT_RESOLVED
- COMPLETED
- ARCHIVED

---

## 7. Allowed State Transitions

The Spine must only permit approved transitions.

Initial transition model:

- CREATED may move to VALIDATION_PENDING.
- VALIDATION_PENDING may move to VALIDATED or VALIDATION_FAILED.
- VALIDATION_FAILED may move to CONFLICT_RAISED or ARCHIVED.
- VALIDATED may move to SCORING_PENDING, COGNITIVE_REVIEW_PENDING, ROUTING_PENDING, or PORTAL_CARD_PENDING.
- SCORING_PENDING may move to SCORED or CONFLICT_RAISED.
- SCORED may move to COGNITIVE_REVIEW_PENDING, ROUTING_PENDING, or PORTAL_CARD_PENDING.
- COGNITIVE_REVIEW_PENDING may move to COGNITIVE_REVIEW_COMPLETE or CONFLICT_RAISED.
- COGNITIVE_REVIEW_COMPLETE may move to ROUTING_PENDING or PORTAL_CARD_PENDING.
- ROUTING_PENDING may move to ROUTED_TO_MANAGER, ROUTED_TO_INTELLIGENCE, ROUTED_TO_PUBLISHER, ROUTED_TO_LIBRARY_REVIEW, ROUTED_TO_ARCHIVE, or CONFLICT_RAISED.
- PORTAL_CARD_PENDING may move to PORTAL_CARD_CREATED or CONFLICT_RAISED.
- PORTAL_CARD_CREATED may move to WAITING_FOR_MIKE.
- WAITING_FOR_MIKE may move to MIKE_APPROVED, MIKE_REJECTED, MIKE_REQUESTED_REVISION, DEFERRED, or CONFLICT_RAISED.
- MIKE_APPROVED may move to COMPLETED, ROUTED_TO_PUBLISHER, ROUTED_TO_LIBRARY_REVIEW, or ROUTED_TO_ARCHIVE.
- MIKE_REJECTED may move to ARCHIVED or COMPLETED.
- MIKE_REQUESTED_REVISION may move to ROUTED_TO_PUBLISHER, ROUTED_TO_INTELLIGENCE, ROUTED_TO_MANAGER, or COGNITIVE_REVIEW_PENDING.
- DEFERRED may move back to ROUTING_PENDING or ARCHIVED.
- CONFLICT_RAISED may move to CONFLICT_RESOLVED, WAITING_FOR_MIKE, or ARCHIVED.
- CONFLICT_RESOLVED may move to VALIDATION_PENDING, ROUTING_PENDING, or PORTAL_CARD_PENDING.
- COMPLETED may move to ARCHIVED.
- ARCHIVED is terminal unless retention policy authorizes later action.

---

## 8. Event Schema

Every meaningful system activity creates an event.

Minimum fields:

- event_id
- timestamp
- work_item_id
- event_type
- actor_type
- actor_id
- previous_state
- new_state
- summary
- source_refs
- requires_audit

Example:

```json
{
  "event_id": "uuid",
  "timestamp": "2026-08-10T00:00:00Z",
  "work_item_id": "uuid",
  "event_type": "STATE_TRANSITION",
  "actor_type": "DISPATCH_SPINE",
  "actor_id": "state_registry",
  "previous_state": "VALIDATION_PENDING",
  "new_state": "VALIDATED",
  "summary": "Required fields validated successfully.",
  "source_refs": [],
  "requires_audit": true
}
```

---

## 9. Portal Card Schema

Portal cards are the human-facing presentation objects.

Minimum fields:

- card_id
- work_item_id
- created_at
- card_level
- card_type
- title
- summary
- source_refs
- recommendation
- decision_needed
- allowed_actions
- required_closing

Approved card levels:

- 0 Silent Log
- 1 Status
- 2 Review
- 3 Decision
- 4 Conflict
- 5 Authority

Required closing:

**This is a recommendation only. No action is authorized. Mike decides.**

---

## 10. Approval Event Schema

Portal approvals produce structured events.

Minimum fields:

- approval_event_id
- timestamp
- work_item_id
- card_id
- approving_user
- approval_type
- approved_action
- comments
- source_refs
- authentication_context

Approved approval types:

- APPROVE_DRAFT
- APPROVE_PACKET
- APPROVE_LIBRARY_PROMOTION
- APPROVE_ARCHIVE_DISPOSITION
- APPROVE_AUTHORITY_ACTION
- APPROVE_REVISION_PATH

No approval event may authorize autonomous external submission unless Mike separately approves that doctrine in writing.

---

## 11. Conflict Event Schema

Conflict events stop progress until resolved or archived.

Minimum fields:

- conflict_id
- timestamp
- work_item_id
- conflict_type
- affected_layer
- affected_function
- trigger
- details
- options
- recommended_path
- human_decision_needed
- current_state

Conflict types:

- MISSING_SOURCE
- CONTRADICTORY_SOURCE
- ROLE_BOUNDARY_RISK
- AUTHORITY_RISK
- FABRICATION_RISK
- VALIDATION_FAILURE
- COMPLIANCE_RISK
- LEGAL_RISK
- ARCHITECTURE_DRIFT_RISK
- PORTAL_VISIBILITY_RISK

---

## 12. Validation Result Schema

Minimum fields:

- validation_id
- work_item_id
- timestamp
- validator_name
- validation_status
- missing_fields
- failed_rules
- warnings
- source_refs
- next_state

Validation statuses:

- PASS
- FAIL
- WARNING
- NEEDS_SOURCE
- NEEDS_MIKE_DECISION

---

## 13. Scoring Result Schema

Scoring results are deterministic outputs.

Minimum fields:

- scoring_id
- work_item_id
- timestamp
- scoring_model
- score_type
- input_values
- formula_version
- score
- flags
- recommendation_label
- source_refs
- next_state

Scoring may recommend but may not decide.

---

## 14. Audit Event Schema

Audit events preserve traceability.

Minimum fields:

- audit_id
- timestamp
- work_item_id
- event_id
- actor_type
- actor_id
- action
- previous_state
- new_state
- source_refs
- hash
- notes

If hashing is used for provenance, SHA-256 is preferred over MD5.

---

## 15. Routing Table Rules

The routing table maps work type and state to next destination.

Initial routing categories:

- government_opportunity routes to Intelligence Analyst.
- packet_draft routes to Publisher.
- library_candidate routes to Library review.
- completed_record routes to Archive.
- conflict routes to Manager and Portal.
- authority_action routes to Portal Level 5.
- load_or_route_evaluation routes to Spine scoring, Intelligence interpretation, Portal presentation, and Mike decision.

The routing table must be explicit and testable.

No routing rule may create hidden decisions.

---

## 16. Silent Log Rules

Silent logging is allowed only for low-risk routine events that require no human attention.

Silent logs must still be auditable.

Silent logs may not hide:

- authority decisions
- compliance risks
- missing source issues
- failed validation
- business commitment risks
- external exposure risks
- role-boundary violations

---

## 17. Portal Card Generation Rules

The Spine may generate or trigger Portal cards based on consequence level.

Level 0 events are logged silently.

Level 1 events may appear as status.

Level 2 events require optional review.

Level 3 events require Mike decision.

Level 4 events require conflict resolution.

Level 5 events require authority approval.

All Level 3, Level 4, and Level 5 cards must be visible to Mike in Portal.

---

## 18. Error Handling Rules

Errors must not disappear.

Errors must route to one of:

- validation failure
- conflict event
- retry queue
- archive as failed record
- Portal card if human attention is needed

The system must not retry indefinitely without escalation.

---

## 19. Human Approval Gates

Human approval is required for:

- final packet approval
- Library promotion
- external submission
- load booking
- contract commitment
- compliance certification
- doctrine change
- architecture change
- deployment approval
- purge or retention exception

All such approvals must be Portal-mediated and audit-logged.

---

## 20. Build Readiness Standard

The Spine is build-ready only when the following exist:

- schema files or equivalent model definitions
- state transition tests
- routing table tests
- validation tests
- audit event tests
- Portal card tests
- approval event tests
- conflict event tests

Until then, the Spine remains specification-level architecture.

---

## 21. Authority Closing

This specification does not authorize implementation by itself.

No deployment is authorized.

No doctrine change is authorized.

No code merge is authorized.

Mike decides.
