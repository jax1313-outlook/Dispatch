# DISPATCH_FINAL_BLUEPRINT_v1.md

**Document Type:** Final Integrated Blueprint Draft
**Program:** Dispatch
**Owner:** Mike Zachary / Level 1 Transport
**Status:** Final Blueprint Draft — Built From Repo-3 Source of Truth
**Authority:** Mike Zachary remains final authority

---

## Authority Notice

This document is a final blueprint draft. It is the end-to-end build target for Dispatch — doctrine to architecture to implementation planning to deployment path — assembled entirely from the current active Repo-3 source documents:

`DISPATCH_CONSTITUTION_v3.md`, `CONTEXT_MASTER.md`, `ARCHITECTURE.md`, `MANAGER.md`, `PUBLISHER.md`, `INTELLIGENCE_ANALYST.md`, `COGNITIVE_FUNCTIONS.md`, `PORTAL_DESCRIPTION.md`, `DISPATCH_SPINE_OVERVIEW.md`, `DISPATCH_SPINE_SPECIFICATION_v1.md`, `DISPATCH_VERSION_DOCTRINE.md`, `ARCHIVE_REVIEW_POLICY.md`, `INTELLIGENCE_VERIFICATION_WORKFLOW.md`, `ALERT_GOVERNANCE_DOCTRINE.md`, `SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md`, `ARCHITECTURAL_DISPOSITION.md`, `SUPERSESSION_MAP.md`, `REFINEMENT_ANALYST_REMOVAL.md`, `DISPATCH_DECISION_MATRIX.md`, `DISPATCH_REPO_MANIFEST_v3.md`.

This document does not authorize deployment, production code, external submission, autonomous approval, autonomous booking, autonomous contract commitment, or authority transfer.

No new agents are introduced. The Dispatcher Agent name is not used. The 11-agent mesh is not reintroduced. No retired concept is revived.

**Mike Zachary is final authority. Mike decides.**

---

## 1. Executive Blueprint Summary

**What is Dispatch?**

Dispatch is a governed digital office for Level 1 Transport. It is a human-authority system built on deterministic runtime machinery (the Dispatch Spine) with bounded cognitive functions (Manager reasoning, Publisher drafting, Intelligence analysis) attached only where reasoning, interpretation, drafting, or judgment support is required. Dispatch reduces owner/operator cognitive and administrative load, improves operational visibility, supports freight and opportunity review, produces documents and packets, preserves useful business knowledge, and presents human-usable deliverables through Portal.

**What problem does Dispatch solve?**

Mike Zachary currently absorbs the cognitive and administrative load of running Level 1 Transport manually — tracking opportunities, drafting packets, chasing paperwork, remembering what changed, and deciding everything from raw information. Dispatch converts that raw load into structured, version-aware, source-grounded, decision-ready work that reaches Mike only when his judgment is actually needed.

**What does Dispatch never do?**

Dispatch never books a load autonomously, commits a contract autonomously, submits a government or external package autonomously, approves a fact/packet/rate/compliance determination/final document, self-modifies its own prompts or code, hides a decision path outside Portal, gives external systems direct access to internal databases, or transfers authority away from Mike. AI is force multiplication, not authority transfer. AI decides nothing.

**What makes this architecture safe?**

Every meaningful action traces to a Work Item, an Event, and — where a human decision was involved — an Approval Event tied to an authenticated, PIN-verified, role-checked Portal session. Deterministic machinery (the Spine) owns state, routing, validation, and scoring so that routine operation never depends on probabilistic reasoning. Cognitive functions are boxed to reasoning, drafting, and interpretation, and are structurally forbidden from approving, submitting, booking, certifying, or inventing facts. Unknown means Unknown — no fabrication is permitted anywhere in the system.

**What makes this architecture buildable?**

The five-layer model (Authority, Presentation, Organizational, Deterministic, Cognitive) maps cleanly onto a real technical stack: an auth/session layer, a Portal frontend, six organizational services, a Spine with explicit schemas and state machines, and three cognitive functions implemented as scoped model calls with strict input/output contracts. Nothing in this blueprint requires more than six organizational functions and one deterministic backbone. There is no agent mesh to coordinate.

**What is the shortest path to useful MVP?**

A working Mike Portal cockpit, backed by a minimal Spine (Work Item lifecycle, Portal Card generation, Approval Events), PIN authentication, one load/opportunity review loop (Spine scores → Intelligence interprets → Portal presents → Mike decides), a Publisher draft flow for one packet type, and basic Library/Archive storage with version display. Section 18 defines this precisely.

---

## 2. Final Architecture Model

Dispatch is governed through five layers. No layer may perform another layer's job without an approved design/spec and Mike's approval.

### 2.1 Authority Layer

- **Purpose:** Hold final human authority over the entire system.
- **Owned responsibilities:** All final decisions, approvals, external submissions, business commitments, doctrine changes, deployment approvals, architecture changes, legal/tax/compliance/risk escalation decisions.
- **Forbidden responsibilities:** Performing drafting, scoring, or interpretation work itself; being simulated by AI, automation, or any other user.
- **Primary inputs:** Portal decision, review, conflict, and authority cards; Manager escalations; Monday/monthly reports.
- **Primary outputs:** Approval Events, rejections, revision requests, doctrine/architecture decisions.
- **Handoffs:** Every approval decision flows back into the Spine as an Approval Event, which updates Work Item state and triggers Archive/Library/Publisher routing as applicable.
- **Failure risks:** Authority bypass (a decision executes without an authenticated Authority approval), authority simulation (AI or automation acting as if it were Mike), decision fatigue from excessive card volume.

### 2.2 Presentation Layer

- **Purpose:** Portal — the required, non-optional presentation layer. Dispatch has no value without it.
- **Owned responsibilities:** Rendering decision/review/status/conflict/authority cards; collecting Portal-mediated human actions; showing version and last-change information; hosting Mike cockpit, Driver Portal, and External Viewer visibility windows; enforcing security boundaries per role.
- **Forbidden responsibilities:** Creating authority; becoming the system of record; approving anything automatically; exposing internal proprietary data, scoring logic, or database access to external users.
- **Primary inputs:** Spine-generated cards, states, and events; Manager-prepared recommendations; Publisher review payloads; Intelligence findings; Library/Archive status.
- **Primary outputs:** Approval Events, rejection events, revision requests, driver submissions, external acknowledgments (if approved).
- **Handoffs:** All Portal actions become structured events recorded by the Spine; Manager reacts only when coordination is required.
- **Failure risks:** Becoming an alert wall; hiding material risk behind low card levels; exposing internal data externally; silent approval paths that bypass authentication.

### 2.3 Organizational Layer

- **Purpose:** Define the business functions that do Dispatch's actual work: Manager, Publisher, Intelligence Analyst, Library, Archive, Portal.
- **Owned responsibilities:** Run-office coordination (Manager); document/packet production (Publisher); interpretation and verification (Intelligence Analyst); approved reusable truth storage (Library); completed history storage (Archive); human presentation (Portal).
- **Forbidden responsibilities:** Performing another function's job without approved spec and Mike approval; owning deterministic routing, storage, scoring formulas, approval gates, or audit mechanics (these belong to the Spine).
- **Primary inputs:** Spine events, Portal actions, cross-function handoffs (e.g., Intelligence → Publisher).
- **Primary outputs:** Work item results, drafts, verified facts, Library candidates, Archive bundles, Portal card payloads.
- **Handoffs:** Defined per function in Sections 5–9.
- **Failure risks:** Role-boundary blur (e.g., Publisher inventing facts, Intelligence deciding pursuit); functions becoming standing agents instead of bounded services.

### 2.4 Deterministic Layer

- **Purpose:** Dispatch Spine — the deterministic runtime backbone that makes routine operation reliable, auditable, and boring.
- **Owned responsibilities:** Work item state, routing mechanics, queue management, validation, scoring formulas, event logging, audit logging, Portal card generation triggers, approval/conflict event recording, automation hooks.
- **Forbidden responsibilities:** Reasoning about business meaning, drafting documents, interpreting solicitations, approving anything, replacing Manager/Portal/Mike, creating doctrine, altering authority.
- **Primary inputs:** Work item creation events, cognitive function outputs, Portal actions.
- **Primary outputs:** State transitions, events, Portal cards, audit records.
- **Handoffs:** Calls cognitive functions only when cognition is actually needed; supplies Portal with structured state.
- **Failure risks:** Undertested state transitions; silent logging that hides risk; routing rules that create hidden decisions.

### 2.5 Cognitive Layer

- **Purpose:** Bounded reasoning, interpretation, drafting, and judgment support — Manager reasoning, Publisher drafting, Intelligence analysis. No other cognitive functions exist in this architecture.
- **Owned responsibilities:** Attention protection and coordination (Manager); document/packet drafting from approved inputs (Publisher); data interpretation, risk detection, and verification (Intelligence).
- **Forbidden responsibilities:** Owning deterministic routing, storage, scoring formulas, approval gates, or audit mechanics; approving, submitting, booking, certifying, or inventing facts; self-modifying its own mission, prompts, or code.
- **Primary inputs:** Approved Library facts, source documents, Spine scoring results, Manager work assignments.
- **Primary outputs:** Recommendations, drafts, interpretations, verification classifications — always Portal-visible, never self-executing.
- **Handoffs:** Cognitive outputs return to the Spine as structured results; the Spine decides Portal card level and routing.
- **Failure risks:** Fabrication (violating No Fabrication), scope creep into deterministic territory, becoming a free-roaming chat interface for Mike.

---

## 3. Human Authority Model

### 3.1 AI Decides Nothing

AI may assist, analyze, compare, draft, summarize, classify, test, map, validate, propose, and produce review-ready output. AI does not decide for the business. AI does not approve, submit, certify, sign, invent facts, decide rates, decide compliance, decide legal sufficiency, decide government pursuit, decide final package readiness, book loads, commit assets, alter doctrine, or promote drafts into truth. This is a structural rule enforced at the Spine and Security layers, not a request made to a model.

### 3.2 Portal-Mediated Approval

Mike does not operate Manager, Publisher, Intelligence, Library, Archive, or the Spine directly. Mike works exclusively through Portal actions. Every Portal action becomes a structured event the Spine records. No hidden decision path is authorized (Constitution §13).

### 3.3 Authority Actions

