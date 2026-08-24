# DISPATCH_RETAIN_REPAIR_REPLACE_REMOVE_MATRIX

**Phase 11 deliverable**
**Audit commit:** `37f4fd033e57c55f46dfd0568d3371e8473d683f`
**Nothing was deleted, moved, or modified by this mission.** Every row is a recommendation.

---

## RETAIN — sound implementation, carry forward unchanged

| Item | Why | Evidence |
|---|---|---|
| `dispatch/store.py`, `dispatch/db.py` | 26-table schema, WAL, FK enforcement, idempotent guarded migrations. The most solid layer in the program. | 502 + 2,232 lines; migration pattern at `db.py:446-460` |
| `dispatch/services.py` | The freight engine. Load lifecycle, milestones, evidence, financials, IFTA, fleet, stakeholder redaction. | 3,448 lines behind ~1,800 behavioral tests |
| `_VALID_TRANSITIONS` + `validate_status_transition()` | Enforced on both status paths since M1; 90 of 121 state pairs refused. | `services.py:74-98`; 28 + 4 tests |
| `_record_status_change()` and its four call sites | Audit symmetry, achieved without a schema change. | C3; 33 tests |
| `route_risk/` + injected `store_fn` / `load_events_fn` / `comi_eval_fn` | The cleanest module boundary in the program — no dual write, no hard import, and durability proven across a real two-process restart. | 20 tests |
| `atomic_write_json()` and the 12 stores that use it | Crash-safety proven, and a structural test forbids reintroducing a bare write. | 18 tests |
| `dispatch/comi_routing.py` | Fail-closed role-based sanitization. | 161 lines |
| The three-namespace authentication model | Authority / Driver / token, provably disjoint. | `portal/app.py`, `driver_portal.py` |
| `RESERVED_SYSTEM_IDENTITIES` | The only governance rule enforced in code. Never weaken it. | `library.py:41,140` |
| Stakeholder IDOR check and flat-404 posture | Correct, and rare. | `stakeholder.py:83-92`; 16 tests |
| `cin_lite/` govcon pipeline and its 9 deterministic rules | Independently useful, determinism asserted. | 3,145 lines; 17 tests |
| `portal/models/operations_feed.py` | Reads seven real subsystems, owns no state, adds no business logic — and implements Spine §9 exactly. | 330 lines; 25 tests |
| The test suite itself | 2,817 passing; ladders were rewritten rather than weakened when M1 broke 26 of them. | §1 of the test report |
| `DECISION_LOG.md` + walkthrough-report convention | The program's memory. It is why this audit could reconstruct intent. | 25 KB |

## REPAIR — right structure, incomplete or defective behavior

| # | Item | Defect | Data concern | Authority |
|---|---|---|---|---|
| P-1 | `dispatch/notifications.py`, `cin_lite/email_delivery.py` | `_secret()` defaults to `"dispatch-dev-secret"` (S-1) | None | Builder, under Mike's approval |
| P-2 | `dispatch/notifications.py` token format | No expiry, no revocation (S-2). Adding a timestamp invalidates existing links — **acceptable only because no real stakeholder link has been issued.** | Verify no live links exist first | Mike |
| P-3 | `portal/config.py` | Default `SECRET_KEY` warns and continues (S-3); no cookie flags, no session lifetime (S-5) | Existing sessions invalidated on change | Builder |
| P-4 | All 109 mutating routes | No CSRF protection (S-4) | None | Builder |
| P-5 | `portal/models/sandbox.py:231-240` + two callers + two templates | Duplicate load status (C1) | The stored copy must be read through, not dropped — two display paths depend on it | Mike (design choice already approved: read-through) |
| P-6 | `portal/routes/pages.py:310` `/calendar` | Presents a calendar Dispatch must not own (C2a) | None | Mike: retire, or rename |
| P-7 | `dispatch/services.py` replay guards | 8 mechanisms cover 14 call sites; **15 remain unguarded**, including duplicate stall notifications and duplicate checkpoint emails (C4) | Ledger must survive restart; assert on the ledger, never the outbox | Mike |
| P-8 | `.github/workflows/ci.yml` | Coverage gate measures 14 % of production | None | Builder |
| P-9 | `portal/app.py` `_ensure_storage_dirs()` | Never runs under gunicorn (S-7) | None | Builder |
| P-10 | `dispatch/capacity.py` optimistic defaults | `stacking_policy="STACKABLE"`, `allows_top_load=True`, `verified_by="Mike Zachary"`, `source="ELD_LOG"` — see the main audit, Phase 8 | None (unwired) | Mike |
| P-11 | `dispatch/acquisition.py` | Sample data is the silent default source (D-3) | None | Builder |
| P-12 | Schema versioning | No version, no down-migration (D-2) | Affects every future upgrade | Builder |
| P-13 | `update_load()` no-op audit entries | Writes `"Status changed from dispatched to dispatched"` — a false statement in an audit log. Identified during C3, deliberately left for Mike. | Existing entries stay | Mike |

