"""Canonical reconciliation package (Stage 4).

Per DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md (Claude-3 repo), Stage 4:
"Build adapters before replacing code."

Everything in this package is read-only and additive:

- No function here writes to any of Dispatch's existing JSON stores
  (`portal/models/*.py`'s `_save()` calls are never invoked from here).
- No existing Dispatch file is imported for its side effects, only its public read functions
  (`get_all()`, `get_queue()`, `list_contracts()`, etc.).
- Nothing here is wired into `portal/routes/*.py` yet -- that is Stage 6 (Integrate object flow),
  a separate, not-yet-authorized step.
- Nothing here fixes the governance gaps documented in `DISPATCH_DEPARTMENT_RECONCILIATION_v1.md`
  (Library's auto-approve, Publisher's unenforced approval flag, Archive's missing
  approval-status precondition) -- that is Stage 5, also separate.

`contracts.py` defines local dataclasses that mirror `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md`
field-for-field, the same "duck-typed, no hard package dependency" pattern the tri-department
Publisher repo already uses for its own Library/Intelligence integration boundaries
(`dispatch_publisher/library_client.py`, `dispatch_publisher/intelligence_client.py`) -- Dispatch
has no dependency mechanism for the tri-department repos' actual Python packages, and adding one
is a bigger decision than "build adapters."
"""
