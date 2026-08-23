# W0-3 — Portal Adjudication Decision Brief

**Unit:** W0-3 of `DISPATCH_REPAIR_AND_CONNECTION_CAMPAIGN_v1` · **Conflict:** CF-01 (adjacent)
**Decision owner:** Mike Zachary. **No agent may make this call.**
**This brief presents evidence and a recommendation. It does not decide.**

---

## The question, stated narrowly

Two working programs both present themselves as Dispatch. **Which one is the product?**

This is not a question about which is better software. It is a question about **which one you are
going to run your business on**, because maintaining both is what produced the situation the audit
found: two state models, two auth postures, two sets of screens, and no shared tests.

## The two candidates

| | **A · `Dispatch/portal/`** | **B · `Jules/`** |
|---|---|---|
| Repository | `jax1313-outlook/Dispatch` @ `37f4fd0` | `jax1313-outlook/Jules` @ `2aeb2be` |
| Size | 7,832 lines across 8 blueprints | ~620 lines, one `app.py` + one `dispatch_spine.py` |
| Routes | **218** | 13 |
| Screens | 40 Jinja templates | 8 templates |
| Persistence | **SQLite, 26 tables, WAL, foreign keys enforced** | **None.** A module-level singleton seeded by `_bootstrap_sample_data()` |
| Survives restart | **Yes — proven** (W0-2 rehearsal, and `tests/test_route_risk_durability.py`) | **No.** Everything a driver reports is gone on restart |
| Authentication | Fail-closed PIN gate, three disjoint session namespaces, scrypt hashing, lockout | **None on any route** — `/operations`, `/stakeholder`, `/api/v1/*` all open |
| Tests | **2,817 passing**, exit 0 | 1 file, covering its own in-memory app |
| Operational truth | POD upload writes a checksummed file through `attach_evidence()` | POD upload returns `"POD uploaded successfully"` **with no file posted** — `"file_saved": "Simulated upload"` |
| Debug posture | `_debug_enabled()` requires explicit `PORTAL_DEBUG=1` | Ran with the Werkzeug debugger active; its PIN was committed *(removed in W0-1)* |
| Bind default | `127.0.0.1` | `0.0.0.0` |
| Financials, IFTA, settlements, compliance, fleet | **Implemented and tested** | Absent |
| Driver screen quality | Functional, plain, read-only | **Better looking**, cockpit-styled, touch-oriented |

## What each option costs you

### If you choose A (`Dispatch/portal/`)

**You keep:** everything that runs the business — the load lifecycle, gated transitions, audited
status changes, evidence with checksums, rate confirmations, settlements, IFTA, driver pay,
maintenance, compliance, the stakeholder view with its redaction and IDOR check, and 2,817 tests.

**You give up:** nothing that stores data, because B stores none. What is genuinely lost is the
**visual design** of B's driver cockpit and public site — and that can be harvested as templates
without taking B's runtime. Recovering the unmerged Driver Transformation (campaign W5) closes most
of the functional gap anyway; it was built against A, not B.

**Cost to switch:** zero. A is what already runs.

### If you choose B (`Jules/`)

**You keep:** the presentation layer and the public website (`/`, `/about`, `/capabilities`,
`/contact`, positioned as "Jacksonville Regional Micro-Response Carrier").

**You give up, and would have to rebuild:** 26 database tables, the entire financial and IFTA
stack, authentication, evidence integrity, the transition gate, the audit trail, and 2,817 tests.

**Cost to switch:** rebuilding Dispatch. B has no persistence layer to add durability to and no auth
layer to harden — retrofitting either means writing A again.

### If you choose "both"

This is the status quo, and it is what the audit was called in to explain. It has already produced
four empty commits merged as delivered work, a driver feature built twice and delivered zero times,
and a committed debugger PIN. **Recommend against explicitly.**

## Recommendation

**Option A — `Dispatch/portal/` is Dispatch.** `Jules/` becomes a read-only design archive.

The evidence is one-sided on every axis that matters for running freight: persistence,
authentication, operational truth, and test coverage. The one axis where B wins — how the driver
screen looks — is transferable without taking anything else, and is worth transferring.

**This recommendation is not a decision.** If you want B's presentation to become Dispatch's, that
is a legitimate and different instruction: *keep A's engine, adopt B's visual language.* Say so and
it becomes a scoped design mission rather than a repository choice.

## The one thing to check before you decide

**Which one have you actually been opening?** The audit found `Jules/flask_app.log` recording real
browser sessions on 2026-08-18 across `/driver`, `/operations`, `/stakeholder` and `/`. If B is what
you have been showing people or clicking through, say so — it changes nothing about the
recommendation, but it means expectations have been set against a program that stores nothing, and
that is worth knowing before the first real load is entered.

## What happens after each answer

| Your answer | Immediate consequences |
|---|---|
| **A** | `Jules/` marked archive, read-only. Its design is harvested in a later, separate mission. W0-4 (governance home) proceeds against Dispatch. Campaign W5 recovers the Driver Transformation into A. |
| **B** | The campaign stops and is rewritten. Every W-unit assumes A. A migration mission is scoped first. |
| **A, but adopt B's look** | Same as A, plus one scoped design mission after W5. **Recommended if B's cockpit is what you want to drive.** |
| **Defer** | W0-4 and everything after it stay blocked. Two portals continue to diverge. |

## What Mike needs to record

W0-3 is complete when a line in your own words exists in `DECISION_LOG.md`. Something of this shape
is enough — but the words must be yours, and no agent may write them for you:

> **W0-3 — Portal adjudication.** *[Dispatch/portal/ | Jules/]* is Dispatch. The other is archived
> read-only and is not maintained. *[Optionally: its presentation design may be harvested into
> Dispatch in a separate mission.]* — Mike Zachary, *[date]*

Once that line exists, tell me and I will land it as the `DECISION_LOG.md` entry, unblocking W0-4.

---

## Evidence index

| Claim | Where to check |
|---|---|
| B stores nothing | `Jules/dispatch_spine.py:183` `_bootstrap_sample_data()`; `grep -nE "sqlite|json.dump|open\(" app.py dispatch_spine.py` → 0 matches |
| B has no authentication | `grep -cin "session|login|auth|token|password" Jules/app.py` → 3, all incidental |
| B reports uploads that did not happen | `Jules/app.py:148-167` |
| B bound to `0.0.0.0` | `Jules/run_portal.sh:10` |
| A fails closed | `portal/app.py::_require_authority_login`; verified live in the W0-2 rehearsal — 302 → `/login` |
| A persists across restart | W0-2 rehearsal: `LOAD-20260823-4941E243` survived a genuine process restart |
| A's test count | `2817 passed in 314.87s`, exit 0 |
| A's route count | 218 across 8 blueprints |
| The Driver Transformation was built against A | `origin/jules-driver-transformation-missions-1-4-…` @ `afd6e00` — modifies `portal/routes/driver_portal.py`, not Jules |
