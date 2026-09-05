# DISPATCH_CURRENT_STATE_INVENTORY

**Phase 1 deliverable — Complete program inventory**
**Audit commit:** `37f4fd033e57c55f46dfd0568d3371e8473d683f` (origin/main, clean tree)
**Audit date:** 2026-08-23
**Authority:** Mike Zachary. This document records what exists. It authorizes nothing.

---

## 0. Correction to the mission's stated workspace

The mission directs inspection of "the full `/app` workspace". **`/app` does not exist in this
environment.** `ls /app` returns `No such file or directory`.

The workspace actually inspected is:

| Path | Repository | Head | Tree |
|---|---|---|---|
| `/home/user/Dispatch` | `github.com/jax1313-outlook/Dispatch` | `37f4fd0` | clean |
| `/home/user/Jules` | `github.com/jax1313-outlook/Jules` | `fe35b13` | clean |
| `/home/user/Claude-3` | `github.com/jax1313-outlook/Claude-3` | `29e7ae0` | clean |

`/app` was the build sandbox of a **different** session. Evidence: `/home/user/Jules/flask_app.log`,
a committed file, contains the line `* Detected change in '/app/app.py', reloading`. That is the
Jules builder's container, not this one, and it no longer exists. Anything reported about `/app`
would be reconstruction from artifacts, not inspection. **UNVERIFIABLE** is the correct
classification for any claim about the live contents of `/app`.

## 1. Source code inventory — Dispatch repository

297 tracked files. **22,193 lines of production Python** across six packages;
**29,520 lines of test Python** in `tests/` (ratio 1 : 1.33).

| Extension | Tracked count |
|---|---|
| `.py` | 202 |
| `.html` | 40 |
| `.md` | 35 |
| `.json` | 5 |
| `.txt` | 3 |
| `.bat` | 3 |
| `.yml` `.toml` `.ps1` `.ini` `.css` `.docx` `.coveragerc` `.gitignore` `.example` | 1 each |

### 1.1 `dispatch/` — freight engine (9,834 lines)

| File | Lines | Purpose | Referenced by app | Classification |
|---|---|---|---|---|
| `services.py` | 3,448 | Service layer: loads, milestones, evidence, financials, IFTA, fleet, stakeholder view | Yes — every route module | PRODUCTION-CAPABLE |
| `store.py` | 2,232 | SQLite persistence, 26 tables | Yes | PRODUCTION-CAPABLE |
| `models.py` | 1,045 | Dataclasses, `LOAD_STATUSES`, `ALLOWED_EXTENSIONS`, `MAX_FILE_SIZE` | Yes | PRODUCTION-CAPABLE |
| `notifications.py` | 684 | Email bodies + HMAC action/stakeholder tokens | Yes | FUNCTIONAL PROTOTYPE (see security report) |
| `db.py` | 502 | Schema, WAL, `PRAGMA foreign_keys=ON`, idempotent migrations | Yes | PRODUCTION-CAPABLE |
| `scoring.py` | 392 | Deterministic advisory load scoring | Yes | PRODUCTION-CAPABLE |
| `email_helper.py` | 309 | Document/packet drafting | Yes | FUNCTIONAL PROTOTYPE |
| `comi_routing.py` | 161 | Role-based fail-closed sanitization, consequence thresholds | Yes | PRODUCTION-CAPABLE |
| `acquisition.py` | 142 | Load normalization; local sample dir by default | Yes | FUNCTIONAL PROTOTYPE (no live board) |
| **`capacity.py`** | **352** | Dynamic Capacity, six dimensions | **No** | **STRUCTURAL PROTOTYPE — unwired** |
| **`opportunities.py`** | **297** | Opportunity Card + 9-stage lifecycle | **No** | **STRUCTURAL PROTOTYPE — unwired** |
| **`truck_arrangement.py`** | **69** | Cargo geometry dataclass | **No** | **STRUCTURAL PROTOTYPE — unwired** |
| `accounting_export.py` | 81 | CSV export | Yes | FUNCTIONAL PROTOTYPE |
| `customer_notifications.py` | 52 | Customer email | Yes | FUNCTIONAL PROTOTYPE |
| `route_risk.py` | 58 | Injects SQLite persistence into the standalone engine | Yes | PRODUCTION-CAPABLE |

**Evidence for the three "unwired" rows** — a repository-wide grep for each module name,
excluding `tests/` and the module itself, returns references **only from `opportunities.py`**:

```
dispatch/opportunities.py:17: from dispatch.capacity import DynamicCapacity
dispatch/opportunities.py:18: from dispatch.truck_arrangement import TruckArrangement
```

No route, no template, no service function, and no database table references any of the three.
`grep -inE "capacit|opportunit|arrangement" dispatch/db.py` returns **zero matches** — there is no
table to store them in.

### 1.2 `portal/` — Flask application (7,832 lines)

8 blueprints, **218 routes**, 40 Jinja templates, 1 stylesheet, 11 JSON-backed models.

