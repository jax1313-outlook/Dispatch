# MASTER_CAPABILITY_MATRIX.md

**Authority: Mike Zachary. Compiled 2026-09-05.**

This matrix answers one question only:

# "What has actually been built?"

Every row is a capability. For each: the repository that holds it, the evidence, its status,
and its primary location. Nothing here is a recommendation. Nothing here is ranked by
importance. Capabilities that do not exist are listed too, because a recovery inventory that
omits absences is not an inventory.

---

## How to read the Status column

Dispatch's fixed truth vocabulary (`Dispatch/CLAUDE.md` §6) is used where it applies, plus the
evidence classes from `Joe-Assistant/Assistant_Plugin/docs/JOE_CAPABILITY_TRUTH_MATRIX.md`:

| Status | Means |
|---|---|
| **PROVEN** | Run against a live external service, with recorded evidence |
| **IMPLEMENTED** | Code exists and a test suite exercises it. **Not** operational proof |
| **IMPLEMENTED (branch)** | Code exists on an unmerged branch; absent from the default branch |
| **PARTIAL** | Works in part; the gap is named |
| **BLOCKED-HUMAN** | Cannot proceed without an action only Mike can take |
| **DOCUMENTED** | Specified in a document; no implementing code found |
| **UNCONFIGURED** | Settings absent — interface exists, provider does not |
| **ABSENT** | Does not exist anywhere in the fourteen repositories |

**Two standing caveats, both load-bearing.**

1. **No test suite was run during this inventory.** Every test count is a static count of
   `def test_` functions. IMPLEMENTED means the code and its tests exist, not that they pass.
2. **`Dispatch/CLAUDE.md` §8: nothing in Dispatch has ever been run on Mike's Windows laptop.**
   Every Dispatch capability below is IMPLEMENTED and **not OPERATIONALLY PROVEN**. The only
   capabilities in the entire ecosystem marked PROVEN are JOE's, measured on 2026-08-26 by
   running the program.

---

## 1. FREIGHT OPERATIONS

| Capability | Repository | Evidence | Status | Primary location |
|---|---|---|---|---|
| **Load lifecycle (Spine)** | Dispatch | `spine.state.transition()` / `spine.store.apply_transition()`; CF-04 in `DECISION_LOG.md`; "Opportunity advises; the Spine decides" | IMPLEMENTED | `dispatch/spine/{state,store,commitment,models,db}.py` |
| Loads, drivers, equipment | Dispatch | 24 dataclasses; `loads`/`drivers`/`equipment` tables; `/drivers/*`, `/equipment/*` routes | IMPLEMENTED | `dispatch/models.py`, `dispatch/store.py` |
| **Load intake / acquisition** | Dispatch | `/loads/import`, `/loads/source-stats`, `/loads/export.csv` | IMPLEMENTED | `dispatch/acquisition.py` |
| Milestones | Dispatch | `/loads/<id>/milestones`, `/milestones/<id>`; `milestones` table | IMPLEMENTED | `dispatch/models.py:MilestoneEvent` |
| Evidence | Dispatch | `/loads/<id>/evidence`, `/evidence/<id>/download`; `evidence` table | IMPLEMENTED | `dispatch/models.py:EvidenceItem` |
| **POD** | Dispatch | `/loads/<id>/pod`; `pod_packages` table | IMPLEMENTED | `dispatch/models.py:PODPackage` |
| POD evidence bundle (as an object) | Publisher | `PODEvidenceBundle` per shared contracts §5 | IMPLEMENTED | `src/dispatch_publisher/models.py` |
| Settlement, disputes, write-offs | Dispatch | `/loads/<id>/settlement{,/dispute,/write-off}`, `/settlements/{aging,batch-create,export.csv}` | IMPLEMENTED | `dispatch/models.py:Settlement` |
| Expenses / detention | Dispatch | `/expenses/*`, `/detentions/*`, `/detentions/summary` | IMPLEMENTED | `dispatch/models.py` |
| Profitability | Dispatch | `/profitability`, `/loads/<id>/financials`, `/dashboard/financials` | IMPLEMENTED | `portal/templates/profitability.html` |
| Rate confirmations | Dispatch | `/loads/<id>/rate`, `/dispatch/<id>/rate-confirmation/print` | IMPLEMENTED | `dispatch/models.py:RateConfirmation` |
| Driver pay | Dispatch | `/driver-pay/*` (8 routes); `driver_pay` table | IMPLEMENTED | `dispatch/models.py:DriverPay` |
| Broker contacts | Dispatch | `/broker-contacts/*` (5 routes); `broker_contacts` table | IMPLEMENTED | `dispatch/models.py:BrokerContact` |
| Fleet / maintenance / compliance | Dispatch | `/fleet/*`, `/maintenance/*` (8), `/compliance/*` (7) | IMPLEMENTED | `dispatch/models.py`, `portal/templates/fleet.html` |
| Truck arrangement & load configuration | Dispatch | `TRUCK_ARRANGEMENT_AND_LOAD_CONFIGURATION_ARCHITECTURE.md` | IMPLEMENTED | `dispatch/truck_arrangement.py` |
| Fuel estimator | Dispatch | `/fuel-estimate`, `/fuel-defaults`, `/fuel-estimator` | IMPLEMENTED | `portal/templates/fuel_estimator.html` |
| Lane templates | Dispatch | `lane_templates` table | IMPLEMENTED | `dispatch/models.py:LaneTemplate` |
| End-load / completion packet | Dispatch | `/loads/<id>/end-load`, `/completion-packet` | IMPLEMENTED | `portal/models/completion_packet.py` |
| Stalled-load detection & notify | Dispatch | `/loads/stalled`, `/loads/stalled/notify` | IMPLEMENTED | `portal/routes/dispatch_api.py` |
| **Mission intake / booking board / arrival notice** | Dispatch | `dispatch/{mission,mission_template,booking,arrival,scheduling}.py`; `MISSION_INTAKE_ARCHITECTURE.md`; `test_booking_board.py`, `test_arrival_notice.py`, `test_mission_intake.py` | **IMPLEMENTED (branch)** | `joe-portal` branch, 48 commits ahead, tip 2026-09-03 |
| **Driver Cockpit** | Dispatch | `portal/cockpit.py` (982 LOC), `test_driver_cockpit.py` (956 LOC), `DRIVER_COCKPIT_LOCKED_DIRECTION.md` | **IMPLEMENTED (branch)** | `joe-portal` branch |
| Trip card / cockpit prototype | Claude-3 | `dispatch_build/{trip_card,cockpit}.py`, `test_cockpit.py` | **IMPLEMENTED (branch)** | `claude/dispatch-jules-arch-review-i87dru` |
| **Load-board sweep (DAT / Truckstop)** | — | `Claude-3/CLONE_MAP.md`: "no working adapter to an actual load-board API was found anywhere… **Biggest genuine build gap**" | **ABSENT** | — |
| **HOLD grace period + stale-runner-up delete** | — | `CLONE_MAP.md`: "*No recovered equivalent found*" for both. A `test_hold_expiration.py` exists on a Claude-3 branch | **ABSENT** (test only) | — |
| **Instant Quote Calculator / rate quoting** | — | Specified in `premium-logistics-platform-`; no implementation in any repository | **ABSENT** | — |
| **ELD / Hours of Service** | — | `Dispatch/CLAUDE.md` §8: "Dispatch does not know a driver's hours of service. There is no ELD feed. Any surface that implies otherwise is a defect." | **ABSENT** | — |

