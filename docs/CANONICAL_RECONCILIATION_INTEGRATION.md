# Canonical Reconciliation Integration Branch

Status: Stage 3 of DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1 (Claude-3 repo).
No adapters, no governance-gap fixes, and no object-flow wiring exist on this branch yet.

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

## What has NOT happened on this branch

Per the canonical matrix's own Stage sequencing (Section 6) and "Do Not Touch Yet" list
(Section 7):

- No adapters have been built (Stage 4).
- No governance gaps have been fixed — Library's auto-approve behavior, Publisher's unenforced
  `human_approval_required` flag, and Archive's missing approval-status precondition on
  `archive_publisher_action()` all still behave exactly as documented in
  `DISPATCH_DEPARTMENT_RECONCILIATION_v1.md` (Claude-3 repo) (Stage 5).
- No object-flow wiring exists (Stage 6).
- This branch has not been merged into `main`, and per Stage 7 will not be until the
  reconciliation work here passes tests and Mike approves.

## Reference documents (Claude-3 repo)

- `DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md` — the ratified decision record
- `DISPATCH_DEPARTMENT_RECONCILIATION_v1.md` — the factual audit this matrix was built on
- `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` — the tri-department build's object schemas

Mike decides.
