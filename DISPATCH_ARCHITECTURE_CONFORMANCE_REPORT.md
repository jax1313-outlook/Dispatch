# DISPATCH_ARCHITECTURE_CONFORMANCE_REPORT

**Phases 3, 4 and 6 — architecture conformance, portal audit, integration audit**
**Audit commit:** `37f4fd033e57c55f46dfd0568d3371e8473d683f`
**Method:** every row below was checked against source. Where a doctrine document could not be read
in the Dispatch repository, that is stated rather than assumed.

---

## 1. Governing-document caveat

Sixteen of the doctrine documents this phase is meant to audit against are **not in the Dispatch
repository** (see the inventory, §2.2). They were read in `/home/user/Jules`, which holds a
byte-identical superset of `/home/user/Claude-3`. Conformance below is measured against those
copies. If a newer version exists on Mike's machine, this report measures against a stale text —
**that risk is a direct consequence of D-3 in the recovery plan and cannot be closed by a builder.**

## 2. Leadership and governance

| Component | Doctrine | Implementation | Tests | Connected | Maturity | Conflicts / dependencies |
|---|---|---|---|---|---|---|
| Manager | YES (`MANAGER.md`, and a second `docs/MANAGER.md` in Dispatch) | Partial — 4 files mention it; no Manager module, no oversight surface | NO | NO | **DOCUMENTATION ONLY** | Two Manager documents in two repositories. Standing bar BM-02 forbids reactivation. Leave dormant. |
| Constitution Guardian | YES | **0 files** | NO | NO | **MISSING** | — |
| Architecture Guardian | YES | **0 files** | NO | NO | **MISSING** | — |
| Drift Guardian | YES | **0 files** | NO | NO | **MISSING** | The absence is self-demonstrating: 718 lines of unwired engine code and a third state model landed on `main` in PR #113 with no drift check. |
| Priority Guardian | YES | **0 files** | NO | NO | **MISSING** | — |
| Human authority control | YES | **YES** — `RESERVED_SYSTEM_IDENTITIES = {"PUBLISHER","SYSTEM","AUTOMATION","INTELLIGENCE","LIBRARY"}` blocks machine approval (`portal/models/library.py:41`, enforced at `:140`) | YES | YES | **PRODUCTION-CAPABLE** | The one governance control that is genuinely enforced in code. |
| Role boundaries | YES | **YES** — three disjoint session namespaces: `session["user_id"]` (Authority), `session["driver_id"]` (Driver), token-only (Stakeholder). Neither session key satisfies the other's gate. | YES | YES | **PRODUCTION-CAPABLE** | — |
| Decision boundaries | YES | Partial — `REQUIRED_CARD_CLOSING` on level ≥3 cards; scoring is advisory | YES | YES | **FUNCTIONAL PROTOTYPE** | No mechanism prevents a future caller from acting on a recommendation. |

## 3. Dispatch Spine

