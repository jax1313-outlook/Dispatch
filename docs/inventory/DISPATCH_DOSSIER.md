# DISPATCH_DOSSIER.md

Repository inventory dossier. Authority: Mike Zachary.
Compiled 2026-09-05 from the repository at commit `3c03ab2` (`origin/main`).

Recovery operation only. This dossier records what exists. It makes no design,
archive, cleanup, or refactor recommendation.

---

## SECTION 1 — REPOSITORY FACTS

| Fact | Value | How established |
|---|---|---|
| Repository name | `Dispatch` | `git remote get-url origin` |
| Repository URL | https://github.com/jax1313-outlook/Dispatch | same |
| Visibility | Public | `list_repos` |
| Creation date (first commit) | 2026-08-02 15:35:43 -0400 | `git log --reverse` |
| Last commit date | 2026-08-31 09:16:34 -0400 (`3c03ab2`, "Merge pull request #127 from jax1313-outlook/remove-broker-trust-scoring") | `git log -1` |
| Last push to repo (any branch) | 2026-09-04T23:48:37Z | `list_repos` `pushed_at` |
| Branch count | **64** remote branches | `git ls-remote --heads` |
| Commit count (main) | **220** | `git rev-list --count HEAD` |
| Default branch | `main` | `git ls-remote` / local HEAD in sync with `origin/main` |
| Contributors | `jax1313-outlook` (138), `Claude <noreply@anthropic.com>` (71), `google-labs-jules[bot]` (11) | `git shortlog -sne` |
| README status | Present — `README.md` at root | `git ls-files` |
| Tracked files | 459 | `git ls-files \| wc -l` |
| Python | 279 files, **82,699 lines** | `git ls-files '*.py'` + `wc -l` |
| Markdown | 112 files, 21,940 lines | same method |
| HTML templates | 41 | `git ls-files '*.html'` |

**Note on `pushed_at`.** The repository's most recent push (2026-09-04) is newer than
the newest commit on `main` (2026-08-31). Work exists on non-`main` branches. 64 branches
are listed in Section 3.

---

## SECTION 2 — PURPOSE

**Evidence sources:** `CLAUDE.md`, `DISPATCH_PURPOSE_STATEMENT.md`,
`docs/architecture/DISPATCH_ARCHITECTURE.md`, `DRIVER_FIRST_DOCTRINE_v2.md`, and the code.

Dispatch is the **freight-operations platform of Level 1 Transport**, an owner-operator
trucking business. `CLAUDE.md` §1 states its purpose is to reduce the owner/operator's
cognitive load: "to show what is true now, lay out what could become true, let a human
choose, and then help execute the mission that was chosen."

`DISPATCH_PURPOSE_STATEMENT.md` gives the four verbs the program is measured against:

> 1. See Reality. 2. Evaluate Possibilities. 3. Choose A Future. 4. Execute The Mission.

`CLAUDE.md` §1 also records Dispatch's declared standing in its own ecosystem
(General Contractor Doctrine, `DECISION_LOG.md` 2026-08-25):

> Dispatch is the General Contractor, System of Record, and Operational Authority.
> Dispatch remains complete and operational without optional plug-ins.

The repository holds **two programs**, both documented in `CLAUDE.md` §1:

1. `dispatch/`, `portal/`, `dispatch_launcher/` — the freight platform (the active program).
2. `cin_lite/` — a government-contracting solicitation pipeline, and Dispatch's only mail transport.

Authority model (`CLAUDE.md` §4, `docs/governance/DISPATCH_AUTHORITY_AND_BOUNDARIES.md`):
Mike Zachary is final authority; software and AI hold zero decision authority; score does
not decide; no Mike attribution may be manufactured.

---

## SECTION 3 — DIRECTORY MAP

```
Dispatch/
├── dispatch/                  Freight domain core (business logic, no HTTP)
│   ├── spine/                 Load lifecycle authority — the decision engine
│   ├── connectors/            Governed external-system boundary (8 connectors + registry)
│   ├── sandbox_survey/        Sandbox file-survey tooling
│   ├── models.py              24 dataclasses: Load, Driver, Equipment, Settlement, IFTA…
│   ├── store.py / db.py       SQLite persistence (WAL, FK enforced)
│   ├── capacity.py            Capacity computation (available/consumed/reserve/position)
│   ├── opportunities.py       Opportunity Cards — possibilities, not commitments
│   ├── scoring.py             Noise-reduction scoring (advisory only)
│   ├── comi_routing.py        COMI routing
│   ├── route_risk.py          Route Risk plug-in surface
│   ├── proof.py               20-step operational-proof system
│   ├── rehearsal.py           Rehearsal mode
│   ├── backup.py              Backup / restore
│   ├── tokens.py              Operational token issue / expiry / revoke
│   ├── truck_arrangement.py   Truck & load configuration
│   ├── accounting_export.py   Accounting export
│   ├── notifications.py       Internal notifications
│   ├── customer_notifications.py  Customer-facing notifications
│   ├── email_helper.py        Email drafting helper
│   ├── acquisition.py         Load acquisition
│   └── readiness.py           Readiness reporting
├── portal/                    Flask web layer (a window over state, per D5)
│   ├── app.py, config.py, csrf.py, errors.py, helpers.py, cli.py
│   ├── routes/                9 blueprints, 178 unique route paths
│   ├── models/                12 portal-side models
│   └── templates/             41 Jinja templates
├── dispatch_launcher/         Windows launcher + Control Center (15 modules)
├── cin_lite/                  Government-contracting pipeline + mail transport
│   ├── rules/                 9 deterministic rule modules
│   ├── agents/                5 Claude-backed non-deterministic helpers
│   ├── workflows/             proposal workflow
│   └── sample_data/           sample contracts
├── tests/                     137 files, 3,793 `def test_` functions
├── docs/                      architecture / governance / operations / maintenance /
│                              connectors / readiness (+ 24 root-level spec docs)
├── .github/workflows/         CI
├── DISPATCH_START_HERE.cmd    Documented launch path
├── dispatch.bat, Dispatch.ps1 Alternate launchers
└── bootstrap_d_drive.py       D: drive bootstrap
```

**Folder purposes**

- `dispatch/spine/` — `state.py` computes a transition; `store.py` persists it. `CLAUDE.md`
  §5.1: "Opportunity **advises**; the Spine **decides**." Also `commitment.py`, `models.py`, `db.py`.