Authority actions require an authenticated session, the Authority role, an active permissions snapshot, a Portal-mediated action, and an audit record (Security Spec §7). Authority actions include: approve draft, approve packet, approve Library promotion, approve Archive delete/retention exception, approve external submission, approve load pursuit, approve deployment, approve doctrine change, approve architecture change. No Authority action may execute from a cognitive function result alone — cognitive output may only recommend; Portal and Spine require authenticated Authority approval before execution.

### 3.4 Approval Gates

Human approval is required for: final packet approval, Library promotion, external submission, load booking, contract commitment, compliance certification, doctrine change, architecture change, deployment approval, purge or retention exception (Spine Spec §19). All such approvals must be Portal-mediated and audit-logged.

### 3.5 Prohibited Autonomous Actions

No Dispatch function may: approve, submit, certify, sign, invent facts, claim eligibility, decide rates, decide compliance, decide legal sufficiency, decide business strategy, decide government pursuit, decide final package readiness, book loads, commit company assets, promote drafts into Library truth, merge Library and Archive, alter doctrine, alter architecture, change role boundaries, create new agents without approval, bypass Portal, bypass Manager when escalation is required, bypass Mike, self-modify its mission, self-modify code or prompts, treat research as truth, or treat recommendation as approval (Constitution §15).

### 3.6 Audit Requirements

Every authority action records who acted, what role the user carried, what object was affected, what version was involved, what decision was made, and when the action occurred (Security Spec §2.4). No authority action may occur silently.

### 3.7 Relationship to Security and Authentication Specification

The Human Authority Model is enforced technically by the Security and Authentication Specification (Section 14): identity, PIN, session, role, and permission records make "Mike approved this" a provable system fact rather than an assumption. The Approval Event schema (Spine Spec §10; Security Spec §9) is the join point between authority doctrine and the audit trail.

### 3.8 Proof Chain

Dispatch proves an authority decision by joining five records for a single action:

1. **Who acted** — `user_id` from the Identity record.
2. **What role acted** — `role` from the Authentication Context / permissions snapshot at the moment of action.
3. **What version was affected** — `object_version` on the Approval Event, tied to Version Doctrine (Section 11).
4. **What decision was made** — `action` and `approved_action` fields on the Approval Event.
5. **When the decision occurred** — `timestamp` on the Approval Event and its linked Audit Event.

This chain must be reconstructable for any Authority action without relying on memory, chat history, or unaudited state.

---

## 4. Portal Blueprint

Portal equals the Presentation Layer. It is not optional — without Portal, Dispatch has no human-usable value (Portal Description §1).

### 4.1 Mike Cockpit

The Mike view is the command cockpit. It includes: decision cards, review cards, active work queue, packet approval items, load/opportunity recommendations, exceptions and conflicts, Archive and Library review prompts, high-value operational alerts.

### 4.2 Driver Portal

Assignment visibility, pickup/delivery details, route notes, required documents, proof photo upload, POD upload, check-in status prompts, issue notes. Defined fully in Section 15.

### 4.3 Broker / Customer Visibility Window

Controlled confidence-building windows only, never internal system access. Defined fully in Section 16.

### 4.4 Card Types

- **Decision cards** — Mike action required (Level 3).
- **Review cards** — optional inspection (Level 2).
- **Status cards** — awareness only (Level 1).
- **Conflict cards** — Mike resolution required (Level 4).
- **Authority cards** — final approval required (Level 5).

### 4.5 Version Display and Last-Change Display

Every review, decision, conflict, and authority card must prominently display `Ver: X` and, where practical, a plain-language `Last Change:` label, per Dispatch Version Doctrine (Section 11). Version information must not be hidden behind metadata panels when operationally relevant.

### 4.6 Alert Governance Controls

Portal must expose Mike's alert governance authority: suppress, unsuppress, alter, refine, enhance, downgrade, upgrade, merge, split, delete, create, change level, change report destination (Section 13).

### 4.7 Security Boundaries

Portal is the only human-facing authentication surface (Security Spec §12.6). All roles — Authority, Driver, External Viewer, System Service — authenticate through Portal with role-appropriate scope enforcement.

### 4.8 External Visibility Limitations

External users must never receive direct access to internal databases, proprietary intelligence, raw scoring logic, or internal decision notes (Portal Description §5).

### 4.9 Preventing Cognitive Overload Without Hiding Alerts

Portal filters presentation by consequence level (0–5), not by suppressing risk. Combined with Version Doctrine (fewer redundant cards for repeat items) and Alert Governance (Mike-controlled refinement rather than automatic suppression), Portal reduces volume without ever silently hiding safety, compliance, authority, legal, business-commitment, source-conflict, or role-boundary risk (Alert Governance §4).

### 4.10 Forbidden Portal Behavior

Portal must never: approve work automatically, hide material risk, expose internal proprietary data to external users, allow external database queries, allow uncontrolled customer/broker/driver access, replace Mike's final authority, or display noisy low-value alerts by default (Portal Description §8).

---

## 5. Manager Blueprint

Manager is the Run Office function. It protects Mike's attention, organizes work, receives structured reports, reacts to meaningful events, handles exceptions, prepares decision-ready cards, and keeps the office coordinated (Manager §1).

### 5.1 Activation Triggers

Manager is always available but not continuously active. It activates through four trigger classes:

1. **Scheduled reviews** — morning briefing, end-of-day summary, weekly review, monthly cleanup review, Archive/Library review cycle.
2. **Workflow events** — new opportunity received, packet draft completed, Intelligence analysis completed, Publisher returns a draft, Library/Archive candidate created, Portal card status changed, deadline approaching.
3. **Exception conditions** — missing required source, contradictory source data, failed validation, authority/compliance/deadline risk, high-value opportunity, workflow failure, Portal visibility failure.
4. **Portal-mediated human actions** — Mike approves/rejects/requests revision/defers/ignores/flags/approves-final through Portal.

### 5.2 Work Item Classification

Every incoming item is classified before routing: Routine, Status, Review Needed, Decision Needed, Conflict, Authority, Archive, Library Candidate, Noise (Manager §7).

### 5.3 Priority Framework

Consequence first, urgency second: (1) safety/compliance/legal/authority risk, (2) active revenue opportunity, (3) customer/broker/shipper/driver-facing need, (4) government packet/opportunity deadline, (5) operational positioning/route risk, (6) document production work, (7) Library/Archive/cleanup work, (8) discovery/research intake, (9) deferred improvement work.

### 5.4 Staff Report Model

Structured, status-driven reports from the office, not conversation. Minimum fields: source function, work item ID, current status, priority, required action if any, risk level, deadline if any, recommended routing, human attention required (yes/no).

### 5.5 Recommendation Card Levels

Level 0 Silent Log through Level 5 Authority, matching Portal consequence levels (Manager §9).

### 5.6 Relationship to Spine

Manager does not replace the Spine. The Spine executes deterministic state, routing, validation, storage, queues, audit logs, scoring, automation triggers, and event records. Manager interprets office state, protects priorities, prepares meaningful cards, and escalates only when needed.

### 5.7 Relationship to Portal

Manager routes human-facing output through Portal, never through direct Manager-to-Mike conversation. Mike does not directly operate Manager (Manager §3.4).

### 5.8 Forbidden Actions

Manager must never: approve on Mike's behalf, submit packets externally, book loads, sign documents, alter doctrine, change authority structure, modify its own instructions, create new roles without approval, bypass Portal visibility, hide material risk from Mike, or become a direct human chat interface replacing Portal (Manager §12).

### 5.9 How Manager Protects Attention Without Becoming a Free-Roaming Router

Manager is event-driven and exception-driven, not a probabilistic router for routine state transitions — routine routing mechanics belong to the Spine's deterministic routing table (Architecture §9). Manager's cognitive work is bounded to prioritization, card preparation, and escalation; it never performs deterministic routing, storage, or scoring itself, and it never substitutes for Portal as the human interface.

---

## 6. Publisher Blueprint

Publisher is the document and packet production function. Publisher drafts. Mike approves (Publisher §1).

### 6.1 Packet Drafting Scope

Government opportunity packets, VA/FEMA/DLA/agency response drafts, carrier packets, broker packets, shipper packets, customer-growth material, cover letters, capability statements, rate tender materials, requirement matrices, document checklists, form-fill drafts, reusable template candidates.

### 6.2 Approved Fact Use and Source Grounding

Publisher uses only approved or traceable inputs: approved Library facts, approved templates/forms, source documents, Intelligence requirement/risk notes, Manager work assignments, Portal-approved tasks, Mike-approved edits, archived completed packets for reference only. Publisher output distinguishes approved Library fact, source document fact, copied template language, inferred wording, missing information, and recommendation — with source references attached wherever possible. Unsupported material is marked NEEDS SOURCE, UNKNOWN, NEEDS REVIEW, or NEEDS MIKE DECISION.

### 6.3 Library Relationship

Publisher reads from Library and may nominate new Library candidates. Publisher may not promote material into Library truth — promotion requires approval (Section 8).

### 6.4 Archive Relationship

Publisher sends completed production bundles, final approved documents, source mappings, and major draft histories to Archive per approved workflow. Archived material is not automatically reusable — it must be nominated and approved before becoming Library material.

### 6.5 Intelligence Relationship

Intelligence identifies requirements, risks, special terms, and interpretation issues. Publisher uses Intelligence output to draft; Publisher requests Intelligence review when requirement meaning is unclear, solicitation language is ambiguous, sources conflict, special compliance language appears, operational risk affects wording, or eligibility/certification language is unclear. Publisher does not independently decide interpretation where cognitive analysis is required.

### 6.6 Portal Review Flow

Publisher outputs become Portal-visible for review: draft review card, packet approval card, gap report card, missing source card, authority approval card, revision request card.

### 6.7 Form-Filling Deterministic Boundary

Publisher may draft the content required for forms, but deterministic tools handle mechanical form placement, PDF field filling, template mapping, and export. Publisher must not rely on cognitive generation alone for coordinate-sensitive or field-sensitive form output. Form output includes: source field, proposed value, source reference, confidence status, missing field marker if needed.

### 6.8 Forbidden Actions

Publisher must never: invent facts, credentials, certification status, source links, rates, or contacts; decide pursuit, pricing, compliance, or legal sufficiency; sign forms; certify eligibility; submit documents externally; promote drafts into Library truth; bypass Intelligence when interpretation is required; bypass Manager when escalation is required; bypass Portal; bypass Mike.