| Component | Doctrine | Implementation | Tests | Connected | Maturity | Conflicts |
|---|---|---|---|---|---|---|
| Current Mission | YES | Partial — `get_mission_visibility()`, `LoadVisibilityRecord`, driver home renders active loads | YES | YES | **PARTIAL** | No concept of *the* current mission; the driver sees a list, not a priority. |
| Current Reality | YES | `loads.status`, 11 values, gated transitions | YES | YES | **PRODUCTION-CAPABLE** | — |
| Possible Future | YES | `dispatch/opportunities.py` — **unwired** | Unit only | **NO** | **STRUCTURAL PROTOTYPE** | See §4. |
| Opportunity lifecycle | YES | `OPPORTUNITY_LIFECYCLE_STAGES` (9 stages) + `ALLOWED_LIFECYCLE_TRANSITIONS` — **unwired** | Unit only | **NO** | **STRUCTURAL PROTOTYPE** | **CONFLICTED — see §4.** |
| State transitions | YES | `_VALID_TRANSITIONS` + `validate_status_transition()`, enforced on both status paths since M1 | YES (28 + 4) | YES | **PRODUCTION-CAPABLE** | — |
| Audit lineage | YES (Spine §8) | `activities` table; `_record_status_change()` on all four status paths since C3 | YES (33) | YES | **FUNCTIONAL PROTOTYPE** | Spine §8 wants structured `previous_state`/`new_state` columns; C3 encodes them in a message string. Known and logged. |
| Event routing | YES (Spine §15) | `comi_routing.py` — role-based fail-closed sanitization | YES | YES | **PRODUCTION-CAPABLE** | — |
| Shared identifiers | YES | Three schemes — `SBX-`, `LOAD-`, `CIN-` — correlated one way via `engine_load_id` | YES | YES | **PARTIAL** | Adjudicated: one retrieval chain, no migration (BM-11). |
| Data ownership | YES | 26 SQLite tables, FK-enforced, WAL | YES | YES | **PRODUCTION-CAPABLE** | **One violation remains:** load status is duplicated into `sandbox.card_data.engine_status` (`portal/models/sandbox.py:231-240`, written from `pages.py:991` and `api.py:509`, read by `dispatch.html:403` and `brief.html:137`). This is corrective mission C1, still open. |
| Intermodule contracts | YES | `route_risk/engine.py` uses injected `store_fn` / `load_events_fn` / `comi_eval_fn` — genuine decoupling, no dual write | YES (20) | YES | **PRODUCTION-CAPABLE** | The best-executed boundary in the program. |

### 3.1 The word "Spine" does not appear in the code

`grep -rn "spine" --include=*.py dispatch portal cin_lite route_risk` returns **zero** matches in the
Dispatch repository. Meanwhile `portal/models/operations_feed.py:32-41` implements Spine §9's Portal
Card taxonomy verbatim — levels 0–5, the exact labels, and the required closing string
character-for-character. **The Spine is implemented and not named.** The only file in the workspace
that names it, `Jules/dispatch_spine.py`, is the in-memory simulation.

## 4. The Dynamic Capacity package — a third state model on `main`

`dispatch/opportunities.py:26-46` defines a nine-stage lifecycle with its own transition table:

```
Discovered → Analyzed → Scored → Filtered → Presented → Selected → Committed
           → Calendar Event → Current Reality
```

`DISPATCH_BUILD_MATRIX_v2` §2 records the standing constraint **BM-10**: *"No mission may merge the
load-status and work-item state models, replace either, or create a third state authority."*

This is a **third state machine**, on `main`, with no `DECISION_LOG.md` entry and no walkthrough
report. It is not yet an *authority* — nothing calls it — which is the only reason this is
CONFLICTED rather than a violation in production. **Disposition: this must be adjudicated by Mike
before anything wires it.** Three outcomes are available: (a) map the stages onto the existing load
status model, (b) adopt it explicitly as the Possible-Future model with a Decision Log entry
amending BM-10, or (c) revert it. This audit recommends (a) or (b), not (c) — the modelling work is
sound; only its governance is missing.

**Wiring status, proven:** grep for each of the three module names across all `.py` and `.html`,
excluding `tests/` and the modules themselves, returns two lines, both inside `opportunities.py`.
There is no table, no route, no template, no service call. **STRUCTURAL PROTOTYPE.**

## 5. Operational departments and layers

