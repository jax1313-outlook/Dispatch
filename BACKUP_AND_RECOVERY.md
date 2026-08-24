# Backup and Recovery

Dispatch keeps the business in four places at once, and until now nothing tied
them together. A disk failure lost all four.

| What | Where it lives | Lost without a backup |
| --- | --- | --- |
| Operational database | `dispatch.db` in the portal data dir | Every load, milestone, evidence row, settlement, IFTA record |
| Portal JSON stores | `*.json` in the portal data dir | Conflict notices, publisher queue, completion packets, sandbox |
| Evidence uploads | `PORTAL_UPLOAD_DIR` (or `<memory root>\Evidence`) | Signed BOLs and PODs — the documents that get invoices paid |
| Archive / Library / Memory | `DISPATCH_ARCHIVE_ROOT`, `DISPATCH_MEMORY_ROOT`, CIN archive tree | Archived records, approved library assets, intelligence output |

`scripts/dispatch_backup.py` captures all four into one verifiable archive, and
restores them onto a clean machine.

---

## Taking a backup

```
python3 scripts/dispatch_backup.py backup D:\Backups
```

This writes `D:\Backups\dispatch-backup-<UTC timestamp>\` containing the data
plus a `manifest.json`. Add `--compress` for a single `.tar.gz` instead of a
directory (easier to move to off-site media; both forms are accepted by `verify`
and `restore`).

Add `--dry-run` to see exactly what would be captured — every source, every file
count, every byte — without writing anything.

**Read the exit code.** It is the whole point of running this on a schedule:

| Code | Meaning |
| --- | --- |
| 0 | Every configured source was captured |
| 2 | The backup ran, but at least one configured source was missing |

Exit code 2 is the failure this tool exists to prevent. It means a directory the
system is configured to use was not there — usually because an env var changed
and part of the estate quietly moved out from under the backup. The manifest
records the absent source and the reason; the run also prints it to stderr. Do
not treat a code-2 run as a backup.

### Scheduling

Run it nightly, to a disk that is not the disk Dispatch runs on. On Windows,
Task Scheduler; on a VPS, cron:

```
0 2 * * *  cd /srv/dispatch && python3 scripts/dispatch_backup.py backup /mnt/backup >> /var/log/dispatch-backup.log 2>&1
```

Keep the env vars the application runs with in the scheduled job's environment.
The backup resolves every source through the *same* functions the application
does, so a job that runs with different env vars backs up a different estate.

---

## Verifying a backup

```
python3 scripts/dispatch_backup.py verify D:\Backups\dispatch-backup-20260823T020000Z
```

This recomputes the SHA-256 of every file and compares it against the manifest.
Exit code 0 means every hash matched; 1 means something is missing or altered.

Verify at least the most recent backup after every scheduled run, and verify any
backup before you rely on it. An unverified backup is an assumption.

---

## Restoring

```
python3 scripts/dispatch_backup.py restore D:\Backups\dispatch-backup-20260823T020000Z D:\Restored
```

The restore refuses to run if the destination already contains anything. That is
deliberate — restores happen under pressure, from a shell, with a path that may
have been typed rather than pasted. Use `--force` only when you intend to
overwrite what is already in the destination.

Every hash is checked *before* a single byte is written. If the archive fails
verification, nothing is written at all and the command exits non-zero. A
half-restored estate looks like data, which is worse than a refused restore.

Exit codes: `3` = destination not empty, `4` = archive failed verification.

Use `--dry-run` to see the file list and the env vars a real restore would
produce, without writing anything.

### After the restore

The restored tree is inert until something points at it. The command prints the
exact variables to set — for example:

```bat
set PORTAL_DATA_DIR=D:\Restored\PortalData
set PORTAL_UPLOAD_DIR=D:\Restored\Memory\Evidence
set DISPATCH_MEMORY_ROOT=D:\Restored\Memory
set DISPATCH_ARCHIVE_ROOT=D:\Restored\ArchiveRecords
set DISPATCH_ARCHIVE_PATH=D:\Restored\CIN
python portal/app.py
```

The restored layout reproduces the topology of the estate that was backed up. If
the source had several roots collapsed onto one directory (the default install,
where the archive and memory roots both fall back to the portal data dir), the
restore prints several variables pointing at the same restored directory — that
is correct and preserves the original arrangement.

**Evidence file paths are repointed automatically.** The database stores the
absolute path of every uploaded file. A restore moves those files, so `restore`
rewrites the affected rows (`evidence`, `ifta_fuel_evidence`, `pod_packages`) to
the restored locations. Without that pass the database would come back intact and
every download link in it would be dead. The command reports how many rows it
repointed.

**Secrets are not in the archive and must be re-supplied by hand.** See below.

---

## Secrets

Nothing whose name contains `SECRET`, `KEY`, `PASSWORD`, `TOKEN` or `CREDENTIAL`
is ever written into a backup. Backup media travel, get copied, and end up in
places live configuration never goes.

What the manifest *does* record is the **names** of the `DISPATCH_*` and
`PORTAL_*` variables that were set, so a recovery operator knows precisely what
must be re-supplied. Credential-shaped names appear with the value
`<redacted, not exported>`; non-secret values (paths, hostnames, the reviewer
address) are recorded in full.

To see what a given backup expects:

```
python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['environment'])" \
    D:\Backups\dispatch-backup-20260823T020000Z\manifest.json