## 2. IFTA, RECEIPTS AND FUEL

| Capability | Repository | Evidence | Status | Primary location |
|---|---|---|---|---|
| **IFTA through finalization** | Dispatch | 15 IFTA routes; 5 tables (`ifta_trip_legs`, `ifta_fuel_purchases`, `ifta_report_approvals`, `ifta_exceptions`, `ifta_fuel_evidence`) | IMPLEMENTED | `dispatch/models.py`, `portal/templates/ifta*.html` |
| IFTA exception detection | Dispatch | `PHASE6A_IFTA_EXCEPTION_DETECTORS_WALKTHROUGH_REPORT_v1.md` | IMPLEMENTED | `dispatch/models.py:IFTAException` |
| IFTA report approvals | Dispatch | `/ifta/report-approvals/*` (4 routes) | IMPLEMENTED | `dispatch/models.py:IFTAReportApproval` |
| Receipt vision pre-fill | Dispatch | `/ifta/fuel-purchases/extract-receipt`; `PHASE6B_RECEIPT_VISION_PREFILL_WALKTHROUGH_REPORT_v1.md` | IMPLEMENTED (labelled non-deterministic helper) | `cin_lite/agents/receipt_vision.py` |
| **IFTA engine** (mileage, rates, worksheet, package, exceptions, live indicators) | **Hold** | `tests/golden/ifta/`, `tests/lane_c/` (25 files); branch `build/ifta-live-indicators` | **IMPLEMENTED (branch)** | `integration`: `src/dispatch/ifta/` (9 modules) |
| **IFTA Clerk** — review dashboard, prepare-this-quarter, payment recommendation | **Hold** | 12 documents in `docs/ifta-clerk/` incl. blueprint + 5 NOTES/WALKTHROUGH pairs; `tests/ifta_clerk/` | **IMPLEMENTED (branch)** — exists nowhere else | `integration`: `src/dispatch/ifta_clerk/` (5 modules) |
| IFTA UI / mileage entry UI | Hold | branches `build/ifta-ui`, `build/mileage-entry-ui`; `docs/ifta-ui/DISPATCH_IFTA_UI_LAUNCH_PACKAGE_v1.md` | **IMPLEMENTED (branch)** | `integration`: `src/dispatch/ifta/{app,mileage}.py`, `tools/mileage_worksheet.py` |
| **Receipt intake, routing, dedup, validators, vocabulary** | **Hold** | `tests/lane_c/` (25 files), `tests/golden/receipts/` | **IMPLEMENTED (branch)** | `integration`: `src/dispatch/receipt/` (16 files) |
| **OCR / vision extraction** | **Hold** | branch `build/ocr-fenced-json-fix`; `docs/governance/OCR_VISION_EXTRACTION_DOCTRINE_v1.md` | **IMPLEMENTED (branch)** | `integration`: `src/dispatch/receipt/extraction/vision.py` |
| Receipt parsers (CSV, statement) | Hold | `tests/golden/receipts/` | **IMPLEMENTED (branch)** | `integration`: `src/dispatch/receipt/parsers/` |
| Fuel / mileage / expense data contracts | Hold | `fuel_record`, `mileage_record`, `expense_record`, `expense_vocabulary` schemas + conformance tests | IMPLEMENTED (on `main`) | `contracts/*.schema.json` |

## 3. THE ASSISTANT (JOE)

All rows in this section come from `Joe-Assistant/Assistant_Plugin/docs/JOE_CAPABILITY_TRUTH_MATRIX.md`,
which states: "Measured: 2026-08-26, **by running the program**… Every row was measured, not read
off a label."