| Blueprint | File | Routes | Auth posture |
|---|---|---|---|
| `dispatch_api` | `routes/dispatch_api.py` (2,340 ln) | 146 | Authority PIN gate; one HMAC-exempt endpoint (`dispatch_decision`) |
| `pages` | `routes/pages.py` (1,005 ln) | 32 | Authority PIN gate |
| `api` | `routes/api.py` (606 ln) | 24 | Authority PIN gate |
| `pipeline` | `routes/pipeline.py` | 7 | Authority PIN gate |
| `driver_portal` | `routes/driver_portal.py` (132 ln) | 4 | Own Phone+PIN gate, `session["driver_id"]` |
| `auth` | `routes/auth.py` | 2 | Login surface |
| `stakeholder` | `routes/stakeholder.py` | 2 | HMAC token only, no session |
| `decisions` | `routes/decisions.py` | 1 | HMAC token only, no session |

### 1.3 Other packages

| Package | Lines | Referenced by application | Classification |
|---|---|---|---|
| `cin_lite/` | 3,145 | Yes — `pipeline` blueprint, sole mail transport | PRODUCTION-CAPABLE (govcon pipeline) |
| `sync/` | 723 | Only by `run_sync.py` launcher | FUNCTIONAL PROTOTYPE |
| `route_risk/` | 179 | Yes, via `dispatch/route_risk.py` injection | PRODUCTION-CAPABLE |
| `reconciliation/` | 480 | **No** — `grep -rn "reconciliation"` outside itself and `tests/` returns nothing | **ORPHANED** |

### 1.4 Root-level scripts and launchers

| File | Purpose | Status |
|---|---|---|
| `bootstrap_d_drive.py` (224 ln) | Copies workspace into `D:\Dispatch Operations`, `D:\Archive`, `D:\Memory`, `D:\Sandbox\Jules` | **Never executed against a real `D:` drive from this environment.** See §2 of the recovery plan. |
| `run_bootstrap_d_drive.bat` | Windows wrapper for the above | UNVERIFIABLE from Linux |
| `run_portal.bat`, `run_sync.bat`, `run_sync.py` | Launchers | DOCUMENTATION ONLY here (Windows) |
| `setup_dispatch_folders.ps1` | PowerShell folder tree | UNVERIFIABLE from Linux |
| `pyproject.toml`, `pytest.ini`, `.coveragerc`, `.env.example`, `.github/workflows/ci.yml` | Build/test config | PRODUCTION-CAPABLE |

## 2. Architecture and governance documents

### 2.1 Present in the Dispatch repository (35 `.md` files)

Governance and doctrine: `DISPATCH_BUILD_MATRIX_v1.md`, `DISPATCH_BUILD_MATRIX_v2.md`,
`DISPATCH_OWNERSHIP_MATRIX_v1.md`, `DISPATCH_SPINE_OWNERSHIP_PARTITION_AMENDMENT_v1.md`,
`DRIVER_FIRST_DOCTRINE_v2.md`, `DISPATCH_GOVERNANCE_MANIFEST_REPAIR_PLAN_v1.md`,
`DISPATCH_TRIGGER_AND_SIDE_EFFECT_INVENTORY_v1.md`, `DECISION_LOG.md`, `CLAUDE.md`.

Architecture notes added post-#111 by another builder: `DISPATCH_PURPOSE_STATEMENT.md`,
`DISPATCH_DYNAMIC_CAPACITY_ARCHITECTURE.md`, `CURRENT_REALITY_VS_POSSIBLE_FUTURES_ARCHITECTURE.md`,
`OPPORTUNITY_PIPELINE_ARCHITECTURE.md`, `TRUCK_ARRANGEMENT_AND_LOAD_CONFIGURATION_ARCHITECTURE.md`,
`WEEK_VIEW_CAPACITY_VISUALIZATION_ARCHITECTURE.md`, `DRIVER_PORTAL_ARCHITECTURE_V2.md`.

Walkthrough reports: `M1_`, `M3_`, `MA_`, `C3_`, `PHASE2`–`PHASE7` (10 files).

Deployment: `DEPLOY_LOCAL.md`, `DEPLOY_VPS.md`, `README.md`, `docs/MANAGER.md`,
`docs/CANONICAL_RECONCILIATION_INTEGRATION.md`, `cin_lite/README.md`, `reconciliation/README.md`.

### 2.2 Absent from the Dispatch repository — **CONFLICTED**

The following are cited by Dispatch code and by Dispatch governance documents but **are not in the
Dispatch repository**. They exist only in `Claude-3` and `Jules`:

