# DISPATCH_WHOLE_PROGRAM_AUDIT

**Whole-program audit, recovery, and completion blueprint — master document**
**Audit commit:** `37f4fd033e57c55f46dfd0568d3371e8473d683f` (origin/main, clean tree)
**Date:** 2026-08-23
**Authority:** Mike Zachary is final authority. This document recommends. It changes nothing.

**Companion deliverables:** `DISPATCH_CURRENT_STATE_INVENTORY.md` ·
`DISPATCH_ARTIFACT_AND_REPOSITORY_RECOVERY_PLAN.md` ·
`DISPATCH_ARCHITECTURE_CONFORMANCE_REPORT.md` · `DISPATCH_TEST_TRUTH_REPORT.md` ·
`DISPATCH_SECURITY_AND_RUNTIME_REPORT.md` · `DISPATCH_RETAIN_REPAIR_REPLACE_REMOVE_MATRIX.md` ·
`DISPATCH_WORKABLE_PRODUCT_DEFINITION.md` · `DISPATCH_COMPLETION_BLUEPRINT.md` ·
`DISPATCH_BUILD_MATRIX.md` · `DISPATCH_AUDIT_EVIDENCE_MANIFEST.txt`

---

## 0. Two corrections to the mission's premises, stated before anything else

**`/app` does not exist in this environment.** The mission directs inspection of the `/app`
workspace. `ls /app` → `No such file or directory`. `/app` was the *Jules builder's* container —
proven by `Jules/flask_app.log`, a committed file, containing `* Detected change in '/app/app.py'`.
It is gone. Every claim in this audit is grounded in `/home/user/Dispatch`, `/home/user/Jules` and
`/home/user/Claude-3`, all three of which are real, cloned, and at known commits.