| Capability | Repository | Evidence | Status | Primary location |
|---|---|---|---|---|
| **Launch by double-click** | Joe-Assistant | window visible in 4.6 s, `pythonw`, 0 console windows | **PROVEN** | `START_JOE.cmd`, `joe_main.py` |
| **Live Outlook read (read-only)** | Joe-Assistant | live COM read; **21 write calls scanned and refused** | **PROVEN** | `adapters/outlook_com.py` (706 LOC) |
| **Mailbox registry, 3-view discovery** | Joe-Assistant | Accounts + Stores + Folders reconciled; per-mailbox failure isolation | **PROVEN** | `adapters/mailbox_registry.py` (533 LOC) |
| **Live M365 Copilot reasoning** | Joe-Assistant | live prompt, live answer, signed in as Ops@ | **PROVEN** (API is `/beta`, unsupported for production) | `adapters/m365_copilot.py` (492 LOC) |
| **Copilot authentication (MSAL + DPAPI)** | Joe-Assistant | MSAL public client, DPAPI blob verified byte-level | **PROVEN** | `adapters/m365_copilot_auth.py` (347 LOC) |
| **Six enforced reasoning modes** | Joe-Assistant | enforced in the governance gate; a breach is refused | **PROVEN** | `contracts::ReasoningMode` |
| **Company Library retrieval** | Joe-Assistant | 34 documents indexed, real documents returned | **PROVEN** (holds no detention or load-refusal procedure) | `adapters/library_fs.py`, `library/assistant_library/` |
| **Web-grounded research** | Joe-Assistant | 11 real attributions with URLs | **PROVEN** (states it does not replace DOT or 511) | `adapters/research_provider.py` |
| **Per-entry provenance** | Joe-Assistant | Copilot and Library entries stay separate | **PROVEN** | `contracts::Provenance` |
| **Voice output** | Joe-Assistant | spoke aloud | **PROVEN** | `adapters/voice_sapi.py::speak` |
| **Retention Levels 1/2/3, Print Ready, Delete** | Joe-Assistant | proof steps 4–8 | **PROVEN** | `memory/assistant_memory/retention.py` |
| **3-hour expiry surviving restart** | Joe-Assistant | proof 13 | **PROVEN** | `assistant_memory` `MemoryStore` |
| **present / absent / unknown status** | Joe-Assistant | a timeout is unknown, never absent | **PROVEN** | `account_status()` |
| Calendar / contact answers | Joe-Assistant | **no approved mailbox holds a calendar**; JOE refuses and says why | **PARTIAL** | — |
| Multi-turn conversation | Joe-Assistant | context carries; substantive answers non-deterministic — 2/2, 1/2, 1/2, 0/2 across runs | **PARTIAL** | `prove_reasoning.py` |
| **Voice input** | Joe-Assistant | engine binds; microphone enumerated; **no person has ever spoken to it** | **BLOCKED-HUMAN** | `DriverVoiceLoop`, `whisper_listen.py` |
| Bluetooth headset | Joe-Assistant | LEVN headset known to Windows, not connected at last check | **BLOCKED-HUMAN** | `adapters/microphones.py` |
| Continuous Driver Mode | Joe-Assistant | loop, commands, state machine tested headless | IMPLEMENTED (unproven) | `app/driver_voice.py` |
| **Audio-activity detection** | — | "JOE cannot distinguish a dead microphone from a silent room" | **ABSENT** | — |
| **JOE ↔ Dispatch connection** | — | status strip: `Dispatch NOT CONNECTED`. `Dispatch/CLAUDE.md` §5.4 forbids granting Assistant direct Dispatch write authority | **ABSENT** (port exists) | `adapters/dispatch_port.py` |
| JOE Portal / JOE API / JOE voice in Dispatch | Dispatch | `portal/routes/{joe_portal,joe_api}.py`, `portal/joe_voice.py`, `dispatch/{joe_authority,joe_update}.py`, `run_joe_portal.py`, `docs/JOE_PORTAL.md` | **IMPLEMENTED (branch)** | `joe-portal` branch |

## 4. INTELLIGENCE, LIBRARY, PUBLISHER

| Capability | Repository | Evidence | Status | Primary location |
|---|---|---|---|---|
| **Intelligence analysis pipeline** (normalize → classify → extract → risk → route) | L2-intelligence-agent. | 33 test fns; 10 examples across 6 source families; **20 committed output pairs** | IMPLEMENTED — offline, deterministic, no LLM, no network (by design) | `src/dispatch_intel/` (14 modules) |
| 15+ risk-condition flags | L2-intelligence-agent. | `tests/test_risk.py` | IMPLEMENTED | `src/dispatch_intel/risk.py` |
| Fixed-set routing labels (never an approval label) | L2-intelligence-agent. | `README.md`; `tests/test_routing.py` | IMPLEMENTED | `src/dispatch_intel/routing.py` |
| The six doctrine objects | L2-intelligence-agent. | `docs/OBJECT_MODEL.md`; `tests/test_models.py` | IMPLEMENTED | `src/dispatch_intel/models.py` |
| **Library department** — 15-collection closed taxonomy | Library | `tests/test_taxonomy.py` | IMPLEMENTED | `src/dispatch_library/taxonomy.py` |
| **Versioned Object Registry with automatic supersession** | Library | one `CURRENT` per `object_code`; `tests/test_registry_resolver.py` | IMPLEMENTED — **the only place supersession doctrine actually runs** | `src/dispatch_library/registry.py` |
| Human-gated ingestion | Library | `tests/test_ingestion.py`; derived from Constitution §7.4 | IMPLEMENTED | `src/dispatch_library/ingestion.py` |
| **Publisher department** — request→workspace→readiness→inventory→review→approval→handoff | Publisher | 19 test fns; 9 object types per shared contracts §5 | IMPLEMENTED | `src/dispatch_publisher/service.py`, `models.py` |
| **Enforced no-external-send** | Publisher | a dedicated test asserts the department cannot send externally | IMPLEMENTED — only such test anywhere | `tests/test_no_external_send.py` |
| Cross-repo clients with in-process stubs | Publisher | duck-typed, no hard package dependency | IMPLEMENTED — no live consumer connected | `library_client.py`, `intelligence_client.py` |
| Intelligence / Library / Publisher **portal surfaces** | Dispatch | `/intelligence{,/add,/promote,/update}`, `/publisher{,/create,/update}`, library model | IMPLEMENTED — distinct from the department repos | `portal/models/{intelligence,library,publisher}.py` |
| Library (contract pipeline flavour) | Dispatch-Old | `tests/test_library.py`; seeded `Library/Company/`, `Library/Templates/` | IMPLEMENTED | `cin_lite/library.py` (67 LOC) |
| Publisher (contract pipeline flavour) | Dispatch-Old | 4 test files incl. approval state, work orders | IMPLEMENTED | `cin_lite/publisher.py` (84 LOC) |
| Librarian spine | Hold | branch `build/librarian-spine`; `tests/lane_a/`; `LIBRARIAN_CONSTITUTION_v1.md` | **IMPLEMENTED (branch)** | `integration`: `src/dispatch/evidence/`, `common/` |
| **Content generation** (cover letters, technical narratives, form fields) | — | `Publisher/KNOWN_GAPS.md`: "**No content-generation layer.**" Templates and prototype not found on any branch of any repo | **ABSENT** | — |
| **Persistent store for any department** | — | All three department repos state in-memory / stateless in `KNOWN_GAPS.md` | **ABSENT** | — |

## 5. MANAGER

Manager is the most contested capability in the ecosystem and is set out in full.

