# Dispatch — Maintenance Guide

**For:** whoever keeps Dispatch alive between missions. **Current as of:** 2026-08-25.

Day-to-day operation is `docs/operations/DISPATCH_OPERATOR_GUIDE.md`. This document covers
what you do **occasionally** and must not get wrong: backups, restores, the database,
secrets, logs, upgrades, and moving Dispatch to another machine.

The full backup reference is `BACKUP_AND_RECOVERY.md`. This guide is the procedure; that one
is the detail.

> Nothing in this document has been performed on Mike's laptop. Every procedure is
> `IMPLEMENTED` and `UNVERIFIED` — see `docs/readiness/OPERATIONAL_PROOF.md`.

---

## 1. Backups

### 1.1 Take one

```
python scripts\dispatch_backup.py backup D:\Backups --dry-run
python scripts\dispatch_backup.py backup D:\Backups
```

**Always dry-run first.** It reports exactly what would be captured and writes nothing. If
the plan is missing a root you expected, the cause is almost always an unset
`DISPATCH_*_ROOT` in this window — not a bug in the backup.

`--compress` produces a `.tar.gz` instead of a directory. `--name` overrides the timestamped
archive name; leave it alone unless you have a reason.

The database is **snapshotted**, not file-copied. A live SQLite database in WAL mode has
state in `-wal` and `-shm` files, and copying only the `.db` gives you a file that opens and
is silently missing recent writes — the worst kind of bad backup, because it looks fine.

Every file is hashed. The manifest records the hashes, the database shape, and the
environment with **secret names present and secret values absent**.

### 1.2 Verify it

```
python scripts\dispatch_backup.py verify D:\Backups\dispatch-backup-YYYYMMDDTHHMMSSZ
```

This recomputes every hash. It proves the archive is **intact**. It does not prove the
archive is **usable** — only a restore does that.

### 1.3 A backup is not valid until it has been restored

Dispatch's backup display will show, and only ever show:

| | |
|---|---|
| `UNCONFIGURED` | No `DISPATCH_BACKUP_DIR` set |
| `ABSENT` | Folder set, no archives in it |
| `UNVERIFIED` | An archive exists and has **never been restored and proven** |
| `VERIFIED` | A `restore-verification.json` exists for that archive |

**No part of Dispatch writes `restore-verification.json`.** A human performs a restore,
confirms the records are there, and writes it. Until then the honest reading is
`UNVERIFIED`, and Dispatch will keep saying so however many backups you take.

An unverified backup is a hope, and you find out which at the worst possible time.

---

## 2. Restoring

### 2.1 The rule

> **Never restore into the live estate.**

Restore into an **empty** directory, start Dispatch against it, look at it, and only then
decide what to do with the live one. Restoring over live data destroys the thing you were
trying to protect if the archive turns out to be bad.

```
python scripts\dispatch_backup.py restore D:\Backups\dispatch-backup-... D:\RestoreTest --dry-run
python scripts\dispatch_backup.py restore D:\Backups\dispatch-backup-... D:\RestoreTest
```

`--force` allows a non-empty destination. Using it is how you overwrite something you meant
to keep.

### 2.2 Then prove it, and record that you did

Point Dispatch at the restored folders (`setx`, then a **new** window), start it, and open
the loads, milestones and evidence you expect. When you are satisfied, write
`restore-verification.json` **inside the archive folder**:

```json
{
  "archive": "dispatch-backup-YYYYMMDDTHHMMSSZ",
  "verified_at": "<when the restore was completed>",
  "restored_to": "D:\\RestoreTest",
  "checked": "<what you opened and confirmed present>"
}
```

That file is the only thing that moves the backup to `VERIFIED`. Write it honestly; it is a
statement about what **you** checked.

### 2.3 Practise this before you need it

A restore you have never rehearsed is a restore that fails at 2am. Do one deliberately,
while nothing is wrong, and record it.

---

## 3. The database

One SQLite file, WAL journal mode, foreign keys enforced. `sqlite3` from the standard
library — no ORM, no migration framework.

- **Where is it?** `python -m dispatch_launcher status` prints the path. The portal prints
  the same path on startup. **If those two disagree, stop and fix that before anything else** —
  you have two databases and are about to lose work in one of them.
- **It is created on first freight-data read, not at start.** A fresh install that has never
  shown a load has no database file. That is correct, not a fault.
- **Schema changes are idempotent.** `CREATE TABLE IF NOT EXISTS` runs on connect, so a new
  version adds its tables on first run with nothing to do by hand.
