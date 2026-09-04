# Dispatch — Repository-Grounded Gap Analysis

**Date:** 2026-09-04 · **Directive:** Dispatch Gap Analysis Directive, Mike Zachary
**Method:** repository inspection only. Every claim carries a file path. Nothing is assumed.
**Scope inspected:** Dispatch `7669176` · Jules `32d64ef` · Claude-3 `61dd119` ·
Joe-Assistant `4a9a6a3` (read-only clone, history deepened to 36 commits)

**Status vocabulary** is `CLAUDE.md` §6 and is used strictly. `UNKNOWN` means not
established by inspection — it does not mean absent.

---

## PART 0 — What this report could not see

Stated first, because it bounds everything after it.

| Target | Status | Why |
|---|---|---|
| `D:\Joe-Assistant` working tree | **UNKNOWN** | A Windows path on Mike's machine. Not reachable from this Linux container. **Nothing in this report describes it.** |
| Joe-Assistant history before 36 commits | **UNKNOWN** | Clone deepened to 36; that is the whole of `main`, but unpushed local work is invisible by definition. |
| Nine further repositories | **UNKNOWN** | See G-42. |

**The directive names four synchronization targets. Fourteen repositories exist.**

`Dispatch` · `Jules` · `Claude-3` · `Joe-Assistant` · `Publisher` · `Library` ·
`Route-Risk` · `SAM` · `Hold` · `Dispatch-Old` · `Claude` · `Claude-2` ·
`premium-logistics-platform-` · `L2-intelligence-agent.`

Four of those — `Publisher`, `Library`, `Route-Risk`, `SAM` — carry the names of
subsystems that **also exist as modules inside Dispatch**. Which is authoritative is
`UNKNOWN` and is a governance question, not a build question.

---

## PART 1 — Executive Summary

### The finding that reframes the rest

**The Mission Record does not exist.** Not partially, not under another name. Searching
`dispatch/` and `portal/` for `class .*Mission`, `mission_record` and `mission_id` returns
**zero results**. The word "mission" appears 75 times and never as a domain object: it is
either prose about *build* missions, or the name of the Mission Visibility plug-in.

Every architecture document describing a Mission Record flowing through Dispatch →
Calendar → COMI → Route Risk → Driver Portal → Publisher → Closeout → Archive is
describing **target state**. What exists is `Load` — a flat record with no identity field
beyond an opaque primary key.

This is not a defect. It is a gap between an approved architecture and an implementation
that predates it, and it has to be named before a backlog built on it means anything.

### The three structural absences

1. **No Mission Record.** §G-01.
2. **No Sweeper.** No intake from DAT, TruckSmarter or any load board. `LOAD_SOURCES`
   contains `"dat"` and `"truckstop"` as *labels a human may type*, not as intake paths.
   §G-30.
3. **No load number a human can say.** `load_id` is
   `LOAD-20260904-A3F91B2C`. There is no broker load number field anywhere. §G-02, §G-03.

### The condition of the whole system

**Every external system is `UNCONFIGURED`.** Eight connectors are registered; Outlook is
`ABSENT`; the load board is `SIMULATED` / `UNAVAILABLE`. Dispatch has done **zero loads**.
Its suite passes 3,822 tests at 94.80% coverage, and `CLAUDE.md` §6 is explicit that this
is evidence of software behaviour and never operational proof.

**What is genuinely good, and should not be rebuilt:** the connector boundary, the truth
vocabulary and its runtime validation, the Spine's transition guard, CSRF coverage, the
IDOR check on every driver route, and the driver portal's refusal to fail silently
(`_tell_driver`, `driver_portal.py:163`). These are load-bearing and correct.

### Top 20 gaps preventing operational deployment

Ordered by what blocks the `CLAUDE.md` §2 gate — *he uses it to run a load and gets paid*.

| # | ID | Gap | Severity |
|---|---|---|---|
| 1 | G-01 | No Mission Record entity exists | **BLOCKER** |
| 2 | G-02 | No human-speakable load number | **BLOCKER** |
| 3 | G-03 | No broker load number field | **BLOCKER** |
| 4 | G-10 | Driver portal has never had a real driver account | **BLOCKER** |
| 5 | G-20 | No load has ever been created outside a test | **BLOCKER** |
| 6 | G-04 | Two lifecycles coexist: `loads.status` and Spine `work_items` | **CRITICAL** |
| 7 | G-40 | Portal cannot report which build it is running | **CRITICAL** |
| 8 | G-41 | `control.start()` identity race — diagnosed, unfixed | **CRITICAL** |
| 9 | G-11 | BLOCK-01 sample data renders as live freight | **CRITICAL** |
| 10 | G-12 | Fifteen first-start acceptance items `UNVERIFIED` | **CRITICAL** |
| 11 | G-50 | Assistant Plugin Constitution cited by Dispatch, absent from it | **CRITICAL** |
| 12 | G-51 | Directive's Joe verb list contradicts Article II | **CRITICAL** |
| 13 | G-30 | No Sweeper / load board intake | **HIGH** |
| 14 | G-21 | No stop entity; no appointment windows; no stop contacts | **HIGH** |
| 15 | G-60 | Outlook connector `ABSENT` — no calendar, no scheduling read | **HIGH** |
| 16 | G-25 | No closeout workflow joining delivery → invoice → payment | **HIGH** |
| 17 | G-42 | Fourteen repositories, four named, ownership undefined | **HIGH** |
| 18 | G-43 | Constitution v2 / v3 / neither, across three repositories | **HIGH** |
| 19 | G-13 | POD does not leave Dispatch | **HIGH** |
| 20 | G-70 | Publisher queues actions but generates no document | **HIGH** |