| Where | What | Status | Primary location |
|---|---|---|---|
| **Dispatch-Old** | Manager ticketing / human-control workflow. `MGR-<UTC>` tickets to `Archive/ManagerTickets/`; `human_decision_required=True` by default; `tests/test_manager.py`, `test_manager_publisher_handoff.py` | **IMPLEMENTED (merged)** — the only Manager that runs and is tested on a default branch | `cin_lite/manager.py` (101 LOC) |
| **Hold** | Manager queue; `queue_item.schema.json` + conformance test; `tests/lane_b/` | **IMPLEMENTED (branch)** | `integration`: `src/dispatch/queue/{app,store}.py` |
| **Dispatch** | `classify`, `policy_candidates`, `priority`, `security_monitor`, `signals`, `staff_report`, `stage_gate` (767–866 LOC) | **IMPLEMENTED (branch)** — 5 branches: `stage12-manager-{foundation,archive-wiring,m7-policy-hook}`, `stage13-testing-hold-review`, `stage6-archive-review-queue` | `dispatch/manager/` |
| L2-intelligence-agent. | **Manager Decision Support Note** — a Manager object produced by a running pipeline | IMPLEMENTED | `src/dispatch_intel/models.py` |
| Hold | `MANAGER_CONSTITUTION_v1.md` — the only Manager *constitution* anywhere | DOCUMENTED | `docs/governance/` |
| Claude | The only **independent architectural review of Manager** anywhere, in two rounds, with an 8-doc frozen source snapshot | DOCUMENTED (branch) | `claude/dispatch-manager-architecture-review-ha8tm5` |
| Claude-3 | 5 stage designs (`STAGE12_MANAGER_{BUILD,ARCHIVE_WIRING,M4_MIRROR,M4_M6,M7_POLICY_HOOK}_DESIGN_v1`), `DISPATCH_MANAGER_BUILDOUT_DESIGN_v1`, `MANAGER_ORCHESTRATION_REVIEW_v1` | DOCUMENTED (branch) | branches |
| L2-intelligence-agent. | `MANAGER_DESCRIPTION_v2.md` | DOCUMENTED | root |
| **Dispatch `main`** | **No Manager code.** `CLAUDE.md` §5.6: "There is no Manager component in the current architecture. Do not create, restore, reference, or infer a Manager component." `docs/MANAGER.md` is "the permanent record of a capability that was *named* in planning and *never built*." Guarded by `tests/test_repository_doctrine.py` | **ABSENT by doctrine** | `docs/MANAGER.md` |

`Dispatch/CLAUDE.md` §5.6 is accurate about Dispatch's `main`. Across the ecosystem, Manager
exists as running code in three places and as documentation in nine. Recorded as fact.

## 6. GOVERNMENT CONTRACTING (SAM / CIN / SDVOSB)

`Claude-3/RECOVERY_REPORT.md`: *"Most of what was recovered is CIN/SDVOSB material and is not
Dispatch v0 material."*

| Capability | Repository | Evidence | Status | Primary location |
|---|---|---|---|---|
| **9 deterministic solicitation rule modules** | Dispatch, Dispatch-Old | set_aside, naics_sin, past_performance, pricing_anomaly, vendor_network, subcontractor_dominance, jv_mp_structure, foreign_influence, cyber_compliance | IMPLEMENTED | `cin_lite/rules/` (both repos) |
| SAM.gov acquisition | Dispatch, Dispatch-Old | `tests/test_acquisition.py`; falls back to sample data | IMPLEMENTED; provider **UNCONFIGURED** | `cin_lite/acquisition.py` |
| **5-action checkbox email control gate** | Dispatch, Dispatch-Old | Approve for archive / Approve for proposal / Reject / Flag for review / Request deeper analysis | IMPLEMENTED | `cin_lite/control.py` |
| Email transport | Dispatch | `CLAUDE.md` §1: CIN-Lite is Dispatch's **only** mail transport | IMPLEMENTED; **UNCONFIGURED** | `cin_lite/email_delivery.py`, `connectors/email_transport_connector.py` |
| Claude agents (summarizer, router, proposal_writer, extractor, receipt_vision) | Dispatch | 5 agents; labelled non-deterministic, never load-bearing | IMPLEMENTED | `cin_lite/agents/` |
| Proposal-trigger workflow | Dispatch, Dispatch-Old | `tests/test_proposal_trigger.py` | IMPLEMENTED | `cin_lite/workflows/proposal.py` |
| Archive (Raw/Processed/Intelligence/Summaries/Routing) | Dispatch, Dispatch-Old | `tests/test_archive.py` | IMPLEMENTED | `cin_lite/archive.py` |
| Dashboard (server, CLI, HTML, status banner, quick actions, refresh) | **Dispatch-Old only** | 9 dedicated test files | IMPLEMENTED — absent from Dispatch | `cin_lite/dashboard.py` (222 LOC) |
| Portal command | **Dispatch-Old only** | `test_portal_command.py`, `test_portal_env_config.py` | IMPLEMENTED — absent from Dispatch | `cin_lite/portal.py` (70 LOC) |
| SAM portal page | Dispatch | `/sam` route + template | IMPLEMENTED; integration **UNCONFIGURED** | `portal/templates/sam.html` |
| SAM-family analysis examples + outputs | L2-intelligence-agent. | `examples/sam_gov/`, `reports/sample_outputs/sample_sam_report.{json,md}` | IMPLEMENTED | those paths |
| **`cin-hybrid/` runtime** — 16 agents (`gov_engine`, `net_engine`, `ops_engine`, `risk_engine`, `tell_engine`, `sam_ingestion_engine`, `vendor_network_engine`, `cyber_compliance_engine`, `cin_router`, `hybrid_orchestrator`, …), intel layer (`intelligence_guard`, `intelligence_owner`, `cin_scoring`), services (`docusign_bridge`, `outlook_email_client`, `sam_feed`, `set_aside_rules`), runtime (`dispatcher`, `event_bus`, `state_manager`) | **Dispatch** | 42 files, 1,125 py LOC | **IMPLEMENTED (branch)** — 3 branches, tip 2026-07-04; the only surviving `cin-hybrid` code | `feature/init-hybrid-structure`, `claude/sdvosb-contract-opportunities-76rgtu`, `claude/va-2026-541512-exec-summary-lpgno3` |
| **`l2_cos/`** — 6 freight rules (`broker_risk`, `capacity_match`, `deadhead_cost`, `facility_risk`, `lane_fit`, `rate_anomaly`) + 5-module UI | **Dispatch** | 34 files, 1,805 py LOC | **IMPLEMENTED (branch)** — the only surviving L2-COS-era freight code | `claude/l2-cos-dispatch-refactor-c1ett1` |
| `hybrid_engine/ai_agent_collector` | Dispatch | 271 LOC | **IMPLEMENTED (branch)** | `claude/ai-agent-collector-module-l6vpxl` |
| **`SAM` as a repository** | — | 0 commits, 0 branches, 0 files | **EMPTY** | https://github.com/jax1313-outlook/SAM |
| `hybrid_v1`, `hybrid-operator` (Next.js UI), `Micro-CIN` / "CIN-Tell" | — | Named in `Claude-3/RECOVERY_REPORT.md` as recovered codebases; no repository holds them | **ABSENT** | — |

