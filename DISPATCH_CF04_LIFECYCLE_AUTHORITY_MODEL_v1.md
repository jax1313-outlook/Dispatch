# DISPATCH_CF04_LIFECYCLE_AUTHORITY_MODEL_v1

**CF-04 — ADJUDICATED by Mike Zachary, 2026-08-23.**
Supersedes the open framing in `DISPATCH_CONFLICT_AND_AUTHORITY_REGISTER.md` and in
`DISPATCH_RECOVERY_WAVE_1_REPORT.md`, both of which put CF-04 as *"Spine versus Opportunity."*
**Mike's ruling rejects that framing.** They are not competitors; they are different offices.

---

## 1. The ruling, verbatim

> This is not a Spine-versus-Opportunity decision.
>
> Dispatch Spine shall become the authoritative lifecycle engine and single source of lifecycle truth.
>
> Dispatch Opportunity shall remain the authoritative opportunity-analysis, scoring, Dynamic Capacity,
> Scheduler, Route Risk, Special Requirements, and decision-support subsystem.
>
> Opportunity recommends.
>
> Spine records reality.
>
> Opportunity may request transitions.
>
> Spine owns transitions.
>
> Opportunity may not maintain a competing lifecycle authority.
>
> Scheduler, Dynamic Capacity, Route Risk, and Intelligence remain advisory systems and do not become
> lifecycle authorities.

## 2. The model

```
   INTELLIGENCE ─┐
   ROUTE RISK   ─┤
   DYNAMIC CAP  ─┼─► OPPORTUNITY ──── requests ────► SPINE ────► recorded reality
   SCHEDULER    ─┤   (recommends)   a transition   (owns the      (work_items,
   SPECIAL REQS ─┘                                  transition)    events, approvals)
        advisory              never writes state           │
                                                           └─► WAITING_FOR_MIKE ─► MIKE_APPROVED
                                                                   human authority
```

**Four rules, derived directly from the ruling:**

| # | Rule | Consequence in code |
|---|---|---|
| **L-1** | Spine is the **single source of lifecycle truth** | Exactly one module may compute a lifecycle transition, and exactly one may persist it |
| **L-2** | Opportunity **recommends** and **may request** | Opportunity produces a *requested* transition; it never mutates lifecycle state |
| **L-3** | Opportunity **may not maintain a competing lifecycle authority** | No second state list, no second transition table, no second stored `stage` that is authoritative |
| **L-4** | Scheduler, Dynamic Capacity, Route Risk, Intelligence are **advisory** | They may score, warn, refuse-to-recommend and raise. They may not decide, and they may not assert a verified fact they did not observe |

**The ruling is already half-implemented, correctly.** `dispatch/spine/state.py`'s own docstring
states L-1 as its design contract, written before the ruling existed:

> *"`transition()` is the only function that may compute a work item state change.
> `dispatch.spine.store.apply_transition()` is the only function that may persist one… No other code
> path may write `work_items.current_state` directly; a structural test guards this."*

That is L-1, enforced by a structural test, on an unmerged branch.

## 3. Where the two lifecycles meet

Spine's 25 states (Spine Specification §7, implemented verbatim) against Opportunity's 9 stages:

| Opportunity stage | Spine state(s) | Verdict |
|---|---|---|
| `Discovered` | `CREATED` → `VALIDATION_PENDING` | Direct map |
| `Analyzed` | `VALIDATED`, or `COGNITIVE_REVIEW_COMPLETE` | Direct map |
| `Scored` | `SCORING_PENDING` → `SCORED` | Direct map |
| `Filtered` | **none** | **Not a state.** Filtering is a *query over scores*, not a lifecycle position. It should never have been a stage. |
| `Presented` | `PORTAL_CARD_PENDING` → `PORTAL_CARD_CREATED` → `WAITING_FOR_MIKE` | Direct map, and Spine's version is richer |
| `Selected` | `MIKE_APPROVED` | Direct map — and **Spine already models the human gate properly**, with `approval_events` carrying actor, action and object |
| `Committed` | `MIKE_APPROVED` + the Load record | Direct map |
| `Calendar Event` | **none** | **Cannot be a Spine state.** Outlook is the scheduling source of truth and is external; there is no integration in any repository. A calendar event is an *external side effect of an approval*, not a lifecycle position. |
| `Current Reality` | `COMPLETED`, with `loads.status` carrying execution | Direct map |

**Seven of nine map cleanly. The two that do not — `Filtered` and `Calendar Event` — are exactly the
two that were never lifecycle states to begin with.** That is strong corroboration of the ruling:
Opportunity's stage list was a *pipeline narrative* wearing a state machine's clothes.