---

## PART 2 — Gap Matrix

Severity: **BLOCKER** (no load can complete) · **CRITICAL** (load completes but truth is
unreliable) · **HIGH** · **MEDIUM** · **LOW**.

### Area 1 — Mission Record

| | |
|---|---|
| Implemented | **Nothing.** No Mission Record object, table, or module. |
| Partially implemented | `Load` (`dispatch/models.py:149`) covers a fraction of the concept. |
| Missing | Creation, identity, lifecycle-as-one-object, closeout, archive routing as a mission. |
| Conflicting | Two lifecycle engines — G-04. |
| Unknown | Whether a Mission Record specification exists in any repository. None found in Dispatch, Jules, Claude-3 or Joe. |

**G-01 · No Mission Record entity — BLOCKER**
*Location:* absent; nearest is `dispatch/models.py:149` `class Load`.
*Evidence:* `grep -rniE "class .*Mission|mission_record|mission_id" dispatch/ portal/` → 0
results. 75 occurrences of "mission", all prose or "Mission Visibility".
*Impact:* every document describing mission flow describes something that does not exist. A
builder reading the architecture and then the code cannot reconcile them.
*Action:* Mike rules whether `Load` is renamed and extended into the Mission Record, or a
new object wraps it. **Do not build both.**

**G-02 · Load identifier is not human-usable — BLOCKER**
*Location:* `dispatch/models.py:19-22`, `:168-169`.
*Evidence:* `_gen_id("LOAD")` → `f"{prefix}-{stamp}-{short}"` = `LOAD-20260904-A3F91B2C`.
*Impact:* it satisfies uniqueness and fails the 70 MPH test completely. A driver cannot say
it, a broker cannot read it back, a dock cannot match on it. Directive rule 3 — "load number
immediately visible" — cannot be met by this field.
*Action:* add a short sequential operational number. The existing `load_id` stays as the
internal key; it is sound as one.

**G-03 · No broker load number — BLOCKER**
*Location:* absent from `dispatch/models.py`, `dispatch/store.py` schema.
*Evidence:* `grep -rnoE "(reference_number|ref_number|po_number|pickup_number|pro_number|bol_number)"` across `dispatch/` and `portal/` → **0 matches**.
*Impact:* directive Rule 1 ("if a broker provides a load number, use it") **cannot be
implemented**. There is nowhere to put it. Every broker call is answered by reading an
internal UUID.
*Action:* `broker_load_number` field, optional, unconstrained. Schema + migration + display.

**G-04 · Two lifecycle systems coexist — CRITICAL**
*Location:* `dispatch/models.py:25` (`LOAD_STATUSES`, 11 values) vs
`dispatch/spine/state.py:19` (`ALLOWED_TRANSITIONS`, 25 states).
*Evidence:* freight statuses are `created → dispatched → at_pickup → loaded → in_transit →
delivered → completed → invoiced → paid → archived / cancelled`. The Spine's are
`CREATED → VALIDATION_PENDING → … → ROUTED_TO_* → ARCHIVED`. **`apply_transition()` is
called from exactly one place outside the Spine: `dispatch/opportunities.py:180`.** No
freight path calls it.
*Impact:* `CLAUDE.md` §5.1 states the Spine "owns load lifecycle state". For freight loads
it does not. The doctrine and the code use "load" to mean different things.
*Action:* report to Mike as a doctrine conflict (already open in
`COMPLETION_BLUEPRINT_v2.md` Stage 2). Either the Spine takes freight lifecycle, or §5.1 is
amended to say "work item". **Not a refactor to start without a ruling.**

**G-05 · `ROUTED_TO_MANAGER` persists under a No-Manager rule — MEDIUM**
*Location:* `dispatch/spine/state.py:34`.
*Evidence:* the state exists in the transition table; `CLAUDE.md` §5.6 forbids referencing a
Manager component.
*Impact:* a legacy name in the audit trail. Renaming rewrites history.
*Action:* three options already recorded in `docs/architecture/DISPATCH_ARCHITECTURE.md`
§7.1. Awaiting Mike.

### Area 2 — Driver Portal

**Existing routes** — `portal/routes/driver_portal.py`, 8 routes, 448 lines:
`/driver/login` · `/driver/logout` · `/driver/forgot-pin` · `/driver/home` ·
`/driver/loads/<id>/milestone` · `/driver/loads/<id>/pod` ·
`/driver/loads/<id>/exception` · `/driver/fuel-receipt`