## 7. PORTALS, WEB AND PRESENTATION

| Capability | Repository | Evidence | Status | Primary location |
|---|---|---|---|---|
| **Driver Portal** | Dispatch | 8 routes; `driver_home`, `driver_login`, `driver_forgot_pin`, `driver_pay` templates; `DRIVER_PORTAL_ARCHITECTURE_V2.md` | IMPLEMENTED | `portal/routes/driver_portal.py` |
| Driver PIN registry + recovery word | Dispatch | `/driver-pin/{create,reset,delete,status,recovery-word}`, `/forgot-pin` | IMPLEMENTED | `portal/models/driver_pin_registry.py` |
| Stakeholder portal | Dispatch | 2 routes; `stakeholder_view.html` | IMPLEMENTED | `portal/routes/stakeholder.py` |
| **178 unique HTTP routes / 9 blueprints / 41 templates** | Dispatch | route enumeration | IMPLEMENTED | `portal/` |
| **Public marketing website** (`/`, `/about`, `/capabilities`, `/contact`) | **Jules** | 4 routes + 4 templates | IMPLEMENTED — only public website in the ecosystem | `app.py`, `templates/` |
| **Operations Portal** | **Jules** | `templates/operations.html` | IMPLEMENTED — only one so named | `app.py` |
| **Legacy L2-COS URL space** (`/portal`, `/cos`, `/l2-cos`, `/dashboard`, `/admin`) | **Jules** | `legacy_portal_redirect()` | IMPLEMENTED — only surviving record of the old addresses | `app.py` |
| Planning Intelligence Dashboard prototype | Dispatch | `portal/prototype/L1_Transport_Planning_Intelligence_Dashboard.html` (995 lines) | **IMPLEMENTED (branch)** | `joe-portal` branch |
| Dispatch shell | Hold | branch `build/dispatch-shell`; `tests/shell/` | **IMPLEMENTED (branch)** | `integration`: `src/dispatch/shell/app.py` |
| **Brand and visual identity** (palette, typography, brand copy) | **premium-logistics-platform-** | Onyx `#0D0D0E`, charcoal `#141416`, champagne gold; `THE ART OF VELOCITY`, `CLIENT ACCESS`, `ENTER PLATFORM PORTAL` | **DOCUMENTED** (prompts only; no asset produced) — only such material anywhere | `A cinematic, slow-motion tracking s.md` |
| **"Joe screens"** | — | Promised in `premium-logistics-platform-/README.md`; no screen asset exists | **ABSENT** | — |

## 8. CAPACITY, SCHEDULING AND OPPORTUNITY

| Capability | Repository | Evidence | Status | Primary location |
|---|---|---|---|---|
| Capacity computation (available / consumed / reserve / position) | Dispatch | `WEEK_VIEW_CAPACITY_VISUALIZATION_ARCHITECTURE.md`, `DISPATCH_DYNAMIC_CAPACITY_ARCHITECTURE.md` | IMPLEMENTED | `dispatch/capacity.py` |
| Week View / Calendar (presentation over Outlook) | Dispatch | `/calendar` page + API; `CLAUDE.md` §5.5 — Outlook is the scheduling authority; Dispatch must not build a competing scheduler | IMPLEMENTED; Outlook **UNCONFIGURED** | `portal/templates/calendar.html` |
| **Opportunity Cards** (possibilities, never commitments) | Dispatch | `OPPORTUNITY_PIPELINE_ARCHITECTURE.md`; `CURRENT_REALITY_VS_POSSIBLE_FUTURES_ARCHITECTURE.md` | IMPLEMENTED | `dispatch/opportunities.py` |
| **Scoring** (position impact, return-home, HOS risk, route risk, deadhead, fuel, 0–100) | Dispatch | `Claude-3/CLONE_MAP.md`: *"the single most complete, ready-to-clone piece of the entire recovery"* | IMPLEMENTED — advisory; **score does not decide** (`CLAUDE.md` §4.2) | `dispatch/scoring.py` |
| Sandbox / staging (OPEN→INTERESTED→PURSUE→…→BOOKED) | Dispatch | `CLONE_MAP.md` rates it a "strong partial match" | IMPLEMENTED | `portal/models/sandbox.py`, `cin_lite/pending.py` |
| Scheduling / mission templates | Dispatch | `dispatch/scheduling.py` (409), `mission_template.py` (673) | **IMPLEMENTED (branch)** | `joe-portal` branch |
| Sandbox engine (retention, intents, records) | Joe-Assistant | `Testing/SANDBOX_ENGINE_TEST_REPORT_v1.md`; live records in `Sandbox/active` | IMPLEMENTED | `Build/sandbox_engine/` |
| **Routing / distance API** | — | `CLONE_MAP.md`: `_KNOWN_DISTANCES` covers ~20 fixed Southeast city pairs; "No real routing API integration found anywhere in scope" | **PARTIAL** | `dispatch/scoring.py` |

## 9. RISK, VISIBILITY, ROUTING SIGNALS

| Capability | Repository | Evidence | Status | Primary location |
|---|---|---|---|---|
| **Route Risk** | Dispatch | `route_risk_events` table; scoring factor; `M3_ROUTE_RISK_DURABILITY_WALKTHROUGH_REPORT_v1.md`; 672 matching lines | IMPLEMENTED; provider **UNCONFIGURED** | `dispatch/route_risk.py`, `connectors/route_risk_connector.py` |
| **COMI routing** | Dispatch | 92 matching lines; branch `claude/comi-status-everywhere` | IMPLEMENTED | `dispatch/comi_routing.py` |
| **Mission Visibility** | Dispatch | `/loads/<id>/visibility`; `visibility` table; branch `claude/mission-visibility-foundation` | IMPLEMENTED | `dispatch/models.py:LoadVisibilityRecord` |
| Visibility package (as an object) | Publisher | `VisibilityPackage` per shared contracts §5 | IMPLEMENTED | `src/dispatch_publisher/models.py` |
| Conflict detection & resolution | Dispatch | `/conflicts`, `/conflict/resolve`; `conflict_events` table | IMPLEMENTED | `portal/models/conflict.py` |
| Operations feed | Dispatch | `/operations` | IMPLEMENTED | `portal/models/operations_feed.py` |
| **Six-level consequence model** (Silent Log / Status / Review / Decision / Conflict / Authority) | **Jules** | `LEVEL_0_SILENT_LOG`…`LEVEL_5_AUTHORITY`, `CONSEQUENCE_LABELS` | IMPLEMENTED — exists nowhere else | `dispatch_spine.py` |
| **`route-risk` as a repository** | — | 0 commits, 0 branches, 0 files | **EMPTY** | https://github.com/jax1313-outlook/Route-Risk |

