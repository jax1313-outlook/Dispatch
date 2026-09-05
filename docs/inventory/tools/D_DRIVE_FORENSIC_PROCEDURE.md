# D:\ Forensic Inventory — Procedure

**Authority: Mike Zachary.** Status of the mission: **BLOCKED — not started.**

---

## 1. Why the mission could not be executed on 2026-09-05

The D:\ forensic inventory was commissioned in a Claude Code session running in an
**isolated Linux cloud container**. `D:\` is not reachable from there. This was verified,
not assumed:

| Check | Result |
|---|---|
| Mounted filesystems | Only container-local virtual disks (`/dev/vda`–`/dev/vdf`). No Windows volume. |
| Kernel filesystem support | `cifs`, `smb3`, `nfs`, `nfs4` — **none available** |
| Remote-mount tooling | `mount.cifs`, `smbclient`, `sshfs`, `rclone`, `net` — **all absent** |
| Host-share transport | No 9p, no virtiofs |
| User-facing mounts | `/mnt/attach` and `/mnt/user-data/working` — **both empty** |
| Prior evidence in container | none |

This is a hard environment boundary, not a permission that can be granted. The same
boundary was hit and recorded by the earlier recovery mission in
`Claude-3/RECOVERY_REPORT.md`:

> **Not reachable, ever, from this session:** the local path `D:\DISPATCH_AND_SAM_RECOVERY`
> and everything under it. This session runs in an isolated cloud container with no mount,
> network path, or credential that reaches a user's local Windows machine.

That mission worked around it with a hand-uploaded `E-Ingestion.zip` (21.5 MB, ~600 files) —
a partial export, not the drive.

**No forensic inventory of D:\ has been produced. The four deliverables
(`D_DRIVE_FORENSIC_INVENTORY.md`, `D_DRIVE_CAPABILITY_MATRIX.md`,
`D_DRIVE_DUPLICATION_MATRIX.md`, `D_DRIVE_AUTHORITY_MATRIX.md`) do not exist and must not be
represented as existing.** Producing them from a container that cannot see the drive would
mean inventing evidence, which the mission expressly forbids.

---

## 2. Two ways to execute it

### Option A — run the mission where D:\ actually is (recommended)

Claude Code runs natively on Windows, as a desktop app and as a CLI. Run it **on the machine
that has D:\** and re-issue the same mission prompt. Claude then has direct read access to
the drive and can perform the full forensic inventory in one pass — discover, classify,
judge — with no proxy and no upload step.

This is the only route that gives true forensic access: file contents, not just metadata.

### Option B — collect evidence locally, analyse it here

If the mission must be analysed in this cloud session, run the read-only collector in this
directory on the Windows machine and hand back the evidence package.

```powershell
# From an ordinary PowerShell prompt on the machine with D:\
powershell -ExecutionPolicy Bypass -File .\Collect-DDriveForensics.ps1
```

Defaults: `-Root D:\`, output to `C:\DDriveForensics_<timestamp>\` plus a `.zip`.
Expect 20–90 minutes on a large drive; hashing is the slow part.
Then upload the `.zip` (typically 1–20 MB — it is metadata, not file contents).

---

## 3. What the collector does, and does not do

**It is strictly read-only.** It opens files to hash them and does nothing else. It never
builds, modifies, moves, deletes, renames, merges or reorganises anything. Every git call is
a plain-text read (`remote -v`, `rev-parse`, `log`, `branch`, `status`, `ls-files`,
`ls-tree`, `stash list`, `tag`) — no `fetch`, `pull`, `checkout`, `gc`, or config write.
It refuses to run if its output directory is inside the drive being collected.

### Evidence it produces

| File | Contents |
|---|---|
| `files.csv` | Every file: full path, relative path, extension, category, size, **LastWriteUtc**, CreationUtc, **git blob SHA-1**, SHA-256 (archives/DBs/office), first non-blank line, git-internal flag |
| `directories.csv` | Every directory with depth and timestamps |
| `git_repos.csv` / `.json` | Every git working tree: remotes, current branch, HEAD SHA, HEAD date, HEAD subject, **all local branches**, commit count, **dirty file count**, untracked count, **stash count**, tracked file count, tags |
| `git_tracked_blobs.csv` | **Every tracked blob on every local and remote ref** of every repo found: worktree, ref, blob SHA-1, path |
| `project_markers.csv` | `setup.py`, `pyproject.toml`, `requirements.txt`, `pytest.ini`, `package.json`, `Dockerfile`, `CLAUDE.md`, `README.md`, `.env`, `Makefile`, `*.sln`, … |
| `sqlite_databases.csv` | Header-verified SQLite files, with table names where `sqlite3` is on PATH |
| `SUMMARY.txt` | Counts by category, top-level folders, newest 40 files, top 40 duplicated blobs |
| `errors.log` | Every unreadable path, with reason |

### The load-bearing design decision

Files are hashed with the **git blob SHA-1** — `sha1("blob " + length + "\0" + bytes)` — the
same identifier git itself uses.

That is what makes the D:\ evidence **join directly against the GitHub repository inventory
already completed** in `docs/inventory/`, which was built by hashing all 1,218 tracked files
across the fourteen repositories the same way. A shared hash means the following become
mechanical comparisons rather than judgement calls:

- **What exists only on D:\** — blobs on the drive that appear in no repository.
- **What is duplicated** — one blob, many paths, on the drive and across repositories.
- **What is newer than GitHub** — a path whose D:\ blob differs from every committed blob,
  with a `LastWriteUtc` after the relevant commit date.
- **What is older than GitHub** — a D:\ blob matching an *ancestor* commit's blob rather
  than HEAD.
- **What is authoritative** — corroborated by dirty working trees, stash counts, and
  branches on D:\ that never reached the remote.

`git_tracked_blobs.csv` covers **every ref**, so a D:\ clone holding an unpushed branch is
detected as unpushed rather than mistaken for missing work.

---

## 4. What is answered only after the evidence arrives

Every one of the mission's Required Questions is **UNKNOWN** until then, and is recorded that
way rather than inferred:

- What exists? — **UNKNOWN**
- What is unique? — **UNKNOWN**
- What appears duplicated? — **UNKNOWN**
- What exists only on D:\? — **UNKNOWN**
- What appears newer than GitHub? — **UNKNOWN**
- What appears older than GitHub? — **UNKNOWN**
- What capabilities exist nowhere else? — **UNKNOWN**
- What projects exist outside the known repository list? — **UNKNOWN**
- What orphaned artifacts exist? — **UNKNOWN**
- What is likely authoritative? — **UNKNOWN**
- What is likely experimental? — **UNKNOWN**

---

## 5. Verification performed on the collector

The script was not merely written; it was tested before being handed over.

| Check | Result |
|---|---|
| PowerShell parse (7.4.6) | **OK** — no syntax errors |
| End-to-end run, single repo tree | **Passed** — git metadata matched values independently measured from the same repository |
| End-to-end run, 14 git trees / 1,313 files | **Passed** — 26,727 tracked blobs exported across all refs, **0 errors** |
| Duplicate detection | **Validated** — independently reproduced the known ×5 doctrine-set duplication across `Claude`, `Claude-2`, `Claude-3`, `Library` and `Jules` |
| Defect found and fixed in testing | `.git` internals were 74% of rows and drowned the newest-file and duplicate analyses. Now excluded by default (recoverable with `-IncludeGitInternals`); tracked blobs are captured exactly via `git_tracked_blobs.csv` instead |

Testing ran on Linux, where PowerShell 7 is available. The path-separator handling is
separator-agnostic and works on both platforms, but the script has **not** been executed on
Windows — that remains UNVERIFIED, in the sense `Dispatch/CLAUDE.md` §6 uses the word.