**Existing capabilities:** phone + PIN authentication with lockout
(`portal/models/driver_pin_registry.py`), PIN reset with recovery word, a card per active
load showing COMI status, Route Risk, broker contact, Mission Visibility and Publisher
status, one-tap milestone progression, POD photo upload, typed exception logging, fuel
receipt capture with truck selection, and a driver pay summary.

**Proven capabilities: none.** No driver account has ever been created outside tests.

| | |
|---|---|
| Unproven | Every route above. |
| Missing | Share-status to customer · delay declaration with ETA · arrive/depart stamps · document filing beyond local storage · any offline behaviour · any mobile-specific layout verification |

**G-10 · No driver has ever used it — BLOCKER**
*Evidence:* `docs/readiness/OPERATIONAL_PROOF.md`; zero loads exist.
*Impact:* 448 lines of authentication, IDOR protection and upload handling are
`UNVERIFIED`. The suite found none of the four defects that actually blocked Mike.
*Action:* create one driver, one load, and walk it. This is the highest-information action
available and costs an afternoon.

**G-11 · Sample data renders as live freight — CRITICAL**
*Location:* `portal/sample_dispatch_data/`, `/home`.
*Evidence:* four `sandbox.json` entries render as cards with lane, rate and broker while
`ACTIVE LOADS` reads 0. No sample marker exists anywhere in the codebase.
*Impact:* violates `CLAUDE.md` §6 — *never represent sample data as live data*. Was blueprint
RUN-06, written months ago, never implemented.
*Action:* **Mike's decision first** — label them, or clear them.

**G-12 · Fifteen acceptance items `UNVERIFIED` — CRITICAL**
*Location:* `docs/readiness/LAUNCHER_PROOF_TEMPLATE.md`.
*Impact:* item 14 — Reset Session refusing while Dispatch is running — is the control that
prevents an orphaned server, and it is untouched. An orphan has already occurred twice.
*Action:* only Mike can produce these. **Fix G-41 first** or the record captures a check that
was skipping.

**G-13 · POD does not leave Dispatch — HIGH**
*Location:* `portal/routes/driver_portal.py:250` → `dispatch_svc.attach_evidence()`.
*Evidence:* stores locally. No Outlook filing, no email, no packet.
*Impact:* the receivable clock is not started by anything. Directive's success path
("POD Uploaded → Invoice Sent") has no implemented link.
*Action:* depends on the System of Record ruling — see G-52.

**G-14 · No delay declaration, no share-status, no arrive/depart — HIGH**
*Evidence:* absent from the 8 routes. `MILESTONE_TYPES` (`models.py:50`) *does* contain
`arrived_pickup`, `departed_pickup`, `arrived_delivery` — so the vocabulary exists and the
driver-facing control does not.
*Action:* these are the Phase 2 candidates. Sequence them from what a real load exposes.

**G-15 · Mobile usability `UNKNOWN` — HIGH**
*Evidence:* `driver_home.html` is standalone with its own `<style>`; no device testing
recorded anywhere.
*Action:* verify on the phone during the first real load, not before.

### Area 3 — Dispatch Core

**G-20 · No load has ever been created in operation — BLOCKER**
*Location:* `dispatch/services.py:117` `create_load()`, reachable at
`POST /api/dispatch/loads` (`portal/routes/dispatch_api.py:112`).
*Evidence:* the path exists and is tested. Zero loads on Mike's machine.
*Action:* Phase 1. Manual entry is the **only** available creation path — see G-30.

**G-21 · No stop entity — HIGH**
*Location:* `dispatch/models.py:149`.
*Evidence:* `Load` carries flat `pickup_location` / `delivery_location` /
`pickup_datetime` / `delivery_datetime`. No stop list, no per-stop contact, no appointment
window, no special instructions field.
*Impact:* multi-stop loads cannot be represented. Appointment times cannot be shown to a
driver because they are not stored.
*Action:* defer until a real load demands it. **Do not build speculatively.**

**G-22 · `create_load()` accepts no identity fields — HIGH**
*Location:* `dispatch/services.py:117-130` — twelve parameters, none of them a reference
number.
*Action:* follows G-02 / G-03.

**G-23 · Scheduling exists only as a capacity view — MEDIUM**
*Location:* `portal/routes/pages.py:310` `/calendar` → `get_load_calendar(year, month)`.
*Evidence:* renders from `loads`. No external calendar, no Outlook read.
*Note:* this is **correct** per `CLAUDE.md` §5.5 — the calendar presents, it does not own
scheduling. Recorded as a gap only against the target architecture, not against doctrine.

**G-24 · Load templates exist — no gap** — `services.py:2024`
`create_load_from_template()`. Working, useful for repeat lanes.

