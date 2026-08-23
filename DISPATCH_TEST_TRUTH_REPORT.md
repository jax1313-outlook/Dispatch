# DISPATCH_TEST_TRUTH_REPORT

**Phase 7 deliverable — complete test audit**
**Audit commit:** `37f4fd033e57c55f46dfd0568d3371e8473d683f`

---

## 1. Raw suite output

**Command**

```
python3 -m pytest -p no:cacheprovider -rN
```

(`pytest.ini` supplies `testpaths = tests`, `python_files = test_*.py`, `addopts = -q`.)

**Result, verbatim final line**

```
2817 passed in 314.87s (0:05:14)
```

**Exit code:** `0`

| Metric | Value |
|---|---|
| Collected | 2,817 |
| Passed | 2,817 |
| Failed | **0** |
| Skipped | **0** |
| Errors | **0** |
| Warnings | **0** (no warnings summary was emitted) |
| xfail / xpass | 0 |
| Test files | 112 |
| Wall clock | 314.87 s |

Environment: Python 3.12, Flask 3.1.3, pytest 9.1.1, Linux. Dependencies installed with
`pip install --ignore-installed blinker flask pytest pytest-cov`.

**A green suite of this size is evidence of discipline, and it is not evidence of a working
product.** The rest of this report is about the difference.

## 2. What the suite covers, by file

112 files. The ten largest by test count:

| File | Tests |
|---|---|
| `test_portal.py` | 201 |
| `test_dispatch.py` | 130 |
| `test_ifta_mileage.py` | 75 |
| `test_compliance_tracker.py` | 73 |
| `test_financials.py` | 65 |
| `test_ifta_monthly.py` | 64 |
| `test_driver_pay.py` | 62 |
| `test_fleet.py` | 58 |
| `test_maintenance.py` | 55 |
| `test_settlement.py` | 54 |

## 3. Classification method

Every test function was parsed with `ast` and classified by what it actually invokes. Totals are
exact for the 2,813 functions the parser resolved; 4 of the 2,817 collected tests are generated at
class or parametrize level and are not individually classified.

| Class | Definition | Count |
|---|---|---|
| **Behavioral (unit)** | Calls a production function from `dispatch`, `portal`, `cin_lite`, `route_risk`, `sync` or `reconciliation` and asserts on the result | **1,389** |
| **HTTP / integration** | Drives a Flask test client through a real route | **1,162** |
| **Behavioral + negative** | As behavioral, and additionally asserts a refusal via `pytest.raises` | **190** |
| **Flagged as construction-or-default-only** | No production call visible in the function body | **72** |
| Unresolved by the parser | Class- or parametrize-generated | 4 |
| **Total collected** | | **2,817** |

## 4. The 72 flagged tests, read individually

The heuristic cannot see production calls that arrive through a fixture. All 72 were therefore read.
The breakdown is exact:

| Verdict | Count | Basis |
|---|---|---|
| **False positive — genuinely behavioral** | **31** | The production object arrives via a fixture. All 16 `test_sync.py` tests (`sample_config`, `tmp_dirs`), 7 `test_rules.py` tests (`intelligence`), plus `test_dispatch.py::test_create_load_shape`, `test_create_load`, `test_milestone_transition_gate.py::test_accepted_delivery_still_sends`, `test_route_risk_durability.py::test_comi_evaluation_still_drives_the_flags`, `test_status_change_audit.py`'s two ladder tests, `test_portal.py::test_pin_stored_as_hash_not_plaintext` (which verifies the stored hash via `check_password_hash` — a real security property), and `test_rules.py::test_rule_result_shape_and_determinism` |
| **Contract / structural — valuable, correctly flagged as calling nothing** | **2** | `test_atomic_store_writes.py::test_no_portal_store_uses_bare_write_text` scans source to forbid reintroducing a non-atomic write; `test_status_change_audit.py::test_transition_matrix_untouched` pins `_VALID_TRANSITIONS` against drift |
| **Confirmed construction / default-value only** | **37** | Listed below |
| **Trivial existence** | **2** | `test_portal.py::test_app_creates` (`assert app is not None`), `test_app_is_flask` |

### 4.1 The 37 confirmed constant-only tests

| File | What they assert | Count |
|---|---|---|
| `test_portal.py` | `CONFLICT_TYPES`, `SECTIONS`, severities, the eleven statuses, nine action types, three packet manifests, location-intelligence fields, inquiry template text | 14 |
| `test_ifta_monthly.py` | Surcharge flags per jurisdiction, rate-table size, Canadian provinces, DC | 9 |
| `test_compliance_tracker.py` | Doc types, entity types, doc statuses | 3 |
| `test_file_attachments.py` | `ALLOWED_EXTENSIONS` non-empty, `MAX_FILE_SIZE` value | 2 |
| `test_reconciliation_*_adapter.py` | Every enum member has a mapping | 2 |
| `test_detention_tracking.py`, `test_email_decision_audit.py`, `test_ifta_exception_detectors.py`, `test_ifta_mileage.py`, `test_load_source.py`, `test_rules.py`, `test_sandbox_program_scoping.py` | Module constants | 7 |

