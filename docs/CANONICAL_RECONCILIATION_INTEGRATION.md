# Canonical Reconciliation Integration Branch — Finalized as the Approval Chain Safety Gate Fix

**Status: FINALIZED at this scope.** Mike reviewed Stage 5 items 1-3 and approved them as the
complete deliverable for this branch under the name **Approval Chain Safety Gate**. Items 4 and
5 are explicitly out of scope here and have been spun out as separate future missions — see
"What has NOT happened on this branch" below. This branch is not to be expanded beyond items 1-3
without a new, separate scoping decision.

## Architecture note (the rule this branch establishes)

> Human-submitted Library material may be trusted because the human chose to store it.
> Machine-submitted Library candidates require review.
> Publisher actions require real external approval before APPROVED status.
> Archive must not close or preserve Publisher actions without a valid approved_by record.

This branch is a safety-gate correction, not an archive refactor or cross-subsystem integration
build.

## What this branch is for

Per `DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md` (Claude-3 repo) Section 6,
this is the staging branch for reconciling Dispatch's existing `cin_lite/`/`dispatch/`/`portal/`
implementations with the tri-department build's Intelligence/Library/Publisher repos, per the
canonical winners declared in that document's Section 3:

- Intelligence: tri-department wins as canonical object producer
- Library: tri-department wins on governance (candidate review, versioning); Dispatch's
  6-section taxonomy is adapted, not discarded
- Publisher: hybrid — tri-department governs (readiness/review/approval), Dispatch's
  `cin_lite/agents/proposal_writer.py` drafts content
- Archive: Dispatch's `cin_lite/archive.py` wins as the canonical, hash-verified archive engine
- Portal: Dispatch Portal remains the canonical presentation layer

## What HAS happened on this branch (Stage 4)

`reconciliation/` — pure, read-only adapter functions translating Dispatch's existing
`portal/models/{library,intelligence,publisher,archive}.py` records into the canonical
shared-object shapes from `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md`. No file I/O, no writes back
to any Dispatch store, no wiring into any route. See `reconciliation/README.md` for the full
breakdown and `tests/test_reconciliation_*.py` (29 tests) for coverage. Notably, the Publisher
and Archive adapters make the exact gaps in Hard Conflict List items 2 and 3 inspectable and
countable (`publisher_adapter.would_pass_tri_department_gate()`,
`archive_adapter.unverified_publisher_archive_count()`) without changing any of that behavior.

## What HAS happened on this branch — the Approval Chain Safety Gate fix

Corresponds to Stage 5 items 1-3 of the original canonical matrix's priority order, now
finalized as this branch's complete scope:

1. **Library candidate approval gate** — `portal/models/library.py::add_record()` gained a
   `submitted_by` parameter. `submitted_by="human"` (the default, and the only value the
   existing UI route ever passes) keeps today's behavior exactly: immediate `status="approved"`.
   `submitted_by="machine"` starts `status="pending_review"` and can only be promoted via the
   new `review_candidate()`, which requires a real, external, non-system `reviewed_by` identity.
   `get_available_company_assets()` now excludes non-approved records. New route:
   `POST /api/library/review`. Nothing in Dispatch calls `add_record(..., submitted_by="machine")`
   yet — this closes a latent gap before anything machine-driven exists to hit it.
2. **Publisher approval enforcement** — `portal/models/publisher.py::update_action_status()`
   gained an `approved_by` parameter, validated (real, external, non-system identity) only for
   the `APPROVED` transition. `PENDING`/`DRAFT`/`READY`/`ARCHIVED` transitions are unaffected.
   `POST /api/publisher/update` now accepts and threads through `approved_by`.
3. **Archive approval precondition** — `portal/models/archive.py::archive_publisher_action()`
   now refuses to archive an action with no valid `approved_by` recorded. Checks `approved_by`
   rather than `status`, because by the time this function runs the caller has already
   transitioned `status` to `"ARCHIVED"` — see the function's docstring for why a naive
   `status == "APPROVED"` check would be wrong.

10 new test functions added to `tests/test_portal.py`, covering the Library machine-candidate
gate, Publisher approval enforcement, and Archive approval precondition (`git diff --stat main
-- tests/test_portal.py`: +141/-2 lines). Three pre-existing tests had their bodies updated for
the new behavior — one of them
(`test_publisher_archive_on_status_change`) previously asserted the exact forbidden path (archive
with no approval ever recorded) as passing behavior; it's now split into a legitimate-path test
and a dedicated `test_publisher_cannot_archive_without_approval` regression test.

## What has NOT happened on this branch (and will not happen here)

- **Item 4 (Archive duplication resolution)** — downgrading `portal/models/archive.py` to an
  adapter/view. Changes behavior for *every* archive section (`load`, `decision`,
  `location_history`, `broker_history`), not just the `publisher` section items 1-3 touched, and
  has real existing callers (`archive_from_sandbox()`, `sandbox.py`, `conflict.py`) whose impact
  needs its own investigation. Spun out as a separate **Archive Architecture Review** mission —
  see `DISPATCH_ARCHIVE_ARCHITECTURE_REVIEW_MISSION_v1.md` (Claude-3 repo). Planning only, not
  yet a scoped implementation task.
- **Item 5 (Proposal writer under Publisher governance)** — means relating two
  currently-independent subsystems (`cin_lite`'s email-decision flow and `portal`'s
  action-queue flow) — a design decision, not a patch. Spun out as a separate
  **Integration Bridge** mission — see `DISPATCH_INTEGRATION_BRIDGE_MISSION_v1.md` (Claude-3
  repo). Planning only, not yet a scoped implementation task.
- No object-flow wiring exists (Stage 6 of the original canonical matrix — also out of scope for
  this finalized branch).
- This branch has not been merged into `main`. Merging is Mike's decision, made separately from
  this branch's finalization at the Approval Chain Safety Gate scope.

## Reference documents (Claude-3 repo)

- `DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md` — the ratified decision record
- `DISPATCH_DEPARTMENT_RECONCILIATION_v1.md` — the factual audit this matrix was built on
- `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` — the tri-department build's object schemas
- `DISPATCH_ARCHIVE_ARCHITECTURE_REVIEW_MISSION_v1.md` — future work package for item 4
- `DISPATCH_INTEGRATION_BRIDGE_MISSION_v1.md` — future work package for item 5

Mike decides.