- `dispatch/connectors/` — `boundary.py`, `contract.py`, `registry.py`, `audit.py`, `mock.py`
  plus 8 provider connectors. `CLAUDE.md` §5.4: every external system enters here.
- `portal/` — presentation. `CLAUDE.md` §5.2/D5: the portal displays state, it does not hold
  a second copy.
- `cin_lite/` — separate program, kept standalone per THE MIKE RULE (`CLAUDE.md` §5.7).

### Branches (64)

`main` plus 63 others, including: `arch-discoveries-update-…`, `block-01-label-sample-data`,
`block-04-one-copy`, 30 `claude/*` feature branches (`ai-agent-collector-module`,
`comi-status-everywhere`, `contact-routing-foundation`, `d1-status-transition-gate`,
`driver-load-search`, `driver-pin-registry`, `end-load-completion-packet`,
`mission-visibility-foundation`, `operations-feed`, `stakeholder-portal`,
`system-keys-registry`, `sdvosb-contract-opportunities`, …), 6 `dispatch/*` branches,
`docs/manager-reinforcement`, `doctrine/auto-interest-email-exception`,
`feat-d-drive-bootstrap-…`, `joe-portal`, 3 `jules*` branches, `portal-deploy`,
12 `stage*` branches (`stage12-manager-archive-wiring`, `stage12-manager-foundation`,
`stage12-manager-m7-policy-hook`, `stage2`–`stage7`, `stage13-testing-hold-review`),
`remove-broker-trust-scoring`, `wire-scoring-to-capacity`, `externalize-policy-profile`.

**Finding:** three `stage12-manager-*` branches and `docs/manager-reinforcement` exist
even though `CLAUDE.md` §5.6 states "There is no Manager component in the current
architecture." Recorded as fact; no recommendation offered.

### Off-`main` content — 245 files exist on branches and not on `main`

A file-by-file comparison of every branch against `main` was run for this inventory. Whole
subsystems exist on branches only:

| Subsystem | Files | Python LOC | Branch(es) | Tip |
|---|---|---|---|---|
| **`joe-portal`** — JOE Portal, Driver Cockpit, Mission Intake, Booking Board, Arrival Notice, Outlook mail connector | 59 not on `main` | ~14,000 | `joe-portal` (**48 commits ahead of `main`**) | **2026-09-03** |
| **`cin-hybrid/`** — 16 agents, 7 intel modules, 11 services, 3 runtime modules, CLI, 3 test files | 42 | 1,125 | `feature/init-hybrid-structure`, `claude/sdvosb-contract-opportunities-76rgtu`, `claude/va-2026-541512-exec-summary-lpgno3` | 2026-07-03/04 |
| **`l2_cos/`** — a freight-oriented CIN variant: 6 rules (`broker_risk`, `capacity_match`, `deadhead_cost`, `facility_risk`, `lane_fit`, `rate_anomaly`), a 5-module UI, workflows, models | 34 | 1,805 | `claude/l2-cos-dispatch-refactor-c1ett1` | 2026-07-27 |
| **`dispatch/manager/`** — `classify`, `policy_candidates`, `priority`, `security_monitor`, `signals`, `staff_report`, `stage_gate` | 7–8 | 767–866 | `stage12-manager-foundation`, `stage12-manager-archive-wiring`, `stage12-manager-m7-policy-hook`, `stage13-testing-hold-review`, `stage6-archive-review-queue` | 2026-08-10/11 |
| **`dispatch/security/`** — `auth`, `db`, `models`, `store` | 5 | 690 | `stage7-security-foundation` + 5 others | 2026-08-10/11 |
| **`hybrid_engine/`** — `ai_agent_collector` | 2 | 271 | `claude/ai-agent-collector-module-l6vpxl` | 2026-07-04 |
| `Hybrid/` (14 docs), `Dockerfile`/`.dockerignore` | 16 | 0 | 4 branches | 2026-07 |

Three facts follow, all recorded without recommendation:

1. **`joe-portal` is the newest work in the entire ecosystem** (2026-09-03), newer than `main`
   (2026-08-31), and explains the repository's `pushed_at` of 2026-09-04. It contains a Driver
   Cockpit (`portal/cockpit.py`, 982 LOC), a JOE Portal (`portal/routes/joe_portal.py`, 694),
   a JOE API (`joe_api.py`, 471), mission and scheduling engines
   (`dispatch/mission_template.py` 673, `dispatch/scheduling.py` 409, `dispatch/mission.py` 353),
   a booking board (`dispatch/booking.py` 316), an **Outlook mail connector**
   (`dispatch/connectors/outlook_mail.py`, 286), a JOE authority module
   (`dispatch/joe_authority.py`, 144) and **19 test files** including
   `test_driver_cockpit.py` (956 lines) and `test_contract_neutrality.py`.
2. **`dispatch/manager/` exists as code on five Dispatch branches**, contradicting nothing on
   `main` (where no Manager code exists) but standing beside `CLAUDE.md` §5.6's instruction not
   to create, restore, reference or infer a Manager component. Two other Manager implementations
   exist elsewhere: `Dispatch-Old/cin_lite/manager.py` and `Hold`'s `src/dispatch/queue/`.
3. **Branches predate `main`.** `cin-hybrid/` branches tip at 2026-07-03/04 and `l2_cos/` at
   2026-07-27 — before this repository's first `main` commit (2026-08-02). The repository's
   branch history reaches further back than its trunk.

---

## SECTION 4 — CODE INVENTORY

### Applications
| Application | Entry point | Evidence |
|---|---|---|
| Dispatch Portal (Flask) | `portal/app.py` | `python portal/app.py` documented in `CLAUDE.md` §9 |
| Dispatch Launcher / Control Center | `dispatch_launcher/__main__.py`, `cli.py` | `python -m dispatch_launcher start\|status` |
| CIN-Lite pipeline | `cin_lite/run.py` | `python -m cin_lite.run` |

### Entry points
`DISPATCH_START_HERE.cmd` (documented launch path per `docs/readiness/LAUNCH_PATH.md`),
`dispatch.bat`, `Dispatch.ps1`, `bootstrap_d_drive.py`, `portal/cli.py`,
`dispatch_launcher/__main__.py`, `cin_lite/run.py`.