**Mike's `D:` drive was not updated, and cannot be reached from here.** This is a Linux container.
`mount` shows no Windows filesystem of any kind — no drvfs, no CIFS, no `/mnt/d`. **No file was
written to `D:\Dispatch Operations`, `D:\Archive`, `D:\Memory` or `D:\SANDBOX\Jules` by anything
visible from this session.** `bootstrap_d_drive.py` (PR #115) declares those paths as defaults; its
four tests copy between Linux temporary directories. The utility is plausible and **unproven against
its actual target.**

---

## PHASE 8 — Operational truth audit

The question for each item: is the value **calculated**, **verified from a trusted source**, or
**merely a default that arrived optimistic**?

### 8.1 Confirmed optimistic defaults

| # | Location | Value | Calculated? | Verified? | Default? | Can be returned without evidence? | Can affect Score / Scheduler / Pricing / Routing / a human decision? |
|---|---|---|---|---|---|---|---|
| **OT-1** | `dispatch/capacity.py:155` | `stacking_policy = "STACKABLE"` | No | No | **Yes** | **Yes** | Would reach capacity and scheduling **once wired**. Not wired today. |
| **OT-2** | `dispatch/capacity.py:156` | `allows_top_load = True` | No | No | **Yes** | **Yes** | Same |
| **OT-3** | `dispatch/truck_arrangement.py:43` | `is_stackable = True` | No | No | **Yes** | **Yes** | Same |
| **OT-4** | `dispatch/capacity.py:216` | `apply_asset_profile(verified_by="Mike Zachary")` **and** `configuration_status="VERIFIED"` unconditionally | No | **No — and it attributes the verification to Mike by default** | **Yes** | **Yes** | **This is the most serious item in this phase.** Any caller — including an automated one — stamps a capacity profile as VERIFIED BY MIKE without Mike doing anything. It is a false human attribution, produced by a default argument. |
| **OT-5** | `dispatch/capacity.py:244` | `set_verified_hos(source="ELD_LOG")`, sets `hos_status="VERIFIED"`, `confidence="HIGH"` | No | **No — no ELD integration exists anywhere in the program** | **Yes** | **Yes** | Declares ELD-verified hours of service with no ELD. |
| **OT-6** | `dispatch/capacity.py:338` | `can_accommodate` returns feasible when every reason is a `NEEDS_REVIEW` containing "stale" — which includes **`"Asset configuration status is STALE"`**, not only the intended stale-HOS-under-simulation case | Partly | No | — | **Yes** | A stale asset configuration reports **feasible**. This is precisely "unknown becomes feasible". |
| **OT-7** | `route_risk/engine.py:144` | With no events recorded: `available: False` **and** `delivery_commitment_status: "achievable"` | No | No | **Yes** | **Yes** | Renders on the Driver Portal. An absence of information is reported as a positive commitment. |
| **OT-8** | `route_risk/engine.py:32`, `dispatch/services.py:371` | `has_map_visual = True` → `map_visual_placeholder.available = True` | No | No | **Yes** | **Yes** | A placeholder reports itself as an available map visual. |
| **OT-9** | `dispatch/acquisition.py:47` | Source defaults to the bundled sample directory | n/a | No | **Yes** | **Yes** | **Sample loads enter the system unlabelled** and are scored like real ones. |
| **OT-10** | `Jules/app.py:148-167` | POD upload returns `"status": "success"`, `"message": "POD uploaded successfully"`, `pod_status = "UPLOADED"` **with no file posted** — `"file_saved": "Simulated upload"` | No | **No** | — | **Yes** | **A false operational record of delivery evidence.** If Jules is what is running, this is the worst finding in the program. |

### 8.2 Where "unknown becomes feasible", enumerated

| Transition the mission asks about | Instance |
|---|---|
| Unknown → feasible | OT-6 (stale configuration → feasible); OT-7 (no data → "achievable") |
| Not evaluated → verified | OT-4 (`VERIFIED` + `verified_by="Mike Zachary"` on construction); OT-5 (`hos_status="VERIFIED"` with no ELD) |
| Possible Future → Current Reality | **None found in the running system.** `dispatch/opportunities.py` defines a `Committed → Calendar Event → Current Reality` path, but nothing calls it. The separation currently holds by virtue of the module being unwired. |
| A simulated fact appears operational | OT-10 (Jules POD); OT-8 (map placeholder); OT-3 (default stackability) |
| A stored field treated as calculated intelligence | OT-1, OT-2, OT-3 — these are stored dataclass fields that read as engineering determinations |

### 8.3 What the program gets right here — recorded, because it is the counter-example

- Every Route Risk event carries `is_live_data: False`, **always**, and `dispatch/store.py:2164`
  documents that it is deliberately never stored as a value that could drift true.
- The no-data Route Risk summary says so in words: *"Live weather/traffic API integrations are not
  connected; any risk events are internal/manual entries."*
- The PR #114 hardening added genuine `NEEDS_REVIEW` and `INSUFFICIENT_DATA` paths to
  `can_accommodate` — unconfigured assets and unknown HOS now refuse. **The direction of that work
  was right.** OT-1 through OT-6 are what it did not finish.
- `dispatch/scoring.py` is deterministic and advisory: it recommends and does not decide.
- COMI sanitization is fail-closed by recipient role.

**The pattern across OT-1 … OT-8 is one habit: a dataclass field that should mean "nobody has told
me yet" was given the most convenient value instead of the most honest one.** The fix is uniform —
default to `UNKNOWN`, require an explicit source, and never default a human's name into a
verification field.

---

## PHASE 10 — Whole-program maturity map

No percentages. No "approximately complete".

### A · Governing architecture

| Item | Maturity | Evidence | Operational consequence | Next action |
|---|---|---|---|---|
| Constitution, Spine spec, Manager, Security spec, 16 more | **CONFLICTED** | Not in the Dispatch repository; present in Claude-3 and Jules (byte-identical, `cmp`-verified) | Doctrine cannot be checked against code in one place | OWN-02 |
| `PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md` | **MISSING** | Cited 10 times across 4 files; exists in no repository here | Four code comments cite a document nobody can read | OWN-02 |
| Spine partition model, Driver-First v2, Ownership Matrix, Build Matrix v2 | **PROVEN as documents** | In the Dispatch repository | The adjudication is recorded and usable | — |
| The word "Spine" in code | **MISSING** | 0 occurrences in `dispatch/`, `portal/`, `cin_lite/`, `route_risk/`; yet `operations_feed.py:32-41` implements Spine §9 verbatim | The Spine is implemented and unnamed | Cosmetic; low priority |
| Opportunity lifecycle vs BM-10 | **CONFLICTED** | A third state machine on `main` with no Decision Log entry | Nothing today; a governance breach the moment it is wired | SPINE-01 |
| Four Guardians (Constitution, Architecture, Drift, Priority) | **MISSING** | 0 files each | Nothing detected that 718 unwired lines and a third state model landed on `main` | Adjudication |
| Decision Log discipline | **PARTIAL** | 25 KB of entries ending at C3; three later merges unrecorded | The program's memory has a gap | OWN-05 |

### B · Core backend

| Item | Maturity | Evidence | Consequence | Next action |
|---|---|---|---|---|
| SQLite store, 26 tables, WAL, FK on | **PROVEN** | `dispatch/db.py`, `store.py`; survives a real two-process restart | Data is durable | — |
| Service layer, 3,448 lines | **PROVEN** | ~1,800 behavioral tests | The freight engine works | — |
| Transition gate | **PROVEN** | 90 of 121 pairs refused; enforced on both paths since M1 | Illegal state moves are impossible | — |
| Status-change audit | **PROVEN**, with a known shortfall | C3; four paths, 33 tests | Every status change leaves a trail; it is a message string, not Spine §8's structured fields | Accepted; SPINE-05 for the no-op case |
| Atomic JSON writes | **PROVEN** | 12 stores; 18 tests; structural test forbids regression | No torn writes | — |
| Route Risk durability | **PROVEN** | 20 tests | Conditions survive restart | — |
| Replay protection | **PARTIAL** | 8 mechanisms, 14 sites guarded, **15 unguarded** | Duplicate emails and notifications are possible | SPINE-04 |
| Schema versioning | **MISSING** | No `schema_version` table | Upgrades over live data are unlabelled and one-way | RUN-07 |
| Backup / restore | **MISSING** | Nothing in the repository | **A disk failure loses the business** | RUN-05 |

### C · Operational logic

| Item | Maturity | Evidence | Consequence | Next action |
|---|---|---|---|---|
| Scoring | **PROVEN** | 43 tests; advisory | Reduces noise; does not decide | — |
| COMI routing | **PROVEN** | Fail-closed by role | External parties see only what they may | — |
| Financials, settlements, IFTA, driver pay, maintenance, compliance | **PROVEN** | 400+ tests across 8 files | Real bookkeeping | — |
| Conflict detection | **PROVEN** | Booking overlap and turnaround; warns, never blocks | Correct posture — Mike decides | — |
| Dynamic Capacity | **STRUCTURAL PROTOTYPE** | 352 lines, referenced by nothing | Deleting it changes no behavior; 2,817 tests still pass | SPINE-01, then ENG-01/02 |
| Opportunity pipeline | **STRUCTURAL PROTOTYPE** | 297 lines, same | Same | Same |
| Truck Arrangement | **STRUCTURAL PROTOTYPE** | 69 lines, same | Same | Same |
| Stop Sequence | **STRUCTURAL PROTOTYPE** | A stop *count* field, not a sequence; no stop records in the schema | Multi-stop work cannot be represented | Blocked |
| Scheduler | **MISSING** | The word appears once in production code, in a comment | Outlook remains the schedule — doctrinally correct | Blocked on the Outlook decision |
| Revenue Projection | **MISSING** | No implementation | No forward view | Doctrine needed |
| Capacity projection, Visual Capacity Board | **MISSING** | — | — | Blocked on Reserve Capacity Doctrine |

### D · Portals and presentation

| Item | Maturity | Evidence | Consequence | Next action |
|---|---|---|---|---|
| Operations Portal | **PROVEN** | 178 routes over real state; `operations_feed` unifies 7 subsystems | Mike can run the business from it | — |
| `/calendar` | **PLACEHOLDER** | Real loads inside a construct doctrine forbids | Presents Dispatch as a calendar owner | SPINE-03 |
| Stakeholder Portal | **PROVEN** in shape, **PARTIAL** in lifecycle | Redaction and IDOR proven by 33 tests; tokens never expire | Links cannot be revoked | RUN-02 |
| Driver Portal — read | **PROVEN** | Real backend data, not fixtures; one column, no JS, contacts at the top | Passes the 70 MPH test for *reading* | — |
| Driver Portal — write | **MISSING** | **The page has exactly one interactive control: Sign Out** | **A driver cannot report anything from the cab.** Under Driver-First Doctrine this is the largest gap in the program. | PORTAL-01/02/03 |
| Jules portals | **PLACEHOLDER OR SIMULATION** | In-memory singleton, sample bootstrap, no auth, POD success without a file | Convincing and empty | OWN-03 |

### E · Integrations

| Live | Implemented but unconfigured | Stubbed | Not present |
|---|---|---|---|
| GitHub CI; local filesystem; authentication stack | SAM.gov, SMTP, Anthropic | Generic load board, accounting export, credential registry | **Outlook (calendar and mail), ELD/HOS, GPS, routing, weather, traffic, DOT, DAT, TruckSmarter, map visuals** |

`grep -riE "graph\.microsoft|outlook|ews|icalendar|\.ics|msal|exchangelib"` across all production
code returns **exactly one line**, and it is a consumer email domain in a govcon vendor-network rule.

### F · Data and persistence

| Property | Status |
|---|---|
| Durable across restart | **PROVEN** |
| Durable across machine restart | **PROVEN** |
| Durable across upgrade | **PARTIAL** — forward-only, unversioned |
| Reproducible | **PARTIAL** — no seed/reset procedure |
| Recoverable | **FAILED** — no backup exists |
| Operational data present in this workspace | **None.** Every JSON store here is test residue. No `dispatch.db` exists at all. |

### G · Testing

| Property | Status |
|---|---|
| Suite runs clean | **PROVEN** — 2,817 passed, 0 failed, 0 skipped, 0 warnings, exit 0, 314.87 s |
| Engine behavior proven | **PROVEN** — 1,389 behavioral, 1,162 HTTP, 190 negative |
| Shallow tests | 37 of 2,817 (1.3 %) — constant pins, not defects |
| Misleading tests | 1 file — `test_bootstrap_d_drive.py` tests Linux temp copying under a D:-drive name |
| Authentication proven in shipping posture | **FAILED** — 1,161 of 1,162 HTTP tests run with the gate disabled |
| New Dynamic Capacity work proven integrated | **FAILED** — provably unreferenced |
| Coverage gate | **PARTIAL** — measures 3,145 of 22,193 production lines (14 %) |

### H · Deployment and ownership

| Question | Status |
|---|---|
| Does Mike possess the code? | **PROVEN** — three GitHub repositories under his account |
| Does Mike possess a *running* copy? | **UNVERIFIABLE** — never demonstrated on his hardware from here |
| Is there a proven path from merge to his machine? | **FAILED** — the last link of the source-control model does not exist |
| Is the governance with the code? | **FAILED** — split across three repositories |
| Is there one product? | **FAILED** — two portals both claim to be Dispatch |
| Can he recover from a disk failure? | **FAILED** — no backup |

---

## EXECUTIVE CONCLUSION

### WHERE DISPATCH IS NOW

Dispatch is a **real, working, well-tested freight engine that nobody has yet proven can run on
Mike's machine, and that no driver can talk back to.** 22,193 lines of production Python, 26 SQLite
tables, 218 routes, 2,817 passing tests, gated state transitions, audited status changes, verified
evidence and correctly redacted external views. It is being held out of operational use not by
missing features but by five unglamorous items: a proven launch, non-default secrets, a backup, a
sample-data label, and one page that presents a calendar it must not own.

Alongside it sits a second program — the Jules portal — that renders three beautiful screens over an
in-memory dictionary, stores nothing, authenticates nobody, ran with a debugger exposed, and reports
proof-of-delivery uploads that never happened.

### WHAT GENUINELY WORKS — PROVEN

Load lifecycle and state gating · status-change audit on all four paths · evidence attachment with
SHA-256 verification · financials, settlements, IFTA, driver pay, maintenance, compliance ·
deterministic advisory scoring · fail-closed COMI routing by role · Route Risk with durable storage
and honest `is_live_data: False` · atomic JSON writes across twelve stores · three disjoint
authentication namespaces with scrypt-hashed PINs and lockout · stakeholder redaction with a real
IDOR check · safe upload handling · the govcon pipeline with nine deterministic rules · the unified
Operations Feed · 2,817 tests, and a discipline that rewrote 26 test ladders rather than weaken them.

### WHAT ONLY APPEARS TO WORK — PLACEHOLDER

The Jules portal in its entirety · `/calendar` · Dynamic Capacity, the Opportunity pipeline and
Truck Arrangement (718 lines, referenced by nothing, with their own passing tests) ·
`bootstrap_d_drive.py` and its D:-named tests · the integrations credential registry, which stores
keys nothing reads · sample loads presented unlabelled as real · a green CI badge whose coverage
gate measures 14 % of the program · 1,161 HTTP tests that prove routes work with authentication
switched off.

### WHAT IS MISSING

Backup and restore · driver write capability of any kind — POD, photos, milestones, lookup · CSRF
protection · token expiry and revocation · session expiry and cookie flags · schema versioning ·
Outlook, ELD, GPS, routing, weather, traffic, load boards — all of them · Scheduler · Revenue
Projection · capacity in any wired form · the four Guardians · an access audit log · rate limiting ·
an owner for receivables and for IFTA report generation.

### WHAT BLOCKS OPERATIONAL USE

1. **No proven delivery to Mike's machine.** The last link of the source-control model does not exist.
2. **No backup.** A disk failure loses the business.
3. **A published default signing secret** (`"dispatch-dev-secret"`) that makes every stakeholder and decision link forgeable on any deployment that misses one environment variable.
4. **Two portals both claiming to be Dispatch**, one of them unauthenticated and non-persistent.
5. **Sample data indistinguishable from real data.**

### WHAT CAN BE RETAINED

Almost all of it. Fourteen subsystems are listed RETAIN with no change: the store, the schema, the
service layer, the transition gate, the audit helper, Route Risk and its injection contract, atomic
writes, COMI, the authentication model, `RESERVED_SYSTEM_IDENTITIES`, the stakeholder IDOR posture,
the govcon pipeline, the Operations Feed, and the test suite itself. **The engine is sound. This is
a recoverable program, not a failed one.**

### WHAT MUST BE REPAIRED

Secrets and session policy · CSRF across 109 mutating routes · stakeholder token lifecycle · the C1
duplicate status copy · the C2a calendar · the 15 unguarded replay sites · schema versioning ·
storage directories under WSGI · the coverage gate · the ten optimistic defaults of Phase 8, and
above all `verified_by="Mike Zachary"` as a default argument.

### WHAT SHOULD BE BUILT NEXT

In this order: **OWN-04** (delete the committed debugger PIN — today), **OWN-01** (Mike proves the
program runs on his own machine), **OWN-03** (Mike names which portal is Dispatch), **RUN-01**
(refuse to start on a default secret), **RUN-05** (backup and restore, with one proven restore).
Then Stage 1 in full, then SPINE-01's adjudication, then the driver write missions — which are the
ones that make Dispatch Driver-First in fact rather than in doctrine.

### WHAT MIKE MUST OWN BEFORE BUILDING RESUMES

Five decisions. No builder may make any of them.

1. **Which portal is Dispatch** — Dispatch/portal/ or Jules. They cannot both be maintained.
2. **Where governance lives** — one repository, one supersession map, and what became of `PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md`.
3. **The Opportunity lifecycle against BM-10** — map it into the existing models, adopt it with an explicit amendment, or revert it.
4. **`/calendar`** — retire, or rename.
5. **The 402 conflict notices and the rest of the test residue in `portal/data/`** — a protected-record decision under the Archive Review Policy, not housekeeping.

And one thing Mike must **do**, not decide: **run the program on his own machine, create a load,
restart, and see it still there.** Until that transcript exists, every other statement in this audit
about Dispatch being usable is a statement about a repository, not about a business.

---

*This is an audit and blueprint. Nothing here rewrites the program, implements a correction, deletes
a file, changes doctrine, creates a feature, declares production readiness, or hands the program to
any builder. The next builder is selected by Mike Zachary.*