### 6.9 How Publisher Drafts Without Approving

Every major Publisher output carries an explicit status: DRAFT, REVIEW_READY, NEEDS_SOURCE, NEEDS_MIKE_DECISION, REJECTED, or APPROVED_BY_MIKE — and Publisher may never self-assign the last status. Only a Portal-mediated, authenticated Authority approval event (Section 3) can move an output to APPROVED_BY_MIKE. Quality Control Review (invoked, not standing) may be applied to high-risk Publisher output — government packets, final customer-facing packets, authority card packages, compliance-sensitive wording, major reusable templates — before it reaches Mike.

---

## 7. Intelligence Analyst Blueprint

The Intelligence Analyst is the cognitive analysis function: it makes sense of collected data, identifies operational meaning, detects risks, sorts findings, explains uncertainty, and routes insight (Intelligence Analyst §1).

### 7.1 Deterministic Feed Layers (not owned by Intelligence)

- **Sweepers** collect source material from defined places (SAM, load boards, email intake, folders, approved sources). Sweepers do not interpret meaning.
- **Acquisition** obtains, names, stores, and prepares source material, preserving source identity and traceability.
- **Parsing** extracts structured data (dates, titles, solicitation numbers, locations, deadlines, contacts, rates, required fields).
- **Scoring** applies defined formulas, rules, thresholds, and tables deterministically.

### 7.2 Cognitive Layer (owned by Intelligence)

Requirements interpretation, operational risk analysis, special requirement detection, anomaly detection, opportunity-context reasoning, suitability analysis, route/load implication interpretation, pattern recognition, uncertainty explanation, recommendation development, routing meaning to the correct function.

### 7.3 Fact Verification

Intelligence owns the verification workflow (fully detailed in Section 12): classifying findings as Verified, Partially Verified, Unverified, or Rejected before Publisher or Library may treat them as usable truth.

### 7.4 Load and Route Evaluation Model

Load and route evaluation is a supported business capability handled by combination, not by a standing "Dispatcher" role:

- **Spine calculates** deterministic factors: mileage, rate per mile, estimated fuel/operating cost, gross revenue, estimated profit, pickup/delivery timing, Jacksonville positioning impact, return-home impact, HOS/ELD constraints if available, reserve capacity impact, radius band, rule-based route risk flags.
- **Intelligence interprets**: whether the load fits the operating model, whether it conflicts with owner/operator priorities, whether rate/time/distance/positioning create risk, whether special requirements create hidden cost, whether tomorrow's opportunity could be harmed, whether Mike review is required, whether uncertainty is too high to recommend action.
- **Portal presents** the evaluation as a review, decision, conflict, or authority card with enough source and scoring context for Mike to understand the recommendation.
- **Mike decides** whether to pursue, reject, defer, negotiate, revise, or ignore. **No autonomous booking is authorized. No system function may commit Level 1 Transport to a load without Mike approval.**

### 7.5 Library Candidate Nomination / Publisher Handoff / Manager Escalation / Portal Output

Intelligence routes findings per the following table (Intelligence Analyst §7):

| Finding Type | Destination |
|---|---|
| Approved reusable fact candidate | Library review |
| Completed historical source | Archive |
| Packet production requirement | Publisher |
| Business decision needed | Manager to Portal |
| Operational risk | Manager and Portal |
| Load or route issue | Spine scoring → Intelligence interpretation → Portal presentation → Mike decision |
| Irrelevant or stale data | Archive or discard path |

### 7.6 Forbidden Actions

Intelligence must never: decide whether Mike pursues a load or contract, book a load, approve government packet content, change scoring doctrine, promote research to approved company fact, alter Library truth status, delete source records without approval, act as Publisher, act as Manager, act as final authority, or submit external material.

---

## 8. Library Blueprint

Library stores approved reusable truth, approved facts, approved templates, approved forms, approved rate sheets, reusable packet language, company data, customer-growth materials, and approved production parts. Library is not temporary workspace. Library begins as a reliable deterministic service; cognitive assistance (classification, duplicate detection, recommendation) may be added later.

Library has two distinct ingestion paths, governed differently (full doctrine: `LIBRARY_INGESTION_RULE.md`):

- **Human-placed documents** — accepted immediately on placement, per Section 8.3a. A human placing a document into Library is itself the approval act.
- **Publisher-generated, Intelligence-nominated, or Archive-nominated candidates** — still require the Library Promotion Workflow (Section 8.3) before entering Library as truth.

### 8.1 Approved Facts, Templates, Rate Sheets, Packet Language, Company Data

These are the core Library asset classes. Each asset carries a status of `APPROVED` and a version history.

### 8.2 Versioning, Current Pointer, Prior Versions

Every Library asset follows Dispatch Version Doctrine (Section 11): a `current` pointer to the active version and retained prior versions, distinguishable from the current at all times.

### 8.3 Library Promotion Workflow (Cognitively-Derived and Nominated Candidates)

This workflow governs Publisher-generated, Intelligence-nominated, and Archive-nominated candidates only. It does not apply to documents a human places directly into Library — see Section 8.3a.

1. A candidate is nominated (by Publisher, Intelligence, or Archive review) with source references and verification classification (Section 12).
2. The candidate is presented to Mike as a Library promotion card (Portal Level 3 or higher).
3. Mike approves, rejects, or requests revision through an authenticated Authority action.
4. On approval, the Spine records an `APPROVE_LIBRARY_PROMOTION` event and the asset enters Library as version 1 (or a new version of an existing asset).

### 8.3a Human Ingestion Rule

Any document placed into any Library by a human is accepted immediately — no verification workflow, no approval workflow, no promotion workflow. The human's act of placing the document is the approval act. This applies to every Library section, including the Security sub-library (Section 8.9), where the PIN-protected access requirement governs *who may place or read* material, not *whether placed material is approved*.

This rule does not apply to Publisher-generated assets, which continue to follow the Library Promotion Workflow (Section 8.3) and Publisher's own review/approval process (Section 6.9), and does not create a bypass for cognitively-derived material routed through a human's hands without genuine human review. Full doctrine: `LIBRARY_INGESTION_RULE.md`.

### 8.4 Approved Truth Boundary

For cognitively-derived candidates (Section 8.3), only Verified facts, or Partially Verified facts Mike explicitly approves for the specific use, may enter Library as truth (Section 12.4). Raw Intelligence guesses, unverified internet material, or unapproved drafts may never be promoted this way.

For human-placed documents (Section 8.3a), the human's placement is the truth boundary — no separate verification classification gates entry. The distinction is source, not content: a human handing the system a real document is not the same act as a cognitive function inferring or drafting one.

### 8.5 Relationship to Publisher

Publisher reads Library facts and templates as primary source material and may nominate new candidates, but cannot promote candidates into Library truth itself (Section 6.3).

### 8.6 Relationship to Intelligence

Intelligence nominates verified findings for Library review but does not approve final classification — approval is Mike's or an approved workflow's (Section 12.6).

### 8.7 Relationship to Archive

Archive material may be nominated for Library review but never automatically becomes Library truth; Library and Archive must never be merged (Constitution §15).

### 8.8 Version Doctrine Applied to Library

Library assets display `Ver: X` and a `Last Change:` label. Superseded versions remain retrievable per the retention rule in Section 9 (Current Version + Three Previous Versions, older versions entering the Archive Review Queue). This applies identically to human-placed and cognitively-promoted assets — immediate acceptance on ingestion does not exempt a record from version tracking.

### 8.9 Security Sub-Library

Library includes a distinct Security sub-library for security-sensitive material (PIN policy documents, credential-handling procedures, access-control records, and other material `SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md` governs).

- **PIN-protected access** — opening the Security sub-library requires a separate, valid PIN check at the moment of access, distinct from the general Portal session login PIN (Security Spec §4.3).
- **PIN reset capability** — an Authority user may reset the Security sub-library's access PIN through the existing governed PIN reset workflow (Security Spec §4.5) — Authority approval or an approved reset workflow, never a silent reset.
- Governed by Security Spec §11 (Library and PIN Records): may store PIN-related and credential-control records, but must never expose readable PIN values to Publisher, Intelligence, Driver users, External Viewers, or any cognitive function.
- The Human Ingestion Rule (Section 8.3a) still governs *what* enters the Security sub-library; the PIN-protected access requirement governs *who may reach it*. These are independent controls — one is not a substitute for the other.

### 8.10 Scanner API Integration (Future Build Item)

A Scanner API integration — physical/network document scanner intake feeding directly into Library ingestion — is identified as a future build item, not authorized for implementation now. It is recorded here so the Library ingestion path (Section 8.3a) is designed to accept a scanner-originated document the same way it accepts any other human-placed document, once built. No scanner vendor, protocol, or implementation detail is specified or authorized by this blueprint. Priority: Future.

---

## 9. Archive Blueprint

Archive stores completed history, final records, evidence, source records, decision records, audit bundles, completed packets, past decisions, and retention material. Archive is not the active workspace and is not Library. Archive is **preserve-by-default, not keep-forever-by-default** (Archive Review Policy §1).

### 9.1 Contents

Completed packets, source records, audit bundles, past decisions, historical records.

### 9.2 Version Retention Rule

Dispatch automatically retains the Current Version plus the Three Previous Versions of any versioned object. Example: Current is Ver: 10; Ver: 9, 8, 7 are retained automatically; anything older than Ver: 7 enters the Archive Review Queue.

### 9.3 Archive Review Queue

Versions older than the retention window enter the Archive Review Queue. The queue does not delete automatically — it prepares items for Mike's review.

### 9.4 Monthly Archive Review

Queue items appear in the monthly report with a simple Keep/Delete control per item, showing object name, version number, current version, age/relative history position, last change summary, reason for review, and a suggested disposition if available.

### 9.5 Monday Report Escalation for Critical Records

Critical records do not wait for the monthly cycle: compliance-sensitive documents, government packet records, high-value opportunity records, authority approval history, broker/customer documents, load/route records with business consequence, security/PIN-related audit records, and records tied to active disputes/claims/unresolved issues may appear on the Monday Report instead.

### 9.6 Keep/Delete Decision Process and Purge Approval

- **Delete** requires Mike approval and records who approved, what was deleted, version number, reason, timestamp, related work item, and an audit event. Delete is never a silent system cleanup.
- **Keep** records who approved retention, version number, reason if provided, timestamp, and next review status if any.

### 9.7 Relationship to Library