### Services / modules — `dispatch/` (22 top-level modules)
`accounting_export`, `acquisition`, `backup`, `capacity`, `comi_routing`,
`customer_notifications`, `db`, `email_helper`, `models`, `notifications`, `opportunities`,
`proof`, `readiness`, `rehearsal`, `route_risk`, `scoring`, `services`, `store`, `tokens`,
`truck_arrangement`, plus packages `spine/` and `connectors/` and `sandbox_survey/`.

### Spine (lifecycle authority)
`dispatch/spine/{__init__,commitment,db,models,state,store}.py`

### APIs / Routes — **178 unique route paths** across 9 blueprints
| Blueprint | Route decorators | Scope |
|---|---|---|
| `portal/routes/dispatch_api.py` | 146 | Loads, drivers, equipment, milestones, evidence, POD, settlements, expenses, detentions, IFTA, maintenance, compliance, driver pay, broker contacts, integrations |
| `portal/routes/pages.py` | 33 | Rendered pages (fleet, calendar, IFTA, archive, publisher, intelligence, conflicts, operations, queues, search, settings, SAM, billing, profitability…) |
| `portal/routes/api.py` | 24 | Pipeline/archive/decision API |
| `portal/routes/driver_portal.py` | 8 | Driver-facing surfaces incl. `/forgot-pin`, driver login/home |
| `portal/routes/pipeline.py` | 7 | CIN-Lite pipeline control |
| `portal/routes/auth.py` | 2 | `/login`, `/logout` |
| `portal/routes/stakeholder.py` | 2 | External stakeholder view |
| `portal/routes/decisions.py` | 1 | Decision capture |

Representative route families: `/loads/<load_id>/{milestone,evidence,pod,settlement,rate,expenses,detentions,end-load,completion-packet,email-package,exception,visibility,financials,archive,duplicate,bundle}`;
`/ifta/{trip-legs,fuel-purchases,report,report-approvals,review,export-csv,monthly-report,fuel-purchases/extract-receipt}`;
`/driver-pin/{create,reset,delete,status,recovery-word}`; `/maintenance/*`; `/compliance/*`;
`/driver-pay/*`; `/broker-contacts/*`; `/integrations/*`; `/settlements/*`.

### CLI tools
`dispatch_launcher/cli.py` (start/stop/status/backups/first-run/probe/copies/redaction),
`portal/cli.py`, `cin_lite/run.py`.

### Background / operational services
`dispatch_launcher/{processes,pidfile,probe,control,status,backups,first_run,locations,settings,copies,glyphs,redaction}.py`.

### Database models
`dispatch/models.py` — 24 dataclasses: `Load`, `LoadVisibilityRecord`, `MilestoneEvent`,
`EvidenceItem`, `IFTAFuelEvidence`, `ExceptionNotice`, `PODPackage`, `RetentionArchive`,
`RateConfirmation`, `Expense`, `Settlement`, `Driver`, `Equipment`, `MaintenanceSchedule`,
`ComplianceDocument`, `LoadActivity`, `DetentionEvent`, `IFTATripLeg`, `IFTAFuelPurchase`,
`IFTAReportApproval`, `IFTAException`, `LaneTemplate`, `DriverPay`, `BrokerContact`.

`portal/models/` — `archive`, `completion_packet`, `conflict`, `driver_pin_registry`,
`email_helper`, `identity`, `integrations_registry`, `intelligence`, `library`,
`operations_feed`, `publisher`, `sandbox`.

**SQLite tables created in code (35):** `activities`, `approval_events`, `audit_events`,
`broker_contacts`, `compliance_documents`, `conflict_events`, `connector_audit`,
`detention_events`, `driver_pay`, `drivers`, `equipment`, `events`, `evidence`,
`exceptions`, `expenses`, `ifta_exceptions`, `ifta_fuel_evidence`, `ifta_fuel_purchases`,
`ifta_report_approvals`, `ifta_trip_legs`, `lane_templates`, `loads`,
`maintenance_schedules`, `milestones`, `operational_tokens`, `pod_packages`,
`portal_cards`, `rate_confirmations`, `rehearsal_sessions`, `retention`,
`route_risk_events`, `settlements`, `token_audit`, `visibility`, `work_items`.

### Contracts
`dispatch/connectors/contract.py` (fixed connector contract), `dispatch/connectors/boundary.py`,
`dispatch/connectors/registry.py`, `dispatch/connectors/audit.py`.

### Adapters / Connectors (8 + mock)
`accounting_connector`, `email_transport_connector`, `future_intelligence_connector`,
`load_board_connector`, `mapping_connector`, `outlook_connector`, `route_risk_connector`,
`scanner_connector`, plus `mock.py`.

### Rule modules — `cin_lite/rules/` (9 + base)
`set_aside`, `naics_sin`, `past_performance`, `pricing_anomaly`, `vendor_network`,
`subcontractor_dominance`, `jv_mp_structure`, `foreign_influence`, `cyber_compliance`.

### Claude-backed agents — `cin_lite/agents/` (5)
`extractor`, `proposal_writer`, `receipt_vision`, `router`, `summarizer`.
Per `CLAUDE.md` §7, these are labelled non-deterministic helpers, never load-bearing.

### Tests
137 files under `tests/`, **3,793 `def test_` functions**.
`.coveragerc` present; `pytest.ini`/`pyproject.toml` config present; CI at `.github/workflows/`.
`CLAUDE.md` §8 records **3,696 passed / 0 failed / 0 skipped / 0 warnings** and **94.74%**
gated coverage as of 2026-08-25. *The suite was not run during this inventory; the 3,793
figure is a static count of test functions, not a run result.*

### Scripts / utilities
`bootstrap_d_drive.py`, `DISPATCH_START_HERE.cmd`, `dispatch.bat`, `Dispatch.ps1`,
`dispatch_launcher/glyphs.py`, `dispatch_launcher/redaction.py`,
`dispatch/sandbox_survey/`.

---

## SECTION 5 — FUNCTIONAL CAPABILITIES

Status words follow the fixed vocabulary in `CLAUDE.md` §6.
Per `CLAUDE.md` §8, **every item below is IMPLEMENTED but not OPERATIONALLY PROVEN** —
nothing in this repository has been run on Mike's Windows laptop.