- **Copy it only when Dispatch is stopped**, and copy the `-wal` and `-shm` files with it —
  or use §1.1, which handles this properly.

### 3.1 Rehearsal records

Rehearsal records live in the **same tables** as live records, tagged with a session
identifier. That is deliberate: travelling the same code path is the entire point.

`purge-plan` reports what a purge would remove before it removes anything:

```
python scripts\dispatch_proof.py sessions
python scripts\dispatch_proof.py purge-plan <session_id>
```

A purge respects foreign keys — it defers them to the commit rather than disabling them, and
derives the delete order from the schema. If it refuses, something references a record you
did not expect, and that is worth reading before you insist.

---

## 4. Secrets

Two matter, both set with `setx`, both **required in operational mode**:

| | |
|---|---|
| `PORTAL_SECRET_KEY` | Signs the browser session cookie |
| `DISPATCH_EMAIL_SECRET` | Signs decision, stakeholder and IFTA links sent by email |

```
setx PORTAL_SECRET_KEY "<a long random value you generate>"
```

**`setx` reaches only windows opened afterwards.** Set it, close the console, open a new one.
`set` lasts until the window closes and produces the most confusing bug available: Dispatch
works this afternoon and is broken tomorrow.

### 4.1 Rules

- **A value set to this repository's published default is not configured.** Settings will
  report it `UNCONFIGURED`, deliberately — "set to a value anyone reading the source already
  knows" is not a secret.
- **Dispatch never prints a secret value.** Not on screen, not in a log, not in a backup
  manifest, not in the clipboard. Settings names them and reports status only.
- **Rotating `DISPATCH_EMAIL_SECRET` invalidates every outstanding emailed link.** That is
  the correct behaviour. If links were leaked, rotate; expect to reissue.
- Tokens can be revoked individually or per object — see `dispatch/tokens.py`
  (`revoke`, `revoke_for_object`), which keeps an audit trail of both.

---

## 5. Logs

`python -m dispatch_launcher --logs` prints the launcher log directory.

- Logs live **outside version control** by design. `git status` should never show one.
- Secret **values** are redacted to `[REDACTED]`; secret **names** are kept, because the name
  is what you need to fix the problem.
- The launcher log holds the stack trace for any failed start. The screen gets one sentence;
  the trace goes here.
- Nothing rotates them automatically. Delete old ones when they get large — they are
  diagnostics, not records.

**Check a log before sending it.** The redaction is good and you should still look.

---

## 6. Upgrading

1. **Back up first** (§1), and dry-run it.
2. **Stop Dispatch** — `[8]`, and confirm it says the process is gone.
3. Pull or copy the new code.
4. `python -m dispatch_launcher version` — confirm the **commit** is the one you meant.
5. `python -m dispatch_launcher status` — confirm every path is what it was before. A path
   that changed to a default means a variable is missing from this window.
6. Start, and open one real load.

### 6.1 Dependencies

`flask` is required. `paramiko` and `anthropic` are **optional** — Version reports each as a
version string or `ABSENT`, and `ABSENT` is a normal reading. Dispatch runs without them;
the features that use them report `UNCONFIGURED`.

`pip install -e .` is **not** required to run Dispatch.

---

## 7. Moving Dispatch to another machine

1. Back up on the old machine and **verify** (§1.2).
2. Copy the repository folder and the archive.
3. On the new machine: install Python 3.11+, `pip install flask`, then set the roots and
   secrets with `setx` and **open a new window**.
4. `python -m dispatch_launcher status` — read every line before starting anything.
5. Restore into the new roots (§2), prove it, and write the verification record.
6. `DISPATCH_FIRST_START_GUIDE.md` covers a first start end to end.

**The copied folder may have no `.git`.** Version then reports commit `UNVERIFIED`. Dispatch
still runs — it just cannot prove which code it is, which matters the first time you need to
report a problem. Copy `.git` if you can.

---

## 8. Health checks worth doing on a schedule

| How often | Check |
|---|---|
| Every start | Status block: paths, mode, secrets, last failure |
| Weekly | Take a backup and dry-run it |
| Monthly | Restore a backup into a scratch folder, prove it, write the verification record |
| Monthly | `git status` — confirm no log, database, evidence file or backup has crept in |
| Per upgrade | Confirm the commit, then confirm the paths (§6) |
| Whenever a number looks wrong | Re-read `docs/readiness/KNOWN_LIMITATIONS.md`. Fuel, MPG and drive-speed constants are defaults, not measurements from your trucks |