Archive does not create Library truth. A record may become Library material only through the approved Library promotion workflow (Section 8.3).

### 9.8 Preserve-by-Default, Not Keep-Forever-by-Default

Archive Review Policy explicitly rejects both extremes: uncontrolled accumulation of every historical version, and automatic deletion without human review. The queue-plus-report model gives Mike simple, periodic Keep/Delete control without manual file archaeology, while critical records escalate faster than the default monthly cycle.

---

## 10. Dispatch Spine Blueprint

The Dispatch Spine is the deterministic runtime backbone. It exists so routine system behavior does not depend on probabilistic reasoning (Spine Overview §1). The Spine does not reason, approve, replace Manager, replace Portal, or replace Mike.

### 10.1 Core Schemas

**Work Item Schema** — minimum fields: `work_item_id`, `created_at`, `updated_at`, `source_type`, `source_id`, `current_state`, `priority`, `consequence_level`, `assigned_function`, `required_action`, `source_confidence`, `due_date`, `related_files`, `source_refs`, `validation_status`, `scoring_status`, `cognitive_status`, `portal_card_id`, `final_disposition`.

**Event Schema** — `event_id`, `timestamp`, `work_item_id`, `event_type`, `actor_type`, `actor_id`, `previous_state`, `new_state`, `summary`, `source_refs`, `requires_audit`.

**Portal Card Schema** — `card_id`, `work_item_id`, `created_at`, `card_level` (0–5), `card_type`, `title`, `summary`, `source_refs`, `recommendation`, `decision_needed`, `allowed_actions`, `required_closing` (always: *"This is a recommendation only. No action is authorized. Mike decides."*).

**Approval Event Schema** — `approval_event_id`, `timestamp`, `session_id`, `user_id`, `role`, `work_item_id`, `portal_card_id`, `object_type`, `object_id`, `object_version`, `action`, `previous_state`, `new_state`, `comments`, `authentication_context`, `audit_id`. Approved actions: `APPROVE_DRAFT`, `REJECT_DRAFT`, `REQUEST_REVISION`, `APPROVE_PACKET`, `APPROVE_LIBRARY_PROMOTION`, `APPROVE_ARCHIVE_DELETE`, `APPROVE_ARCHIVE_KEEP`, `APPROVE_LOAD_PURSUIT`, `REJECT_LOAD_PURSUIT`, `APPROVE_DEPLOYMENT`.

**Conflict Event Schema** — `conflict_id`, `timestamp`, `work_item_id`, `conflict_type` (`MISSING_SOURCE`, `CONTRADICTORY_SOURCE`, `ROLE_BOUNDARY_RISK`, `AUTHORITY_RISK`, `FABRICATION_RISK`, `VALIDATION_FAILURE`, `COMPLIANCE_RISK`, `LEGAL_RISK`, `ARCHITECTURE_DRIFT_RISK`, `PORTAL_VISIBILITY_RISK`), `affected_layer`, `affected_function`, `trigger`, `details`, `options`, `recommended_path`, `human_decision_needed`, `current_state`.

**Validation Result Schema** — `validation_id`, `work_item_id`, `timestamp`, `validator_name`, `validation_status` (`PASS`, `FAIL`, `WARNING`, `NEEDS_SOURCE`, `NEEDS_MIKE_DECISION`), `missing_fields`, `failed_rules`, `warnings`, `source_refs`, `next_state`.

**Scoring Result Schema** — `scoring_id`, `work_item_id`, `timestamp`, `scoring_model`, `score_type`, `input_values`, `formula_version`, `score`, `flags`, `recommendation_label`, `source_refs`, `next_state`. Scoring may recommend; it may not decide.

**Audit Event Schema** — `audit_id`, `timestamp`, `work_item_id`, `event_id`, `actor_type`, `actor_id`, `action`, `previous_state`, `new_state`, `source_refs`, `hash` (SHA-256 preferred if hashing is used), `notes`.

### 10.2 State List

`CREATED`, `VALIDATION_PENDING`, `VALIDATION_FAILED`, `VALIDATED`, `SCORING_PENDING`, `SCORED`, `COGNITIVE_REVIEW_PENDING`, `COGNITIVE_REVIEW_COMPLETE`, `ROUTING_PENDING`, `ROUTED_TO_MANAGER`, `ROUTED_TO_INTELLIGENCE`, `ROUTED_TO_PUBLISHER`, `ROUTED_TO_LIBRARY_REVIEW`, `ROUTED_TO_ARCHIVE`, `PORTAL_CARD_PENDING`, `PORTAL_CARD_CREATED`, `WAITING_FOR_MIKE`, `MIKE_APPROVED`, `MIKE_REJECTED`, `MIKE_REQUESTED_REVISION`, `DEFERRED`, `CONFLICT_RAISED`, `CONFLICT_RESOLVED`, `COMPLETED`, `ARCHIVED`.

### 10.3 Allowed State Transitions

As specified in `DISPATCH_SPINE_SPECIFICATION_v1.md` §7 — the transition table is a build-readiness artifact and must be implemented exactly, including: `CREATED → VALIDATION_PENDING`; `VALIDATION_PENDING → VALIDATED | VALIDATION_FAILED`; `VALIDATION_FAILED → CONFLICT_RAISED | ARCHIVED`; `VALIDATED → SCORING_PENDING | COGNITIVE_REVIEW_PENDING | ROUTING_PENDING | PORTAL_CARD_PENDING`; `SCORING_PENDING → SCORED | CONFLICT_RAISED`; `SCORED → COGNITIVE_REVIEW_PENDING | ROUTING_PENDING | PORTAL_CARD_PENDING`; `COGNITIVE_REVIEW_PENDING → COGNITIVE_REVIEW_COMPLETE | CONFLICT_RAISED`; `COGNITIVE_REVIEW_COMPLETE → ROUTING_PENDING | PORTAL_CARD_PENDING`; `ROUTING_PENDING → ROUTED_TO_MANAGER | ROUTED_TO_INTELLIGENCE | ROUTED_TO_PUBLISHER | ROUTED_TO_LIBRARY_REVIEW | ROUTED_TO_ARCHIVE | CONFLICT_RAISED`; `PORTAL_CARD_PENDING → PORTAL_CARD_CREATED | CONFLICT_RAISED`; `PORTAL_CARD_CREATED → WAITING_FOR_MIKE`; `WAITING_FOR_MIKE → MIKE_APPROVED | MIKE_REJECTED | MIKE_REQUESTED_REVISION | DEFERRED | CONFLICT_RAISED`; `MIKE_APPROVED → COMPLETED | ROUTED_TO_PUBLISHER | ROUTED_TO_LIBRARY_REVIEW | ROUTED_TO_ARCHIVE`; `MIKE_REJECTED → ARCHIVED | COMPLETED`; `MIKE_REQUESTED_REVISION → ROUTED_TO_PUBLISHER | ROUTED_TO_INTELLIGENCE | ROUTED_TO_MANAGER | COGNITIVE_REVIEW_PENDING`; `DEFERRED → ROUTING_PENDING | ARCHIVED`; `CONFLICT_RAISED → CONFLICT_RESOLVED | WAITING_FOR_MIKE | ARCHIVED`; `CONFLICT_RESOLVED → VALIDATION_PENDING | ROUTING_PENDING | PORTAL_CARD_PENDING`; `COMPLETED → ARCHIVED`; `ARCHIVED` terminal unless retention policy authorizes further action.

### 10.4 Routing Table

`government_opportunity → Intelligence Analyst`; `packet_draft → Publisher`; `library_candidate → Library review`; `completed_record → Archive`; `conflict → Manager and Portal`; `authority_action → Portal Level 5`; `load_or_route_evaluation → Spine scoring, Intelligence interpretation, Portal presentation, Mike decision`. The routing table must be explicit and testable; no routing rule may create a hidden decision.

### 10.5 Silent Log Rules

Silent logging (Level 0) is allowed only for low-risk routine events requiring no human attention, and must remain auditable. Silent logs may never hide authority decisions, compliance risks, missing-source issues, failed validation, business-commitment risks, external exposure risks, or role-boundary violations.

### 10.6 Portal Card Generation Rules

Card level is driven by consequence: Level 0 logged silently; Level 1 status; Level 2 optional review; Level 3 Mike decision required; Level 4 conflict resolution required; Level 5 authority approval required. All Level 3–5 cards must be Portal-visible to Mike.

### 10.7 Human Approval Gates

Per Section 3.4 — final packet approval, Library promotion, external submission, load booking, contract commitment, compliance certification, doctrine change, architecture change, deployment approval, purge/retention exception. All Portal-mediated and audit-logged.

### 10.8 Error Handling Rules

Errors must not disappear. They route to one of: validation failure, conflict event, retry queue, archive-as-failed-record, or a Portal card if human attention is needed. The system must not retry indefinitely without escalation.

### 10.9 Build-Readiness Requirements

The Spine is build-ready only when the following exist: schema files or equivalent model definitions, state transition tests, routing table tests, validation tests, audit event tests, Portal card tests, approval event tests, conflict event tests. Until then it remains specification-level architecture.

### 10.10 What the Spine Does and Does Not Do

Does: state, routing mechanics, queues, validation, storage, scoring formulas, audit logs, event records, automation triggers, status transitions. Does not: reason about business meaning, draft documents, interpret solicitations, decide what Mike should do, approve anything, replace Manager, replace Portal, replace Mike, create doctrine, alter authority.

---

## 11. Dispatch Version Doctrine Blueprint

### 11.1 Why Version Beats Timestamp

A timestamp answers *when did this happen*. A version answers the operationally useful questions under time pressure: *Have I seen this before? How many times has this changed? Is this a repeat item? Is this worth looking at again?* Dispatch prioritizes version visibility for operational decision-making (Version Doctrine §2).

### 11.2 How `Ver: X` Works

Every significant Dispatch object displays a human-readable version marker in the standard format `Ver: X`. Version increases only on a meaningful change to the object — rate changed, deadline changed, route changed, requirement changed, document revised, score changed, source updated, status changed, packet draft changed, Library asset updated, Archive review disposition changed. Version does not increase for meaningless system noise.

### 11.3 How `Last Change` Works

Where practical, version display includes a plain-language change label — e.g., `Last Change: Rate Updated`, `Last Change: Deadline Changed`, `Last Change: New Attachment Added`, `Last Change: Score Increased`, `Last Change: Route Risk Added`, `Last Change: Mike Requested Revision` — enabling fast triage without reading a full history log.

