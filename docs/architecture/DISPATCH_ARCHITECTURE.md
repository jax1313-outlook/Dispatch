# Dispatch — Architecture

**Program:** Dispatch · **Owner/operator and final authority:** Mike Zachary
**Status of this document:** current as of 2026-08-25. Describes what the repository
**is**, not what it should become.

This is the architecture reference and the **map to every other document**. It was written
because the repository had accumulated ~60 top-level markdown files with no index, so a
builder arriving cold could not tell doctrine from a superseded report. Nothing here
replaces those documents; §1 tells you which one to open.

---

## 1. The document map

### 1.1 Read these first — they bind

| Document | What it settles |
|---|---|
| `CLAUDE.md` | Cold-start brief. Program, mission, authority, boundaries, working rules. |
| `DISPATCH_PURPOSE_STATEMENT.md` | The four verbs, and ten guiding architectural discoveries. |
| `DRIVER_FIRST_DOCTRINE_v2.md` | D1–D15, including the 70 MPH Test. Supersedes v1. |
| `DECISION_LOG.md` | Every decision, in date order. The authority of last resort. |
| `docs/governance/DISPATCH_AUTHORITY_AND_BOUNDARIES.md` | Who decides what; what software may never do. |
| **This file** | Subsystems, data flow, boundaries, and the document map. |

### 1.2 Operating Dispatch

| Document | What it is for |
|---|---|
| `DISPATCH_FIRST_START_GUIDE.md` | Never started it before. Where the launcher lives and what first start does. |
| `docs/operations/DISPATCH_OPERATOR_GUIDE.md` | Day-to-day operation. |
| `docs/readiness/CONTROL_CENTER.md` | The eight controls and seven displays. |
| `docs/maintenance/DISPATCH_MAINTENANCE_GUIDE.md` | Backups, restores, upgrades, database care, log hygiene. |
| `BACKUP_AND_RECOVERY.md` | The full backup/restore reference the maintenance guide summarizes. |
| `DEPLOY_LOCAL.md`, `DEPLOY_VPS.md` | Deployment procedures. |

### 1.3 Readiness — what is proven and what is not

| Document | What it is for |
|---|---|
| `docs/readiness/OPERATIONAL_PROOF.md` | The single current readiness answer. Start here. |
| `docs/readiness/KNOWN_LIMITATIONS.md` | What is broken, missing, assumed, or unproven — and the next blocker. |
| `docs/readiness/OPERATIONAL_PROOF_PROCEDURE.md` | How to actually run the twenty-step load proof. |
| `docs/readiness/LAUNCHER_PROOF_TEMPLATE.md` | The fifteen first-start acceptance items. |
| `docs/readiness/OPERATIONAL_LOAD_PROOF_TEMPLATE.md` | The twenty-step load proof, blank. |
| `docs/readiness/COMPLETION_REPORT.md` | The Operational Readiness Mission's own report. |
| `docs/readiness/SANDBOX_SURVEY_PROCEDURE.md` | The read-only Sandbox survey and its templates. |

### 1.4 Extending Dispatch

| Document | What it is for |
|---|---|
| `docs/connectors/PROVIDER_INSERTION.md` | Adding an external provider. The only sanctioned route. |
| `docs/MANAGER.md` | Permanent record of a capability named and never built. **Authorizes nothing.** See §7.3. |
| `docs/CANONICAL_RECONCILIATION_INTEGRATION.md` | Tri-department object reconciliation. |

### 1.5 Subsystem architecture notes

`DISPATCH_DYNAMIC_CAPACITY_ARCHITECTURE.md` · `WEEK_VIEW_CAPACITY_VISUALIZATION_ARCHITECTURE.md` ·
`TRUCK_ARRANGEMENT_AND_LOAD_CONFIGURATION_ARCHITECTURE.md` · `DRIVER_PORTAL_ARCHITECTURE_V2.md` ·
`OPPORTUNITY_PIPELINE_ARCHITECTURE.md` · `CURRENT_REALITY_VS_POSSIBLE_FUTURES_ARCHITECTURE.md` ·
`DISPATCH_CF04_LIFECYCLE_AUTHORITY_MODEL_v1.md` · `DISPATCH_SPINE_OWNERSHIP_PARTITION_AMENDMENT_v1.md` ·
`governance/PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md`