**G-25 · No closeout workflow — HIGH**
*Evidence:* the pieces exist separately — `archive_load()` (`services.py:874`),
`create_settlement()` (`:1155`), `list_uninvoiced_loads()` (`:2095`),
`notify_invoice_created()` (`notifications.py:380`). **Nothing joins delivered → invoiced →
paid → archived as one guarded sequence.**
*Impact:* the last third of the directive's success path is four unconnected functions.
*Action:* Phase 1 will expose the real sequence. Build it from that, not from a diagram.

### Area 4 — Publisher

| | |
|---|---|
| Exists | Action queue with typed manifests, human approval gate, govcon draft trigger |
| Partial | Freight packet definitions — the manifests name the contents but nothing assembles them |
| Missing | Document generation, POD packages, invoice packages, carrier packets, broker communications |

**G-70 · Publisher queues actions but produces no document — HIGH**
*Location:* `portal/models/publisher.py:85` `_manifest_for()`, `:95` `create_action()`.
*Evidence:* manifests exist for `Broker Packet` (`["Business Card", "W-9", "Insurance",
"Authority", "Rate Sheet", "Terms"]`), `Direct Shipper`, `Rate Confirmation`, and
`POD/BOL Document Package Draft`. `create_action()` writes a JSON record with
`human_approval_required: True`. **No `render_template`, no PDF, no assembly.** The module
docstring says "Publisher produces documents from approved inputs only" — it currently
produces a to-do.
*Impact:* every packet is assembled by hand.
*Action:* one real packet, produced during the first load, defines the format.

**G-71 · One document does render — no gap**
`portal/routes/pages.py:223` `rate_confirmation_print()` →
`rate_confirmation_print.html`. This is the only real document generation in the system and
is the natural pattern to extend.

**G-72 · Publisher is JSON-file-backed, not SQLite — MEDIUM**
*Location:* `publisher.py:63` `_publisher_path()`, `:69` `_load()`, `:76` `_save()`.
*Impact:* the freight core is SQLite with WAL and enforced foreign keys; Publisher, Library,
Archive and Intelligence are JSON files. Two storage models, different durability.
*Note:* consistent with THE MIKE RULE (§5.7) — standalone subsystems are deliberate. Recorded
as a fact, **not** a recommendation to unify.

### Area 5 — Library

| | |
|---|---|
| Exists | Sectioned record store, add/update/delete, approval workflow (`review_candidate`), company asset tracking, Publisher trigger on approval |
| Partial | Metadata (name + content + section only) |
| Missing | Versioning, retrieval by anything but section, routing rules, reusable component model |

**G-80 · No versioning — MEDIUM**
*Location:* `portal/models/library.py:193` `update_record()` — overwrites in place.
*Impact:* an approved asset replaced by a newer one leaves no trace of the old.
*Action:* matters when a real packet cites a specific insurance certificate. Not before.

**G-81 · `get_missing_company_assets()` exists and is useful — no gap**
`library.py:236`. Reports what a packet cannot yet be built from. Already the right shape.

### Area 6 — COMI

**G-90 · COMI is a routing evaluator, not a communications system — HIGH**
*Location:* `dispatch/comi_routing.py` — three functions total:
`sanitize_payload_for_role()`, `evaluate_comi_routing()`, `_utc_now()`.
*Evidence:* 78 statements, 65% covered — the lowest of any module in the freight core.
*Present:* stakeholder role sanitisation, routing evaluation, a
`mission_visibility_update_required` flag.
*Missing:* event detection, communication generation, delivery tracking, return-message
handling, mission linking.
*Impact:* the driver card shows `comi_status` (`driver_portal.py:114`), so the driver sees a
COMI state that is decided by one evaluator and never becomes a message.
*Action:* define what COMI *is* before extending it. The name currently covers a design that
is not written down in any repository inspected.

### Area 7 — Archive

| | |
|---|---|
| Exists | Sectioned archive, `create_record`, three inbound paths (`archive_from_sandbox`, `archive_publisher_action`, `archive_from_intelligence`), age-based review queue |
| Partial | Retrieval — by section only |
| Missing | Mission archival as a unit, search, history reconstruction, retention policy |

**G-100 · No mission archival — HIGH**
*Evidence:* `archive_load()` (`services.py:874`) sets a load's status. The Archive model
(`portal/models/archive.py`) has **no load or mission inbound path** — its three entry points
are sandbox, publisher and intelligence.
*Impact:* archiving a load and archiving *to* the Archive are unrelated operations that share
a word.
*Action:* resolve as part of G-25 closeout.

**G-101 · No search — MEDIUM** · `archive.py:92` `get_section()` is the only retrieval.

**G-102 · Audit trail is partial — MEDIUM**
*Evidence:* Spine events are recorded for work items; `LoadActivity` (`models.py:654`)
records load comments. There is no single reconstructable history for one load across both.

### Area 8 — JOE

**JOE does not exist in the Dispatch repository.** It is a separate program:
`jax1313-outlook/Joe-Assistant`, 342 tracked files, 135 Python files, `main` at `4a9a6a3`
(2026-08-28), 36 commits.