| Capability | Exists | Evidence | Primary files | Status |
|---|---|---|---|---|
| Load lifecycle (Spine) | Yes | `spine.state.transition()` / `spine.store.apply_transition()`; CF-04 in `DECISION_LOG.md` | `dispatch/spine/state.py`, `store.py`, `commitment.py` | IMPLEMENTED |
| Driver Portal | Yes | 8 routes; `driver_home.html`, `driver_login.html`, `driver_forgot_pin.html`, `driver_pay.html` | `portal/routes/driver_portal.py`, `portal/templates/driver_*.html` | IMPLEMENTED |
| Driver PIN registry / recovery | Yes | `/driver-pin/{create,reset,delete,status,recovery-word}`, `/forgot-pin` | `portal/models/driver_pin_registry.py` | IMPLEMENTED |
| Load intake / acquisition | Yes | `/loads/import`, `/loads/source-stats`, `/loads/export.csv` | `dispatch/acquisition.py`, `portal/routes/dispatch_api.py` | IMPLEMENTED |
| Milestones & evidence | Yes | `/loads/<id>/milestones`, `/evidence/*`; `milestones` + `evidence` tables | `dispatch/models.py`, `dispatch/store.py` | IMPLEMENTED |
| POD | Yes | `/loads/<id>/pod`; `pod_packages` table; `PODPackage` | `dispatch/models.py` | IMPLEMENTED |
| Settlement & billing | Yes | `/loads/<id>/settlement{,/dispute,/write-off}`, `/settlements/{aging,batch-create,export.csv}` | `dispatch/models.py`, `portal/templates/billing.html` | IMPLEMENTED |
| Expenses / detention / profitability | Yes | `/expenses/*`, `/detentions/*`, `/profitability` | `portal/templates/profitability.html` | IMPLEMENTED |
| IFTA (through finalization) | Yes | 15 IFTA routes; `ifta_trip_legs`, `ifta_fuel_purchases`, `ifta_report_approvals`, `ifta_exceptions`, `ifta_fuel_evidence` | `portal/templates/ifta*.html` | IMPLEMENTED |
| IFTA exception detection | Yes | `ifta_exceptions` table; `/ifta/report-approvals/<id>/exceptions` | `dispatch/models.py:IFTAException` | IMPLEMENTED |
| Receipt vision pre-fill | Yes | `/ifta/fuel-purchases/extract-receipt` | `cin_lite/agents/receipt_vision.py` | IMPLEMENTED (labelled non-deterministic helper) |
| Capacity / Week View | Yes | `dispatch/capacity.py`; `calendar.html`; `WEEK_VIEW_CAPACITY_VISUALIZATION_ARCHITECTURE.md` | `dispatch/capacity.py` | IMPLEMENTED |
| Calendar (presentation over Outlook) | Yes | `/calendar` page + API; `CLAUDE.md` §5.5 | `portal/templates/calendar.html` | IMPLEMENTED; Outlook `UNCONFIGURED` |
| Opportunity Cards (possibilities) | Yes | `dispatch/opportunities.py`; `OPPORTUNITY_PIPELINE_ARCHITECTURE.md` | `dispatch/opportunities.py` | IMPLEMENTED |
| Scoring | Yes | `dispatch/scoring.py`; `docs/DISPATCH_SCORING_ACCEPTANCE_CRITERIA.md` | `dispatch/scoring.py` | IMPLEMENTED — advisory, never deciding (`CLAUDE.md` §4.2) |
| COMI routing | Yes | `dispatch/comi_routing.py`; 92 in-repo references | `dispatch/comi_routing.py` | IMPLEMENTED |
| Route Risk | Yes (plug-in surface) | `dispatch/route_risk.py`, `connectors/route_risk_connector.py`, `route_risk_events` table | those files | IMPLEMENTED; provider `UNCONFIGURED` |
| Mission Visibility | Yes | `/loads/<id>/visibility`; `visibility` table; `LoadVisibilityRecord` | `dispatch/models.py` | IMPLEMENTED |
| Archive | Yes | `/archive`, `/archive/create`, `/archive/<contract_id>`; `retention` table | `portal/models/archive.py` | IMPLEMENTED |
| Publisher (in-portal) | Yes | `/publisher`, `/publisher/create`, `/publisher/update` | `portal/models/publisher.py`, `portal/templates/publisher.html` | IMPLEMENTED |
| Library (in-portal) | Yes | `/intelligence/promote`; library model | `portal/models/library.py`, `portal/templates/library.html` | IMPLEMENTED |
| Intelligence (in-portal) | Yes | `/intelligence{,/add,/promote,/update}` | `portal/models/intelligence.py` | IMPLEMENTED |
| Operations feed | Yes | `/operations` | `portal/models/operations_feed.py` | IMPLEMENTED |
| Conflict detection | Yes | `/conflicts`, `/conflict/resolve`; `conflict_events` table | `portal/models/conflict.py` | IMPLEMENTED |
| Communications / notifications | Yes | `dispatch/notifications.py`, `customer_notifications.py`, `/loads/stalled/notify` | those files | IMPLEMENTED |
| Email helper / templates | Yes | `/email-templates`, `/email-preview`, `/loads/<id>/email-package/*` | `dispatch/email_helper.py`, `portal/models/email_helper.py` | IMPLEMENTED |
| Email transport | Yes | `cin_lite/email_delivery.py` via `email_transport_connector` | `CLAUDE.md` §1: CIN-Lite is Dispatch's only mail transport | IMPLEMENTED; `UNCONFIGURED` |
| CSRF + fail-closed auth | Yes | `portal/csrf.py`; `CLAUDE.md` §7 forbids weakening | `portal/csrf.py`, `portal/routes/auth.py` | IMPLEMENTED |
| Operational tokens | Yes | `operational_tokens`, `token_audit` tables | `dispatch/tokens.py` | IMPLEMENTED |
| Stakeholder portal | Yes | 2 routes; `stakeholder_view.html` | `portal/routes/stakeholder.py` | IMPLEMENTED |
| Connector boundary (8 connectors) | Yes | `dispatch/connectors/`; `connector_audit` table; `docs/connectors/PROVIDER_INSERTION.md` | that package | IMPLEMENTED; all providers `UNCONFIGURED` |
| Backup & restore | Yes | `dispatch/backup.py`, `dispatch_launcher/backups.py`, `BACKUP_AND_RECOVERY.md` | those files | IMPLEMENTED |
| Rehearsal mode | Yes | `dispatch/rehearsal.py`; `rehearsal_sessions` table | `dispatch/rehearsal.py` | IMPLEMENTED |
| 20-step operational proof | Yes | `dispatch/proof.py`; `docs/readiness/OPERATIONAL_LOAD_PROOF_TEMPLATE.md` | those files | IMPLEMENTED; the 20 steps themselves **UNVERIFIED** |
| Launcher / Control Center v1 | Yes | 15 modules; `docs/readiness/CONTROL_CENTER.md` | `dispatch_launcher/` | IMPLEMENTED; 87.75% coverage, Windows branches untested |
| Sandbox survey | Yes | `dispatch/sandbox_survey/`, 10 templates in `docs/readiness/sandbox_templates/` | those files | IMPLEMENTED |
| Truck arrangement | Yes | `dispatch/truck_arrangement.py`; `TRUCK_ARRANGEMENT_AND_LOAD_CONFIGURATION_ARCHITECTURE.md` | that file | IMPLEMENTED |
| Accounting export | Yes | `dispatch/accounting_export.py`, `connectors/accounting_connector.py` | those files | IMPLEMENTED; `UNCONFIGURED` |
| Fleet / maintenance / compliance | Yes | `/fleet`, `/maintenance/*`, `/compliance/*` | `dispatch/models.py`, `portal/templates/fleet.html` | IMPLEMENTED |
| Fuel estimator | Yes | `/fuel-estimate`, `/fuel-defaults`, `/fuel-estimator` | `portal/templates/fuel_estimator.html` | IMPLEMENTED |
| CIN-Lite gov-contract pipeline | Yes | 9 rule modules + 5 agents + `pipeline.py` + `control.py` | `cin_lite/` | IMPLEMENTED |
| SAM surface | Yes (page only) | `/sam` route, `sam.html` | `portal/templates/sam.html` | IMPLEMENTED; SAM.gov integration `UNCONFIGURED` |
| Joe Research / Assistant | **No** | Assistant is a plug-in; `CLAUDE.md` §5.4 forbids embedding it | — | ABSENT in this repository (see `JOE_ASSISTANT_DOSSIER.md`) |
| Manager component | **No** | `CLAUDE.md` §5.6: "There is no Manager component"; `docs/MANAGER.md` is history only | `docs/MANAGER.md` | ABSENT by doctrine (3 `stage12-manager-*` branches exist; `main` has no Manager code) |
| ELD / Hours of Service | **No** | `CLAUDE.md` §8: "Dispatch does not know a driver's hours of service. There is no ELD feed." | — | ABSENT |