**37 of 2,817 is 1.3 %.** These are cheap regression pins, not defects. They are listed only so
nobody counts them as behavioral coverage. `test_all_conflict_types_defined` is deliberately
order-sensitive and was kept that way during M1 — the new conflict type was appended rather than
inserted — so it remains a meaningful check rather than one rewritten around.

## 5. Misleading tests — 1

`tests/test_bootstrap_d_drive.py` (4 tests). Its subject is a utility whose entire purpose is
writing to `D:\Dispatch Operations`, `D:\Archive`, `D:\Memory` and `D:\SANDBOX\Jules`. All four
tests exercise `copy_tree_safe` between `tmp_path` directories on Linux.

**They pass, and they prove nothing about the utility's purpose.** A reader scanning test names sees
"bootstrap d drive: 4 passed" and concludes the D: migration is verified. It is not, and cannot be
from this platform. Classification: **MISLEADING** — not because the tests are wrong, but because
their names claim a scope their assertions do not reach.

## 6. Significant production capability with no meaningful behavioral test

| Capability | Lines | Test status | Consequence |
|---|---|---|---|
| **Dynamic Capacity wiring** | 352 | 9 unit tests on the dataclasses; **zero tests that any part of Dispatch calls them** | The module could be deleted and 2,817 tests would still pass |
| **Opportunity lifecycle wiring** | 297 | Same | Same |
| **Truck Arrangement wiring** | 69 | Same | Same |
| **The Authority login gate** | — | Exercised by exactly one test class (`TestDispatchPinAuthentication`, which passes `LOGIN_DISABLED=False`). **The other 1,161 HTTP tests run with `TESTING=True`, which disables the gate.** | The suite proves routes work *when authentication is off*. It does not prove any specific route is protected when it is on. |
| **CSRF protection** | — | No test, because no implementation | — |
| **Token expiry / revocation** | — | No test, because no implementation | — |
| **Backup and restore** | — | No test, because no implementation | — |
| **Concurrent access** | — | No test | WAL is enabled; multi-process behavior is unproven above the two-process restart test in `test_route_risk_durability.py` |
| **`reconciliation/` package** | 480 | 30 tests | The tests are real; **the package is called by nothing**, so they guard dead code |

## 7. Coverage gate — what CI actually measures

`.coveragerc` declares `source = cin_lite, dispatch`. `.github/workflows/ci.yml` then runs:

```
python -m pytest --cov=cin_lite --cov-config=.coveragerc --cov-fail-under=90
```

The command-line `--cov=cin_lite` **overrides** the config's source list. The 90 % gate therefore
measures **3,145 of 22,193 production lines — 14 %.** `dispatch/` (9,834 lines), `portal/` (7,832),
`sync/`, `route_risk/` and `reconciliation/` are outside the gate entirely.

This is not a claim that those packages are untested — they are heavily tested. It is a claim that
**CI cannot fail on their coverage regressing**, which is what a coverage gate is for. A capacity
module with zero integration coverage passed CI three times.

## 8. Test isolation

`tests/conftest.py` provides two autouse fixtures. `_scrub_env` deletes 26 integration environment
variables so agents take deterministic fallbacks and acquisition stays offline. `tmp_archive`
redirects `cin_lite.archive.ARCHIVE_ROOT`, the email outbox, the pending directory **and**
`PORTAL_DATA_DIR` into a per-test `tmp_path`.

That last redirect was added during M-A after the suite was found writing into the developer's live
`portal/data/conflicts.json`. It holds: the file's bytes are unchanged across a full run.

**Residual leak, disclosed:** analysis probes run outside the harness during earlier missions wrote
two Conflict Notices into `portal/data/conflicts.json` (400 → 402). Those were left in place
deliberately — unresolved notices are protected under the Archive Review Policy and purging them is
Mike's decision, not a builder's. `portal/data/` is gitignored; nothing reached the repository.

## 9. Verdict

| Question | Answer |
|---|---|
| Does the suite run clean? | **PROVEN** — 2,817 passed, 0 failed, 0 skipped, exit 0 |
| Does it prove the freight engine works? | **PROVEN for the engine's own logic** — status transitions, financials, IFTA, fleet, evidence integrity and stakeholder redaction are all behaviorally asserted |
| Does it prove the product works for Mike? | **NO** — no test covers authentication in the posture it ships in, no test covers a driver capturing a POD, no test covers backup or restore, and no test covers any external integration, because none exist |
| Does it prove the new Dynamic Capacity work is integrated? | **FAILED** — the modules are provably unreferenced; their tests would pass unchanged if Dispatch were deleted around them |