## 10. ARCHIVE, EVIDENCE, AUDIT AND RETENTION

| Capability | Repository | Evidence | Status | Primary location |
|---|---|---|---|---|
| Archive & retention | Dispatch | `/archive`, `/archive/create`, `/retention`; `retention` table | IMPLEMENTED | `portal/models/archive.py` |
| Audit events / connector audit / token audit | Dispatch | `audit_events`, `connector_audit`, `token_audit` tables | IMPLEMENTED | `dispatch/connectors/audit.py`, `dispatch/tokens.py` |
| **Evidence index + interface** | Hold | branch `amend/evidence-record-v1.1`; `evidence_record.schema.json` | **IMPLEMENTED (branch)** | `integration`: `src/dispatch/evidence/` |
| **Audit trail + audit rolls export** | Hold | `audit_entry.schema.json` + `tests/conformance/test_audit_entry_conformance.py` | **IMPLEMENTED (branch)** | `integration`: `common/audit.py`, `tools/export_audit_rolls.py` |
| **Reports** (queries, dates, rendering, snapshots, template engine, fidelity gate) | Hold | `tests/lane_d/` (15 files) incl. `test_fidelity_gate.py`; `docs/lanes/D/FIDELITY_GATE_REPORT_v1.md` | **IMPLEMENTED (branch)** | `integration`: `src/dispatch/reports/` (8 modules) |
| Memory retention (Levels 1/2/3, 3-hour expiry) | Joe-Assistant | proof steps 4–8, 13 | **PROVEN** | `memory/assistant_memory/retention.py` |
| Backup & restore | Dispatch | `BACKUP_AND_RECOVERY.md` | IMPLEMENTED | `dispatch/backup.py`, `dispatch_launcher/backups.py` |
| **Live Archive department** | — | `Library/KNOWN_GAPS.md`: "nothing writes them to an actual Archive department" | **ABSENT** | — |

## 11. SECURITY, AUTH AND GOVERNANCE ENFORCEMENT

| Capability | Repository | Evidence | Status | Primary location |
|---|---|---|---|---|
| CSRF across mutating routes | Dispatch | `CLAUDE.md` §7 forbids weakening it | IMPLEMENTED | `portal/csrf.py` |
| Fail-closed authentication | Dispatch | `/login`, `/logout` | IMPLEMENTED | `portal/routes/auth.py` |
| Operational tokens (issue / expiry / revoke) | Dispatch | `operational_tokens`, `token_audit` tables | IMPLEMENTED | `dispatch/tokens.py` |
| **`dispatch/security/`** (`auth`, `db`, `models`, `store`) | Dispatch | 690 LOC; `tests/test_security_foundation.py` | **IMPLEMENTED (branch)** | 6 branches incl. `stage7-security-foundation` |
| Governance gate (reasoning-mode enforcement) | Joe-Assistant | a breach is refused | **PROVEN** | `Assistant_Plugin/governance/` |
| **Repository doctrine tests** | Dispatch | asserts no Manager component; asserts plug-in separation | IMPLEMENTED | `tests/test_repository_doctrine.py` |
| **Doctrine-enforcing boundary tests** (`test_no_tax_math`, `test_no_delete_sql`, `test_readonly_enforcement`, `test_ifta_position_display_only`, `test_fidelity_gate`) | Hold | `tests/lane_d/` | **IMPLEMENTED (branch)** | `integration` |
| **No-external-send enforcement** | Publisher | dedicated test | IMPLEMENTED | `tests/test_no_external_send.py` |
| **`REQUIRED_CARD_CLOSING`** — authority doctrine as a code constant | **Jules** | "This is a recommendation only. No action is authorized. Mike decides." | IMPLEMENTED — only such enforcement anywhere | `dispatch_spine.py` |
| **8 JSON Schemas + CONTRACT_REGISTER** | **Hold** | `audit_entry`, `config`, `evidence_record`, `expense_record`, `expense_vocabulary`, `fuel_record`, `mileage_record`, `queue_item` + conformance tests | IMPLEMENTED (on `main`) — **only formal machine-readable data contracts in the ecosystem** | `contracts/` |

## 12. CONNECTORS AND EXTERNAL SYSTEMS

`Dispatch/CLAUDE.md` §8: **"Every external system is `UNCONFIGURED`.** No ELD, GPS, traffic,
weather, load board, mapping, accounting, scanner or Outlook client is connected."

| Connector | Repository | Interface | Provider | Status |
|---|---|---|---|---|
| Connector boundary + registry + audit + contract | Dispatch | `boundary.py`, `contract.py`, `registry.py`, `audit.py`, `mock.py`; `docs/connectors/PROVIDER_INSERTION.md` | — | IMPLEMENTED |
| Outlook | Dispatch | `connectors/outlook_connector.py` | none | **UNCONFIGURED** |
| **Outlook — actual working implementation** | **Joe-Assistant** | `adapters/outlook_com.py` (706 LOC), `mailbox_registry.py` (533) | **live COM** | **PROVEN** |
| Outlook mail (Dispatch-side) | Dispatch | `dispatch/connectors/outlook_mail.py` (286 LOC), `tests/test_outlook_connectors.py` | — | **IMPLEMENTED (branch)** — `joe-portal` |
| Accounting | Dispatch | `connectors/accounting_connector.py`, `dispatch/accounting_export.py` | none | **UNCONFIGURED** |
| Load board | Dispatch | `connectors/load_board_connector.py` | none | **UNCONFIGURED** |
| Mapping | Dispatch | `connectors/mapping_connector.py` | none | **UNCONFIGURED** |
| Route Risk | Dispatch | `connectors/route_risk_connector.py` | none | **UNCONFIGURED** |
| Scanner | Dispatch | `connectors/scanner_connector.py` | none | **UNCONFIGURED** |
| Email transport | Dispatch | `connectors/email_transport_connector.py` → `cin_lite/email_delivery.py` | none | **UNCONFIGURED** |
| Future intelligence | Dispatch | `connectors/future_intelligence_connector.py` | none | **UNCONFIGURED** |
| M365 Copilot | Joe-Assistant | `adapters/m365_copilot{,_auth}.py` | **live, signed in as Ops@** | **PROVEN** (API `/beta`) |
| Claude API | Dispatch, Joe-Assistant | `cin_lite/agents/`, `adapters/claude_provider.py` | — | IMPLEMENTED |
| Voice SAPI / Whisper / microphones | Joe-Assistant | `voice_sapi.py`, `whisper_listen.py`, `microphones.py` | output live; input never used | **PROVEN** (out) / **BLOCKED-HUMAN** (in) |
| DocuSign bridge | Dispatch | `cin-hybrid/core/services/docusign_bridge.py` | — | **IMPLEMENTED (branch)** |
| **ELD / GPS / traffic / weather** | — | no interface, no provider | **ABSENT** | — |

