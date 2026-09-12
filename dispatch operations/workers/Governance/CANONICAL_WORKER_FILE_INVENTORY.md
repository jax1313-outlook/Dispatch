# CANONICAL WORKER FILE INVENTORY
**Document ID:** CANONICAL_WORKER_FILE_INVENTORY.md
**Status:** VERIFIED & AUTHORITATIVE
**Authority:** Mike Zachary / Dispatch Platform Doctrine

---

## 1. AUTHORITATIVE WORKER WORKSPACE

Per WORKER REPOSITORY AUTHORITY, the authoritative development workspace is:
`D:\Dispatch Operations\Workers\` (`dispatch operations/workers/`)

| Asset Category | Authoritative Location | Description |
|---|---|---|
| **Governance Docs** | `dispatch operations/workers/Governance/` | Binding Constitutions, Implementation Plans (`01_`–`06_`), and Pre-Submission Proof Reports. |
| **Joe Worker** | `dispatch operations/workers/Joe/` | `worker.py` and `__init__.py` for Joe Voice Capture. |
| **Intelligence Worker** | `dispatch operations/workers/Intelligence/` | `worker.py` and `__init__.py` for Dynamic Capacity evaluation & scoring. |
| **Publisher Worker** | `dispatch operations/workers/Publisher/` | `worker.py` and `__init__.py` for Packet & Outlook draft generation. |
| **Worker Framework** | `dispatch operations/workers/worker_framework/` | `base.py` and `__init__.py` providing BaseWorker, Constitutions, and HandoffRunner. |
| **Worker Tests** | `dispatch operations/workers/Test/` | Independent test modules (`test_joe.py`, `test_intelligence.py`, `test_publisher.py`, `test_handoffs.py`). |

---

## 2. DISPATCH RUNTIME BRIDGE

To integrate seamlessly with Dispatch platform runtime without code duplication or competing sources of truth, `dispatch/workers/` contains thin forwarding proxies that re-export directly from the authoritative `dispatch operations/workers/` workspace.

### Runtime Bridge Paths (`dispatch/workers/`)
- `dispatch/workers/joe/worker.py` → Re-exports `dispatch_operations.workers.Joe.worker`
- `dispatch/workers/intelligence/worker.py` → Re-exports `dispatch_operations.workers.Intelligence.worker`
- `dispatch/workers/publisher/worker.py` → Re-exports `dispatch_operations.workers.Publisher.worker`
- `dispatch/workers/worker_framework/base.py` → Re-exports `dispatch_operations.workers.worker_framework.base`

---

## 3. VERIFICATION

All worker functionality, tests, and rehearsal scripts run against this single authoritative source of truth.