**Every external system is `UNCONFIGURED`** (`CLAUDE.md` §8): no ELD, GPS, traffic, weather,
load board, mapping, accounting, scanner or Outlook client is connected.

---

## SECTION 6 — DOCUMENT INVENTORY

112 markdown files. Complete by category:

**Cold-start brief / constitution-equivalent**
`CLAUDE.md` (the binding cold-start brief), `DISPATCH_PURPOSE_STATEMENT.md`,
`DRIVER_FIRST_DOCTRINE_v2.md` (D1–D15, incl. the 70 MPH Test).

**Architecture documents**
`docs/architecture/DISPATCH_ARCHITECTURE.md` (the document map),
`CURRENT_REALITY_VS_POSSIBLE_FUTURES_ARCHITECTURE.md`,
`DISPATCH_DYNAMIC_CAPACITY_ARCHITECTURE.md`, `DRIVER_PORTAL_ARCHITECTURE_V2.md`,
`OPPORTUNITY_PIPELINE_ARCHITECTURE.md`,
`TRUCK_ARRANGEMENT_AND_LOAD_CONFIGURATION_ARCHITECTURE.md`,
`WEEK_VIEW_CAPACITY_VISUALIZATION_ARCHITECTURE.md`,
`docs/DISPATCH_DETERMINISTIC_CHASSIS.md`, `docs/DISPATCH_EXTERNAL_ADAPTER_BOUNDARIES.md`,
`docs/DISPATCH_SYSTEM_INDEPENDENCE_DOCTRINE.md`, `docs/CANONICAL_RECONCILIATION_INTEGRATION.md`.

**Governance**
`docs/governance/DISPATCH_AUTHORITY_AND_BOUNDARIES.md`,
`DISPATCH_CONFLICT_AND_AUTHORITY_REGISTER.md`, `DISPATCH_OWNERSHIP_MATRIX_v1.md`,
`DISPATCH_CF04_LIFECYCLE_AUTHORITY_MODEL_v1.md`,
`DISPATCH_SPINE_OWNERSHIP_PARTITION_AMENDMENT_v1.md`,
`DISPATCH_GOVERNANCE_MANIFEST_REPAIR_PLAN_v1.md`,
`docs/DISPATCH_FACT_AND_PROVENANCE_DOCTRINE.md`,
`docs/DISPATCH_CONFIGURABLE_BUSINESS_POLICY_DOCTRINE.md`,
`docs/DISPATCH_ACCESSORIAL_POLICY_DOCTRINE.md`, `docs/DISPATCH_CAPACITY_PLAN_DOCTRINE.md`,
`docs/MANAGER.md` (permanent record of a capability named but never built).

**Decision log**
`DECISION_LOG.md` — every decision in order, incl. General Contractor Doctrine (2026-08-25)
and CF-04 (2026-08-23).

**Specifications**
`docs/DISPATCH_CONFIDENCE_MODEL_SPEC.md`, `docs/DISPATCH_DECISION_MATRIX_SPEC.md`,
`docs/DISPATCH_EVALUATION_ENGINE_SPEC.md`, `docs/DISPATCH_FILTER_SCORE_SORT_SPEC.md`,
`docs/DISPATCH_LOAD_ARRANGEMENT_SPEC.md`, `docs/DISPATCH_OVERRIDE_RULES_SPEC.md`,
`docs/DISPATCH_POLICY_PROFILE_SPEC.md`, `docs/DISPATCH_POLICY_PROFILE_EXAMPLES.md`,
`docs/DISPATCH_RECOMMENDATION_MODEL_SPEC.md`, `docs/DISPATCH_STATE_TRANSITION_RULES.md`,
`docs/DISPATCH_SCORING_ACCEPTANCE_CRITERIA.md`, `docs/DISPATCH_SCORING_LINEAGE_AND_RECOVERY.md`.