| Component | Doctrine | Impl | Tests | Connected | Maturity | Note |
|---|---|---|---|---|---|---|
| Dispatcher | YES | YES | YES | YES | PRODUCTION-CAPABLE | 146 API routes over the load lifecycle |
| Intelligence collection | YES | YES (`cin_lite/acquisition.py`, SAM.gov) | YES | YES | FUNCTIONAL PROTOTYPE | Live only with `DISPATCH_SAM_API_KEY`; falls back to sample data |
| Intelligence Analyst | YES | YES (`cin_lite/rules/`, 9 deterministic rules) | YES (17) | YES | PRODUCTION-CAPABLE | Determinism is asserted by test |
| Scheduler | YES | **NO** — the only occurrence of the word in production code is a comment in `capacity.py:12` | NO | NO | **MISSING** | Blocked on the Outlook integration decision |
| Score | YES | YES (`dispatch/scoring.py`) | YES (43) | YES | PRODUCTION-CAPABLE | Advisory only; does not decide or book |
| Filters | YES | Partial | YES | YES | PARTIAL | Search/filter exists on pages; no opportunity filter stage |
| Routing | YES | YES (`comi_routing.py`) | YES | YES | PRODUCTION-CAPABLE | Fail-closed |
| Route Risk | YES | YES (`route_risk/` + SQLite persistence) | YES (20) | YES | PRODUCTION-CAPABLE **with no live feeds** | Honest: every event carries `is_live_data: False` |
| Dynamic Capacity | YES (new doc) | Unwired | Unit only | **NO** | STRUCTURAL PROTOTYPE | §4 |
| Truck Arrangement | YES (new doc) | Unwired | Unit only | **NO** | STRUCTURAL PROTOTYPE | §4 |
| Stop Sequence | YES | `StopSequenceCapacity` dataclass only — a stop *count*, not a sequence | Unit only | **NO** | STRUCTURAL PROTOTYPE | No stop records exist in the schema |
| Pricing | Partial | `confirm_rate`, expenses, settlements | YES (54+) | YES | PRODUCTION-CAPABLE | Records prices; does not propose them |
| Revenue Projection | YES | **NO** | NO | NO | **MISSING** | `profitability` reports history, not projection |
| Manager | YES | Dormant | NO | NO | DOCUMENTATION ONLY | BM-02 |
| Librarian | YES | **0 files** | NO | NO | **MISSING** | The *Library* exists; the *Librarian* role does not |
| Company Library | YES | YES (`portal/models/library.py`, 6 sections) | YES | YES | PRODUCTION-CAPABLE | Machine approval blocked |
| Intelligence Library | YES | YES (`portal/models/intelligence.py`) | YES | YES | PRODUCTION-CAPABLE | — |
| Publisher Library | YES | YES (`portal/models/publisher.py`) | YES | YES | PRODUCTION-CAPABLE | — |
| Workspace | YES | Partial — `sandbox.py` + `Current Workspace` folder | YES | YES | PARTIAL | Holds the C1 duplicate-status defect |
| Archive | YES | YES (`cin_lite/archive.py` with SHA-256 sidecars and fail-closed integrity verification; `portal/models/archive.py`) | YES (26) | YES | PRODUCTION-CAPABLE | No retention policy is implemented; nothing can be purged |
| Publisher | YES | YES | YES | YES | PRODUCTION-CAPABLE | — |
| COMI | YES | YES | YES | YES | PRODUCTION-CAPABLE | The COMI context document is absent from every repository |
| Email Helper boundary | YES | YES — `dispatch/email_helper.py` deliberately inlines the atomic-write pattern rather than importing from `portal`, preserving THE MIKE RULE | YES (21) | YES | PRODUCTION-CAPABLE | — |

## 6. Portal audit

### 6.1 Driver Portal — 4 routes (`portal/routes/driver_portal.py`, 132 lines)

Reads **real backend state**, not fixtures: `dispatch_svc.list_loads(driver_id=…)`,
`get_comi_status()`, `route_risk_model.get_route_risk()`, `get_mission_visibility()`,
`get_publisher_status()`, `get_load_contacts()`.