### 11.4 Where Version Appears

Portal cards, Intelligence findings, Library assets, Archive records, Publisher drafts, packet drafts (carrier/broker/shipper), opportunity evaluations, load board matches, route reviews, Manager reports, Monday Reports, monthly reports, driver-facing documents, customer/broker visibility artifacts.

### 11.5 Load-Board Example

```
HIGH VALUE MATCH
Score: 97%
Ver: 9
Last Change: Rate Updated
```

This is more useful operationally than `Updated: 8/10/2026 10:41:15` because the version number immediately tells Mike the item has appeared or changed multiple times, without requiring him to recall or look up prior appearances.

### 11.6 Why This Reduces Cognitive Load

Version Doctrine succeeds when Mike can determine within seconds whether an item is new, previously seen, how many times it has changed, what changed last, and whether it's worth opening again — without reading timestamps, comparing file names, or relying on memory of prior appearances.

---

## 12. Intelligence Verification Blueprint

This workflow enforces the No Fabrication Rule using the existing Intelligence Analyst function — it does not create a new compliance agent (Intelligence Verification Workflow §1).

### 12.1 Core Flow

`Raw Information → Collection Layer → Parsing Layer → Intelligence Verification → Verified Fact or Rejected Fact → Library if approved → Publisher use if verified or approved`.

### 12.2 Verification Classifications

- **Verified** — supported by source material or approved Library material; may proceed to Library review or Publisher use per workflow.
- **Partially Verified** — some support exists but with uncertainty or missing support; requires notation and may not be treated as fully approved truth unless Mike approves the specific use.
- **Unverified** — source support is missing; may not enter Library as truth; Publisher may not use as a factual claim.
- **Rejected** — determined unreliable, contradictory, stale, unsupported, or wrong; may be archived as history but never used as truth.

### 12.3 Source Grounding Rule

Every significant factual claim must point to a source record, an approved Library record, an Intelligence Verification record, or a Mike-approved exception. Absent a source, output is marked UNKNOWN, MISSING, NEEDS SOURCE, NEEDS REVIEW, or NEEDS MIKE DECISION.

### 12.4 Publisher Use Rules

Publisher may consume Verified facts, approved Library facts, and Partially Verified facts only when clearly labeled and approved for that specific use. Publisher may never present Unverified or Rejected facts as truth.

### 12.5 Library Promotion Rules

Verified facts may be nominated for Library promotion; promotion still requires approval (Section 8.3). Library stores approved reusable facts, not raw Intelligence guesses.

### 12.6 Archive Handling

Rejected, stale, superseded, or unverified material may be archived for history if useful — archive storage never makes a fact true.

### 12.7 Portal Reliability Display

Portal cards involving facts identify whether information is Verified, Partially Verified, Unverified, Rejected, or Unknown, letting Mike evaluate reliability at a glance.

### 12.8 Unknown Means Unknown

Missing information is never silently filled in. This workflow enforces No Fabrication structurally: Intelligence classifies and recommends; it does not approve final truth by itself; Library and Publisher gate their use of any fact on its verification classification; Mike or an approved workflow controls final promotion where required.

---

## 13. Alert Governance Blueprint

Dispatch does not treat alerts as noise by default. Alerts exist for a reason. **Mike is the alert governance authority** — the goal is human-controlled refinement, not automatic suppression (Alert Governance Doctrine §1).

### 13.1 Core Rule

There is no uncontrolled automatic suppression of alerts. A bad alert is refined, altered, downgraded, upgraded, merged, split, or deleted through approved governance — the system works for Mike, not the reverse.

### 13.2 Mike's Governance Authority

Mike may: suppress, unsuppress, alter, refine, enhance, downgrade, upgrade, merge, split, delete, create, change consequence level, or change report destination for any alert.

### 13.3 Alert Levels

Aligned with Portal consequence levels 0–5. Silent logging must never hide safety, compliance, authority, legal, business-commitment, source-conflict, or role-boundary risk, regardless of level assignment.

### 13.4 Alert Change Record

Every governance change records: `alert_id`, previous behavior, new behavior, reason, `approved_by`, timestamp, affected version if applicable, expected effect.

### 13.5 Refinement Examples

A repeated 97% opportunity moves from multiple separate cards to a single card showing `Ver: 9` and `Last Change`. A non-critical status update may move from Level 1 to Level 0 only if Mike decides it is not useful. A missed source or compliance risk is never silently suppressed. A high-value opportunity may be escalated to the Monday Report or an immediate Portal card.

### 13.6 Relationship to Manager

Manager may recommend alert refinement but may not permanently suppress an alert class without Mike's approval. Manager protects attention; Mike governs alert behavior.

### 13.7 Relationship to Reports

Alerts may surface in immediate Portal cards, the Monday Report, the monthly report, the Archive Review report, the Security report, or the Manager report. Mike may relocate any alert's destination.

### 13.8 Why Governed Refinement, Not Uncontrolled Suppression

Alert Governance succeeds when useful alerts reach Mike at the right level and bad alerts can be improved without disabling the whole system; it fails when alerts are hidden by default, suppress important risk, flood Mike without control, or cannot be adjusted by Mike. The correct response to a noisy or low-value alert is always governed refinement under Mike's authority — never silent, system-driven suppression.

---

## 14. Security and Authentication Blueprint

### 14.1 Identity Doctrine

Every Dispatch user has a unique identity — a controlled system record tied to role, permissions, status, and audit history. Minimum fields: `user_id`, `display_name`, `role`, `status`, `pin_record_id`, `created_at`, `updated_at`, `last_login_at`, `permissions`, `authority_level`.

### 14.2 PIN Doctrine

Every user has a managed Dispatch PIN — the Portal authentication method proving the user is claiming their assigned identity. Dispatch manages PIN creation, assignment, storage, validation, change, reset, revocation, expiration if required, and failed-attempt handling. A PIN is a controlled authentication credential, never casual text, and PIN records store only protected validation material, never plaintext.

### 14.3 Authority Doctrine

Roles determine permissions. Mike Zachary is the top security authority and final business authority. Only the Authority role may approve authority-level actions. Roles never create business authority beyond what Mike approves.

### 14.4 Audit Doctrine

Every authority action records who performed it, what role the user carried, what object was affected, what version was involved, what decision was made, and when it occurred. No authority action occurs silently.

### 14.5 Roles

- **Authority** — belongs to Mike Zachary unless Mike explicitly approves another authority role later. May approve packets, reject packets, request revision, approve Library promotion, approve Archive deletion/retention exception, approve load pursuit, approve deployment, approve doctrine/architecture change, override non-authority recommendations. Authority may never be simulated by AI, automation, or another user.
- **Driver** — driver-facing Portal views only. May view assigned work, pickup/delivery information, route notes; upload proof photos and POD/delivery records; submit check-in status and issue notes. May not approve packets, approve Library promotion, delete Archive material, view proprietary scoring logic or internal Intelligence notes (unless explicitly shared), access customer/broker views, approve load pursuit, or commit Level 1 Transport.
- **External Viewer** — approved customer/broker/shipper visibility users, limited to Mike-approved windows. May not query internal databases, view proprietary scoring, internal Intelligence notes, Library internals, Archive internals, trigger internal workflows, approve anything, or see driver-only details unless approved.
- **System Service** — deterministic system activity (Spine transitions, scheduled checks, validation runs, automated logs, approved background tasks). May not approve, submit, book, sign, or certify. Audit-logged whenever it affects state.

### 14.6 PIN Lifecycle

**Creation** — via approved PIN management function; creates `pin_record_id`, `user_id`, `role`, `created_at`, `status`, `reset_required` flag if applicable. **Assignment** — one PIN per user identity, never shared. **Validation** — user selects identity, enters PIN, Dispatch validates PIN and role, creates an authenticated session on success, records the login; failed attempts are recorded and repeated failures trigger lockout or Manager/Authority review. **Change** — only through approved Portal workflow, event recorded. **Reset** — requires Authority approval or an approved reset workflow; Driver/External Viewer resets never grant new permissions. **Revocation** — on access end, suspected compromise, role change, Mike's order, or access review; revoked PINs may never authenticate a session.

### 14.7 Session Model

Minimum fields: `session_id`, `user_id`, `role`, `started_at`, `last_active_at`, `status`, `authentication_method`, `permissions_snapshot`. A session answers who is using Portal, what role is active, what the user may do, and whether the session is still valid.

### 14.8 Permission Model

Role-based. Minimum categories: `view_portal`, `view_driver_assignment`, `upload_driver_document`, `view_external_status`, `view_internal_card`, `approve_draft`, `approve_packet`, `approve_library_promotion`, `approve_archive_action`, `approve_load_pursuit`, `approve_deployment`, `approve_doctrine_change`, `approve_architecture_change`. Authority may carry all approval permissions; Driver carries operational permissions only; External Viewer carries visibility permissions only; System Service carries state/validation/logging/execution permissions only — never approval permissions.

### 14.9 Authority Actions

Require an authenticated session, the Authority role, an active permissions snapshot, a Portal-mediated action, and an audit record. No Authority action may execute from a cognitive function result alone.

### 14.10 Portal-Mediated Approval Flow

1. Work item reaches Portal review state.
2. Portal displays the card to an authenticated user.
3. User selects an action.
4. Portal checks role and permissions.
5. Portal creates an Approval Event.
6. Spine records the event.
7. Spine transitions state if allowed.
8. Audit event is written.

Mike approving something means: Mike was authenticated, Mike carried the Authority role, Mike selected an approved action, and Dispatch recorded it.

### 14.11 Approval Event Schema

See Section 10.1. Minimum fields include `approval_event_id`, `timestamp`, `session_id`, `user_id`, `role`, `work_item_id`, `portal_card_id`, `object_type`, `object_id`, `object_version`, `action`, `previous_state`, `new_state`, `comments`, `authentication_context`, `audit_id`.

### 14.12 Authentication Context Schema

`authentication_method`, `pin_verified`, `verified_at`, `failed_attempt_count`, `session_id`, `user_id`, `role`, `permissions_snapshot_id`.

### 14.13 Library Handling of PIN-Related Records

PIN identity records may be stored under controlled Library governance only if Mike treats identity/credential records as approved operational control records. If so, Library must never expose readable PIN values to Publisher, Intelligence, Driver users, External Viewers, or any cognitive function. PIN records are operational security records, not reusable drafting facts — Publisher may not use them, Intelligence may not interpret them, and Archive may store audit history of PIN *events* only, never active PIN material.