### 1.6 Historical — reports, audits and matrices

Everything else at the repository root is a **record of work done at a point in time**:
audits (`DISPATCH_WHOLE_PROGRAM_AUDIT.md`, `DISPATCH_AUDIT_AMENDMENT.md`), inventories,
build matrices (`_v1`, `_v2`, and the current `DISPATCH_BUILD_MATRIX.md`), campaign plans,
walkthrough reports (`PHASE*`, `M1_`, `M3_`, `MA_`, `C3_`, `W0-*`), and recovery reports.

**They are history. They are not instructions.** Where one contradicts §1.1, §1.1 wins.
Where a matrix exists in several versions, the highest version is current and the lower
ones are superseded. Do not delete them — see the Repository Doctrine entry in
`DECISION_LOG.md`.

### 1.7 Dispatch's standing

**Dispatch is the General Contractor, System of Record, and Operational Authority**
(`DECISION_LOG.md` 2026-08-25). It coordinates core operational work and uses external
wheels or optional plug-ins where appropriate, and it **remains complete and operational
without optional plug-ins**.

That last clause is what §4.6 enforces and what `tests/test_repository_doctrine.py` tests.

---

## 2. Subsystems

```
                            ┌──────────────────────────┐
   double-click ──────────► │  dispatch_launcher/      │  start · stop · restart
   dispatch.bat             │  Control Center v1       │  status · settings · version
                            └───────────┬──────────────┘  reset session
                                        │ starts, observes; never bypasses
                                        ▼
                            ┌──────────────────────────┐
   browser ───────────────► │  portal/  (Flask)        │  8 blueprints, ~40 templates
                            │  a window, not a store   │
                            └───────────┬──────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
┌───────────────┐            ┌─────────────────────┐        ┌────────────────────┐
│ dispatch/     │            │ dispatch/spine/     │        │ cin_lite/          │
│ freight core  │◄──────────►│ lifecycle authority │        │ govcon pipeline    │
│ 22.7k lines   │            │ 25 states           │        │ + mail transport   │
└───────┬───────┘            └─────────────────────┘        └────────────────────┘
        │
        │ every external system passes through here, and only here
        ▼
┌──────────────────────────────────────────────────────────────────────┐
│ dispatch/connectors/   contract · boundary · audit · registry        │
│ 8 connectors, all UNCONFIGURED · 1 mock, SIMULATED, unregistered     │
└──────────┬───────────────────────────────────────────────────────────┘
           │  (plug-ins — none required for startup)
           ▼
   route_risk/ · sync/ · reconciliation/ · Mission Visibility · SAM · Assistant
```

| Package | Lines | Responsibility |
|---|---|---|
| `dispatch/` | ~22,700 | Freight core: loads, drivers, equipment, capacity, truck arrangement, milestones, evidence, POD, IFTA, settlement, scoring, opportunities, backup, tokens, notifications |
| `dispatch/spine/` | (within the above) | The lifecycle authority. State machine, event log, work items, portal cards, approvals, conflicts, audit |
| `dispatch/connectors/` | (within the above) | The governed external boundary |
| `portal/` | ~8,500 | Flask application: 8 blueprints, ~40 Jinja templates. Presentation and request handling only |
| `dispatch_launcher/` | ~3,000 | Process control and observation. Windows-native entry point |
| `cin_lite/` | ~3,200 | Government-contracting pipeline; **also Dispatch's sole mail transport** |
| `route_risk/`, `sync/`, `reconciliation/` | ~1,400 | Plug-ins. Optional by construction |
| `scripts/` | ~500 | Operator entry points: proof, backup, sandbox survey |
| `tests/` | ~38,900 | 129 files |

### 2.1 Storage

One SQLite database, `sqlite3` from the standard library, **WAL journal mode, foreign keys
enforced**. No external database, no ORM, no migration framework — schema is created
idempotently with `CREATE TABLE IF NOT EXISTS`.

- Freight tables (25): `loads`, `drivers`, `equipment`, `milestones`, `evidence`,
  `exceptions`, `pod_packages`, `activities`, `expenses`, `settlements`, `driver_pay`,
  `rate_confirmations`, `broker_contacts`, `detention_events`, `lane_templates`,
  `maintenance_schedules`, `compliance_documents`, `retention`, `visibility`,
  `route_risk_events`, and the five `ifta_*` tables.