| Capability the mission asks about | Status | Evidence |
|---|---|---|
| Current Mission priority | **PARTIAL** | Renders *all* active loads as equal cards; no priority concept — `driver_home.html` iterates `load_cards` |
| Immediate operational retrieval | **PARTIAL** | Pickup/delivery/customer/next-expected are shown; nothing is searchable |
| Pickup and delivery information | **PROVEN** | `driver_home.html` rows 1–3 |
| Mission inquiry | **MISSING** | No inquiry control on the page |
| Load search | **MISSING** | `/search` exists but is on `pages_bp`, behind the **Authority** gate. The Driver Portal has no route to it. |
| Proof of pickup | **MISSING** | No upload control |
| Proof of delivery | **MISSING** | No upload control |
| Photo evidence | **MISSING** | Evidence upload exists in `dispatch_api` — Authority-gated only |
| Routing information | **PARTIAL** | Route Risk summary text only |
| Stop sequence | **MISSING** | No stop records exist |
| Truck arrangement | **MISSING** | Unwired module |
| Schedule visibility | **MISSING** | No calendar or schedule on the driver surface |
| 70 MPH phone-call usability | **PARTIAL** | Single-column, large type, no JS, dispatch and broker phone numbers at the top — good. But the page has **exactly one interactive control: Sign Out.** A driver cannot report anything. |
| Reduced cognitive load | **PROVEN (by omission)** | Deliberately minimal, and documented as such |

**Verdict: a read-only status board.** Every write path a driver needs — POD, photos, milestone
reporting — is behind the Authority gate. Under Driver-First Doctrine this is the single largest
functional gap in the program.

### 6.2 Operations Portal — 32 page routes + 146 API routes

| Capability | Status | Evidence |
|---|---|---|
| Current missions | **PROVEN** | `/dispatch`, `/operations` read live SQLite |
| Opportunity cards | **PARTIAL** | `operations_feed.py` normalizes seven real subsystems into one card shape; the *freight* Opportunity Card is the unwired module |
| Operational alerts | **PROVEN** | Exceptions, stalled loads, conflicts, maintenance, compliance |
| Scheduling visibility | **PLACEHOLDER** | `/calendar` renders a month grid from Dispatch's own load records — corrective mission **C2a**, still open, still in the main navigation |
| Scoring and filtering | **PROVEN** | `scoring.py` + page filters |
| Human decision routing | **PROVEN** | `/api/action`, decision endpoints, `REQUIRED_CARD_CLOSING` |
| Capacity visibility | **MISSING** | Blocked on Reserve Capacity Doctrine |
| Mission status | **PROVEN** | Status stepper, timeline, activities |
| Work queues | **PROVEN** | `/queues`, `/pipeline` |
| Actionable exceptions | **PROVEN** | `/exceptions` + resolve endpoints |
| Manager oversight | **MISSING** | Manager is dormant |

### 6.3 Stakeholder Portal — 2 routes

| Capability | Status | Evidence |
|---|---|---|
| Controlled mission visibility | **PROVEN** | `services.build_stakeholder_view()` withholds internal economics |
| Stakeholder-specific views | **PARTIAL** | One view for all external parties; no per-role shaping |
| Reference-based access | **PROVEN** | `?token=` HMAC-SHA256 |
| Shipper/broker/customer context | **PARTIAL** | D11's four-party chain is documented, not modelled in data |
| Proof artifacts | **PROVEN** | Token-scoped evidence download with a mandatory IDOR check; a mismatched `load_id` returns a flat 404, never 403 |
| Current status | **PROVEN** | — |
| Privacy and authorization boundaries | **PARTIAL** | Correct in shape; **the token never expires and cannot be revoked** — see the security report, finding S-2 |
| Non-disclosure of internal information | **PROVEN** | 33 tests across two files |

### 6.4 Route and endpoint classification — 218 routes

| Classification | Count | Basis |
|---|---|---|
| Working (reads or writes real backend state) | **214** | All 146 `dispatch_api`, 24 `api`, 7 `pipeline`, 4 `driver_portal`, 2 `auth`, 2 `stakeholder`, 1 `decisions` route, and 28 of 32 `pages` routes |
| Working with static or sample data | **3** | `pages./sam` and the two SAM-fed pipeline listing routes when `DISPATCH_SAM_API_KEY` is unset; `dispatch/acquisition.py` likewise serves two tracked sample JSON files when `DISPATCH_LOAD_SOURCE` is unset |
| Partially wired | **1** | `pages./calendar` — renders real loads inside a construct doctrine forbids (corrective mission C2a) |
| Not wired | 0 | — |
| Broken | 0 | Full suite green; no route raised in 2,817 tests |
| Unknown | 0 | — |
| **Total** | **218** | |