### 14.14 Security Boundaries by Function

Manager may see user role, session status, and action outcome for coordination, never plaintext PIN values. Publisher and Intelligence may never access PIN records, authentication secrets, or credential material. Library may store approved identity-control records if authorized but must protect credential material from cognitive and production functions. Archive stores security event history but never serves active credentials. Portal is the sole human-facing authentication surface. The Spine validates sessions, permissions, and approval-state transitions — it enforces authority, it does not decide it.

### 14.15 Driver Portal Security

Driver users authenticate with unique PINs, access only assigned driver scope, and have every upload/submission action recorded. Drivers cannot approve dispatch, packet, Library, Archive, deployment, or authority actions.

### 14.16 External Viewer Security

External viewers authenticate with unique access credentials or PINs if approved, see only approved visibility fields, cannot query internal databases, cannot see proprietary scoring/internal Intelligence notes/Library internals/Archive internals, and cannot trigger internal state transitions except approved visibility acknowledgments if later explicitly designed.

### 14.17 Security Event Reporting

PIN changes, resets, failures, lockouts, and revocations must be reportable — in the Monday Report for critical security events, the Monthly Report for routine access review, or an immediate Authority Card for suspected compromise. Initial event types: `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `PIN_CREATED`, `PIN_CHANGED`, `PIN_RESET`, `PIN_REVOKED`, `SESSION_CREATED`, `SESSION_EXPIRED`, `AUTHORITY_ACTION_APPROVED`, `AUTHORITY_ACTION_REJECTED`, `PERMISSION_DENIED`, `SUSPICIOUS_ACTIVITY`.

### 14.18 Forbidden Security Actions

No component may: store plaintext PINs in repository files, expose PINs to cognitive functions, allow shared PINs by default, allow unauthenticated approval, allow Driver approval of authority actions, allow External Viewers to query internal databases, allow System Service to approve authority actions, treat recommendation as approval, or bypass Portal for an authority action.

### 14.19 How Dispatch Knows Mike Is Mike

A unique `user_id` identity record, tied to a managed Dispatch PIN, produces an authenticated session upon successful validation; that session carries the Authority role and a permissions snapshot; every action taken under that session writes an audit event capturing who, what role, what object, what version, what decision, and when. This five-part chain — identity, PIN, session, role/permissions, audit event — is how "Mike approved this" becomes a provable system fact.

---

## 15. Driver Portal Blueprint

The Driver Portal is part of the system, not a deferred future idea — it is one of the three Portal views (Mike cockpit, Driver Portal, External Viewer window) defined from the outset (Portal Description §4, Architecture §12).

### 15.1 Scope

- **Assignment visibility** — view assigned work.
- **Pickup / delivery details** — locations, timing.
- **Route notes** — operational notes relevant to the run.
- **Required documents** — checklist of what's needed for the assignment.
- **Proof photo upload** — capture and submit proof-of-condition/delivery photos.
- **POD upload** — submit proof-of-delivery records.
- **Check-in status** — submit status updates at defined checkpoints.
- **Issue notes** — flag problems for Manager/Portal visibility.
- **Driver PIN access** — unique PIN per driver, per Section 14.6/14.15.

### 15.2 Driver Role Boundaries

Drivers may view assigned work, pickup/delivery info, route notes; upload proof photos and POD; submit check-in status and issue notes. Drivers may not approve packets, approve Library promotion, delete Archive material, view proprietary scoring logic, view internal Intelligence notes unless explicitly shared, access customer/broker views, approve load pursuit, or commit Level 1 Transport (Security Spec §3.2).

### 15.3 Offline / Low-Signal Concern

Not covered by current source doctrine in implementation detail; this blueprint records it as a **future implementation requirement**: Driver Portal must plan for degraded or absent connectivity during transit (queued uploads, local caching of assignment data, retry-on-reconnect for photo/POD submission) before full production rollout. This requirement does not authorize any specific technical approach — it is scoped for design work in a later build wave (Section 19).

---

## 16. Broker / Customer Portal Blueprint

External visibility windows are controlled, confidence-building views — never internal system access (Portal Description §5).

### 16.1 Scope

- **Shipment status** — current status of relevant shipments.
- **Proof package visibility** — access to proof-of-delivery materials for their shipments.
- **POD access** — delivery confirmation records.
- **ETA / route status if approved** — only where Mike has explicitly approved exposing this.
- **Customer confidence features** — visibility designed to build trust without exposing internals.

### 16.2 Broker / Shipper Visibility Boundaries

External Viewers may not: query internal databases, view proprietary scoring, view internal Intelligence notes, view Library internals, view Archive internals, trigger internal workflows unless explicitly approved, approve anything, or see driver-only details unless approved (Security Spec §3.3, §14).

### 16.3 No Internal Exposure

No direct database access, no proprietary scoring exposure, no internal intelligence exposure, no workflow triggering unless explicitly approved by Mike.

### 16.4 Level 1 Transport's Visibility Moat

Controlled external Portal views let Level 1 Transport offer customers and brokers real-time confidence (status, proof, POD) that competitors relying on phone calls and email cannot match — without ever surrendering the proprietary scoring, internal risk analysis, or operational data that make Dispatch valuable. The moat is the combination of transparency where it builds trust and opacity where it protects competitive advantage.

---

## 17. Telematics Blueprint

Telematics is an input category, not a decision-maker. This is inferred as a build requirement from the Intelligence Analyst's deterministic scoring inputs (Intelligence Analyst §5.1, listing "HOS or ELD constraints if data is available" as a Spine responsibility); no dedicated telematics doctrine exists yet in Repo-3, so this section states blueprint requirements rather than halting.

### 17.1 Input Categories

- **GPS / position data** — current and historical vehicle position.
- **HOS / ELD data if later connected** — hours-of-service and electronic logging device data, when integrated.
- **Route risk input** — feeds Spine route-risk flagging.
- **Position protection input** — feeds Jacksonville positioning and return-home impact calculations.
- **Return-home impact input** — feeds the same deterministic factors listed in Section 7.4.
- **Load evaluation input** — one of several deterministic inputs to load/route scoring.

### 17.2 Spine Scoring Relationship

Telematics data feeds the Spine's deterministic scoring engine as raw input values alongside mileage, rate per mile, and other factors (Section 10.1, Scoring Result Schema `input_values`). The Spine calculates; telematics supplies data points, nothing more.

### 17.3 Intelligence Interpretation Relationship

Intelligence may use telematics-derived Spine outputs (e.g., a route risk flag or return-home impact figure) as part of its suitability and risk interpretation for a load, exactly as it uses other deterministic scoring outputs (Section 7.4).

### 17.4 Portal Presentation Relationship

Telematics-derived factors surface in Portal only as part of the load/route evaluation card context — never as a standalone automated action trigger.

### 17.5 Telematics Supports, Never Decides

Telematics data is strictly an input to deterministic Spine calculation and Intelligence interpretation. It never triggers autonomous action, never bypasses Portal presentation, and never substitutes for Mike's decision. Full ELD/telematics integration is explicitly deferred from MVP (Section 18.2) and is a build-wave placeholder only (Section 19, Wave 13).

---

## 18. MVP Blueprint

### 18.1 Must Include

- Mike Portal cockpit (decision, review, status, conflict, authority cards).
- Spine state registry (Work Item schema, state list, allowed transitions).
- Work Item lifecycle end to end.
- Portal card flow (generation, display, action collection).
- Manager event triggers (workflow events and exception conditions at minimum; scheduled reviews may follow).
- Publisher draft flow for at least one packet type, with source grounding and status labeling.
- Intelligence interpretation and verification (Verified/Partially Verified/Unverified/Rejected classification) for at least one intake category.
- Library basic approved assets (storage, versioning, current pointer), including immediate acceptance of human-placed documents per the Human Ingestion Rule (Section 8.3a).
- Archive basic retention (storage, version retention rule).
- Version display (`Ver: X` and `Last Change:`) on Portal cards.
- PIN authentication (Identity, PIN, Session records; Authority role at minimum).
- Authority approval audit (Approval Event + Audit Event schemas, fully wired).
- One load/opportunity review loop: Spine scores → Intelligence interprets → Portal presents → Mike decides.

### 18.2 Must Exclude or Limit

- Full external Broker/Customer Portal — architecture must be preserved (Section 16 stays a design constraint) but full implementation is not required for MVP.
- Full telematics integration — position/GPS input may be a placeholder; HOS/ELD and full route-risk automation are deferred.
- Autonomous submission of any kind.
- Autonomous booking of any kind.
- Complex RAG or vector-database-backed retrieval — Library remains a deterministic, directly-queried store for MVP.
- Multi-agent mesh of any kind — MVP uses exactly the six organizational functions and the Spine, nothing more.
- Security sub-library PIN-gated access (Section 8.9) — build after the Security Foundation wave lands.
- Scanner API integration (Section 8.10) — Future build item, not MVP.

### 18.3 What MVP Proves

MVP proves that a real Work Item can move from creation through deterministic validation and scoring, through bounded cognitive interpretation, to a Portal-visible decision, to an authenticated Mike approval, to a recorded audit trail — without any point in the chain requiring Mike to manually track state, chase files, or trust an unaudited AI claim. It proves the architecture is real, not just documented, and gives Mike a genuinely useful daily tool (one packet type drafted, one load loop evaluated) while the rest of the system is built out.

---

## 19. Build Sequence

Each wave states goal, files/modules affected, deliverables, validation checks, human review requirement, and stop/go criteria. Waves are sequential; a wave does not start build work until the prior wave's stop/go criteria are met, per the Constitution's Implementation Rule (Constitution §20): *No Spec. No Prompt. No Build. No Approval. No Implementation.*

### Wave 1 — Architecture Package Freeze
- **Goal:** Freeze the current Repo-3 doctrine set as the locked reference for build.
- **Modules:** All 20 governing/spec documents (read-only reference).
- **Deliverables:** A frozen, tagged snapshot of Repo-3 plus this blueprint.
- **Validation:** Confirm no open doctrine conflicts remain per `SUPERSESSION_MAP.md`.
- **Human review:** Mike reviews and approves the blueprint itself.
- **Stop/Go:** Go only after Mike explicitly approves this blueprint as current.

### Wave 2 — Security and PIN Authentication Foundation
- **Goal:** Stand up Identity, PIN, Session, Role, Permission records and the PIN validation flow.
- **Modules:** `security/` (identity, pin, session, roles, permissions).
- **Deliverables:** Working PIN login for at least the Authority role; Authentication Context schema implemented.
- **Validation:** PIN creation/validation/failed-attempt tests; no plaintext PIN storage anywhere in the repo.
- **Human review:** Mike tests his own login.
- **Stop/Go:** Go only when Mike can log in with his PIN and the session/permissions snapshot is correct.

### Wave 3 — Spine Schema and State Registry
- **Goal:** Implement Work Item, Event, Validation Result, Audit Event schemas and the approved state transition table.
- **Modules:** `spine/schemas/`, `spine/state/`.
- **Deliverables:** State registry enforcing only approved transitions; audit log writing on every transition.
- **Validation:** State transition tests covering every listed transition and rejecting all unlisted ones.
- **Human review:** Not required at this stage (deterministic, testable).
- **Stop/Go:** Go when all transition tests pass.

### Wave 4 — Portal Mike Cockpit
- **Goal:** Build the Mike-facing Portal shell: card list, card detail, action buttons wired to Approval Events.
- **Modules:** `portal/mike/`, `spine/cards/`.
- **Deliverables:** Portal Card schema rendering at all six levels (0–5); approve/reject/revise/defer actions functional.
- **Validation:** Portal card tests; approval event tests.
- **Human review:** Mike walks through the cockpit live.
- **Stop/Go:** Go when Mike confirms the cockpit is usable and every action produces a correct Approval Event.

### Wave 5 — Version Display and Card Model
- **Goal:** Implement `Ver: X` and `Last Change:` display across Portal cards.
- **Modules:** `portal/version/`, `spine/versioning/`.
- **Deliverables:** Version field on every versioned object; last-change label generation.
- **Validation:** Version display tests confirming version increments only on meaningful change.
- **Human review:** Mike confirms the load-board example (Section 11.5) renders as specified.
- **Stop/Go:** Go when version behavior matches Version Doctrine.

### Wave 6 — Intelligence Verification Workflow
- **Goal:** Implement Verified/Partially Verified/Unverified/Rejected classification and source grounding.
- **Modules:** `intelligence/verification/`.
- **Deliverables:** Verification record schema; classification pipeline for one intake source.
- **Validation:** Fact-grounding tests; no-fabrication tests.
- **Human review:** Mike reviews sample classifications for accuracy.
- **Stop/Go:** Go when Unverified/Rejected facts are structurally blocked from Publisher use.

### Wave 7 — Publisher Draft Workflow
- **Goal:** Implement one packet type end to end: draft, status labeling, source mapping, Portal review card.
- **Modules:** `publisher/draft/`, `publisher/source_mapping/`.
- **Deliverables:** One working packet draft flow reaching Mike as a review card.
- **Validation:** No-fabrication tests on Publisher output; status label tests (DRAFT/REVIEW_READY/NEEDS_SOURCE/etc.).
- **Human review:** Mike approves or rejects a real draft.
- **Stop/Go:** Go when a draft can reach `APPROVED_BY_MIKE` only via an authenticated Approval Event.

### Wave 8 — Library and Archive Services
- **Goal:** Implement Library promotion workflow and Archive retention/review queue.
- **Modules:** `library/`, `archive/`.
- **Deliverables:** Library candidate nomination → promotion card → approval → stored asset with version history; Archive Review Queue with Keep/Delete controls.
- **Validation:** Library promotion tests; Archive retention tests (current + 3 prior versions rule).
- **Human review:** Mike runs one promotion and one Keep/Delete decision.
- **Stop/Go:** Go when both workflows produce correct audit trails.

### Wave 9 — Alert Governance Controls
- **Goal:** Implement Mike's alert governance actions (suppress/alter/merge/split/etc.) and the alert change record.
- **Modules:** `spine/alerts/`, `portal/alert_controls/`.
- **Deliverables:** Alert governance UI in Portal; alert change record schema.
- **Validation:** Alert governance tests confirming no alert can be permanently auto-suppressed without a recorded Mike action.
- **Human review:** Mike tests refining one real alert.
- **Stop/Go:** Go when every alert change is attributable to an approved actor and reason.

### Wave 10 — Load and Route Evaluation Loop
- **Goal:** Implement the full loop: Spine scoring → Intelligence interpretation → Portal presentation → Mike decision, for load/opportunity review.
- **Modules:** `spine/scoring/`, `intelligence/load_evaluation/`, `portal/load_cards/`.
- **Deliverables:** One working evaluation loop against real or representative load data.
- **Validation:** Load evaluation tests; no-autonomous-action tests (confirm no booking path exists without Mike approval).
- **Human review:** Mike runs several real evaluations through Portal.
- **Stop/Go:** Go when Mike confirms the recommendation quality and the absence of any autonomous booking path.

### Wave 11 — Driver Portal Foundation
- **Goal:** Build the minimal Driver Portal: assignment view, document upload, check-in.
- **Modules:** `portal/driver/`.
- **Deliverables:** Driver login (PIN), assignment visibility, proof/POD upload.
- **Validation:** Driver portal boundary tests (confirm Driver role cannot reach Authority-only actions).
- **Human review:** Test with one real driver account.
- **Stop/Go:** Go when boundary tests pass and a real upload flow works end to end.

### Wave 12 — Broker / Customer Visibility Foundation
- **Goal:** Build the minimal External Viewer window: shipment status, POD access.
- **Modules:** `portal/external/`.
- **Deliverables:** External Viewer login and one approved visibility view.
- **Validation:** External viewer boundary tests (confirm no internal data leakage).
- **Human review:** Mike approves the specific fields exposed before any external user gets access.
- **Stop/Go:** Go only after Mike explicitly approves the visibility field list.

### Wave 13 — Telematics Input Placeholders
- **Goal:** Define the input contract for GPS/HOS/ELD data without full integration.
- **Modules:** `spine/telematics_input/` (placeholder schema only).
- **Deliverables:** Documented input schema Spine scoring can accept later; no live integration required.
- **Validation:** Schema validation only.
- **Human review:** Not required at placeholder stage.
- **Stop/Go:** Go when the placeholder schema is reviewed for forward compatibility with Section 17.

### Wave 14 — Testing and Hardening
- **Goal:** Run the full testing plan (Section 22) across every wave's deliverables together.
- **Modules:** All.
- **Deliverables:** Full test suite passing; security review complete.
- **Validation:** All categories in Section 22.
- **Human review:** Mike reviews a hardening summary.
- **Stop/Go:** Go only when no unresolved Level 4/5 conflict exists in the test results.

### Wave 15 — Hold Review
- **Goal:** Stabilization checkpoint before promotion to a production-intent repository.
- **Modules:** All.
- **Deliverables:** Stabilized build with no open defects above Level 2.
- **Validation:** Regression pass on all prior wave tests.
- **Human review:** Full Mike walkthrough of every implemented flow.
- **Stop/Go:** Go only on Mike's explicit sign-off.

### Wave 16 — Production-Intent Dispatch Repo Promotion
- **Goal:** Promote the stabilized build into the production-intent Dispatch repository.
- **Modules:** All, per the Target Repository Structure (Section 20).
- **Deliverables:** Promoted repo, tagged release.
- **Validation:** Final promotion checklist against Section 23.
- **Human review:** Mike's explicit deployment approval.
- **Stop/Go:** This blueprint does not authorize this step. It occurs only under separate, explicit Mike approval at the time of promotion.

---

## 20. Target Repository Structure

```text
dispatch/
├── docs/                # doctrine, architecture, blueprint, specs (this document's descendants)
├── frontend/             # Portal client application
│   └── portal/
├── backend/
│   ├── spine/            # deterministic runtime: schemas, state machine, routing, scoring, events, audit
│   │   ├── schemas/
│   │   ├── state/
│   │   ├── routing/
│   │   ├── scoring/
│   │   ├── events/
│   │   └── audit/
│   ├── manager/           # Manager reasoning service
│   ├── publisher/          # Publisher drafting service
│   ├── intelligence/        # Intelligence Analyst: sweepers, acquisition, parsing, scoring feed, analysis, verification
│   │   ├── sweepers/
│   │   ├── acquisition/
│   │   ├── parsing/
│   │   └── verification/
│   ├── library/            # Library service: approved assets, promotion workflow
│   ├── archive/            # Archive service: retention, review queue
│   └── security/            # identity, PIN, session, roles, permissions, audit
├── schemas/               # canonical shared schema definitions (Section 21) referenced by backend modules
├── services/               # shared/cross-cutting services (e.g., notification, report generation)
├── storage/                # file/object storage abstractions (documents, photos, PODs)
├── reports/                # Monday Report, monthly report, Archive Review report generation
├── tests/                  # test suites mirroring backend module structure (Section 22)
├── deployment/              # deployment configuration and promotion tooling (not authorized for use without Mike approval)
└── scripts/                 # build, migration, and maintenance scripts
```

This structure keeps deterministic machinery (`spine/`), organizational functions (`manager/`, `publisher/`, `intelligence/`, `library/`, `archive/`), presentation (`frontend/portal/`), and security (`security/`) cleanly separated, preventing any function from silently absorbing another's responsibility. It is deliberately shallow — enough structure to prevent code spaghetti, not so much that it becomes its own maintenance burden.

---

## 21. Data Model and Schema Roadmap

| Schema | Owning Layer/Function |
|---|---|
| Work Items | Spine |
| Events | Spine |
| Portal Cards | Spine (generated) / Portal (rendered) |
| Approval Events | Spine / Security |
| Conflict Events | Spine |
| Audit Events | Spine / Security |
| User Identity | Security |
| PIN Records | Security |
| Sessions | Security |
| Permissions | Security |
| Library Assets | Library |
| Security Sub-Library Access Records | Library / Security |
| Archive Records | Archive |
| Version Records | Spine (shared field pattern) / applies across Library, Archive, Publisher, Intelligence, Portal |
| Alert Rules | Spine / Portal (governance controls) |
| Intelligence Verification Records | Intelligence |
| Publisher Draft Records | Publisher |
| Load Evaluation Records | Spine (scoring) / Intelligence (interpretation) |
| Driver Submissions | Portal (Driver) / Spine (storage) |
| External Visibility Records | Portal (External Viewer) / Security (permission boundary) |

Each schema listed above must become a concrete build artifact (schema file or equivalent model definition) no later than the build wave that first depends on it (Section 19). Version Records are not a standalone service — they are a shared field pattern (`version`, `last_change`) applied consistently wherever Section 11 requires it.

---

## 22. Testing and Validation Plan

- **State transition tests** — every approved transition in Section 10.3 succeeds; every non-approved transition is rejected.
- **Permission tests** — each role (Authority, Driver, External Viewer, System Service) can perform only its permitted actions.
- **PIN authentication tests** — creation, validation, failed-attempt lockout, change, reset, revocation.
- **Approval audit tests** — every Approval Event produces a linked Audit Event with correct actor, role, object, version, decision, timestamp.
- **Portal card tests** — correct card level, correct required closing, correct allowed actions per level.
- **Version display tests** — version increments only on meaningful change; `Last Change` label correctness.
- **Archive retention tests** — current + three previous versions retained automatically; older versions enter the Review Queue, not silent deletion.
- **Library promotion tests** — no asset reaches Library status without a recorded Approval Event.
- **Fact grounding tests** — every factual claim in Publisher/Intelligence output traces to a source, Library record, or Verification record, or is explicitly marked UNKNOWN/MISSING/NEEDS SOURCE/NEEDS REVIEW/NEEDS MIKE DECISION.
- **Publisher no-fabrication tests** — Publisher output never contains invented facts, credentials, rates, contacts, or source links.
- **Intelligence verification tests** — classification logic correctly assigns Verified/Partially Verified/Unverified/Rejected and blocks Unverified/Rejected from Library/Publisher truth use.
- **Alert governance tests** — no alert is permanently suppressed without a recorded, attributable Mike action; safety/compliance/authority-risk alerts cannot be silently suppressed at all.
- **Load evaluation tests** — Spine scoring, Intelligence interpretation, and Portal presentation each produce correct, source-traceable output for representative load scenarios.
- **Driver portal boundary tests** — Driver role cannot reach Authority-only actions or non-driver views.
- **External viewer boundary tests** — External Viewer role cannot query internal data, see internal scoring, or trigger unapproved workflows.
- **No-autonomous-action tests** — for every path that could plausibly reach booking, submission, approval, or contract commitment, confirm an authenticated Authority Approval Event is structurally required before execution.

---

## 23. Deployment and Promotion Path

The promotion path: **Holding → Claude / Jules Review → Decision Matrix → Final Blueprint → Test-Grounds → Hold → Dispatch.**

| Stage | Purpose | Entry Criteria | Exit Criteria | Allowed Work | Forbidden Work | Mike Approval Point |
|---|---|---|---|---|---|---|
| Holding | Local working collection of current architecture files | Any updated doctrine draft exists | Files are stable and internally consistent | Drafting, editing doctrine | Build work | None required to hold files; required to promote out |
| Claude / Jules Review | Independent clean review of architecture | Holding package frozen | Review findings produced | Analysis, findings, recommendations | Doctrine changes, code | Mike reviews findings before they influence the Decision Matrix |
| Decision Matrix | Sort findings into KEEP / MODIFY / REJECT / DEFER | Review findings exist | Matrix fully populated and reasoned | Evaluation against promotion rules (Decision Matrix §5) | Autonomous adoption of any finding | Mike approves final bucket assignments |
| Final Blueprint | Assemble approved KEEP/corrected MODIFY items into this document | Decision Matrix complete | This document exists and is internally consistent | Synthesis, structuring, gap-filling as blueprint requirements | Introducing REJECTed or unreviewed DEFERred items as current doctrine | **Mike approves this blueprint as current — required before Wave 1 proceeds to Wave 2** |
| Test-Grounds | Experimental build and prototype testing | Blueprint approved | Wave deliverables pass their validation checks | Implementation per approved build waves (Section 19) | Production deployment, external submission, autonomous action of any kind | Mike reviews each wave's stop/go criteria |
| Hold | Stabilization and review lane | All build waves complete and tested | No open defect above Level 2; full Mike walkthrough passed | Bug fixing, hardening, regression testing | New feature work, doctrine changes | Mike's explicit sign-off (Wave 15) |
| Dispatch | Production-intent repository | Hold stage signed off | N/A — this is the destination | Promotion per Section 20 structure | Any deployment action without a separate, explicit, contemporaneous Mike approval | **Mike's explicit deployment approval — not granted by this document** |

Code moves from experiment to production-intent repository only through this full chain, with an explicit Mike approval gate at Final Blueprint, at Hold, and again at Dispatch promotion itself. No stage may be skipped, and no stage's output becomes doctrine or authorizes deployment merely by having been produced.

---

## 24. Risks and Mitigations

| Area | Risk | Mitigation |
|---|---|---|
| Architecture | Role-boundary drift as the system grows (a function quietly absorbing another's job) | Constitution §5/§11 (No Architecture Drift Rule); every function change requires approved spec + Mike approval |
| Security | Plaintext PIN exposure or credential leakage to cognitive functions | Security Spec §14.13–14.14 boundaries; forbidden actions list (§14.18); no-plaintext-PIN build requirement |
| Portal | Portal becomes an alert wall, causing Mike to tune out | Consequence-level filtering (Section 4.4) + Version Doctrine (fewer redundant cards) + Alert Governance (Mike-controlled refinement) |
| Manager | Manager drifts into a free-roaming LLM router or direct chat interface | Manager §12 forbidden actions; activation strictly limited to four trigger classes (Section 5.1) |
| Spine | Undertested state transitions allow invalid or hidden state changes | Build-readiness standard (Section 10.9) requires transition/routing/validation/audit/card/approval/conflict tests before build-ready status |
| Publisher | Fabricated or overstated facts reach a customer or government packet | Source grounding rules (Section 6.2) + Intelligence Verification gate (Section 12.4) + status labeling that blocks self-assigned approval |
| Intelligence | Intelligence output is treated as decided fact rather than interpretation | Verification classifications (Section 12.2) + explicit forbidden actions (Section 7.6) + Portal reliability display (Section 12.7) |
| Library | Unverified or unapproved material is promoted into reusable truth | Library promotion workflow requires an Approval Event (Section 8.3); Publisher/Intelligence can nominate but never promote |
| Archive | Uncontrolled accumulation of stale versions, or silent deletion of history | Version retention rule + Archive Review Queue + Keep/Delete controls, never silent (Section 9) |
| Driver access | A driver account reaching Authority-only or customer-facing functionality | Role/permission boundaries (Section 14.5, 14.15) + driver portal boundary tests (Section 22) |
| External access | An external viewer reaching internal data, scoring, or workflow triggers | External Viewer boundary rules (Section 14.16) + explicit Mike approval of exposed fields (Wave 12 stop/go) |
| Telematics | Live position/HOS data is treated as decision-making rather than input | Section 17.5 — structurally an input to Spine scoring only; no autonomous trigger path; full integration deferred from MVP |
| Versioning | Version numbers increment on noise, defeating the purpose of the doctrine | Version display tests (Section 22) enforce "meaningful change only" per Section 11.2 |
| Alerts | Alert suppression becomes uncontrolled or hides real risk | Alert Governance Doctrine core rule (Section 13.1) — no uncontrolled automatic suppression; safety/compliance/authority risk can never be silently suppressed |
| Deployment | A build stage output is treated as authorization to deploy or merge | Explicit Mike approval gates at every promotion stage (Section 23); this blueprint itself authorizes nothing beyond planning |

---

## 25. Final Blueprint Recommendation

**Is Dispatch ready for final blueprint status?**
Yes. The current Repo-3 source package is internally consistent: the Constitution, context, architecture, all six organizational function documents, the Spine specification, and the four hardening doctrines (Version, Archive Review, Intelligence Verification, Alert Governance, Security) all agree on the same five-layer model, the same six organizational functions, and the same authority boundaries. No unresolved doctrine conflict blocks assembly of this blueprint.

**Is Dispatch ready for build planning?**
Yes, for the MVP scope defined in Section 18, following the build sequence in Section 19. It is not ready for production deployment — that requires completing the full promotion path in Section 23 and a separate, explicit Mike approval.

**What must be built first?**
Security and PIN authentication foundation (Wave 2), immediately after the Spine schema/state registry (Wave 3) — authority and traceability must exist before any cognitive function or Portal action is wired up, so that every subsequent capability is auditable from day one.

**What must never be built?**
Any path by which a load is booked, a contract is committed, a package is submitted externally, or a fact/rate/compliance/final-document determination is approved without a Portal-mediated, authenticated Authority Approval Event. No Dispatcher Agent. No return to an 11-agent mesh. No self-modifying prompts or code. No hidden decision path outside Portal.

**What requires Mike's decision?**
This blueprint's approval as current doctrine (before Wave 1 completes); every stop/go gate in the build sequence (Section 19); every promotion-path stage gate (Section 23); every Authority action defined in Sections 3 and 14; the specific fields exposed to any External Viewer (Wave 12); and, ultimately, the production deployment decision itself, which this document does not and cannot grant.

**What should be reviewed before coding?**
The Spine state transition table and schemas (Section 10) should get one more pass for completeness against real operational scenarios Mike expects Dispatch to handle in its first 90 days, since every other function depends on the Spine being correct before they're built on top of it.

**What is the cleanest first prototype?**
A single load/opportunity evaluated end to end: Spine scores it, Intelligence interprets it, Portal presents it as a decision card with `Ver: 1`, and Mike approves or rejects it through an authenticated PIN session that produces a correct Approval Event and Audit Event. This single loop exercises Security, Spine, Intelligence, Portal, and the audit trail together — the smallest slice that proves the whole architecture works.

**What is the path from blueprint to working Dispatch?**
Mike approves this blueprint → Waves 1–16 execute in order, each gated by its own stop/go criteria and, where specified, Mike's direct review → the system stabilizes at Hold → Mike grants a separate, explicit deployment approval → the production-intent Dispatch repository goes live. At no point in that path does approval, submission, booking, or authority transfer happen without Mike acting through an authenticated Portal session.

---

## Authority Closing

This is a final blueprint draft only.

No deployment is authorized.
No code merge is authorized.
No doctrine change is authorized unless Mike approves.
No production code, autonomous approval, autonomous booking, autonomous submission, autonomous contract commitment, or authority transfer is authorized by this document.

Mike Zachary remains final authority.

**Mike decides.**