`DISPATCH_CONSTITUTION_v3.md` · `DISPATCH_SPINE_SPECIFICATION_v1.md` · `DISPATCH_SPINE_OVERVIEW.md` ·
`DISPATCH_REPO_MANIFEST_v3.md` · `DISPATCH_VERSION_DOCTRINE.md` · `SUPERSESSION_MAP.md` ·
`ARCHITECTURE.md` · `ARCHITECTURAL_DISPOSITION.md` · `CONTEXT_MASTER.md` · `COGNITIVE_FUNCTIONS.md` ·
`SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md` · `DISPATCH_DECISION_MATRIX.md` · `MANAGER.md` ·
`PUBLISHER.md` · `INTELLIGENCE_ANALYST.md` · `INTELLIGENCE_VERIFICATION_WORKFLOW.md` ·
`ARCHIVE_REVIEW_POLICY.md` · `ALERT_GOVERNANCE_DOCTRINE.md` · `PORTAL_DESCRIPTION.md` ·
`REFINEMENT_ANALYST_REMOVAL.md`

`PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md`, cited by name in
`portal/models/identity.py:5` as living in "(Claude-3 repo)", is **in neither** Claude-3 nor Jules
as inspected. It is cited by code and does not exist in any repository in this workspace —
**MISSING**.

**Consequence:** the repository that is the implementation source of truth does not contain the
constitution it is governed by. Any check of code against doctrine requires three checkouts.

## 3. Runtime and operational assets

| Asset | Path | Tracked | Content |
|---|---|---|---|
| SQLite operational DB | `portal/data/dispatch.db` | gitignored | **Does not exist.** `find / -name "dispatch.db"` returns only test temporaries. |
| Conflicts store | `portal/data/conflicts.json` | gitignored | 237 KB — **test/probe residue**, not operations |
| Completion packets | `portal/data/completion_packets.json` | gitignored | 45 KB — test residue |
| Email packages | `portal/data/email_packages.json` | gitignored | 30 KB — test residue |
| Publisher queue | `portal/data/publisher_queue.json` | gitignored | 17 KB — test residue |
| Sandbox | `portal/data/sandbox.json` | gitignored | 5 KB — test residue |
| Archive index | `portal/data/archive.json` | gitignored | 643 B — test residue |
| Uploads | `portal/data/uploads/` | gitignored | empty |
| Sample loads | `portal/sample_dispatch_data/sample_load*.json` | **tracked** | 2 files — **sample data, default acquisition source** |
| CIN archive | `cin_lite/Archive/` | gitignored | pipeline output |

**There is no operational data anywhere in this workspace.** Every JSON store present is residue
from test runs and analysis probes. Classification of all runtime data here: **test data**.

`dispatch/acquisition.py:47` defaults `DISPATCH_LOAD_SOURCE` to `portal/sample_dispatch_data`.
With no env var set, the acquisition layer serves **two sample loads** and nothing else.

## 4. The Jules repository — the portal Mike described as "running"

`/home/user/Jules` @ `fe35b13`. 24 documents, `app.py` (9.4 KB), `dispatch_spine.py` (16.3 KB),
8 templates, 1 test file, `run_portal.sh`.

| Property | Finding | Evidence |
|---|---|---|
| Persistence | **None.** All state is a module-level singleton `spine_store`, populated by `_bootstrap_sample_data()` | `dispatch_spine.py:183`; `grep -nE "sqlite\|json.dump\|open\(" app.py dispatch_spine.py` → no matches |
| Authentication | **None.** No session, no login, no token check on any route including `/operations` and `/api/v1/*` | `grep -cin "session\|login\|auth\|token\|password" app.py` → 3 matches, all incidental |
| Debug mode | **Was running with the Werkzeug debugger active and its PIN written to a committed file** | `flask_app.log`: `Debug mode: on` … `Debugger is active!` … `Debugger PIN: 631-326-424` |
| Bind address | `0.0.0.0` by default | `run_portal.sh:10` — `HOST=${HOST:-"0.0.0.0"}` |
| POD upload | Returns `"status": "success"` and sets `pod_status = "UPLOADED"` **even when no file was posted** | `app.py:148-167` — `"file_saved": saved_filename if saved_filename else "Simulated upload"` |

**Classification: PLACEHOLDER OR SIMULATION.** It renders three portals convincingly and stores
nothing. It is a presentation study, not an operational system.

## 5. Inventory summary by classification

| Classification | Count of inventoried units |
|---|---|
| PRODUCTION-CAPABLE | 8 modules (`services`, `store`, `models`, `db`, `scoring`, `comi_routing`, `route_risk`, `cin_lite` core) |
| FUNCTIONAL PROTOTYPE | 6 (`notifications`, `email_helper`, `acquisition`, `accounting_export`, `customer_notifications`, `sync`) |
| STRUCTURAL PROTOTYPE | 3 (`capacity`, `opportunities`, `truck_arrangement`) |
| PLACEHOLDER OR SIMULATION | 1 (entire Jules portal) |
| DOCUMENTATION ONLY | 15 architecture/doctrine documents with no implementation |
| ORPHANED | 1 package (`reconciliation/`, 480 lines) |
| MISSING | `PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md` |
| CONFLICTED | 20 governance documents split across three repositories |
| UNVERIFIABLE | `/app` contents; `D:` drive state; all Windows launchers |
