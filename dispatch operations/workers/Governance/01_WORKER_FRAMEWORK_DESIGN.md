# DISPATCH WORKER FRAMEWORK DESIGN
**Document ID:** 01_WORKER_FRAMEWORK_DESIGN.md
**Status:** BINDING GOVERNANCE AND ARCHITECTURE
**Location:** D:\Dispatch Operations\Workers\Governance\01_WORKER_FRAMEWORK_DESIGN.md
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
