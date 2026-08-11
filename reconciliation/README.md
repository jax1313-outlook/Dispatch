# Reconciliation Adapters (Stage 4)

Per `DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md` (Claude-3 repo) Section 6,
Stage 4: "Build adapters before replacing code."

## What exists here

Pure, read-only translation functions from Dispatch's existing record shapes
(`portal/models/{library,publisher,archive,intelligence}.py`) into the canonical shared-object
shapes defined in `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` (Claude-3 repo):

- `contracts.py` — local dataclasses. `LibraryObject`/`LibraryCandidate` mirror the canonical
  contract field-for-field. `PublisherActionCanonicalView`/`ArchiveRecordCanonicalView` are
  purpose-built read-only views, not literal reconstructions of `DraftReviewPackage`/
  `ArchiveHandoffPackage` — see their docstrings for why forcing that fit would require
  inventing data Dispatch doesn't have.
- `adapters/library_adapter.py` — Dispatch's 6-section Library taxonomy → the canonical
  15-collection taxonomy.
- `adapters/intelligence_adapter.py` — Dispatch's 6 intel types → canonical Library collections
  (not `IntelligenceFinding` — see the module docstring for the reasoning).
- `adapters/publisher_adapter.py` — Dispatch's action-queue records → a canonical-shaped view
  that honestly reports `is_approval_enforced=False` for every record today.
- `adapters/archive_adapter.py` — Dispatch's `publisher`-section archive records → a view with
  `had_verified_approval`, plus `unverified_publisher_archive_count()`, the concrete/countable
  form of Hard Conflict List item 3.

## What does NOT exist here

- No fix to the governance gaps these adapters report on (Stage 5 — Library's auto-approve,
  Publisher's unenforced flag, Archive's missing precondition — none of that is implemented).
- No wiring into `portal/routes/*.py` (Stage 6 — object-flow integration).
- No writes to any Dispatch store. Every adapter function takes plain data in (the dict/list a
  `get_all()`/`get_queue()` call already returns) and returns a dataclass; none of them call
  `_load()`/`_save()` or touch a file.
- No dependency on the tri-department repos' actual Python packages (`dispatch_intel`,
  `dispatch_library`, `dispatch_publisher`) — Dispatch has no mechanism for that today, and
  adding one is a bigger decision than this stage. The dataclasses in `contracts.py` are local
  mirrors, matching the same duck-typed pattern the tri-department Publisher repo already uses
  for its own cross-repo boundaries.

## Running the tests

```bash
python -m pytest tests/test_reconciliation_*.py -v
```

29 tests, all passing as of this stage — see each test file for what's covered.

Mike decides.
