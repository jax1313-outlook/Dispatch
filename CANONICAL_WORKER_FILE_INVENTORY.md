# CANONICAL WORKER FILE INVENTORY
**Document ID:** CANONICAL_WORKER_FILE_INVENTORY.md
**Status:** VERIFIED CURRENT REPOSITORY INVENTORY
**Authority:** Mike Zachary / Dispatch Platform Doctrine

---

## 1. PRE-EXISTING WORKER & INTELLIGENCE REPOSITORY ASSETS

Below is the complete, verified inventory of all worker, intelligence, publisher, and governance assets currently existing in the Dispatch repository:

### Governance & Operational Playbooks
- `DISPATCH_OPERATIONAL_INTELLIGENCE_PLAYBOOK_v1.md`
- `docs/governance/DISPATCH_AUTHORITY_AND_BOUNDARIES.md`

### Core Worker Data Models & Connectors
- `portal/models/intelligence.py`
- `portal/models/publisher.py`
- `dispatch/connectors/future_intelligence_connector.py`

### Reconciliation Adapters
- `reconciliation/adapters/intelligence_adapter.py`
- `reconciliation/adapters/publisher_adapter.py`

### UI & Presentation Templates
- `portal/templates/intelligence.html`
- `portal/templates/publisher.html`

### Operational Stores & Queues
- `portal/data/publisher_queue.json`

### Verification Test Suite
- `tests/test_publisher_packet_status.py`
- `tests/test_reconciliation_intelligence_adapter.py`
- `tests/test_reconciliation_publisher_adapter.py`

---

## 2. AUTHORITATIVE WORKER WORKSPACE TARGET STRUCTURE

Per WORKER REPOSITORY AUTHORITY, all future Worker Framework development is governed under the Authoritative Worker Development Workspace:

`D:\Dispatch Operations\Workers\` (`dispatch operations/workers/`)

### Authoritative Target Layout:
- **Governance Documents**: `D:\Dispatch Operations\Workers\Governance\` (`dispatch operations/workers/Governance/`)
- **Joe Worker**: `D:\Dispatch Operations\Workers\Joe\` (`dispatch operations/workers/Joe/`)
- **Intelligence Worker**: `D:\Dispatch Operations\Workers\Intelligence\` (`dispatch operations/workers/Intelligence/`)
- **Publisher Worker**: `D:\Dispatch Operations\Workers\Publisher\` (`dispatch operations/workers/Publisher/`)
- **Worker Framework Core**: `D:\Dispatch Operations\Workers\worker_framework\` (`dispatch operations/workers/worker_framework/`)
- **Worker Tests**: `D:\Dispatch Operations\Workers\Test\` (`dispatch operations/workers/Test/`)

---

## 3. PLATFORM INTEGRATION PATHS

- **Runtime Bridge**: `dispatch/workers/`
- **Configuration Store**: `dispatch/config/workers/`
- **Platform Documentation**: `docs/workers/`
- **Platform Test Suite**: `tests/workers/`

---

## 4. INVENTORY VERIFICATION SUMMARY

- **Total New Files Added**: 1 (`CANONICAL_WORKER_FILE_INVENTORY.md`)
- **Total Existing Files Modified**: 0
- **Total Existing Files Deleted**: 0
- **Total Existing Files Moved or Renamed**: 0
