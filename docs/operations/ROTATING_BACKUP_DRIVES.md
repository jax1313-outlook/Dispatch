# Rotating Backup Drives

**What this is:** how to prepare, use, swap and restore from the rotating external backup
drives. It is an operator document (`docs/governance/OPERATOR_DOCUMENT_RULE.md`): if the code
changes, this changes with it.

**The direction it implements** (Owner, 2026-09-14): *"Back up is rotating 4TB Crucial external
hard drives."*

> **Recorded difference, not resolved here.** CLAUDE.md §5A R8 still names the **home NAS** as the
> off-node backup destination. This procedure implements the 2026-09-14 direction for rotating
> drives. The doctrine text has not been changed; that is the Owner's call.

**Status of this procedure: `IMPLEMENTED`, not `OPERATIONALLY PROVEN`.** The software is covered by
`tests/test_backup_drives.py`. Nothing below has yet been run on the truck's node with a real
drive. The first real run, swap and restore test are the proof, and should be recorded.

---

## 0. How it works, in five lines

1. Each backup drive carries a small file at its root, `dispatch-backup-drive.json`, naming it
   (for example **Drive A**). Dispatch finds the drive by that file, **not by its drive letter**.
2. A backup run writes a new archive into `DispatchBackups\` on whichever prepared drive is
   plugged in, then **re-hashes what it just wrote** and reports `PASS` or `FAIL`.
3. Every run adds one line to `DispatchBackups\rotation-log.jsonl` **on the drive** and one line to
   `backup_drive_record.jsonl` **on the node** (in the portal data folder).
4. Status shows the age of the newest backup that passed, per drive; **warns when the newest is
   older than 24 hours**; and says **"Time to swap drives"** when one drive has been in use for 7
   days (change with `DISPATCH_BACKUP_SWAP_DAYS`).
5. **Nothing ever deletes a backup.** When a drive fills up, that is a decision for you.

**A `PASS` means the copy on the drive matches its own manifest. It is not a restore test.** Only a
restore you perform (section 5) proves a backup is usable.

---

## 1. What is backed up

Everything under the configured roots, and nothing outside them:

| What | Setting | Notes |
|---|---|---|
| Portal data — every file | `PORTAL_DATA_DIR` | All JSON stores, **`joe_audit.jsonl`, `security_events.jsonl`, `LibraryDocuments\`** (before 2026-09-14 only top-level `*.json` was taken) |
| The operational database | inside the portal data folder | Snapshotted through SQLite, never file-copied |
| Evidence uploads | `PORTAL_UPLOAD_DIR` | |
| Archive | `DISPATCH_ARCHIVE_ROOT`, `DISPATCH_ARCHIVE_PATH` | |
| Memory (and its evidence) | `DISPATCH_MEMORY_ROOT` | When configured |
| Library catalog | `DISPATCH_LIBRARY_CATALOG` | Snapshotted through SQLite, when configured |

Shortcuts, symbolic links and junctions inside those folders are **recorded and skipped, never
followed**, so a link pointing at the whole data drive cannot drag it into the backup. Secrets are
never written to the drive (names only, values redacted).

A configured folder that is missing makes the run exit `2` and is written in the log. **Do not
treat an exit-2 run as a backup.**

---

## 2. Prepare a new 4 TB drive (once per drive)

Do this for each drive — at least two, so there is something to rotate.

1. **Plug in only the new drive.** Note the letter Windows gives it, for example `T:`. The letter
   only matters for this one step.
2. Optional but recommended: turn on BitLocker To Go first — **section 7**.
3. Open a command window in `D:\Dispatch` and run:

   ```
   python scripts\dispatch_backup.py prepare-drive T:\ --name "Drive A"
   ```

   Use `"Drive B"` for the second drive, and write the same name on the drive's case with a marker.

4. It prints the drive id and creates `T:\DispatchBackups\`. It will **refuse**, and change
   nothing, if:
   - the drive is already prepared (a copied identity file would make two drives look like one);
   - the folder holds Dispatch data — **never prepare `D:`**, the data drive. A backup on the same
     drive as the data protects nothing. (Dispatch cannot tell two partitions of one physical disk
     apart; do not partition the data drive to make a "backup drive".)
5. Check it is found:

   ```
   python scripts\dispatch_backup.py drives
   ```

**Do not delete or edit `dispatch-backup-drive.json`.** Without it the drive is not recognised. If
it is lost, prepare the drive again under a *new* name (for example `"Drive A2"`); the old backups on
it are untouched and still restorable.

---

## 3. Run a backup

With **one** prepared drive plugged in:

```
python scripts\dispatch_backup.py drive-backup
```

It finds the drive by identity wherever Windows mounted it, writes the archive, re-hashes it, and
logs the run on the drive and on the node. Read the result:

| Exit | Meaning | What to do |
|---|---|---|
| `0` | Written, hash check `PASS`, every configured source present | Nothing |
| `2` | Written and `PASS`, but a configured source was missing | Read the `MISSING:` lines; fix the setting; run again |
| `3` | Refused: no prepared drive plugged in, more than one, or the drive holds data | Plug in exactly one drive, or add `--drive "Drive B"` |
| `5` | Hash check `FAIL`: the copy on the drive does not match | **Do not rely on that archive.** Try again; if it repeats, suspect the drive |

Add `--compress` for a single `.tar.gz` per backup instead of a folder.

Check status at any time (works with no drive plugged in, because it reads the node's record):

```
python scripts\dispatch_backup.py rotation-status
```

It lists each drive with its newest passing backup's age, the drive in use now, and warnings. It
exits `1` when the newest passing backup is older than 24 hours or a swap is due. The same facts
are on the **Node** page in Operations and, in short form, on the NODE card in the Driver Cockpit.

---

## 4. Swap drives

When status says **"Time to swap drives"** (every 7 days by default):

1. Make sure the last run on the current drive passed (`rotation-status`).
2. **Safely remove** the drive: the "Safely Remove Hardware" icon in the taskbar, then unplug.
   Pulling it mid-write can corrupt the archive being written.
3. Plug in the other drive. Whatever letter it gets does not matter.
4. Run `python scripts\dispatch_backup.py drives` — you should see the other drive's name.
5. Run a backup now (section 3) rather than waiting for the night, so the new drive starts current.
6. Take the drive you removed **out of the truck** — home, or wherever the off-node copy lives. A
   drive stored in the same case as the node is not an off-node copy.

To change the interval: `setx DISPATCH_BACKUP_SWAP_DAYS 14`, then open a **new** window.

---

## 5. Restore to a scratch folder (the proof)

Do this once when the drives are new, and again periodically. **Never restore into the live
estate** (`docs/maintenance/DISPATCH_MAINTENANCE_GUIDE.md` §2).

1. Find the archive: `T:\DispatchBackups\dispatch-backup-YYYYMMDDTHHMMSSZ` (the name is in the
   `drive-backup` output and in `rotation-log.jsonl`).
2. Check it: `python scripts\dispatch_backup.py verify T:\DispatchBackups\dispatch-backup-...`
3. Dry run, then restore into an **empty** folder on a disk that is not the data drive:

   ```
   python scripts\dispatch_backup.py restore T:\DispatchBackups\dispatch-backup-... C:\RestoreTest --dry-run
   python scripts\dispatch_backup.py restore T:\DispatchBackups\dispatch-backup-... C:\RestoreTest
   ```

4. It prints the settings to start Dispatch against the restored copy. Start it that way in a
   separate window, open a recent load, its milestones and an evidence file.
5. When — and only when — you have looked, record it as described in
   `docs/maintenance/DISPATCH_MAINTENANCE_GUIDE.md` §2.2 (`restore-verification.json`, written by
   the person who checked, saying what they checked).
6. Delete `C:\RestoreTest` yourself when finished. Dispatch does not.

---

## 6. Nightly backup with Windows Task Scheduler — steps for Mike to perform

**Dispatch does not create scheduled tasks.** These are instructions; nothing in the repository
runs them. Doing this is a change to the laptop's configuration and is your decision.

1. Confirm a manual `drive-backup` works first (section 3).
2. Open **Task Scheduler** → **Create Task…** (not "Basic Task").
3. **General:** Name `Dispatch nightly backup`. Choose **Run whether user is logged on or not** only
   if you are willing to store your Windows password with the task; otherwise **Run only when user
   is logged on** (with auto-login from `NODE_UNATTENDED_RECOVERY.md` this is normally true).
   Leave "Run with highest privileges" **off** — the backup needs no administrator rights.
4. **Triggers:** New → Daily, 02:00 (pick a time the truck is normally parked and Dispatch idle).
5. **Actions:** New → Start a program
   - Program: the full path to `python.exe` that Dispatch uses (`where python` shows it)
   - Arguments: `scripts\dispatch_backup.py drive-backup`
   - Start in: `D:\Dispatch`
6. **Conditions:** untick "Start the task only if the computer is on AC power" if the node may be on
   battery at 02:00; tick "Wake the computer to run this task" if the node sleeps.
7. **Settings:** tick "Run task as soon as possible after a scheduled start is missed".
8. The task runs as your user, so it sees the same `DISPATCH_*` / `PORTAL_*` settings you set with
   `setx`. A task run as a different account backs up a different estate — or nothing.
9. Next morning: `python scripts\dispatch_backup.py rotation-status`. Task Scheduler's "Last Run
   Result" should be `0x0`; `0x2`, `0x3` or `0x5` are the exit codes in section 3.

Command-line equivalent, if you prefer (run in your own window, as yourself):

```
schtasks /Create /TN "Dispatch nightly backup" /SC DAILY /ST 02:00 /TR "\"C:\path\to\python.exe\" D:\Dispatch\scripts\dispatch_backup.py drive-backup"
```

(`/TR` does not set a start folder; the script finds the repository from its own path.)

---

## 7. Encrypt the drives with BitLocker To Go — steps for Mike to perform

The archives are **not encrypted by Dispatch**. The drives leave the truck, so encrypt them.
Windows 11 Pro includes BitLocker To Go. **Dispatch does not turn this on and does not hold the
keys.**

1. Plug in the drive. In File Explorer, right-click it → **Turn on BitLocker**.
2. Choose **Use a password to unlock the drive**. Use a strong password you keep in your password
   manager — not on the laptop, not in the truck.
3. **Save the recovery key** — print it or save it to a location that is **not** the node and not
   the drive. Without password or recovery key the backups are unrecoverable, by design.
4. Choose **Encrypt used disk space only** for a brand-new empty drive (faster), and
   **Compatible mode** so the drive can be read on another Windows machine during a recovery.
5. Wait for encryption to finish before unplugging.
6. For unattended nightly runs, on the node only: right-click the unlocked drive →
   **Manage BitLocker** → **Turn on auto-unlock**. Auto-unlock works only on this laptop; a spare
   machine used for a restore will ask for the password — which is the point.
7. Prepare the drive (section 2) after encryption, or before — the identity file survives either
   way. Repeat for every drive.

If a drive is locked when the backup runs, it is not readable, is not found, and the run exits `3`
("no prepared backup drive is plugged in"). Status will then start warning after 24 hours.

---

## 8. Files, for reference

| File | Where | Written by |
|---|---|---|
| `dispatch-backup-drive.json` | root of each backup drive | `prepare-drive` (once) |
| `DispatchBackups\dispatch-backup-<UTC>\` | backup drive | each run |
| `DispatchBackups\rotation-log.jsonl` | backup drive | each run, append-only |
| `backup_drive_record.jsonl` | portal data folder on the node (`DISPATCH_BACKUP_RECORD` overrides) | each run, append-only |

Code: `dispatch/backup_drives.py`, `dispatch/backup.py`, `scripts/dispatch_backup.py`.