## REPLACE — repair is more dangerous than controlled replacement

| # | Item | Why replacement, not repair | Dependencies | Migration | Authority |
|---|---|---|---|---|---|
| R-1 | **The Jules portal as an operational candidate** | It has no persistence layer to add durability to, no auth layer to harden, and no tests against Dispatch. Retrofitting it means writing Dispatch again. Its **presentation design should be harvested** — the driver screen is better than Dispatch's — and its runtime discarded. | R-0.1 in the recovery plan | None — it stores nothing | **Mike only** |
| R-2 | **The three-repository governance split** | Reconciling doctrine across three checkouts by hand will fail again. One repository, one supersession map. | R-0.2 | Documents move; no code change | **Mike only** |
| R-3 | **Werkzeug's dev server as the run mode** | `python portal/app.py` is the documented start command. It is single-threaded and not a production server. | DEPLOY_LOCAL | A `waitress`/`gunicorn` launcher | Builder |

## REMOVE OR ARCHIVE — obsolete, duplicated, misleading, unused, or unsafe

**Nothing in this section was removed. Every row requires Mike's authority.**

| # | Item | Why | Dependencies | Data concern | Authority |
|---|---|---|---|---|---|
| X-1 | `Jules/flask_app.log` | Committed file containing a live Werkzeug debugger PIN (J-2) | None | None | **Mike — remove first, before anything else on this list** |
| X-2 | `reconciliation/` (480 lines, 30 tests) | Referenced by nothing outside itself and its tests. Dead code that a reader will mistake for a live integration. | None | None | Mike — archive, don't delete |
| X-3 | 54 stale remote branches | Merged and never deleted; obscures what is live | None | Git history retains everything | Mike |
| X-4 | `portal/data/*.json` test residue (≈336 KB, 402 conflict notices) | Test output that reads as operations | None | **Unresolved notices are protected under the Archive Review Policy** — this is a policy decision, not housekeeping | **Mike only** |
| X-5 | `Claude-3` repository | A strict, byte-identical subset of Jules's document set with nothing of its own (`cmp` verified) | R-2 | Documents must land in Dispatch first | Mike |
| X-6 | `DISPATCH_BUILD_MATRIX_v1.md` | Superseded by v2, which supersedes it explicitly | None | Keep as history | Mike |
| X-7 | One of `docs/MANAGER.md` / `Jules/MANAGER.md` | Two Manager documents, two repositories, one dormant subsystem | R-2 | None | Mike |
| X-8 | `tests/test_bootstrap_d_drive.py`'s **name**, not its tests | The name claims D:-drive verification the tests cannot provide | None | None | Builder — rename to reflect the actual subject (`copy_tree_safe`) |

## Summary

| Disposition | Count |
|---|---|
| RETAIN | 14 subsystems |
| REPAIR | 13 items |
| REPLACE | 3 items |
| REMOVE OR ARCHIVE | 8 items |

The shape of this matrix is the finding: **the engine is retained almost entirely, and almost
everything requiring repair is at the edges** — secrets, session policy, CSRF, delivery, governance
location. That is a recoverable program, not a failed one.