**Roadmaps / build plans**
`DISPATCH_BLUEPRINT_TO_COMPLETION_v1.md`, `DISPATCH_COMPLETION_BLUEPRINT.md`,
`docs/readiness/COMPLETION_BLUEPRINT_v2.md`, `DISPATCH_BUILD_MATRIX{,_v1,_v2}.md`,
`docs/DISPATCH_AGGRESSIVE_BUILD_SEQUENCE.md`,
`DISPATCH_REPAIR_AND_CONNECTION_CAMPAIGN_v1.md`, `DISPATCH_WORKABLE_PRODUCT_DEFINITION.md`.

**Recovery / inventory / audit reports**
`DISPATCH_ARTIFACT_AND_REPOSITORY_RECOVERY_PLAN.md`,
`DISPATCH_CROSS_REPOSITORY_RECONCILIATION.md`, `DISPATCH_CURRENT_STATE_INVENTORY.md`,
`DISPATCH_RECOVERABLE_WORK_MATRIX.md`, `DISPATCH_RECOVERY_WAVE_1_REPORT.md`,
`DISPATCH_RECOVERY_WAVE_1_COMPLETION_REPORT.md`,
`DISPATCH_RETAIN_REPAIR_REPLACE_REMOVE_MATRIX.md`,
`DISPATCH_THREE_REPOSITORY_ARTIFACT_INVENTORY.md`, `DISPATCH_WHOLE_PROGRAM_AUDIT.md`,
`DISPATCH_ARCHITECTURE_CONFORMANCE_REPORT.md`, `DISPATCH_AUDIT_AMENDMENT.md`,
`DISPATCH_SECURITY_AND_RUNTIME_REPORT.md`, `DISPATCH_TEST_TRUTH_REPORT.md`,
`DISPATCH_TRIGGER_AND_SIDE_EFFECT_INVENTORY_v1.md`,
`docs/DISPATCH_COMPONENT_RECOVERY_REGISTER.md`, `docs/DISPATCH_GOLD_RECOVERY_FINDINGS.md`,
`DISPATCH_AUDIT_EVIDENCE_MANIFEST.txt`.

**Walkthrough reports (11)**
`C3_STATUS_CHANGE_AUDIT_…`, `DRIVER_TRANSFORMATION_RECOVERY_…`, `M1_MISSION_TRANSITION_GATE_…`,
`M3_ROUTE_RISK_DURABILITY_…`, `MA_ATOMIC_STORE_WRITES_…`, `PHASE2_IFTA_…`, `PHASE3_ARCHIVE_…`,
`PHASE4_IFTA_FINALIZATION_GATE_…`, `PHASE5_IFTA_EVIDENCE_AND_REVIEW_…`,
`PHASE6A_IFTA_EXCEPTION_DETECTORS_…`, `PHASE6B_RECEIPT_VISION_PREFILL_…`,
`PHASE7_SUSPECT_ENTRIES_…` (all `_WALKTHROUGH_REPORT_v1.md`).

**Readiness (what is proven / not proven)**
`docs/readiness/OPERATIONAL_PROOF.md`, `OPERATIONAL_PROOF_PROCEDURE.md`,
`OPERATIONAL_LOAD_PROOF_TEMPLATE.md`, `LAUNCHER_PROOF_TEMPLATE.md`, `LAUNCH_PATH.md`,
`KNOWN_LIMITATIONS.md`, `STATUS_2026-08-26.md`, `COMPLETION_REPORT.md`,
`CONTROL_CENTER.md`, `RECON.md`, `SANDBOX_SURVEY_PROCEDURE.md`,
plus 10 `sandbox_templates/`.

**Operational documents**
`docs/operations/DISPATCH_OPERATOR_GUIDE.md`,
`docs/operations/GET_DISPATCH_ONTO_YOUR_LAPTOP.md`,
`docs/maintenance/DISPATCH_MAINTENANCE_GUIDE.md`, `DISPATCH_FIRST_START_GUIDE.md`,
`BACKUP_AND_RECOVERY.md`, `DEPLOY_LOCAL.md`, `DEPLOY_VPS.md`,
`docs/connectors/PROVIDER_INSERTION.md`,
`DISPATCH_OPERATIONAL_INTELLIGENCE_PLAYBOOK_v1.md`,
`W0-2_DELIVERY_PROOF_PROCEDURE.md`, `W0-3_PORTAL_ADJUDICATION_BRIEF.md`.

**Non-markdown source document**
`Final_Architecture_for_Hybrid_CIN-Lite_System (1).docx` — the CIN-Lite spec.

**Prompts / handoffs:** none as standalone files in this repository.

---

## SECTION 7 — UNIQUE ASSETS

Method: every tracked file in all 12 non-empty repositories was hashed by git blob ID and
compared. **438 of 459 Dispatch files (95.4%) have content that exists in no other
repository.** Only 21 files are byte-identical to a file elsewhere.

### Unique to Dispatch — nothing comparable exists in any other repository

1. **The entire freight platform.** `dispatch/` (22 modules + `spine/` + `connectors/` +
   `sandbox_survey/`), `portal/` (9 blueprints, 178 routes, 41 templates, 12 models), and
   `dispatch_launcher/` (15 modules). ~82,699 lines of Python. No other repository contains
   any of it.
2. **The Spine lifecycle engine** — `dispatch/spine/{state,store,commitment,models,db}.py`.
   Jules holds a *different, earlier* `dispatch_spine.py` (717 LOC, in-memory,
   consequence-level model); Claude holds a *third* in-memory prototype under
   `proposal/spine_prototype/`. The three are unrelated implementations, not copies.
3. **The connector boundary and its 8 connectors** — `dispatch/connectors/`. Only place in
   the ecosystem with `connector_audit`, `boundary.py`, `contract.py`, `registry.py`.
4. **The full IFTA subsystem** — 5 tables, 15 routes, exception detectors, report approvals,
   fuel evidence, receipt vision pre-fill. Hold holds *schemas* for receipts/fuel/mileage
   (`contracts/*.schema.json`) and IFTA doctrine, but no IFTA code at all.
5. **The 20-step operational proof system** — `dispatch/proof.py` plus
   `docs/readiness/OPERATIONAL_LOAD_PROOF_TEMPLATE.md` and `OPERATIONAL_PROOF.md`.
6. **The Dispatch Launcher / Control Center** — `dispatch_launcher/` and
   `DISPATCH_START_HERE.cmd`. Joe-Assistant has its own `.cmd` launcher family for JOE;
   they are different programs.
7. **The 3,793-function test suite** — no other repository is within two orders of magnitude
   (next largest: Joe-Assistant, 729).
