# CANONICAL WORKER FILE INVENTORY
**Document ID:** CANONICAL_WORKER_FILE_INVENTORY.md
**Status:** VERIFIED & AUTHORITATIVE
**Authority:** Mike Zachary / Dispatch Platform Doctrine

---

## 1. CANONICAL LOCATION SUMMARY

All worker framework files exist in single, non-duplicated authoritative locations inside the Dispatch repository:

| Asset Category | Canonical Path | Description |
|---|---|---|
| **Worker Code** | `dispatch/workers/` | Framework base classes and bounded worker implementations (`joe`, `intelligence`, `publisher`, `worker_framework`). |
| **Worker Config** | `dispatch/config/workers/` | JSON configuration files (`joe_config.json`, `intelligence_config.json`, `publisher_config.json`). |
| **Worker Docs** | `docs/workers/` | Governance documents and worker implementation plans (`01` through `06`). |
| **Worker Tests** | `tests/workers/` | Unit and integration test suites (`test_joe.py`, `test_intelligence.py`, `test_publisher.py`, `test_handoffs.py`). |

---

## 2. DETAILED INVENTORY

### Worker Source Code (`dispatch/workers/`)
- `dispatch/workers/worker_framework/__init__.py`
- `dispatch/workers/worker_framework/base.py`
- `dispatch/workers/joe/__init__.py`
- `dispatch/workers/joe/worker.py`
- `dispatch/workers/intelligence/__init__.py`
- `dispatch/workers/intelligence/worker.py`
- `dispatch/workers/publisher/__init__.py`
- `dispatch/workers/publisher/worker.py`

### Worker Configuration (`dispatch/config/workers/`)
- `dispatch/config/workers/joe_config.json`
- `dispatch/config/workers/intelligence_config.json`
- `dispatch/config/workers/publisher_config.json`

### Worker Documentation (`docs/workers/`)
- `docs/workers/01_WORKER_FRAMEWORK_DESIGN.md`
- `docs/workers/02_WORKER_INTEGRATION_PLAN.md`
- `docs/workers/03_WORKER_HANDOFF_MATRIX.md`
- `docs/workers/04_JOE_IMPLEMENTATION_PLAN.md`
- `docs/workers/05_INTELLIGENCE_IMPLEMENTATION_PLAN.md`
- `docs/workers/06_PUBLISHER_IMPLEMENTATION_PLAN.md`

### Worker Tests (`tests/workers/`)
- `tests/workers/test_joe.py`
- `tests/workers/test_intelligence.py`
- `tests/workers/test_publisher.py`
- `tests/workers/test_handoffs.py`

---

## 3. DUPLICATE REMOVAL PROOF

All temporary path aliases (`dispatch operations/`, `dispatch_operations/`, `dispatchoperations/`) and unnumbered doc copies have been completely purged from the repository.
