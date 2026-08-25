# Dispatch — Operator Guide

**For:** the person running Dispatch day to day. **Current as of:** 2026-08-25.

This is the *day-to-day* guide. Two others sit either side of it:

- **Never started Dispatch before?** → `DISPATCH_FIRST_START_GUIDE.md` (where the launcher
  lives, what to double-click, what has to be set first).
- **Backups, restores, upgrades, database care?** → `docs/maintenance/DISPATCH_MAINTENANCE_GUIDE.md`.

> **Read this first.** Nothing below has been performed on Mike's laptop. Every procedure
> here is `IMPLEMENTED` and `UNVERIFIED` — see `docs/readiness/OPERATIONAL_PROOF.md`. When a
> screen and this document disagree, **the screen is right and this document is a defect**.

---

## 1. Starting and stopping

Double-click **`dispatch.bat`** in the Dispatch folder. A console window opens showing the
status block and then the menu. From PowerShell instead:
`powershell -ExecutionPolicy Bypass -File .\Dispatch.ps1`.

### The eight controls

| | Control | Does |
|---|---|---|
| `[1]` | **Start** | Starts one portal process, records its process ID, prints the address |
| `[2]` | **Open Dispatch** | Opens the portal in your browser |
| `[3]` | **Refresh Status** | Re-reads everything and redraws the status block |
| `[4]` | **Settings** | Every setting Dispatch consults, where each value came from, and the `setx` command that changes it |
| `[5]` | **Version** | Version, **commit**, Python, platform, repository, installed dependencies |
| `[6]` | **Restart** | Proves the old process is dead, then starts a new one |
| `[7]` | **Reset Session** | Clears a *stale* launcher record — see §1.2 |
| `[8]` | **Stop Dispatch** | Terminates the server and confirms it is gone |

Type the number, or the word (`start`, `stop`, `restart`, `settings`, `version`, `reset`,
`open`, `refresh`). `[Q]` quits the menu — **it does not stop Dispatch.**

Every control has a command-line equivalent: `python -m dispatch_launcher <start|stop|restart|status|settings|version|reset-session>`.

### 1.1 What Start refuses to do

- **Start twice.** A second Start reports the same process ID and starts nothing. It names
  how it knows — process start time and command line, not just a PID number.
- **Start over an orphan.** If the port is held by a process the launcher did not record, it
  refuses and names the process ID rather than creating a duplicate server.
- **Start without a secret.** In operational mode a missing `PORTAL_SECRET_KEY` or
  `DISPATCH_EMAIL_SECRET` stops the start, and the message names the **setting**, never a value.
- **Start on a stale record.** A recorded process that is no longer running is reported as a
  leftover, cleared, and the start proceeds.

### 1.2 Reset Session — the one control that can hurt you

Reset Session clears the launcher's **record** of a process. It does not touch loads,
milestones, evidence, or the database.

It **refuses while Dispatch is running**, and refuses when it cannot identify the live
process. That refusal is the point: clearing the record of a live server is how an orphan is
made — the process keeps the port and can no longer be stopped from the Control Center.

If it refuses and you believe it is wrong, stop Dispatch first. If Stop also refuses, open
Task Manager, find the named process ID, and end it there.

### 1.3 Shutting down properly

`[8] Stop`, then close the window. Stop confirms the process is gone before saying so. If
you close the console window without stopping, the server keeps running — the launcher will
tell you so on next start, and Task Manager will show it.

---

## 2. Reading the status block

Seven displays, each read from this machine at the moment you look:

| Display | What to check |
|---|---|
| **Status** | `RUNNING - process ID NNNN` or `STOPPED` |
| **Version** | Version and the **commit**. Quote the commit in any report or proof document |
| **Portal URL** | The address Start will use, or is using |
| **Database path** | Must match what the portal itself prints. If they differ, stop and fix that first |
| **Operations path** | `DISPATCH_OPERATIONS_ROOT`, or `UNCONFIGURED - using defaults` |
| **Archive path** | `DISPATCH_ARCHIVE_ROOT`, or the default, **marked as a default** |
| **Memory path** | `DISPATCH_MEMORY_ROOT`, or the default, marked as a default |

Plus mode, security settings (by **name**), backup status, and the last start failure in
plain language.

**A word you do not recognise is a defect, not a mystery.** The only status words Dispatch
uses are `LIVE`, `CONFIGURED`, `UNCONFIGURED`, `SIMULATED`, `UNAVAILABLE`, `MANUAL`,
`ABSENT`, `UNVERIFIED`.

### 2.1 `UNCONFIGURED` is not an error

It means nobody set that variable. The screen shows the fallback it will use instead. That
is normal on a fresh machine — but if you *meant* to point Dispatch at `D:`, then
`UNCONFIGURED` is telling you the `setx` did not reach this window. **`setx` only reaches
windows opened after it.** Close the console and reopen it.

---

## 3. Running a load

### 3.1 Practise first — rehearsal mode

**Do not learn Dispatch on a revenue load.** Rehearsal mode runs the real code path and tags
every record it creates.