## 4. What in `dispatch/opportunities.py` is a competing lifecycle authority

Precise, by line. All of it is currently unwired, so none of it is live — which is the only reason
this is alignment work rather than an incident.

| # | Surface | Lines | Why it violates L-3 |
|---|---|---|---|
| A-1 | `OPPORTUNITY_LIFECYCLE_STAGES` | 25–35 | A second state list |
| A-2 | `ALLOWED_LIFECYCLE_TRANSITIONS` | 37–47 | A second transition table — a second gate |
| A-3 | `OpportunityCard.stage` | 87 | A second stored lifecycle position, treated as authoritative |
| A-4 | `OpportunityCard.transition_to()` | 111–131 | **The authority itself.** Validates a transition and mutates state. Under L-1 only `spine.state.transition()` may compute this, and only `spine.store.apply_transition()` may persist it |
| A-5 | `__post_init__` stage validation | 102–103 | Enforces the second state list at construction |
| A-6 | Auto-advance inside analysis | 182, 216, 252 and 254 | `analyze_opportunity`, `score_opportunity` and `filter_and_present` **advance the lifecycle as a side effect of thinking about it.** Under L-2 analysis recommends; it does not move anything |
| A-7 | `commit_opportunity_to_reality()` | 261–297, transitions at 268–272 | The sharpest violation: it walks four stages in a row (`Selected → Committed → Calendar Event → Current Reality`), then **creates the Load and confirms the rate itself**. Opportunity writing reality directly is precisely what L-1 forbids |
| A-8 | Human-authority rule inside `transition_to` | 124–129 | Correct rule, wrong office. `Committed` requiring a human actor belongs at Spine's `WAITING_FOR_MIKE → MIKE_APPROVED` gate, which records an `ApprovalEvent` with actor, role and object — strictly better than a string on a dataclass |

**Nothing in A-1…A-8 is bad work.** It is well-formed and carefully tested. It is in the wrong
office, and the ruling names which office it belongs to.

## 5. Recovery work to align Opportunity with Spine authority

Nine units. **None is authorized by this document** — it identifies the work, as instructed.
Dependencies are real, not stylistic.

### Gate: SPINE-R · Recover `dispatch/spine/`
Measured in the Wave 1 report: 835 lines, 23 tests, **zero defects, zero conflicts, five hand-written
lines** to wire (`init_spine_schema` in `_init_db`, splitting the branch's hunk to drop the excluded
security import). **2,840 passed, exit 0** in trial. **Every unit below depends on this.** Under the
ruling this is no longer a question — Spine is the lifecycle engine, so it must exist.

### OPP-01 · Delete the second gate
Remove `ALLOWED_LIFECYCLE_TRANSITIONS` and `transition_to()`. **Do not preserve them as "internal
only"** — a second gate that is merely private is still a second gate. *Depends: SPINE-R.*

### OPP-02 · Make `stage` a read-through, not a store
`OpportunityCard.stage` becomes a **projection of the linked work item's Spine state**, resolved via
a correlation key, exactly as C1 resolves the sandbox's duplicate load status. **BM-11 still holds:
correlation, not identifier migration.** *Depends: OPP-01.*

### OPP-03 · Turn auto-advance into a requested transition
`analyze_opportunity`, `score_opportunity` and `filter_and_present` stop moving anything. Each
returns its finding plus, where appropriate, a **requested** transition for Spine to accept or
refuse. **`Filtered` disappears entirely** — it is a query, and §3 shows it was never a state.
*Depends: OPP-01, OPP-02.*

### OPP-04 · Route commitment through Spine's human gate
`commit_opportunity_to_reality()` becomes a **request**. Spine moves `WAITING_FOR_MIKE →
MIKE_APPROVED`, records the `ApprovalEvent`, and only then is the Load created. The human-authority
rule moves from a string check to Spine's approval record — **a strengthening, not a loss**.
*Depends: SPINE-R, OPP-01. **Also needs Mike's answer to §7.***

### OPP-05 · Remove `Calendar Event` from the lifecycle
It is an external side effect of an approval, and Outlook remains the scheduling source of truth.
Under BM-03 and the standing Outlook boundary, **no calendar is created here.** *Depends: OPP-01.*

### OPP-06 · Structural test: one lifecycle authority
A test that fails if any module outside `dispatch/spine/` defines a lifecycle state list, a
transition table, or writes a lifecycle state — the same shape as the structural test M-A already
uses to forbid bare `write_text`, and the one Spine's own docstring says guards
`work_items.current_state`. **This is what makes L-3 enforceable rather than aspirational.**
*Depends: OPP-01…OPP-05.*

