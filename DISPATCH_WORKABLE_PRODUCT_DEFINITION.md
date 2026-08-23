# DISPATCH_WORKABLE_PRODUCT_DEFINITION

**Phase 12 deliverable — the minimum complete Dispatch that Mike can use in real Level 1 Transport
operations**
**Audit commit:** `37f4fd033e57c55f46dfd0568d3371e8473d683f`

---

## 1. The governing question

Not "what would a complete freight platform have," but: **what does Mike need before he can run one
real load through Dispatch without lying to himself about what the system knows?**

Everything below respects the standing constraints: Outlook remains the scheduling source of truth;
no AI approves, accepts, books, assigns, schedules, or commits work on Mike's behalf; Driver-First
Doctrine and the 70 MPH phone-call test are binding; external systems stay external wheels.

## 2. Tier 1 — Required for first operational use

Mike enters one real load, runs it, delivers it, and bills it. Nothing more.

| # | Requirement | Present today | Gap |
|---|---|---|---|
| T1-1 | The program launches reproducibly **on Mike's machine** and he can log in | Code yes; **never proven on the target** | R-0.3 |
| T1-2 | A load survives a restart | **PROVEN** | — |
| T1-3 | `PORTAL_SECRET_KEY` and `DISPATCH_EMAIL_SECRET` are set, and the app refuses to start without them | Defaults published; warning only | S-1, S-3 |
| T1-4 | Backup and restore, proven once | **MISSING ENTIRELY** | D-1 |
| T1-5 | Operational data is distinguishable from sample and test data | Not distinguishable | D-3, D-4 |
| T1-6 | Status changes are gated and audited | **PROVEN** (M1 + C3) | — |
| T1-7 | Human acceptance authority is enforced | **PROVEN** (`RESERVED_SYSTEM_IDENTITIES`) | — |
| T1-8 | Evidence can be attached and its integrity verified | **PROVEN** | — |
| T1-9 | A rate confirmation, a settlement, and an invoice can be produced | **PROVEN** | — |
| T1-10 | Nothing in the UI presents an unverified value as a fact | **FAILS** — `/calendar` presents a calendar Dispatch must not own; Route Risk reports `delivery_commitment_status: "achievable"` when it has no data | C2a, Phase 8 findings |

**Tier 1 is five items away from done, and every one of the five is small.** None of them is a
feature. They are: prove the launch, refuse weak secrets, back up the data, label the samples, and
stop presenting one unowned surface.

## 3. Tier 2 — Required before broader daily reliance

Mike runs everything through Dispatch instead of alongside it.

| # | Requirement | Status |
|---|---|---|
| T2-1 | Driver Portal supports **proof of pickup and proof of delivery with photos** | **MISSING** — the driver surface has exactly one control, Sign Out |
| T2-2 | Driver can look up a load without calling Mike | **MISSING** — `/search` is Authority-gated |
| T2-3 | Current Mission is presented as *the* mission, not one card among equals | **PARTIAL** |
| T2-4 | Replay guards on the 15 unguarded side-effect sites | **MISSING** (C4) |
| T2-5 | CSRF protection on the 109 mutating routes | **MISSING** (S-4) |
| T2-6 | Session expiry and secure cookie flags | **MISSING** (S-5) |
| T2-7 | Stakeholder links expire and can be revoked | **MISSING** (S-2) |
| T2-8 | Load status has exactly one home | **FAILS** (C1) |
| T2-9 | Schema versioning before the first upgrade over live data | **MISSING** (D-2) |

## 4. Tier 3 — Required before use by another driver

| # | Requirement | Status |
|---|---|---|
| T3-1 | Driver PIN issuance, reset, lockout, recovery | **PROVEN** — already built |
| T3-2 | Per-driver load scoping | **PROVEN** — `list_loads(driver_id=…)` |
| T3-3 | Driver actions are attributable in the audit trail | **PARTIAL** — `_record_status_change` records an actor when one is known; drivers cannot currently act at all |
| T3-4 | Access log for who read or downloaded what | **MISSING** (S-8) |
| T3-5 | Rate limiting on both login surfaces | **MISSING** (S-9) |
| T3-6 | A second driver cannot see the first driver's loads | Implied by T3-2; **no test asserts it** |

## 5. Tier 4 — Required before possible commercial release

Named to keep it out of Tiers 1–3, not to schedule it.

Multi-tenant isolation · encryption at rest for the credential registry (S-6) · a real secrets
manager · production WSGI server (R-3) · TLS termination and security headers · penetration test ·
disaster recovery with RPO/RTO · support and incident process · pricing, billing, terms.

## 6. Tier 5 — Future capability

Outlook two-way integration · live ELD/HOS · live load boards (DAT, TruckSmarter) · GPS tracking ·
weather and traffic feeds · real routing and mileage · map visuals · Dynamic Capacity wired into
scoring and scheduling · the Visual Capacity Board (blocked on Reserve Capacity Doctrine) ·
Revenue Projection · Manager reactivation · full CIN and AZP integration.

**Every item in Tier 5 is currently NOT PRESENT.** That is the correct state for them.

## 7. What must not become a blocker

Per the mission's instruction that commercial scalability must not block Mike's usable system:

- **Dynamic Capacity does not block Tier 1 or 2.** It is unwired, it is unadjudicated, and Mike can
  run loads without it.
- **Outlook integration does not block Tier 1 or 2.** Outlook is already the scheduling source of
  truth by keeping it *outside* Dispatch. Doing nothing here is doctrinally correct.
- **The Manager does not block anything.** It is dormant by standing bar.
- **Reserve Capacity Doctrine blocks only Tier 5 items.**
- **The full Spine Event schema does not block Tier 1 or 2.** C3's activity-based audit already
  satisfies the operational need.

## 8. The honest bottom line

**Dispatch is closer to Tier 1 than it looks and further from Tier 2 than it looks.**

The freight engine — 22,193 lines, 2,817 passing tests, gated transitions, audited status changes,
verified evidence, redacted external views — is genuinely a working system. It is being held out of
operational use by five small items, none of which is a feature: **prove it runs on Mike's machine,
refuse default secrets, back up the data, label the samples, and retire one page.**

Tier 2 is further than it looks because its centrepiece — a driver who can report from the cab —
does not exist at all. The Driver Portal reads; it cannot write. Under Driver-First Doctrine that is
the single most important gap in the program, and it is the one the new Dynamic Capacity work did
not touch.