- Spine tables (6): `events`, `work_items`, `portal_cards`, `approval_events`,
  `conflict_events`, `audit_events`.

**The database is created on first freight-data read, not at start.** A launcher that has
never shown a load has no `dispatch.db`, and that is correct behaviour rather than a fault.

### 2.2 The five roots

Every path Dispatch uses resolves from an environment variable with a documented fallback.
Nothing is hard-coded and nothing is guessed:

| Variable | Holds |
|---|---|
| `DISPATCH_OPERATIONS_ROOT` | Working files, database, logs |
| `DISPATCH_ARCHIVE_ROOT` | Completed loads and PODs |
| `DISPATCH_MEMORY_ROOT` | Evidence, receipts, the library |
| `DISPATCH_BACKUP_DIR` | Backups |
| `DISPATCH_LAUNCHER_LOG_DIR` | Launcher PID file and logs |

Unset means the surface reports `UNCONFIGURED` **and names the fallback it will use
instead** — it never prints the fallback as though someone had chosen it.

---

## 3. Data flow

### 3.1 Possibility → reality (the one-way gate)

```
INTELLIGENCE  →  ANALYSIS  →  SCORE  →  FILTER/SORT  →  OPPORTUNITY CARDS
                                                                │
                                                    Mike decides (and only Mike)
                                                                ▼
                                            COMMIT LOAD  →  CALENDAR  →  CURRENT REALITY
```

Opportunity Cards store **possibilities**. The Calendar stores **commitments**. The two are
never merged and a possibility must never render as though it were a commitment.

### 3.2 Load lifecycle

`dispatch/spine/` holds **25 states**, from `CREATED` through `WAITING_FOR_MIKE`,
`MIKE_APPROVED` / `MIKE_REJECTED` / `MIKE_REQUESTED_REVISION`, to `COMPLETED` and
`ARCHIVED`.

- `spine.state.transition()` **computes** a transition and refuses illegal ones.
- `spine.store.apply_transition()` **persists** it and writes the audit event.

Nothing else may move a load between states. A route that mutates lifecycle state directly
is a defect.

### 3.3 Execution

`Mission assigned → Driver Portal shows Active Mission → milestones tapped →
evidence and POD attached → exceptions raised → settlement and IFTA → archive.`

Every milestone write goes through `services.add_milestone()`, so the M1 transition gate and
the C3 audit symmetry both apply. Every evidence write goes through `attach_evidence()`, so
the extension allowlist, the size cap and the SHA-256 checksum all apply. **A refused
transition must be shown to the driver** — see `CLAUDE.md` §3.

### 3.4 Government contracting (CIN-Lite)

`acquire (SAM.gov) → process (9 deterministic rule modules) → summarize + recommend route
→ control email → human decides → archive + route + email → [if approved] proposal workflow`

See §6.

---

## 4. Boundaries that are load-bearing

### 4.1 The Spine decides; everything else advises

CF-04, adjudicated 2026-08-23 (`DECISION_LOG.md`, `DISPATCH_CF04_LIFECYCLE_AUTHORITY_MODEL_v1.md`).
Opportunity scoring, Route Risk, capacity and every connector **advise**. They produce
inputs. The Spine owns the transition.

### 4.2 The portal is a window (Driver-First D5)

`portal/` renders state and handles requests. It does not hold a second copy of the truth,
and it does not own lifecycle. Presentation logic in a route is fine; business rules in a
template are not.

### 4.3 The launcher controls, it does not reimplement

`dispatch_launcher/` starts, stops, observes and reports. It is **not a second Dispatch**.
It does not duplicate portal functionality, it does not read freight data, and it may not
import `dispatch.*` — the two places where it needs a shared constant duplicate the literal
and pin it with a test instead (THE MIKE RULE, §4.6).

### 4.4 Every external system enters through a connector

`dispatch/connectors/` is a fixed contract plus a boundary, an audit trail and a registry.
Eight connectors exist — email transport, load board, mapping, accounting, scanner,
route risk, Outlook, future intelligence — and **all eight report `UNCONFIGURED`**. One mock
reports `SIMULATED` and is deliberately not registered.

