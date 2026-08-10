# SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md

**Document Type:** Security and Authentication Specification  
**Program:** Dispatch  
**Owner:** Mike Zachary / Level 1 Transport  
**Status:** Build-Readiness Specification Draft  
**Authority:** Mike Zachary remains final authority  

---

## 1. Purpose

This specification defines how Dispatch identifies users, authenticates Portal access, assigns authority, records approval actions, and protects role boundaries.

The goal is not to create unnecessary security complexity.

The goal is to ensure Dispatch can answer four questions clearly:

1. Who is this user?
2. How did Dispatch verify this user?
3. What is this user allowed to do?
4. What did this user approve, reject, change, or request?

Dispatch security exists to preserve Mike Zachary's final authority, protect driver and external access boundaries, prevent hidden decisions, and ensure every authority action is traceable.

---

## 2. Core Security Doctrine

### 2.1 Identity Doctrine

Every Dispatch user has a unique identity.

A Dispatch identity is not just a name. It is a controlled system record tied to role, permissions, status, and audit history.

Minimum identity fields:

- user_id
- display_name
- role
- status
- pin_record_id
- created_at
- updated_at
- last_login_at
- permissions
- authority_level

### 2.2 PIN Doctrine

Every Dispatch user has a managed Dispatch PIN.

The PIN is the user's Portal authentication method.

The PIN indicates that the user is claiming the assigned identity.

Dispatch must manage:

- PIN creation
- PIN assignment
- PIN storage
- PIN validation
- PIN change
- PIN reset
- PIN revocation
- PIN expiration if required
- failed PIN attempt handling

A PIN is never treated as casual text.

A PIN is a controlled authentication credential.

### 2.3 Authority Doctrine

Roles determine permissions.

Mike Zachary is the top security authority and final business authority.

Only the Authority role may approve authority-level actions.

Roles do not create business authority beyond what Mike approves.

### 2.4 Audit Doctrine

Every authority action is recorded.

Dispatch must record who performed the action, what role the user carried, what object was affected, what version was involved, what decision was made, and when the action occurred.

No authority action may occur silently.

---

## 3. User Roles

Initial Dispatch roles:

- Authority
- Driver
- External Viewer
- System Service

### 3.1 Authority

The Authority role belongs to Mike Zachary unless Mike explicitly approves another authority role later.

Authority may:

- approve packets
- reject packets
- request revision
- approve Library promotion
- approve Archive deletion or retention exception
- approve load pursuit
- approve deployment
- approve doctrine change
- approve architecture change
- override non-authority recommendations

Authority may not be simulated by AI, automation, or another user.

### 3.2 Driver

Driver users may access driver-facing Portal views only.

Driver users may:

- view assigned work
- view pickup and delivery information
- view route notes
- upload proof photos
- upload POD or delivery records
- submit check-in status
- submit issue notes

Driver users may not:

- approve packets
- approve Library promotion
- delete Archive material
- view proprietary scoring logic
- view internal Intelligence notes unless explicitly shared
- access customer or broker views
- approve load pursuit
- commit Level 1 Transport

### 3.3 External Viewer

External Viewer users include approved customer, broker, or shipper visibility users.

External Viewer users may see only controlled visibility windows approved by Mike.

External Viewer users may not:

- query internal databases
- view proprietary scoring
- view internal Intelligence notes
- view Library internals
- view Archive internals
- trigger internal workflows
- approve anything
- see driver-only details unless approved

### 3.4 System Service

System Service is used for deterministic system activity such as Spine transitions, scheduled checks, validation runs, automated logs, and approved background tasks.

System Service may not approve, submit, book, sign, or certify.

System Service actions must be audit logged when they affect state.

---

## 4. PIN Lifecycle

### 4.1 PIN Creation

PINs are created by an approved PIN management function.

PIN creation must create:

- pin_record_id
- user_id
- role
- created_at
- status
- reset_required flag if applicable

PIN records should store only protected PIN validation material, not plain readable PIN text.

### 4.2 PIN Assignment

Each PIN is assigned to exactly one user identity.

A PIN may not be shared across users.

