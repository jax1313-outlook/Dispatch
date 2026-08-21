# MA_ATOMIC_STORE_WRITES_WALKTHROUGH_REPORT_v1

## Atomic JSON Store Writes

**Status:** Implemented and verified. Branch: `claude/dispatch-repo-context-reconcile-7mblbb`.

**Mission:** M-A of `DISPATCH_BUILD_MATRIX_v1` (Level 1 — defect).

**Closes:** B-20 in `DISPATCH_REPO_RECONCILIATION_PLAN_v1`.

---

## The defect

Every JSON store in the repository does read-modify-write: `_load()` reads the whole file, the
caller mutates it, `_save()` writes it all back. All twelve `_save()` functions were the identical
line:

```python
path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
```

`write_text()` truncates the file and *then* writes. A power cut, an OOM kill, or a full disk
between those two steps leaves a half-written JSON file — and every subsequent `_load()` raises
`JSONDecodeError`. The failure mode is not "one lost record"; it is **"this store is now
unreadable"**, taking the whole record set with it.

This matters directly to the shutdown work: any function claiming to "finish local writes safely"
was claiming something the JSON layer could not deliver. The SQLite side never had this problem —
it is transactional, WAL-journaled, and commits or rolls back per operation (`dispatch/db.py:463-477`).

Affected stores: `archive`, `completion_packet`, `conflict`, `driver_pin_registry`, `email_helper`,
`identity`, `integrations_registry`, `intelligence`, `library`, `publisher`, `sandbox` (all under
`portal/models/`), plus `dispatch/email_helper.py`.

## What changed

1. **`portal/models/__init__.py`** — new `atomic_write_json(path, data)`. Writes to a temporary file
   in the **same directory**, `flush()` + `fsync()`, then `os.replace()`. `os.replace` is atomic on
   both POSIX and Windows; same-directory matters because the guarantee only holds within one
   filesystem. On any failure — including `KeyboardInterrupt` — the scratch file is removed and the
   exception re-raised, so a `.tmp` never lingers in a directory that gets read.
2. **The eleven `portal/models/*.py` stores** — each `_save()` now calls it. No schema change, no
   data-shape change, no read-path change.
3. **`dispatch/email_helper.py`** — the same routine inlined locally, **deliberately not imported
   from `portal`**.

## Design decision, stated as an assumption (BM-08)

**Why `dispatch/email_helper.py` duplicates instead of importing.** That module's own docstring says
it is a *"Local Dispatch copy, duplicated to enforce standalone ownership under THE MIKE RULE"*, and
it already duplicates `RESERVED_SYSTEM_IDENTITIES` for the same reason. Importing
`portal.models.atomic_write_json` would have given `dispatch/` a hard dependency on `portal/` that it
does not currently have and that THE MIKE RULE exists to prevent. A ~15-line duplication with a
comment explaining why is the lesser cost, and it matches an explicit precedent. A test asserts
`dispatch/email_helper.py` contains no `import portal`, so a future refactor cannot quietly couple
them.

The alternative — a new shared utility module — was rejected under **BM-01**: a new module is an
architectural change needing its own review, and `portal/models/__init__.py` already exists and
already holds the shared path helpers (`get_data_dir`, `get_memory_dir`, `get_archive_dir`).

## What this does NOT fix, stated plainly

**Concurrency.** Two writers doing read-modify-write against the same store still lose one update —
the last `os.replace()` wins. Locking is a separate and larger question and is deliberately not
attempted here.

This limit is not merely documented, it is **tested**: `test_last_writer_wins_on_a_lost_update`
asserts the lost update explicitly. If locking is ever added, that test fails and forces the
docstrings that state the limit to be corrected at the same time. The point is that nobody reads
"atomic" as more safety than it provides.

## Automated test results

Full suite: `python -m pytest` — **2771 passed**. 18 new tests in
`tests/test_atomic_store_writes.py`:

- **The helper** — readable JSON, parent directories created, complete overwrite of longer prior
  content, no temp files left on success, unicode preserved.
- **Crash safety** (the point of the mission) — previous content survives a failed `os.replace`; no
  temp file left behind after a failure; unserializable data raises partway through `json.dump` and
  the original store is still intact and parseable. Under the old `write_text()` every one of these
  left a truncated file.
- **Structural guards** — no file in `portal/models/` still contains the truncating pattern (so a
  store added later cannot silently reintroduce it); `dispatch/email_helper.py` uses `os.replace`
  and imports nothing from `portal`.
- **Real stores round-trip** — conflict, publisher, completion packet, sandbox, and the dispatch
  email helper, plus a ten-cycle read-modify-write loop.
- **The stated limit** — the lost update, asserted.

## Boundaries observed

No new module, no new store, no schema change, no data migration, no behavior change — the same
bytes land in the same files by a safer route. Manager untouched. No calendar. No source-of-truth
moved: every store still belongs to the element that already owned it. No judgment added anywhere.