The boundary is structural, not advisory: a connector cannot reach into Dispatch's stores.
See `docs/connectors/PROVIDER_INSERTION.md`.

### 4.5 Outlook is the scheduling authority

Dispatch may create or request schedule information through an approved interface, read it,
present it, use it for capacity awareness, and show gaps and conflicts. **Dispatch must not
create a separate competing scheduling system.**

The Driver Portal Calendar is a Monday-through-Sunday visual capacity board that presents
Outlook schedule data — **not an independent calendar database**. This is the same boundary
as §4.2 applied to time: the calendar is a window onto committed reality, not a second place
where scheduling truth is decided.

Familiar terms only: `Calendar`, `PU`, `DEL`.

### 4.6 Plug-in separation

Route Risk, Mission Visibility, SAM and Assistant are plug-ins.

- Dispatch starts and runs core operation without any of them.
- Assistant code is never embedded into Dispatch; Dispatch is never redesigned around it.
- **No direct Dispatch write authority may be granted to Assistant.**
- **Degradation is permitted. Incapacity is not.**

Guarded by `tests/test_repository_doctrine.py`.

### 4.7 THE MIKE RULE

Subsystems stay standalone even at the cost of a little duplication. A subsystem that can
be lifted out and run alone is worth more than one sharing a clever abstraction. Do not
consolidate across a subsystem boundary without a `DECISION_LOG.md` entry.

---

## 5. Honesty mechanisms (they are architecture, not decoration)

| Mechanism | What it prevents |
|---|---|
| **The eight truth words** (`CLAUDE.md` §6), validated in `__post_init__` | A surface inventing a status like "OK" or "ready" that means nothing |
| **Rehearsal mode** (`dispatch/rehearsal.py`) | A practice load being mistaken for a live one. Records carry a permanent `REHEARSAL` tag through the same code path |
| **The 20-step proof path** (`dispatch/proof.py`) | "It works" without evidence. Six steps are `NOT_AUTOMATABLE` by design — a human must perform them or the proof is not operational |
| **The readiness checks** (`dispatch/readiness.py`) | Assuming a path is writable. Writability is proven by writing a probe file |
| **Backup status** | A backup being called valid. Nothing reads `VERIFIED` without a restore-verification record that only a real restore produces |
| **Secret redaction** | A key reaching a log. Settings are named; values never printed |
| **Mike-attribution refusal** | An approval nobody gave |

---

## 6. CIN-Lite — the government-contracting half

*Preserved from the previous `CLAUDE.md`, which described this and only this. Authoritative
spec: `Final_Architecture_for_Hybrid_CIN-Lite_System (1).docx`. Full guide:
`cin_lite/README.md`.*

Five layers, and their responsibilities stay separate:

1. **Acquisition** — fetches contracts from designated sources.
2. **Processing** — applies rule modules to extract intelligence.
3. **Control** — email-based approval/rejection/routing. The human decision gate.
4. **Archive** — stores structured outputs and raw files.
5. **Automation** — orchestrates acquisition → processing → email → archive.

**Rule modules.** Each is a standalone logic unit emitting structured JSON, and each must be
**deterministic** — no nondeterministic LLM call inside the deterministic rule path. The nine:
set-aside detection, NAICS/SIN extraction, past-performance relevance, pricing anomalies,
vendor network indicators, subcontractor dominance, JV/MP structure flags, foreign influence
indicators, cyber compliance readiness. New rules are new modules, never folded into a monolith.

**Email control.** A checkbox-driven HTML email with five actions: Approve for archive,
Approve for proposal, Reject, Flag for review, Request deeper analysis. Each is a styled
button linking to `/api/decision/<id>/<action>?token=…`; tokens are HMAC-SHA256 signed. The
pipeline stores a pending decision, sends the email, the reviewer clicks, the portal archives
and routes, and a confirmation page renders. This logic stays clean and deterministic.

**Archive layout.**

```
/Archive
  /Raw            raw fetched files
  /Processed      processed contract data
  /Intelligence   rule-module JSON outputs
  /Summaries      generated summaries
  /Routing        routing decisions
  /Pending        decisions awaiting reviewer action (transient)
```

**Constraints:** lightweight · locally controllable · expandable into full CIN · rule logic
deterministic.

