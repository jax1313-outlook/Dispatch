# Dispatch — Operational Proof

**The one question this document answers:** what has actually been proven, and on what?

**Current as of:** 2026-08-25 · **Branch:** `claude/dispatch-repo-context-reconcile-7mblbb`

---

## 2026-08-25 — Dispatch is operating on Mike's Windows laptop

**Recorded from output Mike pasted, verbatim.** This is the first evidence in this
repository's history that is not a test result.

```
  DISPATCH

    [OK  ] Dispatch folder
           C:\Dispatch\Dispatch2\Dispatch-main
    [OK  ] Security settings
           This machine already has its own settings. Nothing was changed.
    [OK  ] Flask
           Already installed.
    [OK  ] Sign-in PIN
           Already set on this machine. Nothing was changed.
    [OK  ] Start
           Dispatch is running (process ID 14688) at http://127.0.0.1:8080
    [OK  ] Desktop shortcut
           The Dispatch icon is already on your Desktop.
    [OK  ] Open in browser
           Opened http://127.0.0.1:8080 in your browser.

    Dispatch is RUNNING at http://127.0.0.1:8080
```

The portal then rendered `/home` in his browser, with the sidebar reading
**"Dispatch — Operations Cockpit"**. He reports exercising the Control Center menu and
that every control functioned.

### What this establishes

| | |
|---|---|
| The launch file runs when double-clicked, with no command typed | **observed** |
| Windows resolves a Python interpreter (3.14, via `py -3`) | **observed** |
| Flask is found | **observed** |
| First-run setup is **idempotent** — it recognised existing settings, PIN and shortcut and changed nothing | **observed** |
| Start reports a real process ID and a real address | **observed** |
| The Desktop shortcut created on a previous run persisted | **observed** |
| The browser opens on the portal | **observed** |
| The window stays open rather than closing | **observed** |
| A second Start refuses **by identity** rather than starting a duplicate | **observed** (earlier run: *"already running (process ID 126112). Nothing was started."*) |
| The portal renders `/home` and the operator can sign in with his PIN | **observed** |

Every value on that screen was read from his machine. None was hard-coded.

### What it does **not** establish, and why the fifteen stay UNVERIFIED

`docs/readiness/LAUNCHER_PROOF_TEMPLATE.md` asks for something specific: for each numbered
item, the named command run and **its real output pasted into the Observed column by the
person who ran it**. That has not been done, so no item is marked `LIVE` here.

This is not pedantry about paperwork. The items not yet covered by any observation are:

- **Item 2** — the full status block (`Refresh Status`), cross-checked against what the
  portal itself prints. The database path and storage roots have never been read off that
  screen.
- **Items 4, 5, 6** — Stop confirming the process is gone; Restart proving the old process
  died first; an orphan being reported rather than duplicated.
- **Item 7** — a failed start explained in one sentence, with the trace in the log and
  secrets redacted.
- **Item 8** — backup status reported honestly.
- **Items 10, 12, 13** — glyph rendering on his code page, `settings` exiting non-zero while
  blocking, and `version` reporting the running commit.
- **Items 14, 15** — Reset Session refusing while Dispatch is running. **The most important
  one**, and untouched.

"He said the controls all worked" is a good sign. It is not a record of what each one
printed, and the difference is the entire point of this document.

### The defect this run also found

`/home` displays two freight Opportunity Cards — *Dry Van, Jacksonville FL → Savannah GA,
$625, Southeast Freight Partners* — while the `ACTIVE LOADS` counter above reads **0**.

Both are correct: the cards are possibilities from `sandbox.json`, the counter is committed
reality, and the separation is working as `DISPATCH_PURPOSE_STATEMENT.md` requires. But
`sandbox.json` holds **four bundled sample entries**, and a card carrying a lane, a rate and
a broker reads as a real load with nothing on screen saying otherwise.

`CLAUDE.md` §6: *never represent sample data as live data.* This is judged to fail that, and
is awaiting Mike's decision — label the samples, or clear them.

---

## 2026-08-25 — Dispatch ran on Windows for the first time

**The one-line answer below is no longer the whole truth, and this section is why.**

Mike ran `DISPATCH_START_HERE` on his Windows laptop. What happened, from his own screenshots
and report:

| | |
|---|---|
| The launch file ran when double-clicked | **observed** |
| Windows resolved a Python interpreter | **observed** (it got past the no-Python gate) |
| Flask was present or was installed | **observed** (the server started) |
| The first-run PIN prompt appeared and saved a PIN | **observed** — *"i did setup a PIN"* |
| The server started and served on `127.0.0.1:8080` | **observed** |
| Sign-in succeeded | **observed** — the browser reached `/home`, which is behind the gate |
| `/home` renders | **FAILED — HTTP 500** |
| `/dispatch` renders | **FAILED — HTTP 500** |

**This is evidence, not proof, and the distinction is the point of this document.** Nothing
above has been recorded against the acceptance items in §3 in the form they require — an
observed output pasted beside the item by the person who ran it. What it establishes is that
the launch path works on Windows and the failure is past it.

