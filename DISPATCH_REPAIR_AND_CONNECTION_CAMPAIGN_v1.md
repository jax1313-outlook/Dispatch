# DISPATCH_REPAIR_AND_CONNECTION_CAMPAIGN_v1

**Execution-ready campaign definition. NOT STARTED.**
**Baseline audit:** `dd5d6c1` · **Reconciliation:** this branch
**No campaign unit below is authorized. Mike approves each individually.**

---

## 0. What this campaign is

The baseline blueprint assumed Dispatch's gaps were **unbuilt**. Cross-repository evidence shows
most are **built and undelivered**. The campaign therefore has three kinds of unit, and they are
deliberately not interchangeable:

- **RECOVER** — bring existing, tested work into `main`.
- **REPAIR** — fix a defect in work being recovered, or on `main`.
- **CONNECT** — wire a module that exists and is called by nothing.

**A CONNECT unit never runs before its adjudication.** That rule is the whole reason
`dispatch/opportunities.py` is a problem today.

## 1. Standing campaign rules

| # | Rule |
|---|---|
| **CR-1** | Every unit delivers the full artifact chain: source, commit, remote branch, pull request, behavioral tests, **exact test output**, reviewer disposition, Mike's acceptance. A sandbox path is not delivery. A completion report is not delivery. |
| **CR-2** | **No unit merges with another.** R-01's four defects are one unit; PORTAL-02 does not fold into PORTAL-01. |
| **CR-3** | A RECOVER unit **cherry-picks files, never commits**, unless the branch's base is `main`. Every recovery candidate is stale-based; merging a commit would drag duplicate history in. |
| **CR-4** | A recovered file arrives with its tests **re-run against today's `main`**, not against the branch it came from. A branch's green suite is evidence the code works *there*. |
| **CR-5** | No CONNECT unit runs while its model is unadjudicated. |
| **CR-6** | Standing constraints BM-01 … BM-15 remain in force. BM-02 (Manager dormant) is not relaxed by the discovery that Manager exists. |
| **CR-7** | Any unit that changes operator-visible behavior brings an enumerated list of what changes (BM-09). |
| **CR-8** | If a recovery reveals the branch code is worse than `main`'s, **stop and report** — do not "recover" a regression because a plan said to. |

## 2. Campaign units

### Wave 0 — Delivery. Nothing else starts until Wave 0 is accepted.

| Unit | Kind | Scope | Gate | Lane |
|---|---|---|---|---|
| **W0-1** | REPAIR | Delete `Jules/flask_app.log` (live Werkzeug debugger PIN, committed); gitignore `*.log` | None — **today** | Claude Code |
| **W0-2** | — | Mike proves clone → install → init-admin → run → create load → restart → load persists, on Windows | None | **Mike personally** |
| **W0-3** | — | Mike names which portal is Dispatch (CF-01 adjacent) | W0-2 | **Mike** |
| **W0-4** | RECOVER | Governance home: land R-04, R-05, R-06 per CF-01; correct the 10 wrong-repository citations | **CF-01, CF-02** | Claude Code, Mike decides |
| **W0-5** | REPAIR | `DECISION_LOG.md` entries for PRs #113–#115; prune 24 merged branches; archive the empty `Route-Risk` repo | W0-3 | Claude Code drafts, Mike dispositions |

### Wave 1 — Ungated recovery. Cheap, self-contained, no decision needed.

| Unit | Kind | Scope | Evidence required | Lane |
|---|---|---|---|---|
| **W1-1** | RECOVER | CI coverage gate: `--cov=cin_lite --cov=dispatch --cov=portal` from `stage13`. Set `--cov-fail-under` to the **measured** value, not 90 | The CI run showing the measured percentage | Claude Code |
| **W1-2** | RECOVER + REPAIR | `list_route_risk_events()` → `ORDER BY created_at DESC, rowid DESC`. **New test required** — the branch's test targets a `_StubRouteRisk` absent from `main` | Two events forced into one second via direct SQL; deterministic winner asserted | Claude Code |
| **W1-3** | RECOVER | `PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md` (177 ln) + `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` (331 ln) | Structural test: every governance document cited by a `.py` file exists on disk | Claude Code |

### Wave 2 — Security. `main`-only; no repository has these.

| Unit | Kind | Scope | Notes |
|---|---|---|---|
| **W2-1** | REPAIR | Refuse to start on default `DISPATCH_EMAIL_SECRET` / `PORTAL_SECRET_KEY` (S-1, S-3) | Baseline RUN-01 |
| **W2-2** | REPAIR | Backup + restore, SQLite backup API not a file copy (D-1) | **Mike performs one restore** |
| **W2-3** | REPAIR | Cookie flags + session lifetime (S-5) | Baseline RUN-03 |
| **W2-4** | REPAIR | Token expiry + per-load revocation counter (S-2) | **Confirm no live link exists first (U-4)** |
| **W2-5** | REPAIR | **CSRF across 109 mutating routes.** Exemption list identical to the login gate's, no wider | **Stop-the-world — nothing else in flight** |