**Security overlay (not a separate count).** Authentication is implemented on every route.
**Cross-site request protection is implemented on none of them** — `grep -rniE "csrf"` across
`portal/` returns zero matches, while **109 of the 218 routes** accept `POST`, `PATCH`, `PUT` or `DELETE` under
cookie session authentication. See finding **S-4**.

A `200` was not accepted as proof anywhere in this table: each "Working" row was checked to a service
call that reads or writes SQLite or a JSON store.

## 7. Integration audit

| Integration | Classification | Evidence |
|---|---|---|
| **Outlook calendar** | **NOT PRESENT** | `grep -riE "graph\.microsoft\|outlook\|ews\|icalendar\|\.ics"` across all production code returns **one** match: a consumer-domain string in `cin_lite/rules/vendor_network.py:41`. There is no Outlook code of any kind. |
| **Outlook email** | **NOT PRESENT** | Same. Mail leaves via generic SMTP, not Outlook. |
| Load boards (generic) | **STUBBED** | `dispatch/acquisition.py` — `DISPATCH_LOAD_API_URL` documented as "future"; default source is a local sample directory |
| DAT | **NOT PRESENT** | A name in the integrations registry's type list only |
| TruckSmarter | **NOT PRESENT** | Same |
| ELD / HOS | **NOT PRESENT** | No ELD code. `dispatch/capacity.py:250` nonetheless defaults `set_verified_hos(source="ELD_LOG")` — see the operational-truth section of the main audit |
| GPS / location | **NOT PRESENT** | `PositionCapacity` has lat/lon fields; nothing populates them |
| Routing services | **NOT PRESENT** | Distances are entered, not computed |
| Weather | **NOT PRESENT** | Route Risk states this itself: *"Live weather/traffic API integrations are not connected"* (`route_risk/engine.py:132-145`) |
| Traffic | **NOT PRESENT** | Same |
| DOT / restriction intelligence | **NOT PRESENT** | — |
| Map visuals | **PLACEHOLDER** | `route_risk/engine.py:83-87` emits `map_visual_placeholder` with `placeholder_type: "embedded_corridor_map_placeholder"` and `available: has_map_visual`, which **defaults to `True`** |
| File storage | **LIVE (local)** | Local filesystem; extension allowlist + 25 MB cap; filenames regenerated as `{evidence_id}.{ext}` |
| GitHub | **LIVE** | CI on push/PR, py3.11/3.12/3.13 |
| SAM.gov API | **IMPLEMENTED BUT UNCONFIGURED** | Real `urllib` calls at `cin_lite/acquisition.py:67,147`; falls back to local sample data without a key |
| SMTP | **IMPLEMENTED BUT UNCONFIGURED** | Real `smtplib` at `cin_lite/email_delivery.py:106`; writes `.eml` to `Archive/Outbox` when `DISPATCH_SMTP_HOST` is unset |
| Anthropic / Claude API | **IMPLEMENTED BUT UNCONFIGURED** | Deterministic fallback without `ANTHROPIC_API_KEY` |
| Authentication | **LIVE** | scrypt-hashed PINs via `werkzeug.security`; lockout; fail-closed app-level gate |
| Notifications | **IMPLEMENTED BUT UNCONFIGURED** | Rides on SMTP |
| Accounting | **STUBBED** | CSV export only; the registry entry is a credential container that nothing reads |

**Live integrations: three — GitHub, the local filesystem, and the authentication stack.**
Everything an operating freight business would call an integration is absent or unconfigured.
