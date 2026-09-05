"""Dispatch Spine — deterministic runtime backbone.

Six schemas: WorkItem, Event, PortalCard, ApprovalEvent, ConflictEvent,
AuditEvent. Field names and types follow
docs/DISPATCH_SPINE_SPECIFICATION_v1.md Sections 5-14.

Persistence: same SQLite file as dispatch.db (see dispatch.spine.db and
DISPATCH_STAGE4_SPINE_SCHEMA_DESIGN_v1.md for why).

The Spine does not reason, approve, replace Manager, replace Portal, or
replace Mike -- it owns state, routing mechanics, validation, and audit
trail only. See docs/DISPATCH_CONSTITUTION_v3.md Section 6.4.
"""