### Wave 3 — Adjudication. No code.

| Unit | Scope | Decides |
|---|---|---|
| **W3-1** | Present CF-04 as one decision: recover `dispatch/spine/` as the work-item model **and** dispose of `opportunities.py`'s 9 stages | The state-model question, permanently |
| **W3-2** | Present CF-05: does BM-02 hold now that Manager is 866 lines + 790 test lines, wired and passing? | Whether 1,656 lines stay archived |
| **W3-3** | Present R-08: does THE MIKE RULE extend to `dispatch/email_delivery.py` and `dispatch/receipt_vision.py`? | Two modules |

### Wave 4 — Corrective missions on `main`. Unchanged from the baseline.

**W4-1** C1 duplicate mission state · **W4-2** C2a `/calendar` · **W4-3** C4 replay guards (15 sites)
· **W4-4** no-op audit entries · **W4-5** RUN-06 label samples · **W4-6** RUN-07 schema version ·
**W4-7** RUN-08 storage dirs under WSGI.

### Wave 5 — Driver. The reason the program exists.

| Unit | Kind | Scope | Gate |
|---|---|---|---|
| **W5-1** | REPAIR | Fix the four R-01 defects **on a working copy of the branch's four files**, before anything lands: surface refusals (2 sites), scope or remove the unscoped IFTA fuel endpoint, guard `float()` | W2-3, W2-5 |
| **W5-2** | RECOVER | Land `driver_portal.py`, `driver_home.html`, `tests/test_driver_portal.py`, the `dispatch_api.py` delta. **Discard the branch's duplicate PR #111 re-implementation entirely** | W5-1 |
| **W5-3** | REPAIR | Re-run the full suite against `main`; add a test that a **refused** transition shows the driver something | W5-2 |

**W5 is the campaign's purpose.** Everything before it is what makes it safe to land.

### Wave 6 — Post-adjudication recovery and connection.

| Unit | Kind | Scope | Gate |
|---|---|---|---|
| **W6-1** | RECOVER | `dispatch/spine/` + `tests/test_spine.py`, rebased onto today's `main` | **W3-1** |
| **W6-2** | CONNECT/REPAIR | Dispose of `opportunities.py` per W3-1 — map in, adopt with a BM-10 amendment, or revert | **W3-1** |
| **W6-3** | REPAIR | ENG-01 + ENG-02 — kill the optimistic defaults, fix `capacity.py:338` | W3-1 |
| **W6-4** | RECOVER | The 827-line Dynamic Capacity extension incl. the real Stop Sequence model | **W6-3 first** |
| **W6-5** | RECOVER | Archive Review Queue (+334 lines with tests) | Standard review |
| **W6-6** | RECOVER | Portal card levels + Version Doctrine display | Standard review |
| **W6-7** | REPAIR | ENG-03 Route Risk "unknown" not "achievable"; ENG-04 map visual defaults false | None |
| **W6-8** | CONNECT | `reconciliation/` — connect against its now-recovered contract, or archive it | W1-3 |

### Wave 7 — Pilot.

**W7-1** Mike runs one real load end to end and records every point he had to leave Dispatch.
**W7-2** Convert those notes into the next campaign. Nothing beyond this is planned.

## 3. Campaign shape

| Wave | Units | Kind | Blocked by a Mike decision |
|---|---|---|---|
| 0 Delivery | 5 | REPAIR + RECOVER | W0-3, W0-4 |
| 1 Ungated recovery | 3 | RECOVER | — |
| 2 Security | 5 | REPAIR | W2-4 needs U-4 answered |
| 3 Adjudication | 3 | decision only | **all three** |
| 4 Corrective | 7 | REPAIR | W4-2 needs retire-or-rename |
| 5 Driver | 3 | REPAIR + RECOVER | — |
| 6 Recovery/connection | 8 | all three | W6-1 … W6-4 need W3-1 |
| 7 Pilot | 2 | Mike | — |
| **Total** | **36** | | **9 Mike-only decisions** |

## 4. What this campaign deliberately does not do

- Does not merge any repository into another.
- Does not delete anything except `Jules/flask_app.log`, and that only with Mike's word.
- Does not lift BM-02, BM-10, BM-11 or BM-12 — it presents them for decision.
- Does not recover `dispatch/security/`, `dispatch/manager/`, `dispatch_publisher/`,
  `dispatch_library/`, `dispatch_build/`, or the Jules runtime. Each failed an explicit exclusion
  test; reasons are recorded in `DISPATCH_RECOVERABLE_WORK_MATRIX.md` §6 so omission is never
  mistaken for oversight.
- Does not touch the seven uninspected repositories.
- **Does not start.** Wave 0 Unit 1 is a two-minute deletion Mike can authorize in a sentence;
  everything after it waits on W0-2, which only Mike can perform.