**Roadmap:** Phase 1 (current) acquisition, rule modules, email control, archive engine ·
Phase 2 proposal-trigger workflows and deeper intelligence modules · Phase 3 full CIN plus
AZP compatibility.

---

## 7. Conflicts between code and doctrine

Recorded rather than silently resolved, per `CLAUDE.md` §7.

### 7.1 `ROUTED_TO_MANAGER` is a live Spine state name — **OPEN, needs Mike's decision**

The No-Manager rule says not to create, restore, reference or infer a Manager component.
`dispatch/spine/models.py` `STATE_LIST` contains **`ROUTED_TO_MANAGER`**, one of the 25
lifecycle states.

What it is and is not:

- It is a **string in a state list**. There is no Manager module, class, route, table,
  agent or authority anywhere in the code — verified, see §7.5.
- It predates the No-Manager rule and comes from the tri-department reconciliation planning
  recorded in `docs/MANAGER.md`.
- It is **persisted data**. Any load that has ever been in that state carries the string in
  `events` and `audit_events`. Renaming it is a data migration with an audit-history
  rewrite attached, not a find-and-replace.

**Not changed here.** Renaming a persisted lifecycle state is Mike's decision, not a
builder's, and doing it as a side effect of a documentation mission is exactly the kind of
quiet change the doctrine forbids. Three options, stated as options:

1. Leave it. The rule forbids a Manager *component*; a legacy state string is not one.
2. Rename to `ROUTED_TO_REVIEW` with a migration that rewrites existing rows and an entry
   recording that the audit trail was rewritten and why.
3. Rename forward only — new transitions use the new name, historical rows keep the old —
   and document both as valid readings of the same state.

Recommendation, marked as a recommendation: **option 1 plus a comment in `models.py`**
citing this section. It is the only option that changes no persisted history.

### 7.2 The portal called itself "L2-COS Operations Portal" — **RESOLVED 2026-08-25**

The program is Dispatch; its own chrome said otherwise across ~20 templates. Recorded as
known gap 10 in `docs/readiness/COMPLETION_REPORT.md` and fixed in the mission that produced
this document.

### 7.3 The portal required an optional plug-in to start — **RESOLVED 2026-08-25**

§4.6 says Dispatch must run with every plug-in absent. It could not: `portal/routes/driver_portal.py`
imported `dispatch.route_risk` at module scope, which imported the standalone `route_risk`
engine at module scope, so an uninstalled optional advisor broke `create_app()` outright.

Fixed at the binding (`dispatch/route_risk.py`): the import is absorbed, `ENGINE_STATUS`
reports `ABSENT` or `CONFIGURED`, reads degrade to a reading that names the absence, and
writes refuse with `RouteRiskUnavailable` rather than silently discarding a recorded hazard.
Guarded by `tests/test_repository_doctrine.py`, which found it.

### 7.4 `docs/MANAGER.md` exists under a No-Manager rule — **not a conflict**

It is the permanent record of a capability named in planning and never built, and it says so
on its first line. Keeping it is what stops the idea being re-proposed as though it were new.
It authorizes no code, no route, no data model and no runtime behaviour.

### 7.5 What "no Manager component" was verified against

Every `Manager` / `manager` occurrence in Python across the repository, as of 2026-08-25:

| Occurrence | What it is |
|---|---|
| `dispatch_launcher/control.py` ×5, `tests/test_launcher.py` ×2 | **"Task Manager"** — the Windows application, in operator instructions |
| `tests/test_architecture_discoveries.py` ×3, `tests/test_dynamic_capacity.py` ×2 | **"Fleet Manager"** — a human job title in a `verified_by` string |
| `dispatch/rehearsal.py` | "context manager" — Python |
| `portal/models/integrations_registry.py` ×2 | "secrets manager" — the class of product |
| `cin_lite/workflows/proposal.py` | "proposal manager" — a human role in a checklist item |
| `dispatch/spine/__init__.py` | A docstring saying the Spine does **not** replace Manager |
| `portal/helpers.py` | A comment saying a capability is **explicitly not** Manager |
| `dispatch/spine/models.py` | `ROUTED_TO_MANAGER` — §7.1 |

No component. The last three are the doctrine asserting itself in the code, which is the
correct place for it.