```

Re-supply the redacted values from your password manager before starting the
portal. `PORTAL_SECRET_KEY` in particular: leaving it unset invalidates existing
sessions and makes the portal print a warning at startup.

---

## What the manifest contains

`manifest.json` sits at the root of every archive and is the record of what was
captured:

- `tool_version`, `manifest_version`, and the UTC `created_at` time.
- `sources[]` — every configured root, the env vars that point at it, its
  position inside the archive, and whether it was `present` (with a `reason`
  when it was not).
- `files[]` — for every file: its archive-relative path, byte size, SHA-256, the
  source it came from, and the absolute path it was read from.
- `database` — the archive path of the snapshot, the full schema DDL, and a row
  count per table. The counts are read from the *snapshot*, not the live
  database, so they describe what is actually in the archive.
- `absent[]` — anything configured but missing, repeated here so it cannot be
  overlooked.
- `environment` — the configuration described above.
- `notes[]` — anything skipped and why (symlinks, in-flight temp files, the
  database's WAL sidecars).

## Why the database is not just copied

`dispatch/db.py` opens the database in WAL mode, so at any instant the committed
truth is split between `dispatch.db` and `dispatch.db-wal`. Copying the file
alone captures a torn database that silently loses the most recent commits — and
it looks fine until the day you need it. The backup uses SQLite's own
`Connection.backup()`, which takes a transactionally consistent snapshot of a
live database, and it deliberately excludes the `-wal`/`-shm`/`-journal` files
from the file walk so they cannot be mistaken for the real thing.

## Testing your recovery

A backup you have never restored is a hypothesis. Once a quarter:

1. Take a backup and `verify` it.
2. Restore it to a scratch directory.
3. Start the portal against the restored env vars.
4. Open a recent load and download its evidence file.

`tests/test_backup_restore.py` does exactly this on every test run — it seeds
real data, backs it up, deletes the live estate, restores, and reads the records
and the evidence bytes back through `dispatch.services`.

## Limits

- Backups are **cold-consistent**, not point-in-time across all four stores. The
  database snapshot is internally consistent; a JSON store written in the same
  second the walk passed it may be captured before or after that write. Run
  backups when the operation is idle where possible.
- Symlinks are recorded and skipped, never followed.
- The archive is not encrypted. If the backup destination is removable or
  off-site media, use disk-level encryption on that media.