**Structure:** `ASST/1..6` — six numbered, independently built modules, each with its own
Architecture, Constitution, Context, Operator Guide, Source, Tests and BUILD_REPORT.
`Assistant_Plugin/` — 161 files including `adapters/` (`claude_provider.py`,
`dispatch_port.py`, `library_fs.py`) and `contracts/`.

**G-50 · The Assistant Plugin Constitution governs Dispatch behaviour and is absent from Dispatch — CRITICAL**
*Location:* `jax1313-outlook/Joe-Assistant/ASSISTANT_PLUGIN_CONSTITUTION_v1/02_CONSTITUTION_v1.md`.
*Evidence:* Dispatch cites it twice — `DECISION_LOG.md:1099` ("Article II of the Assistant
Plugin Constitution has eight permitted functions and transmission is not one of them") and
`docs/governance/DISPATCH_AUTHORITY_AND_BOUNDARIES.md:99`. **The document exists in no
repository attached to a Dispatch build session.**
*Impact:* this is the directive's problem statement, evidenced. A builder in Dispatch reads a
binding constraint and cannot read the constraint.
*Action:* Dispatch carries a pointer file naming the repository, path and commit — the pattern
already in use for `DISPATCH_IMPLEMENTATION_STATUS.md`. **Not a copy.**

**G-51 · The directive's Joe verb list contradicts Article II — CRITICAL**
*Evidence:* Article II's eight permitted functions are **Research, Retrieve, Summarize,
Explain, Draft, Recommend, Monitor, Remember**, with §2.1: *"These eight are the whole list.
A proposed capability that is not one of these eight is not Assistant work until Mike Zachary
says otherwise in writing."*
The directive states Joe may **Analyze, Recommend, Draft, Gather, Route, Prepare**.
**`Route` and `Prepare` are not among the eight.** "Route" is the closest of all of them to an
operational action, and Article III prohibits the Assistant from triggering one.
*Impact:* two authority documents disagree about what Joe may do.
*Action:* **Mike rules.** Either the directive's list is loose phrasing, or it is an amendment
to Article II — and §2.1 requires that in writing.

**G-52 · Dispatch–Joe integration is one adapter file — HIGH**
*Location:* `Assistant_Plugin/adapters/dispatch_port.py`.
*Evidence:* no Python file in the Dispatch repository imports anything from Joe; the coupling
is entirely on Joe's side.
*Note:* this is **correct** under `CLAUDE.md` §5.4 — plug-in separation, no direct Dispatch
write authority to Assistant. Recorded so it is not mistaken for a gap.

**G-53 · Joe carries its own Dispatch doctrine set — HIGH**
*Evidence:* Joe holds `DISPATCH_CONSTITUTION_v2.md` (267 lines),
`DISPATCH_CONTEXT_MASTER_v2.md`, `DISPATCH_AGENT_GOVERNANCE_LAW_v1.md`,
`02_DISPATCH_AGENT_GOVERNANCE_LAW.md` through `08_DISPATCH_BUILD_VALIDATION_STANDARD.md`,
and `DISPATCH_OPERATIONAL_READINESS_MISSION.md`.
*Impact:* Joe's `DISPATCH_CONTEXT_MASTER_v2.md` §1 instructs a builder to load
`DISPATCH_CONSTITUTION_v2.md` first. Dispatch's own `CLAUDE.md` says read `CLAUDE.md` first.
**Two repositories give a builder different first instructions for the same program.**
*Action:* G-43.

### Area 9 — Operational Intelligence

| Capability | Status | Evidence |
|---|---|---|
| Route Risk | `CONFIGURED` when the plug-in is importable, else `ABSENT` | `dispatch/route_risk.py:47-49` |
| Weather | Named in the connector contract; no provider | `connectors/route_risk_connector.py`, `connectors/mock.py` |
| Traffic | Same | same |
| DOT intelligence | **ABSENT** — the only `DOT` hits are unrelated | `services.py`, `sandbox_survey/classifier.py` |
| Law enforcement alerts | **ABSENT** — zero occurrences | — |
| Port intelligence | **ABSENT** — "port" matches are TCP ports and `pickup/delivery` prose | — |
| Operational reporting | Partial — `portal/models/operations_feed.py`, `/operations` screen | 91% covered |
| Stakeholder notifications | Exists, token-gated | `dispatch/notifications.py`, `routes/stakeholder.py` |

**G-110 · Route Risk is the only intelligence with an engine — HIGH**
*Note:* correctly degraded. `dispatch/route_risk.py` returns `_unavailable(load_id)` when the
plug-in is absent rather than failing — this is `CLAUDE.md` §5.4 working as written, and was
a real defect found by a drift test.

**G-111 · Four named intelligence sources do not exist — MEDIUM**
DOT, law enforcement, port and weather are named in architecture documents and have no
implementation, no connector and no provider.
*Action:* leave absent. `UNCONFIGURED` is the honest state and the surfaces say so.

### Area 10 — Outlook Integration

| Concern | Status | Evidence |
|---|---|---|
| Existing integration | **ABSENT** | `dispatch/connectors/outlook_connector.py` declares `ConnectorStatus.ABSENT` |
| Scheduling | **ABSENT** | no Outlook read anywhere; `/calendar` renders from `loads` |
| Communications | **Separate path, exists** | `cin_lite/email_delivery.py:159` `_send_or_write()` |
| Calendar | **ABSENT** | — |
| Notifications | **CONFIGURED-capable, currently UNCONFIGURED** | see G-121 |
| Planned | `UNKNOWN` — no Outlook integration design found in any repository |

**G-60 · Outlook is doctrine's scheduling authority and is not connected — HIGH**
*Evidence:* `CLAUDE.md` §5.5 makes Outlook the single source of scheduling truth. The
connector is `ABSENT`. Dispatch therefore has **no scheduling truth at all**, and the
capacity views compute from `loads`.
*Action:* Outlook is the obvious first connector. The boundary already exists.

**G-121 · Email sends for real, and fails soft — MEDIUM, and a caution**
*Location:* `cin_lite/email_delivery.py:159-183`.
*Evidence:* if `DISPATCH_SMTP_HOST` is set it opens SMTP with STARTTLS and sends. If not set,
**or if delivery raises**, it writes the message to `Archive/Outbox` and returns a string
describing what happened.
*Impact:* the caller receives a status string, not an exception. Nothing in the freight core
treats "written to a file" differently from "sent". A status notification that never left the
building looks, to every calling surface, exactly like one that did.
*Action:* verify each call site surfaces the distinction before any customer-facing
notification is trusted. This is the §3 silent-failure shape at the communications boundary.

### Area 11 — Sweeper

**G-30 · Sweeper does not exist — HIGH**
*Evidence:* no module, class or function named sweeper anywhere. `LOAD_SOURCES`
(`models.py:39`) contains `"dat"` and `"truckstop"` — these are **labels a human selects**,
not intake paths. `load_board_connector.py` declares `SIMULATED` / `UNAVAILABLE` and its
docstring says *"No provider is selected. DAT and TruckSmart are the two named."*
`portal/models/integrations_registry.py:45` lists DAT and TruckSmart as registry entries.
*Impact:* directive Source A (Sweeper-generated) **has no implementation**. Manual entry is
not merely a first-class path — it is the only path.
*Action:* accept manual entry as the Phase 1 path. Defer Sweeper until one load has run.

**G-31 · Opportunity scoring exists and is Spine-connected — no gap**
`dispatch/opportunities.py:180` is the one freight-adjacent caller of
`apply_transition()`. Opportunity advises; the Spine decides. CF-04, working as ruled.

### Area 12 — Repository Governance

**G-42 · Fourteen repositories, four named, ownership undefined — HIGH**
*Evidence:* listed in PART 0. `Publisher`, `Library`, `Route-Risk` and `SAM` exist as
standalone repositories **and** as modules inside Dispatch.
*Impact:* a builder asked to work on Publisher has two places to go and no rule for choosing.
*Action:* Mike states, per repository: canonical, historical, or superseded. One line each.

**G-43 · Three constitution states across four repositories — HIGH**
*Evidence:*

| Repository | Constitution | Lines |
|---|---|---|
| Joe-Assistant | `DISPATCH_CONSTITUTION_v2.md` | 267 |
| Jules | `DISPATCH_CONSTITUTION_v3.md` | 572 |
| Claude-3 | `DISPATCH_CONSTITUTION_v3.md` | 572 (byte-identical to Jules) |
| Dispatch | **neither** | — |

*And* `DISPATCH_CONFLICT_AND_AUTHORITY_REGISTER.md:24` records the v3 stack as **explicitly
NOT ADOPTED**, quoting Mike verbatim. Joe's v2 is a *different document*, not an earlier
draft of v3, and its adoption status is `UNKNOWN`.
*Impact:* four repositories, three answers, and the one running the code has none.
*Action:* Mike rules on v2's status. v3's is already ruled.

**G-44 · The governing instruction sits on an unmerged branch — HIGH**
*Evidence:* the NOT-ADOPTED ruling is sourced to `DISPATCH_DEPLOYMENT_BLUEPRINT.md` §18,
which is **not** in Claude-3's `main`, not in Jules, and not in Dispatch. It is on the
unmerged Claude-3 branch `claude/dispatch-jules-arch-review-i87dru`, line 494, in a section
headed *"Jules Sandbox Discovery Report — NOT AUTHORITATIVE, reference only"*.
*Impact:* a binding ruling is quoted from a non-authoritative section of an unmerged file.
*Action:* land it, or re-record the ruling in `DECISION_LOG.md` where it can be found.

**G-45 · Four-way sync is a drift mechanism — HIGH**
*Evidence:* the directive requires doctrine in Dispatch, Joe-Assistant, Jules and
`D:\Joe-Assistant`, with **no stated precedence and no enforcement**.
*Impact:* four maintained copies with no authority rule is how the current state arose. And
`D:\Joe-Assistant` as a working copy is structurally identical to the three-copies-of-Dispatch
failure that cost seven hours on 2026-08-25.
*Recommended alternative:* **one canonical copy plus pointers.** Dispatch is canonical for
Dispatch doctrine; Joe-Assistant for Assistant doctrine; every other repository carries a
pointer file naming repository, path and the commit hash it was written against. Staleness
becomes visible instead of silent. This pattern is already working — `Jules` and `Claude-3`
each carry `DISPATCH_IMPLEMENTATION_STATUS.md`.

**G-46 · Two named commits and two named files exist nowhere — MEDIUM**
*Evidence:* `d503eda`, `86ef615`, `gateway_health.py` and `test_contract_neutrality.py` were
searched for across Dispatch (166 commits), Jules, Claude-3 and Joe-Assistant (36 commits,
full `main`). **None found.** `contracts/` and `adapters/` **were** found — in
`Joe-Assistant/Assistant_Plugin/`.
*Inference, flagged as such:* they most likely exist only in an unpushed local working copy,
which is precisely the failure the directive describes.
*Action:* if that work matters, push it. It is currently invisible to every builder.

**G-47 · Orphaned files — LOW**
Jules `main` tracks three `__pycache__/*.pyc` files despite a `.gitignore`. No secret content.

### Cross-cutting

**G-40 · The portal cannot report which build it is — CRITICAL**
*Location:* `portal/__init__.py:3` — `__version__ = "0.1.0"`, hardcoded. No UI surface
displays it. Mike's folder is an extracted ZIP, so the launcher reports
`Commit UNVERIFIED — this folder is not a git checkout`.
*Impact:* **this is the question behind both major failures to date** — the seven-hour HTTP
500 (three copies, wrong one running) and the 2026-08-29 orphan (unknown build serving 8080).
*Action:* display commit and folder path in Settings; make Mike's folder a real checkout.

**G-41 · `control.start()` identity race — CRITICAL**
*Location:* `dispatch_launcher/control.py:480`, guard at `:140`.
*Evidence:* `processes.process_facts(child.pid)` is called on the line after
`subprocess.Popen`, before the child has exec'd. Measured: **72 of 300** immediate
observations read an empty `/proc/<pid>/cmdline`. An empty `command_line` makes
`if record.command_line and facts.command_line:` skip silently.
*Impact:* degrades the check that answers *"is the process on port 8080 mine?"* — which is
acceptance item 14.
*Action:* observe after exec or after a bounded retry. **Before G-12.**

**G-48 · `CLAUDE.md` §8 figures are stale — LOW**
Says 3,696 passed / 94.74%. Merged truth is 3,822 / 94.80%.

---

## PART 3 — Implementation Readiness

### Operational Today — works now, observed on the target machine

- Launcher: find, start, PIN creation, sign-in, second-start refusal by process identity,
  Desktop shortcut, browser open, portal render
- `Open Dispatch Portal` second icon
- Crash page naming the fault and the log path
- Portal renders every page tried

### Exists But Unproven — built, never exercised in operation

- **The entire Driver Portal** — 8 routes
- **The entire freight core** — loads, drivers, equipment, capacity, milestones, evidence, POD
- Spine lifecycle engine and transition guard
- IFTA through finalization, exception detection, receipt vision pre-fill
- Backup and restore · CSRF across mutating routes · token expiry and revocation
- Connector boundary, eight connectors
- Rehearsal mode · the twenty-step proof system
- Publisher, Library, Archive, Intelligence queues
- Email delivery via `cin_lite`

### Partially Implemented

| Component | What exists | What does not |
|---|---|---|
| Mission Record | `Load` | identity, mission lifecycle, closeout as one object |
| Publisher | action queue + manifests | document generation |
| COMI | routing evaluator | detection, generation, tracking, return handling |
| Archive | three inbound paths | mission archival, search, retention |
| Library | store + approval | versioning, metadata, routing |
| Closeout | four separate functions | the sequence joining them |
| Operational intelligence | Route Risk | weather, traffic, DOT, law enforcement, port |

### Missing — does not exist

Mission Record · load number (operational) · broker load number · stop entity · appointment
windows · stop contacts · Sweeper / load board intake · Outlook integration of any kind ·
driver share-status · driver delay declaration · arrive/depart stamps · geofencing · document
generation · mission search · build identity display

---

## PART 4 — Drift Analysis

Where doctrine, repository and implementation give three different answers.

**D-1 · "The Spine owns load lifecycle state"**
*Doctrine:* `CLAUDE.md` §5.1. *Repository:* `spine/state.py` — a 25-state governance
lifecycle. *Implementation:* freight loads use an 11-value `loads.status` and never call
`apply_transition()`. **"Load" means two different things.**

**D-2 · "Outlook is the single source of scheduling truth"**
*Doctrine:* `CLAUDE.md` §5.5. *Repository:* `outlook_connector.py` = `ABSENT`.
*Implementation:* `/calendar` renders from `loads`. **Dispatch has no scheduling truth.**

**D-3 · System of Record**
*Doctrine:* `CLAUDE.md` §31/§44 — Dispatch is the System of Record. *Driver Transformation
Roadmap:* "Outlook remains system of record". *Implementation:* POD is stored locally in
Dispatch, so the code agrees with the doctrine and not the roadmap. **Reported, unresolved.**

**D-4 · Joe's permitted functions**
*Constitution:* eight named functions, "these eight are the whole list".
*Directive:* six verbs, two of which are not among the eight. *Implementation:* Joe's
`ASST/1..6` modules. Whether they stay inside the eight is `UNKNOWN` — not inspected.

**D-5 · Which document a builder reads first**
*Dispatch:* `CLAUDE.md` — "this is the first file to read". *Joe:*
`DISPATCH_CONTEXT_MASTER_v2.md` §1 — load `DISPATCH_CONSTITUTION_v2.md` first.
**Same program, two entry points, different doctrine.**

**D-6 · Constitution v3**
*Jules and Claude-3 `main`:* present, byte-identical. *Register:* explicitly NOT ADOPTED.
*Dispatch:* absent. *The ruling itself:* on an unmerged branch, in a section marked NOT
AUTHORITATIVE.

**D-7 · `ROUTED_TO_MANAGER` under a No-Manager rule**
*Doctrine:* §5.6 forbids referencing a Manager. *Implementation:* the state persists in the
transition table and the audit trail.

**D-8 · "Never represent sample data as live data"**
*Doctrine:* §6. *Implementation:* `/home` does exactly that. Known since RUN-06, months ago.

---

## PART 5 — Master Build List

Nothing below is authorized. Mike approves missions individually.

### Blockers — the first real load cannot happen without these

| | | Builder |
|---|---|---|
| **B-1** | G-41 · Fix the `control.start()` identity race | Claude Code |
| **B-2** | G-12 · Record the fifteen acceptance items *(after B-1)* | **Mike only** |
| **B-3** | G-11 · Label or clear the sample data *(decision first)* | Mike decides, Claude Code builds |
| **B-4** | G-02 / G-03 · Operational load number + broker load number | Claude Code |
| **B-5** | G-20 · Create one real load by manual entry | Mike |
| **B-6** | G-10 · Enrol one driver and walk the load end to end | Mike, assisted |

### Critical — truth is unreliable until these are done

| | |
|---|---|
| **C-1** | G-40 · Display commit and folder path; make Mike's folder a real checkout |
| **C-2** | G-01 · Mike rules: is `Load` renamed and extended into the Mission Record, or wrapped? |
| **C-3** | G-04 · Mike rules on the two lifecycles |
| **C-4** | G-50 · Pointer file in Dispatch to the Assistant Plugin Constitution |
| **C-5** | G-51 · Mike rules: is the directive's verb list an Article II amendment? |
| **C-6** | G-121 · Make "written to Outbox" distinguishable from "sent" at every call site |

### High

G-25 closeout sequence · G-60 Outlook as first connector · G-13 POD leaving Dispatch ·
G-70 one real packet · G-42 repository ownership statement · G-43 constitution ruling ·
G-44 land or re-record the NOT-ADOPTED ruling · G-45 replace four-way sync with
canonical-plus-pointers · G-90 define COMI · G-14 driver delay / share-status /
arrive-depart *(from the first load, not before)*

### Medium

G-05 `ROUTED_TO_MANAGER` · G-21 stop entity *(defer until a load demands it)* ·
G-23 scheduling · G-80 Library versioning · G-100 mission archival · G-101 archive search ·
G-102 unified audit trail · G-111 the four absent intelligence sources · G-46 push the
missing work · G-72 storage split *(record only)*

### Low

G-48 `CLAUDE.md` figures · G-47 Jules `.pyc` files · G-15 mobile verification
*(happens during B-6)*

### Explicitly deferred, with reasons

| Deferred | Why |
|---|---|
| Sweeper / load board | No provider. Manual entry is the only live path. |
| Geofencing | Crosses the connector boundary; needs a recorded decision. |
| Multi-stop, appointment windows | No real load has demanded them. |
| Home screen layout (BLOCK-03) | Real use decides what belongs on a second screen. |
| Driver Portal redesign | It is unproven, not missing. Audit it with a real load first. |

---

## Closing

**The ordering that matters:** B-1 through B-6 are one sequence, not six tasks. Fix the
identity check, record the acceptance items against a check that is not skipping, stop the
home screen lying, give a load a number a human can say, create one, and run it. Everything
in Critical and below is better specified after that load than before it.

**On the directive's own instruction — "the goal is not more code":** the largest gaps in
this report are not missing features. They are a missing object (G-01), a missing name
(G-02), a document that governs a repository it does not live in (G-50), and four
repositories that answer the same question differently (G-43). None of those is fixed by
building.

*Repository evidence wins. Where this report and the repository disagree, the repository is
right and this file is stale.*