### The defect it found

Every page behind the login gate returns Flask's bare *"Internal Server Error"*. `/login`
works, because it is the only page that neither extends `base.html` nor reads freight data.

The same code, from the same downloaded ZIP, was run here on Linux: `/home` **200**,
`/dispatch` **200**. So the cause is specific to that machine or its configuration, and it
has not been reproduced.

### The second defect, which is ours

The screen said *"Internal Server Error"* and nothing else. It did not name the error, did
not say the rest of Dispatch was running, and did not mention that a log exists. **Two rounds
of correspondence went by hunting for a log file whose location the failing page could simply
have printed.** Fixed: `portal/errors.py` now renders a page that names the failure, prints
the exact log path, and carries a redacted traceback in a one-click-selectable block.

### What is still unknown

The traceback. His `logs` folder is not where the default would put it, which points at
`DISPATCH_OPERATIONS_ROOT` being set on that machine and moving both the log **and the
freight database** — `<ops root>\Current Workspace\PortalData\dispatch.db`. That is a
hypothesis with a mechanism, not a diagnosis, and it is recorded as one.

---

## The answer, in one line

> **Nothing in Dispatch is OPERATIONALLY PROVEN. Not one step has been executed on Mike's
> machine.**

Everything below explains that sentence, says exactly what *is* established, and gives the
commands that would change it.

---

## 1. Two words that are not the same

| | |
|---|---|
| **IMPLEMENTED** | The code exists and the repository suite exercises it. |
| **OPERATIONALLY PROVEN** | It has been run **on Mike's machine** and evidence was recorded. |

**The repository test suite is evidence of software behaviour only. It is never operational
proof, and nothing in this repository treats it as any.**

A green suite tells you the software behaves as written. It tells you nothing about whether
Dispatch starts on a Windows laptop, resolves the `D:` drive, survives a restart with a load
still in it, or renders correctly on that machine's console code page. Those are properties
of a machine, and they are established by running it there.

This is not modesty. It is the difference between "we tested it" and "it works", and
conflating the two is how software arrives broken on the day it is needed.

---

## 2. What the repository establishes

| | |
|---|---|
| Suite | **3,696 passed** · 0 failed / 0 skipped / 0 warnings |
| Command | `python -m pytest -q --cov=cin_lite --cov=dispatch --cov=portal --cov-fail-under=90` |
| Gated coverage | **94.74%** (floor 90%) |
| Ungated | `dispatch_launcher/` at **87.75%** — measured and reported, deliberately outside the gate; see §2.1 |
| Python | 3.11 locally; CI runs 3.11 / 3.12 / 3.13 |

**IMPLEMENTED:** the Spine lifecycle engine (25 states) · loads, drivers, equipment,
capacity, truck arrangement · milestones, evidence, POD · exceptions · IFTA through
finalization, exception detection and receipt vision pre-fill · settlement and driver pay ·
the Driver Portal · backup, verify and restore · CSRF across mutating routes · token issue,
expiry and revocation · the connector boundary with eight connectors · rehearsal mode · the
twenty-step operational-proof system · the Dispatch Launcher and Control Center v1.

### 2.1 The launcher's coverage figure, stated plainly

`dispatch_launcher/` sits at **87.75%**, below the repository's 90% gate, and is **not** in
the gated set.
The uncovered lines are Windows-only branches — `taskkill`, `tasklist`,
`Get-CimInstance Win32_Process`, `py.exe` resolution, detached process creation — that
cannot execute on the Linux CI running the suite.

Adding the package to the gate would measure *how much Windows code exists* rather than how
well it is tested. Lowering the gate to accommodate it would weaken the gate for everything
else. So it is measured, reported, and every one of those branches is recorded `UNVERIFIED`
below. That is the honest position and it is the one taken.

---

## 3. What is UNVERIFIED — the fifteen first-start items

**Record:** `docs/readiness/LAUNCHER_PROOF_TEMPLATE.md` (committed).
**Live document:** `proof/launcher/LAUNCHER_PROOF.md` — **gitignored**, because a completed
one carries this machine's real paths and process IDs.

Fifteen numbered acceptance items, **all `UNVERIFIED`**:

| # | Item |
|---|---|
| 1 | The launcher opens without typing a Python command |
| 2 | Every display is read from this machine's real configuration |
| 3 | Start creates exactly one server, and a second Start does nothing |
| 4 | Stop terminates the real process and confirms it is gone |
| 5 | Restart proves the first process is dead before starting the second |
| 6 | An orphan from a crash is reported, not duplicated |
| 7 | A failed start is explained in plain language, trace kept in the log |
| 8 | Backup status is reported honestly and never claimed valid |
| 9 | The menu shows all eight controls in order, with icons |
| 10 | The icons render, or are cleanly absent on a legacy code page |
| 11 | Settings names every setting and never prints a secret value |
| 12 | Settings exits non-zero while a setting is blocking a start |
| 13 | Version reports the commit of the code actually running |
| 14 | **Reset Session refuses while Dispatch is running** |
| 15 | Reset Session clears a stale record and nothing else |