8. **`CLAUDE.md` as a cold-start brief** in its current form, `DECISION_LOG.md`,
   `DRIVER_FIRST_DOCTRINE_v2.md`, `DISPATCH_PURPOSE_STATEMENT.md`, and all 11 walkthrough
   reports and 12 spec documents under `docs/`.
9. **64 branches** carrying work that is not on `main`, including three
   `stage12-manager-*` branches and `docs/manager-reinforcement` — the only Manager-labelled
   branches anywhere in the ecosystem.
10. **`cin_lite/` additions not in Dispatch-Old:** `agents/extractor.py`,
    `agents/receipt_vision.py`, `pending.py`, `pipeline.py`.
11. **Off-`main` subsystems that exist nowhere else in the ecosystem** (see §3):
    - The **`joe-portal`** branch's Driver Cockpit, Mission Intake, Booking Board, Arrival
      Notice, mission-template engine, scheduling engine, JOE authority module and
      **Outlook mail connector** (`dispatch/connectors/outlook_mail.py`) — the only Dispatch-side
      Outlook *implementation* anywhere; `main` has only the connector interface.
      Also `portal/prototype/L1_Transport_Planning_Intelligence_Dashboard.html` (995 lines).
    - The **`cin-hybrid/`** tree — 16 named agents (`gov_engine`, `net_engine`, `ops_engine`,
      `risk_engine`, `tell_engine`, `sam_ingestion_engine`, `vendor_network_engine`,
      `cyber_compliance_engine`, `cin_router`, `hybrid_orchestrator`, `hybrid_lifecycle`,
      `hybrid_ops`, `hybrid_summary`, …), an intelligence layer with `intelligence_guard.py`
      and `intelligence_owner.py`, services including `docusign_bridge.py` and
      `outlook_email_client.py`, and a runtime (`dispatcher`, `event_bus`, `state_manager`).
      `Claude-3/RECOVERY_REPORT.md` names `cin-hybrid` as a recovered codebase; these three
      branches are the only place any of it survives.
    - The **`l2_cos/`** tree — six freight-specific rules (`broker_risk`, `capacity_match`,
      `deadhead_cost`, `facility_risk`, `lane_fit`, `rate_anomaly`) and a five-module UI.
      This is the only surviving L2-COS-era freight code; `L2-intelligence-agent./README.md`
      records "L2-COS" as retired terminology.
    - **`dispatch/security/`** — `auth`, `db`, `models`, `store` (690 LOC). `main` has CSRF and
      fail-closed auth in `portal/`, but no `dispatch/security/` package.
    - **`dispatch/manager/`** — 7–8 modules, 767–866 LOC.

### What Dispatch shares (21 files, not unique)
Chiefly the governance document set mirrored across repositories (`MANAGER.md`,
constitution/matrix documents) and the `Final_Architecture_for_Hybrid_CIN-Lite_System (1).docx`
shared with Dispatch-Old.

### Recorded absence — held elsewhere, not here
`cin_lite/{manager,library,publisher,dashboard,portal}.py` and 17 associated tests exist in
**Dispatch-Old only**. Dispatch's `cin_lite/` does not contain them. See
`DISPATCH_OLD_DOSSIER.md` §7. Stated as fact; no recommendation offered.

---

## SECTION 8 — CROSS-REPOSITORY REFERENCES

Counts are matching lines across all tracked text files.

| Referenced entity | Occurrences | Representative files |
|---|---|---|
| Dispatch (self) | 7,267 | throughout |
| Route Risk | 672 | `dispatch/route_risk.py`, `dispatch/connectors/route_risk_connector.py`, `M3_ROUTE_RISK_DURABILITY_WALKTHROUGH_REPORT_v1.md`, `route_risk_events` table |
| Manager | 188 | `docs/MANAGER.md`, `CLAUDE.md` §5.6, `tests/test_repository_doctrine.py`, branches `stage12-manager-*` |
| Jules | 189 | `DISPATCH_CROSS_REPOSITORY_RECONCILIATION.md`, branches `jules-*`, `jules/comi-route-risk-mission-visibility-foundation-*`; 11 commits by `google-labs-jules[bot]` |
| SAM / SAM.gov | 130 | `portal/templates/sam.html`, `/sam` route, `cin_lite/acquisition.py` |
| COMI | 92 | `dispatch/comi_routing.py`, branch `claude/comi-status-everywhere` |
| Mission Visibility | 68 | `/loads/<id>/visibility`, `visibility` table, branch `claude/mission-visibility-foundation` |
| Publisher | 636 | `portal/models/publisher.py`, `portal/templates/publisher.html`, `/publisher/*` |
| Library | 468 | `portal/models/library.py`, `portal/templates/library.html` |
| Joe / Assistant | 45 | `CLAUDE.md` §5.4 (plug-in separation), branch `joe-portal` |

**Explicit cross-repository documents in this repo:**
`DISPATCH_CROSS_REPOSITORY_RECONCILIATION.md`,
`DISPATCH_THREE_REPOSITORY_ARTIFACT_INVENTORY.md`,
`DISPATCH_ARTIFACT_AND_REPOSITORY_RECOVERY_PLAN.md`,
`docs/DISPATCH_COMPONENT_RECOVERY_REGISTER.md`.

**Doctrinal boundary statements** (`CLAUDE.md` §5.4): Route Risk, Mission Visibility, SAM
and Assistant are plug-ins; Dispatch must run without any of them; no direct Dispatch write
authority may be granted to Assistant.

---

## SECTION 9 — BUILT VS PLANNED

### Built In Code
Spine lifecycle engine · loads/drivers/equipment/capacity · milestones · evidence · POD ·
settlement, expenses, detention, profitability · IFTA through finalization, exception
detection, receipt vision pre-fill · Driver Portal · driver PIN registry and recovery ·
stakeholder portal · Opportunity Cards · scoring · COMI routing · Route Risk surface ·
Mission Visibility · archive & retention · in-portal Publisher, Library, Intelligence ·
operations feed · conflict detection · notifications & customer notifications · email helper
and templates · CSRF and fail-closed auth · operational tokens · connector boundary with 8
connectors · backup & restore · rehearsal mode · 20-step operational proof system · Dispatch
Launcher and Control Center v1 · fleet, maintenance, compliance · fuel estimator · truck
arrangement · accounting export · sandbox survey · CIN-Lite pipeline (9 rules, 5 agents) ·
3,793 test functions · CI workflow.