### 4.3 PIN Validation

When a user attempts Portal login:

1. User enters identity or selects assigned user profile.
2. User enters PIN.
3. Dispatch validates the PIN.
4. Dispatch verifies the role assigned to the identity.
5. Dispatch creates an authenticated session if validation succeeds.
6. Dispatch records successful login.

Failed PIN attempts must be recorded.

Repeated failed PIN attempts should trigger lockout or Manager / Authority review depending on final implementation rules.

### 4.4 PIN Change

Users may change PINs only through approved Portal workflow.

PIN change event must be recorded.

### 4.5 PIN Reset

PIN reset requires Authority approval or approved reset workflow.

Driver and External Viewer PIN resets must not grant new permissions.

### 4.6 PIN Revocation

A PIN may be revoked when:

- user access ends
- suspected compromise occurs
- role changes
- Mike orders revocation
- access review requires revocation

Revoked PINs may not authenticate a Portal session.

---

## 5. Session Model

A successful PIN validation creates a Portal session.

Minimum session fields:

- session_id
- user_id
- role
- started_at
- last_active_at
- status
- authentication_method
- permissions_snapshot

A session answers:

- who is using Portal
- what role is active
- what the user may do
- whether the session is still valid

---

## 6. Permission Model

Permissions are role-based.

Minimum permission categories:

- view_portal
- view_driver_assignment
- upload_driver_document
- view_external_status
- view_internal_card
- approve_draft
- approve_packet
- approve_library_promotion
- approve_archive_action
- approve_load_pursuit
- approve_deployment
- approve_doctrine_change
- approve_architecture_change

### 6.1 Authority Permissions

Authority may carry all approval permissions.

### 6.2 Driver Permissions

Driver carries operational permissions only.

### 6.3 External Viewer Permissions

External Viewer carries visibility permissions only.

### 6.4 System Service Permissions

System Service carries state, validation, logging, and deterministic execution permissions only.

System Service does not carry approval permissions.

---

## 7. Authority Actions

Authority actions require:

- authenticated session
- Authority role
- active permissions snapshot
- Portal-mediated action
- audit record

Authority actions include:

- approve draft
- approve packet
- approve Library promotion
- approve Archive delete or retention exception
- approve external submission
- approve load pursuit
- approve deployment
- approve doctrine change
- approve architecture change

No Authority action may be executed only from a cognitive function result.

Cognitive output may recommend.

Portal and Spine require authenticated Authority approval before execution.

---

## 8. Portal-Mediated Approval Flow

Approval flow:

1. Work item reaches Portal review state.
2. Portal displays card to authenticated user.
3. User action is selected.
4. Portal checks role and permissions.
5. Portal creates approval event.
6. Dispatch Spine records event.
7. Dispatch Spine transitions state if allowed.
8. Audit event is written.

Mike approving something in Portal means:

- Mike was authenticated.
- Mike carried Authority role.
- Mike selected an approved action.
- Dispatch recorded the action.

---

## 9. Approval Event Schema

Minimum approval event fields:

- approval_event_id
- timestamp
- session_id
- user_id
- role
- work_item_id
- portal_card_id
- object_type
- object_id
- object_version
- action
- previous_state
- new_state
- comments
- authentication_context
- audit_id

Example actions:

- APPROVE_DRAFT
- REJECT_DRAFT
- REQUEST_REVISION
- APPROVE_PACKET
- APPROVE_LIBRARY_PROMOTION
- APPROVE_ARCHIVE_DELETE
- APPROVE_ARCHIVE_KEEP
- APPROVE_LOAD_PURSUIT
- REJECT_LOAD_PURSUIT
- APPROVE_DEPLOYMENT

---

## 10. Authentication Context Schema

Minimum authentication context fields:

- authentication_method
- pin_verified
- verified_at
- failed_attempt_count
- session_id
- user_id
- role
- permissions_snapshot_id

Example:

```json
{
  "authentication_method": "DISPATCH_PIN",
  "pin_verified": true,
  "verified_at": "2026-08-10T00:00:00Z",
  "failed_attempt_count": 0,
  "session_id": "uuid",
  "user_id": "MIKE_ZACHARY",
  "role": "Authority",
  "permissions_snapshot_id": "uuid"
}
```