```
python scripts\dispatch_proof.py readiness
python scripts\dispatch_proof.py rehearse --actor <your account> --label "first rehearsal"
```

`--actor` is your account. It is **required** — never defaulted and never inferred.
`readiness` checks this machine first and will tell you what is not ready; `rehearse` runs
the fourteen automatable steps and writes the proof report. `sessions` lists what you have
run, and `purge-plan <session_id>` reports exactly what cleaning up would remove before it
removes anything.

A rehearsal record is **labelled, not quarantined**: a red banner sits across every page for
as long as the session is open, and a red `REHEARSAL` badge stays beside the load
identifier **forever**, so a rehearsal load opened six months later still says what it is.

The full twenty-step procedure is `docs/readiness/OPERATIONAL_PROOF_PROCEDURE.md`. Six of
the twenty steps cannot be automated by design — a human performs them, or the proof is not
operational.

Clean up when finished: `purge-plan` first, then the purge — it reports before it acts.

### 3.2 The operator's daily surfaces

| Where | What it is for |
|---|---|
| `/dispatch` | Loads. `/dispatch/<load_id>` is the working detail page |
| `/calendar` | **Committed reality.** What is actually happening. Not a planning board |
| `/operations`, `/home` | The operating overview |
| `/exceptions` | What needs attention now |
| `/fleet`, `/fleet/driver/<id>`, `/fleet/equipment/<id>` | Drivers and equipment |
| `/billing`, `/profitability`, `/driver-pay` | Money |
| `/ifta`, `/ifta/review` | Fuel tax through finalization |
| `/compliance` | Documents and expiry |
| `/search` | Read-only retrieval. Reading never modifies (Driver-First D9) |
| `/settings` | Portal-side configuration |

### 3.3 The driver's surfaces

`/driver` — sign in with the driver PIN, which is a **separate** registry from the Authority
`DISPATCH_PIN` you use.

`/driver/home` is the Active Mission card and the rolling horizon. Milestones, POD upload,
exceptions and fuel receipts are all one tap from it. Everything here is built to the 70 MPH
Test: **if it takes more than seconds, it is a defect** — report it.

**A tap that does nothing is the worst failure Dispatch can have.** If a driver taps a
milestone and the screen does not tell them what happened — accepted or refused — that is a
defect, not a slow network. Report it with the load ID and the time.

---

## 4. What Dispatch does not know

- **Hours of service.** There is no ELD feed. Dispatch does **not** know a driver's HOS.
  Anything that implies it does is a defect.
- **Where the truck is.** No GPS, no telematics.
- **Traffic, weather, or road closures.** Route Risk has no feed configured.
- **What a load actually pays until you enter it.** No load board is connected.
- **Anything from your accounting system, scanner, or Outlook.** All `UNCONFIGURED`.

**Every external system is `UNCONFIGURED`.** Any number derived from fuel price, MPG, or
drive-speed constants is an **estimate** from a default, labelled as one, and has never been
checked against a real settlement. See `docs/readiness/KNOWN_LIMITATIONS.md`.

---

## 5. When something goes wrong

### 5.1 Read the sentence, then the log

A failed start prints **one plain sentence** on screen. The stack trace goes to the launcher
log — never to the screen, and never with a secret in it. `python -m dispatch_launcher --logs`
prints the log directory. `Refresh Status` shows the most recent failure under
**Last start failure**.

### 5.2 The four common ones

| Symptom | What it is |
|---|---|
| "port 8080 is already in use" | Something is already on the port — Dispatch, or another program. Stop it, or set `PORTAL_PORT` |
| "cannot start because PORTAL_SECRET_KEY … is not set" | The secret is unset **in this window**. `setx`, then open a *new* window |
| Paths show `UNCONFIGURED` when you set them | Same cause. `setx` does not reach windows already open |
| Version shows commit `UNVERIFIED` | Git is not installed, or this is a copy of the folder without `.git`. Dispatch still runs; it just cannot prove which code it is |

### 5.3 Before you report a problem

Capture these three, and the report is actionable:

1. `python -m dispatch_launcher version` — the **commit**
2. `python -m dispatch_launcher status` — the whole block
3. The exact sentence on screen, and the last 25 lines of the launcher log

The log redacts secret **values** and prints secret **names**. It is safe to send. Check it
anyway — that habit is worth more than the redaction.

---

## 6. Rules that are yours, not the software's

1. **Nothing says Mike approved it unless Mike approved it.** Dispatch will never write that
   attribution on its own. If you ever see one you did not make, treat it as a serious defect.
2. **Score does not decide.** A low score means "look at this later", never "this was rejected".
3. **A backup is not good until it has been restored.** Dispatch will show `UNVERIFIED`
   forever until a restore is performed and recorded. Believe it.
4. **Rehearsal loads are labelled, not walled off.** A report that forgets to exclude them
   will count them. The badge is the backstop; the discipline is yours.
5. **Believe the process ID, not the browser.** A page that still loads can be served by a
   process you thought you stopped.