### Partially Built
- **Launcher coverage** — `dispatch_launcher/` at 87.75%, ungated; Windows-only branches
  untested (`docs/readiness/OPERATIONAL_PROOF.md` §2.1).
- **Every connector** — interface defined and audited, no provider configured. `CLAUDE.md` §8:
  "Every external system is `UNCONFIGURED`."
- **SAM** — a `/sam` page and template exist; no SAM.gov integration.
- **Outlook / Calendar** — Calendar presentation implemented; Outlook is the scheduling
  authority per `CLAUDE.md` §5.5 but no Outlook client is connected.

### Documented Only
- **Manager** — `docs/MANAGER.md` is explicitly "the permanent record of a capability that
  was *named* in planning and *never built*". `CLAUDE.md` §5.6 forbids creating one.
- Specs under `docs/` without a named implementing module: `DISPATCH_EVALUATION_ENGINE_SPEC.md`,
  `DISPATCH_CONFIDENCE_MODEL_SPEC.md`, `DISPATCH_RECOMMENDATION_MODEL_SPEC.md`,
  `DISPATCH_DECISION_MATRIX_SPEC.md`, `DISPATCH_OVERRIDE_RULES_SPEC.md`.
- The 15 first-start acceptance items (`docs/readiness/LAUNCHER_PROOF_TEMPLATE.md`) and the
  20 load-proof steps (`OPERATIONAL_LOAD_PROOF_TEMPLATE.md`) — templates, not results.

### Referenced But Missing
- **ELD / Hours of Service** — `CLAUDE.md` §8: "Dispatch does not know a driver's hours of
  service. There is no ELD feed. Any surface that implies otherwise is a defect."
- **GPS, traffic, weather, load board, mapping, accounting, scanner providers** — connector
  interfaces exist, providers do not.
- **Route-Risk and SAM as separate repositories** — both referenced; both GitHub
  repositories are **empty** (0 files, 0 branches). See their dossiers.
- **Assistant (JOE)** — referenced as a plug-in; its code lives in `Joe-Assistant`.

### Unknown
- **What is inside the off-`main` work, in detail.** This inventory established *that*
  245 files exist on branches and not on `main`, and identified the subsystems (§3). It did
  **not** read that code, run it, or assess whether any of it duplicates, supersedes or
  conflicts with `main`. In particular the `joe-portal` branch's ~14,000 lines and 19 test
  files were enumerated, not reviewed.
- **Why `joe-portal` (2026-09-03, 48 commits ahead) is unmerged.** No document in the
  repository records a decision about it.
- **Whether the suite currently passes.** `CLAUDE.md` §8 records 3,696 passed / 0 failed as
  of 2026-08-25; the suite was **not run** during this inventory.
- **Everything about behaviour on Mike's laptop.** `CLAUDE.md` §8: laptop readiness is
  `UNVERIFIED`; nothing here has been run on his Windows machine.

---

## SECTION 10 — EXECUTIVE SUMMARY

**What is this repository?**

Dispatch is the freight-operations platform of Level 1 Transport and, by its own recorded
doctrine, the General Contractor, System of Record, and Operational Authority of the
ecosystem. It is by a wide margin the largest and most complete repository of the fourteen:
459 tracked files, 82,699 lines of Python, 220 commits, 64 branches, 112 documents, and a
test suite of 3,793 test functions. It contains two programs: the freight platform
(`dispatch/`, `portal/`, `dispatch_launcher/`) and the CIN-Lite government-contracting
pipeline (`cin_lite/`), which is also Dispatch's only mail transport.

**What is actually implemented?**

A working freight system in software: a Spine that owns load lifecycle state; loads, drivers,
equipment and capacity; milestones, evidence and POD; settlement, expenses and detention; a
complete IFTA subsystem through finalization with exception detection and receipt-vision
pre-fill; a Driver Portal with PIN registry and recovery; a stakeholder portal; Opportunity
Cards, scoring, COMI routing, Route Risk and Mission Visibility surfaces; archive and
retention; in-portal Publisher, Library and Intelligence; conflict detection; notifications
and email helpers; CSRF and fail-closed authentication; operational tokens; a governed
connector boundary with eight connectors and an audit trail; backup and restore; rehearsal
mode; a 20-step operational-proof system; and the Dispatch Launcher and Control Center.
178 unique HTTP routes across 9 blueprints, 41 templates, 35 SQLite tables, 24 domain
dataclasses.

Against that: **every external system is `UNCONFIGURED`** — no ELD, GPS, traffic, weather,
load board, mapping, accounting, scanner or Outlook connection exists. Dispatch does not know
a driver's hours of service. There is no Manager component. And per `CLAUDE.md` §8, **every
implemented item is IMPLEMENTED but not OPERATIONALLY PROVEN**: nothing in this repository
has ever been run on Mike's Windows laptop. Laptop readiness is `UNVERIFIED`.

**What unique value does it contain?**

95.4% of its files (438 of 459) exist in no other repository. Everything in the freight
platform is unique to it: the Spine engine, the connector boundary, the whole IFTA subsystem,
the operational-proof system, the launcher, the portal, and the test suite. The governance
record — `CLAUDE.md`, `DECISION_LOG.md`, `DRIVER_FIRST_DOCTRINE_v2.md`,
`DISPATCH_PURPOSE_STATEMENT.md`, twelve specifications and eleven walkthrough reports —
exists here in a form found nowhere else. It also holds 63 branches of work that is not on
`main`, whose contents this inventory did not diff.

Two recorded findings sit outside `main`. First, **245 files exist on branches and not on
`main`** — including the `joe-portal` branch, which is 48 commits ahead, tips at 2026-09-03
(the newest work anywhere in the ecosystem), and carries roughly 14,000 lines: a Driver
Cockpit, a JOE Portal and API, mission and scheduling engines, a booking board, an Outlook
mail connector, and 19 test files. Also off `main`: a 42-file `cin-hybrid/` tree with sixteen
named agents, a 34-file `l2_cos/` freight-rules-and-UI tree, a `dispatch/manager/` package on
five branches, and a `dispatch/security/` package. Some of these branches tip *earlier* than
this repository's first `main` commit — its branch history reaches further back than its trunk.

Second, one absence: `cin_lite/{manager,library,publisher,dashboard,portal}.py` and 17
associated tests exist in **Dispatch-Old and not here**.