---

## 11. Library and PIN Records

PIN identity records may be stored under controlled Library governance if Mike chooses to treat identity and credential records as approved operational control records.

If Library holds PIN-related information, the Library must not expose readable PIN values to Publisher, Intelligence, Driver users, External Viewers, or cognitive functions.

PIN records are operational security records, not reusable drafting facts.

Publisher may not use PIN records.

Intelligence may not interpret PIN values.

Archive may store audit history of PIN events, not active PIN material.

---

## 12. Security Boundaries by Function

### 12.1 Manager

Manager may see user role, session status, and action outcome when needed for coordination.

Manager may not see plaintext PIN values.

### 12.2 Publisher

Publisher may never access PIN records, authentication secrets, or credential material.

### 12.3 Intelligence Analyst

Intelligence Analyst may never access PIN records, authentication secrets, or credential material.

### 12.4 Library

Library may store approved identity-control records if authorized.

Library must protect credential material from cognitive and production functions.

### 12.5 Archive

Archive stores security event history where appropriate.

Archive does not serve active credentials.

### 12.6 Portal

Portal is the only human-facing authentication surface.

### 12.7 Dispatch Spine

Dispatch Spine validates sessions, permissions, and approval-state transitions.

Spine does not decide authority.

Spine enforces authority.

---

## 13. Driver Portal Security

Driver Portal users authenticate with unique PINs.

Driver users may only access assigned driver scope.

Driver actions must be recorded when they upload or submit operational information.

Driver users cannot approve dispatch, packet, Library, Archive, deployment, or authority actions.

---

## 14. External Viewer Security

External viewers authenticate with unique access credentials or PINs if approved.

External users may only see approved visibility fields.

External users cannot query internal databases.

External users cannot see proprietary scoring, internal Intelligence notes, internal Library structures, or Archive internals.

External users cannot trigger internal state transitions except approved visibility acknowledgments if later designed.

---

## 15. PIN Change and Review Reporting

PIN changes, resets, failures, lockouts, and revocations must be reportable.

Security events may appear in:

- Monday Report for critical security events
- Monthly Report for routine access review
- immediate Authority Card for suspected compromise

---

## 16. Security Event Types

Initial security event types:

- LOGIN_SUCCESS
- LOGIN_FAILURE
- PIN_CREATED
- PIN_CHANGED
- PIN_RESET
- PIN_REVOKED
- SESSION_CREATED
- SESSION_EXPIRED
- AUTHORITY_ACTION_APPROVED
- AUTHORITY_ACTION_REJECTED
- PERMISSION_DENIED
- SUSPICIOUS_ACTIVITY

---

## 17. Build Readiness Requirements

Before security implementation, builders must define:

- user table or equivalent identity record
- PIN validation mechanism
- role table or permission map
- session record
- approval event schema
- security event log
- failed attempt handling
- lockout rules
- PIN reset workflow
- Authority action workflow

No security implementation may store plaintext PINs in application code, public files, prompts, or Git repositories.

---

## 18. Forbidden Security Actions

No Dispatch component may:

- store plaintext PINs in repository files
- expose PINs to cognitive functions
- allow shared PINs by default
- allow unauthenticated approval
- allow driver approval of authority actions
- allow external users to query internal databases
- allow System Service to approve authority actions
- treat recommendation as approval
- bypass Portal for authority action

---

## 19. Success Standard

Dispatch security succeeds when every meaningful action can answer:

- who acted
- what role the user had
- what permission allowed the action
- what object was affected
- what version was affected
- what decision was made
- when the decision occurred
- how the action was recorded

Dispatch security fails when authority relies only on trust, hidden state change, unrecorded action, shared credential, or cognitive assumption.

---

## 20. Authority Closing

This specification defines Dispatch identity, PIN, role, permission, session, and audit doctrine.

It does not authorize deployment.
It does not approve implementation.
It does not create new authority.
It does not transfer authority away from Mike.

Mike decides.