## 13. DEPLOYMENT, LAUNCH AND OPERATIONAL PROOF

| Capability | Repository | Evidence | Status | Primary location |
|---|---|---|---|---|
| **Dispatch Launcher / Control Center v1** | Dispatch | 15 modules; `docs/readiness/CONTROL_CENTER.md`; 87.75% coverage, Windows branches untested | IMPLEMENTED | `dispatch_launcher/` |
| Documented launch path | Dispatch | `docs/readiness/LAUNCH_PATH.md` — why `DISPATCH_START_HERE.cmd` and not `dispatch.bat` | IMPLEMENTED | `DISPATCH_START_HERE.cmd` |
| D: drive bootstrap | Dispatch | `bootstrap_d_drive.py`; branch `feat-d-drive-bootstrap-…` | IMPLEMENTED | that file |
| Rehearsal mode | Dispatch | `rehearsal_sessions` table | IMPLEMENTED | `dispatch/rehearsal.py` |
| **20-step operational-proof system** | Dispatch | `docs/readiness/OPERATIONAL_LOAD_PROOF_TEMPLATE.md` | IMPLEMENTED; **the 20 steps are UNVERIFIED** | `dispatch/proof.py` |
| 15 first-start acceptance items | Dispatch | `docs/readiness/LAUNCHER_PROOF_TEMPLATE.md` | **UNVERIFIED** | that template |
| Sandbox survey (10 templates) | Dispatch | `docs/readiness/sandbox_templates/` | IMPLEMENTED | `dispatch/sandbox_survey/` |
| **VPS deployment — nginx, systemd, certbot, DNS** | **Dispatch-Old** | `nginx.conf`, `portal.service`, `setup_certbot_nginx.sh`, Namecheap DNS records, 5 deployment docs | IMPLEMENTED — **the only concrete hosting config in the ecosystem**; deployment itself UNVERIFIED | `Portal Deploy/` |
| VPS / local deployment (prose) | Dispatch | `DEPLOY_VPS.md`, `DEPLOY_LOCAL.md` — no nginx/systemd/certbot artefact exists | DOCUMENTED | those files |
| Dockerfile | Dispatch | on one branch | **IMPLEMENTED (branch)** | `claude/baseagent-abstract-interface-1xr9bn` |
| **JOE packaging + shortcuts + 30 operator launchers** | Joe-Assistant | `PACKAGE_JOE.cmd`, `verify_package.ps1`, `install_shortcuts.ps1` | IMPLEMENTED | `Deployment/`, `launchers/` |
| **9-script proof harness with screenshots** | Joe-Assistant | `run_proof.py` (1,663 LOC), `prove_*.py` ×8, 3 PNGs | **PROVEN** (executed) | `Assistant_Plugin/proof/` |
| Pilot runs 1 and 2 | Hold | `docs/pilot/DISPATCH_PILOT_RUN_{1,2}_REPORT_v1.md` | **IMPLEMENTED (branch)** — executed | `integration` |
| **Dispatch running on Mike's laptop** | — | `Dispatch/CLAUDE.md` §8: "Nothing in this repository has been run on Mike's Windows laptop." Laptop readiness **UNVERIFIED** | **ABSENT** | — |

## 14. DOCTRINE AND RECOVERY ARTEFACTS

| Artefact | Repository | Status | Location |
|---|---|---|---|
| Cold-start brief; purpose statement; Driver-First doctrine (D1–D15, 70 MPH Test) | Dispatch | DOCUMENTED | `CLAUDE.md`, `DISPATCH_PURPOSE_STATEMENT.md`, `DRIVER_FIRST_DOCTRINE_v2.md` |
| Decision log | Dispatch | DOCUMENTED | `DECISION_LOG.md` |
| 12 specifications; 11 walkthrough reports | Dispatch | DOCUMENTED | `docs/`, root |
| Constitution v3 + 18 doctrines | Claude-3, Jules, Library | DOCUMENTED | roots |
| Constitution v2 family | Claude, Joe-Assistant, L2-intelligence-agent., Publisher | DOCUMENTED | roots |
| **`DISPATCH_FINAL_BLUEPRINT_v1.md`** (1,133 lines) | Claude-3, Jules, Library, Dispatch | **DOCUMENTED — on 13 branches, on NO default branch anywhere.** `L2-intelligence-agent./KNOWN_GAPS.md` records it as "not found in any repo in scope" | branch `claude/dispatch-final-blueprint-v1-1vlkkc`; `Dispatch` `stage*` branches |
| **`DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md`** | Claude-3 (+ Jules, Library) | **DOCUMENTED (branch)** — cited as governing authority by 3 repositories | branches |
| **`LIBRARY_INGESTION_RULE.md`** | Claude-3, Jules, Library | **DOCUMENTED (branch)** — `Library/KNOWN_GAPS.md` records it as not found in any repo in scope | branches |
| Prior recovery mission: report, clone map, source index, survives/evolves/retires, V0 blueprint & build plan | Claude-3 | DOCUMENTED | `main` |
| **`OPEN_QUESTIONS_FOR_MIKE.md`** | Claude-3 | DOCUMENTED — only standing decision register anywhere | `main` |
| 7 per-worker constitutions + `APPROVAL_REGISTER.md` (14 approval items) | Hold | DOCUMENTED | `docs/governance/`, mirrored in `library_seed/Constitutions/` |
| 11 reference audits | Hold | DOCUMENTED | `docs/reference/` |
| `REPO_TO_DISPATCH_MAP.md` — the CIN-Lite↔Dispatch vocabulary map | Dispatch-Old | DOCUMENTED | root |
| Independent Manager architecture review (2 rounds + frozen source snapshot) | Claude | DOCUMENTED (branch) | `claude/dispatch-manager-architecture-review-ha8tm5` |
| Architecture stress test **prompt + result**; consensus matrix + revision | Claude-2 | DOCUMENTED (prompt on `main`, results on branch) | root, `claude/new-session-jwlb0v` |
| 16 stage designs (stages 4–13) | Claude-3, Library, Jules | DOCUMENTED (branch) | branches |
| **`CONSTITUTION.md`** — Level 1 Transport master constitution, declared supreme law by `Hold/README.md` | — | **ABSENT from all fourteen repositories** | stated to live in "Copilot Workspace/Constitution" |
| `07_DISPATCH_REPO_PLACEMENT_PLAN.md` | — | **ABSENT** from every default branch; cited by `Library/README.md` and `Publisher/README.md` | — |
| 9 named Publisher source artefacts (`publisher_mvp.py`, `publisher_recipes.json`, templates, Legacy Publisher Emails 1–5, `Visibility_SOP.docx`, …) | — | **ABSENT** — not found on any branch of any repository | — |
| `Jules-2`, `Jules-3`, `Test-Grounds` repositories | — | **ABSENT** from the account; named in `Claude-3/RECOVERY_REPORT.md` and `Publisher/README.md` | — |