### OPP-07 · Hold the advisory line in Dynamic Capacity
L-4 says Dynamic Capacity is advisory and may not assert facts it did not observe. Three defects
already identified block this and are **still present** in the unmerged 827-line extension:
`apply_asset_profile(verified_by="Mike Zachary")` stamping Mike as verifier by default;
`set_verified_hos(source="ELD_LOG")` naming an integration that exists nowhere; and
`capacity.py:338` returning **feasible** for a STALE asset configuration. These are audit findings
ENG-01 and ENG-02. *Independent of SPINE-R; blocks the capacity extension recovery.*

### OPP-08 · Hold the advisory line in Route Risk
Already advisory and honest — every event carries `is_live_data: False`. Two audit items remain:
the no-data path reports `delivery_commitment_status: "achievable"` (an unknown presented as a
positive commitment, ENG-03) and `has_map_visual` defaults `True` (ENG-04). *Independent.*

### OPP-09 · Record the ruling against BM-10
`DISPATCH_BUILD_MATRIX_v2` BM-10 forbids a third state authority and says the load-status and
work-item models coexist. The ruling **refines** it: Spine is the lifecycle authority; Opportunity
holds none. BM-10 is not repealed — it is satisfied, by removing the third model rather than by
blessing it. *Documentation only.*

## 6. Sequence

```
SPINE-R ──► OPP-01 ──► OPP-02 ──► OPP-03 ──► OPP-06 (the structural lock)
                 │                     
                 ├──► OPP-04  (needs §7 answered)
                 └──► OPP-05

OPP-07, OPP-08, OPP-09  — independent, may run in parallel
```

**OPP-06 last, deliberately.** Locking the rule before the violations are removed would fail the
suite; locking it after is what stops this recurring.

## 7. The one question the ruling does not settle — **needs Mike**

**Does "single source of lifecycle truth" absorb `loads.status`?**

Dispatch has two lifecycles today, on different subjects:

- **`loads.status`** — 11 values, gated by `_VALID_TRANSITIONS`, audited by `_record_status_change()`,
  covering **freight execution**: created → dispatched → en route → picked up → delivered → archived.
  It is live, wired, and behind roughly 1,800 tests.
- **Spine work-item state** — 25 values covering **review, routing, approval and decision**.

Two readings of the ruling:

| | **Reading A — narrow (recommended)** | **Reading B — broad** |
|---|---|---|
| Scope of "lifecycle" | The **review/decision lifecycle**. Spine is its single authority. `loads.status` remains the freight-execution record and is untouched. | **Everything**, including freight execution. `loads.status` becomes a projection of Spine state. |
| What OPP-01…OPP-06 cost | What is scoped above | The above **plus** a migration touching `services.py`, `store.py`, `db.py`, every status route and roughly 1,800 tests |
| Consistency with prior adjudication | **Consistent.** The 2026-08-21 adjudication settled that the two models coexist on different subjects, and BM-10 protects both | **Supersedes** that adjudication and reopens BM-10 and BM-11 |
| Risk | Low. Additive. | High. The largest change ever proposed to this program, over the only part of it that is genuinely production-capable |

**Recommendation: Reading A.** The ruling's own words support it — *"Spine records reality"* and
*"Opportunity may not maintain a competing lifecycle authority"* are aimed at **Opportunity's**
stage machine, which is the thing that exists in duplicate. `loads.status` is not a competing
authority; it is a different subject, and it is the one part of Dispatch that has never been in
doubt.

**Nothing in §5 is blocked by this question except OPP-04**, which has to know whether creating a
Load is Spine recording reality (A) or Spine *becoming* the load record (B).

## 8. What this changes elsewhere

| Document | Change |
|---|---|
| `DISPATCH_CONFLICT_AND_AUTHORITY_REGISTER.md` | CF-04 marked **ADJUDICATED**, framing corrected |
| `DISPATCH_RECOVERY_WAVE_1_REPORT.md` | Its CF-04 gate is now satisfied for the Spine; the "one decision, not two" framing is superseded by the ruling, which answers both halves at once |
| `DISPATCH_BUILD_MATRIX.md` | BM-10 refined, not repealed (OPP-09) |
| `DISPATCH_REPAIR_AND_CONNECTION_CAMPAIGN_v1.md` | W3-1 is answered. W6-1 (recover Spine) and W6-2 (dispose of `opportunities.py`) are now specified rather than open |