Items 1–8 came from the launcher's original acceptance list; 9–15 were added when Control
Center v1 introduced Settings, Version and Reset Session. **Fifteen is what the repository
supports**, and each item carries the exact command that would move it to `LIVE` or
`UNAVAILABLE` — no other word.

Item 14 matters most. Clearing the record of a live server is how an orphan is created: the
process keeps the port and can no longer be stopped from the Control Center. The refusal is
tested in the repository; a test on Linux is not evidence about Windows.

---

## 4. What is UNVERIFIED — the twenty load-proof steps

**Record:** `docs/readiness/OPERATIONAL_LOAD_PROOF_TEMPLATE.md` (committed).
**Procedure:** `docs/readiness/OPERATIONAL_PROOF_PROCEDURE.md`.
**Live document:** `proof/load/OPERATIONAL_LOAD_PROOF.md` — gitignored.

**20 of 20 steps `UNVERIFIED`.** Performed by Mike: nothing (`ABSENT`). Executed by tooling:
nothing (`ABSENT`).

**Six of the twenty cannot be automated, by design** — steps 1, 2, 9, 10, 16 and 17. A human
performs them or the proof is not operational. That is what makes the remaining fourteen
worth anything: a proof path a machine can complete alone proves only that a machine ran.

The headline is computed, never asserted: it reads `PASSED` only when every step has been
performed *and* the machine is not `UNVERIFIED`. Otherwise it reads `NOT RUN`, or names the
first step that failed.

---

## 5. What is UNVERIFIED — the Windows environment itself

Six facts about the target machine that no test here can establish. Each is a question for
Mike, not an assumption made in code:

1. Whether `py.exe` is installed, and whether it resolves to the interpreter that has Flask.
2. Whether `Get-CimInstance Win32_Process` runs for this user. Without it the launcher can
   see a process is alive but cannot confirm its identity — and will **refuse to stop it**
   rather than risk terminating the wrong program.
3. Whether `taskkill` and `tasklist` are available and permitted.
4. Whether the `D:` drive and the three `DISPATCH_*_ROOT` variables are set **in the session
   that double-clicks `dispatch.bat`**. `setx` reaches only new windows.
5. Whether Defender or SmartScreen interferes with a detached process from a double-clicked
   `.bat`.
6. Whether the console code page renders the status block and the menu glyphs. The glyphs
   drop cleanly when the stream cannot encode them; that path is untested on a real console.

---

## 6. Why none of it has been run

Every build session so far has executed in an **isolated Linux container** with no reachable
Windows filesystem. Verified repeatedly, including a full `/proc/mounts` inspection: only
`/dev/vda` (ext4), five read-only tool images, and kernel pseudo-filesystems. No CIFS/SMB,
no 9p, no virtiofs, no NFS, no NTFS, no drvfs. `C:\` and `D:\` are not unreachable *by
permission* — they are not present at all, and no credential grants access to a device that
is not attached.

One attempt to copy files to `D:\Sandbox` from such a session **reported success three times
and had created directories literally named `D:\Sandbox` inside the repository**. It was
caught by resolving the paths, and the directories were removed. It is recorded here because
it is the exact shape of failure this document exists to prevent: a report of success
generated by a check that could not fail.

**This is not a limitation that can be lifted from inside the container.** The proof must be
run by Mike, or by a builder running on his machine.

---

## 7. What raises confidence but proves nothing

The launcher was exercised end to end **on Linux**, against the real code: status with
nothing running; start (one process, PID recorded); a second start refused *by identity* —
process start time and command line, not just a PID number; `HTTP 200` from the portal;
restart with the old PID confirmed dead via `/proc`; stop with the port refusing connections
afterwards; and both secrets appearing in the logs as `[REDACTED]` with **zero** occurrences
of the real values.

That is a sound control core. **It moves no item in §3 off `UNVERIFIED`**, and the appendix
recording it says so on its own first line.

### 7.1 A verification error worth keeping

The first liveness check in that exercise was `ps -p <pid> >/dev/null && echo ALIVE`. It
reported a stopped process as alive — that `ps` build exits 0 whether or not the PID matches,
so the check was meaningless. Re-checked against `/proc/<pid>`: the process was gone.

The launcher's own reporting was correct throughout. The ad-hoc check was the unreliable one.
This is why the proof procedure tells Mike to believe the process ID rather than the browser.

---

## 8. How to change this document

Run the items. Then:

1. Paste the real output into `proof/launcher/LAUNCHER_PROOF.md` and replace each
   `UNVERIFIED` with `LIVE` or `UNAVAILABLE` — **no other word**.
2. Run `python scripts\dispatch_proof.py readiness`, then `rehearse --actor <you> --label <name>`.
3. Update §3 and §4 here with the counts, and record the outcome in `DECISION_LOG.md`.

**Nothing in this document is, or may become, a record of approval, acceptance or
verification by Mike Zachary.** It records only whether a command was run and what it
printed.