---

# THE ANSWER

**What has actually been built?**

**One thing has been proven.** `Joe-Assistant` is the only repository in the ecosystem whose
capabilities were measured by running the program against live external services. On 2026-08-26
it demonstrably launched in 4.6 seconds, read a real Outlook mailbox over COM while refusing 21
write calls, reasoned through Microsoft 365 Copilot signed in as a real account, stored tokens
via MSAL and DPAPI verified byte-level, retrieved real documents from a 34-document library,
returned web research with eleven real URL attributions, and spoke aloud. It also records,
equally plainly, that **voice input has never heard a person**, that audio-activity detection is
not implemented, and that **Dispatch is not connected**.

**A great deal has been built and none of it has been proven.** `Dispatch` is a substantially
complete freight platform in software — 82,699 lines, 178 routes, 35 tables, 24 domain objects,
3,793 test functions — covering the Spine lifecycle, loads, drivers, equipment, capacity,
milestones, evidence, POD, settlement, a full IFTA subsystem, the Driver Portal, Opportunity
Cards, scoring, COMI, Route Risk, Mission Visibility, archive, conflicts, notifications,
CSRF and fail-closed auth, a governed connector boundary, backup and restore, rehearsal mode, a
20-step proof system, and a Windows launcher. Its own `CLAUDE.md` states that **none of it has
ever run on Mike's laptop** and that **every external system is `UNCONFIGURED`** — no ELD, GPS,
traffic, weather, load board, mapping, accounting, scanner or Outlook connection exists. Dispatch
does not know a driver's hours of service.

**A great deal has been built and never merged.** This is the largest finding of the inventory:
**692 files exist only on unmerged branches.**
- `Hold`'s `main` contains **zero Python**; its `integration` branch contains **13,770 lines,
  148 modules and 428 test functions** — a receipt and IFTA system with OCR extraction, a full
  IFTA engine, an **IFTA Clerk** that exists nowhere else, a Reports lane with a fidelity gate,
  a Manager queue and a Librarian spine. Built in ~26 hours on 2026-08-04/05. Never merged.
- `Dispatch`'s `joe-portal` branch is **48 commits ahead of `main`**, tips at **2026-09-03** —
  the newest work in the entire ecosystem — and carries roughly 14,000 lines: a Driver Cockpit,
  a JOE Portal and API, mission and scheduling engines, a booking board, an Outlook mail
  connector, and 19 test files.
- Three `Dispatch` branches carry the only surviving `cin-hybrid` runtime (16 agents); one
  carries the only surviving L2-COS freight rules and UI; five carry a `dispatch/manager/`
  package; six carry a `dispatch/security/` package.
- `DISPATCH_FINAL_BLUEPRINT_v1.md` — 1,133 lines, the stated purpose of two whole repositories —
  exists identically in thirteen places across four repositories and **on no default branch
  anywhere.** Two other documents cited as governing authority by three repositories
  (`DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md`, `LIBRARY_INGESTION_RULE.md`) are in the same
  condition. `L2-intelligence-agent.` and `Library` were each built while recording those
  documents as "not found in any repo in scope."

**Three departments were built to integration-ready and stopped.** `L2-intelligence-agent.`
(Intelligence, 2,006 LOC), `Library` (875 LOC) and `Publisher` (872 LOC) were completed on
2026-08-11, each declared "Integration-ready candidate. Not merged. Not deployed. Not
production-promoted." None has a persistent store. None has been touched since. Each recorded
its own gaps honestly and stated that missing content was not invented.

**Manager exists.** `Dispatch/CLAUDE.md` §5.6 states there is no Manager component and that
`docs/MANAGER.md` records a capability "named in planning and never built." That is accurate
about Dispatch's `main`. Across the ecosystem, Manager runs as tested code in
`Dispatch-Old/cin_lite/manager.py` (merged), in `Hold`'s queue (branch), and in
`Dispatch/dispatch/manager/` (five branches) — and is documented in nine repositories, with its
own constitution in `Hold` and its only independent architectural review in `Claude`.

**Two repositories are empty.** `Route-Risk` and `SAM` were created 115 seconds apart on
2026-08-19 and contain zero commits, zero branches and zero files. Both capabilities exist —
elsewhere.

**Four things are named everywhere and exist nowhere.** `CONSTITUTION.md`, declared by
`Hold/README.md` to be the supreme law over all governed development work, is in none of the
fourteen repositories. The `Jules-2`, `Jules-3` and `Test-Grounds` repositories, named as working
instances of the promotion pipeline, are not in the account. Nine Publisher source artefacts are
not on any branch of any repository. And a load-board sweep adapter — which
`Claude-3/CLONE_MAP.md` calls "the biggest genuine build gap" — has never been built.

**What has actually been built is more than any single default branch shows.**
The working system is spread across four places: `Dispatch`'s `main`, `Dispatch`'s unmerged
branches, `Hold`'s `integration` branch, and `Joe-Assistant`. Reading any one of them alone
understates the whole by a wide margin — and reading only default branches misses 692 files,
including the blueprint two repositories were created to produce.
