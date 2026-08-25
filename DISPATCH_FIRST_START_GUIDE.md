# Dispatch — First Start Guide

**For:** Mike Zachary, Owner/Operator, Level 1 Transport
**Commit this guide was verified against:** `abb963f827e815fa2b37a785024e4aa288ebfd11`

Everything below was **run and observed**, not described from intent. Every screen
in this guide is real output copied from an actual run. Where something has only
been proven on Linux and not on your Windows machine, it says so.

---

> **Updated 2026-08-25 — the file to double-click has changed.**
>
> This guide originally said to double-click `dispatch.bat`. That file still exists and
> still works, but it is **not** what to click first. Two reasons, both found by
> investigating why nobody ever clicked it:
>
> - With Windows' default *"hide extensions for known file types"*, `dispatch.bat` displays
>   as **`dispatch`** — and there is a **folder** in the same directory also displaying as
>   **`dispatch`**, listed first because Explorer sorts folders above files. Among 82
>   entries in that folder, the obvious thing to click is the wrong one.
> - On a machine that has never run Dispatch, `dispatch.bat` opens a *menu* rather than
>   starting anything, and then refuses to start at all until two security settings exist.
>
> **Double-click `DISPATCH_START_HERE` instead.** Full evidence:
> `docs/readiness/LAUNCH_PATH.md`.

## 1. Where the launcher lives

**`DISPATCH_START_HERE.cmd`, in the root of the Dispatch folder** — the same folder that
contains `portal\`, `dispatch\` and `README.md`.

```
Dispatch\
├── DISPATCH_START_HERE.cmd <-- DOUBLE-CLICK THIS
│                               (Windows may show it as "DISPATCH_START_HERE")
├── dispatch.bat                the Control Center menu, once Dispatch is working
├── Dispatch.ps1                the same menu, for a PowerShell window
├── dispatch_launcher\          the Control Center itself
├── portal\                     the Dispatch portal
├── dispatch\                   the engine  (a FOLDER — not the launcher)
└── ...
```

**After the first successful start you will not need this folder again.** The first run puts
a **Dispatch icon on your Desktop**; double-click that from then on.

I cannot tell you the absolute path, because I have never seen your machine and
will not guess at one. To find it, open the Dispatch folder in File Explorer and
click the address bar — or run this in PowerShell:

```powershell
Get-ChildItem -Path C:\,D:\ -Filter DISPATCH_START_HERE.cmd -Recurse -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty FullName
```

### Every launcher and Control Center file

All paths are relative to the Dispatch folder. All are in the repository.

| Path | What it is |
|---|---|
| `DISPATCH_START_HERE.cmd` | **The file you double-click.** Finds Python, hands off to `start-here`, holds the window open on failure. Holds no logic. |
| `dispatch_launcher\first_run.py` | What `start-here` runs: creates this machine's security settings, installs Flask if missing, starts, opens the browser, makes the Desktop icon. |
| `dispatch.bat` | The Control Center menu. Sets the UTF-8 code page, finds Python, hands off. Holds no logic. |
| `Dispatch.ps1` | Same, for a PowerShell console. Also holds no logic. |
| `dispatch_launcher\__init__.py` | Package definition and the control-not-application boundary. |
| `dispatch_launcher\__main__.py` | Makes `python -m dispatch_launcher` work. |
| `dispatch_launcher\cli.py` | The eight-item menu and the one-shot commands. |
| `dispatch_launcher\control.py` | Start, Stop, Restart, Open, Reset Session. |
| `dispatch_launcher\status.py` | The status screen. |
| `dispatch_launcher\settings.py` | The Settings and Version screens. |
| `dispatch_launcher\glyphs.py` | Decides whether your console can draw the menu icons. |
| `dispatch_launcher\probe.py` | Reads Dispatch's real configuration, in a separate process. |
| `dispatch_launcher\processes.py` | Is that process alive, is it really Dispatch, how to end it. |
| `dispatch_launcher\pidfile.py` | The record of which process the launcher started. |
| `dispatch_launcher\backups.py` | Observes the last backup. Never calls it valid without a verified restore. |
| `dispatch_launcher\locations.py` | Where the launcher keeps its own four files. |
| `dispatch_launcher\redaction.py` | Strips secret values before anything is logged. |
| `tests\test_launcher.py` | 103 tests. |
| `tests\test_control_center.py` | 78 tests. |
| `docs\readiness\CONTROL_CENTER.md` | The full operator guide. |
| `docs\readiness\LAUNCHER_PROOF_TEMPLATE.md` | The acceptance-evidence sheet to fill in. |
| `run_portal.bat` | The **old** launcher. Still works, starts the portal only — no Stop, no status. Superseded by `dispatch.bat`. |

> **The launcher only works from inside the Dispatch folder.** I copied
> `dispatch.bat` and `dispatch_launcher\` to an empty folder on their own and ran
> them. It did not crash — but every line read `UNVERIFIED`:
>
> ```
>     Version               UNVERIFIED (no version could be read)
>     Commit                UNVERIFIED
>                           this folder is not a git checkout
>     Portal address        UNVERIFIED
> ```
>
> It cannot find Dispatch, so it can start nothing. Move or copy the **whole**
> folder, never the launcher on its own.

---

## 2. What you need before the first launch

| # | Requirement | Status | How to check |
|---|---|---|---|
| 1 | **Python 3.11 or newer** | Required | `py -3 --version` |
| 2 | **Flask 3.0 or newer** | Required | `py -3 -m pip install "flask>=3.0"` |
| 3 | **`PORTAL_SECRET_KEY`** | **Required — Dispatch refuses to start without it** | Control Center → `[4] Settings` |
| 4 | **`DISPATCH_EMAIL_SECRET`** | **Required — same** | Control Center → `[4] Settings` |
| 5 | **Sign-in PIN** | Required to get past the login page — **`DISPATCH_START_HERE` now asks you to choose one** | see step 3 below |
| 6 | Storage folders (`D:\Dispatch Operations` etc.) | **Optional** | `.\setup_dispatch_folders.ps1` |
| 7 | Database | **Nothing to do** — created automatically | see below |
| 8 | `pip install -e .` | **Not needed** | see below |
| 9 | `paramiko` | **Not needed to run Dispatch** | see below |

**Two things you were probably told you needed and do not.** I ran the Control
Center and the portal in an environment where `pip show cin-hybrid` reports
*"Package(s) not found"* and `import paramiko` fails with *"No module named
'paramiko'"*. Both started, ran and stopped normally. `paramiko` is only used by
the VPS sync tool; the install is only needed for the `cin-portal-*` shortcut
commands, and `py -3 -m portal.cli` does the same job without it.

**The database needs nothing from you.** `dispatch.db` does not exist before the
first start, and — I checked — it still does not exist after starting the server
and loading the login page. It is created the first time Dispatch touches freight
data. Observed: the file appeared at `portal\data\dispatch.db`, 561,152 bytes, the
moment the first load list was read.

**The storage folders are optional.** With none of the `DISPATCH_*` variables set,
Dispatch runs entirely inside the repository folder and the status screen says so
plainly — `Operations root  UNCONFIGURED - using defaults`. Setting them moves your
operational data onto `D:\` where `setup_dispatch_folders.ps1` puts it.

### Setting the two required secrets

```powershell
setx PORTAL_SECRET_KEY "<a long random value you generate>"
setx DISPATCH_EMAIL_SECRET "<a different long random value>"
```

`setx`, not `set`. `set` lasts until the window closes, which gives you the most
confusing possible bug: Dispatch works this afternoon and is broken tomorrow.
**A new value only reaches windows opened afterwards** — close the window and
open a new one before launching.

---

## 3. The first screen

Double-click `dispatch.bat`. This is the **actual** first screen on a machine
where nothing has been configured yet:

```
  DISPATCH - Operations Control

    Dispatch              STOPPED

    Version               0.1.0 (portal.__version__)
    Commit                abb963f827e815fa2b37a785024e4aa288ebfd11
    Portal address        http://127.0.0.1:8080
    Mode                  operational
                          DISPATCH_MODE is not set; Dispatch defaults to operational.
    Security settings     UNCONFIGURED - DISPATCH_EMAIL_SECRET, PORTAL_SECRET_KEY
                          Dispatch will refuse to start until this is set.

    Database              ...\portal\data\dispatch.db
    Portal data           ...\portal\data
    Operations root       UNCONFIGURED - using defaults
    Archive root          ...\portal\data  (default - DISPATCH_ARCHIVE_ROOT is not set)
    Memory root           ...\portal\data  (default - DISPATCH_MEMORY_ROOT is not set)
    Contract archive      ...\cin_lite\Archive

    Backup                UNCONFIGURED
                          No backup location is configured. Set DISPATCH_BACKUP_DIR to the
                          folder scripts/dispatch_backup.py writes to.

    Logs                  ...\logs
    Last start failure    ABSENT - no failure recorded

  [1] ▶ Start
  [2] 🌐 Open Dispatch
  [3] 🔄 Refresh Status
  [4] ⚙ Settings
  [5] ℹ Version
  [6] ↻ Restart
  [7] ⎌ Reset Session
  [8] ■ Stop Dispatch
  [Q] Quit

  Choose:
```

**If the icons are missing, nothing is wrong.** A console that is not on UTF-8
cannot draw them, so the Control Center leaves them out rather than printing
garbage. The rows read `[1] Start`, `[2] Open Dispatch`, and so on. The number is
what you type either way.

**A lot of `UNCONFIGURED` on the first screen is normal.** Only the
`Security settings` line stops you from starting.

---

## 4. Status messages you should expect

Real output, copied from runs.

| When | Message |
|---|---|
| Start, secrets not set | `Dispatch cannot start because DISPATCH_EMAIL_SECRET, PORTAL_SECRET_KEY is not set, and Dispatch is in operational mode. Set a real value for it and start again.` |
| Start, working | `Dispatch is running (process ID 5118) at http://127.0.0.1:8094` |
| Start, already running | `Dispatch is already running (process ID 15628). Nothing was started.` |
| Status, running | `Dispatch              RUNNING - process ID 5118` |
| Status, secrets set | `Security settings     CONFIGURED - required settings have real values` |
| Restart | `Stopped process ID 15628. Dispatch is running (process ID 16365)` |
| Stop | `Dispatch has stopped. Process ID 16365 is gone.` |
| Stop, nothing running | `Dispatch is not running. Nothing to stop.` |
| Open, no browser | `The browser could not be opened automatically. Go to http://127.0.0.1:8096` |
| Reset Session, while running | `Dispatch is running (process ID 12246). Nothing was reset.` |
| Reset Session, stopped and clean | `Nothing needed resetting. Dispatch is stopped and the session is already clean.` |

The launcher **names a setting and never prints its value**. I checked the log
after a run with real secrets in the environment: it recorded
`{"DISPATCH_EMAIL_SECRET": "[REDACTED]", "PORTAL_SECRET_KEY": "[REDACTED]"}`, and
a search for either real value across every log file returned **0 matches**.

---

## 5. Your first actions, in order

**1. Double-click `dispatch.bat`.** Read the status screen. It will almost
certainly say `Security settings UNCONFIGURED`.

**2. Press `4` for Settings.** It lists every setting, what it is for, and the
exact `setx` command for each. Secrets show as `not set` — never a value.

**3. Set the two secrets** with the commands from that screen. **Close the window
and open a new one.** `setx` does not reach windows that are already open.

**4. Create the sign-in PIN.** *(Updated 2026-08-25 — you no longer do this by hand.)*

**`DISPATCH_START_HERE` asks you to choose a PIN on its first run**, in the same
window, typed twice with nothing echoed. That is the whole step. There is no
command to type and no terminal to open.

The manual route still exists and still works if you want it — `py -3 -m portal.cli`
at the terminal, which asks for a user id, a display name and a PIN twice, and
refuses to run a second time. It is no longer the expected path.

> **What this guide warned about, and why it is now fixed.** This section used to
> say: *"If you skip this, Dispatch starts fine but you cannot get in."* That was
> accurate and it was the whole problem — Dispatch shipped able to start and unable
> to be entered, and the error it showed named `cin-portal-init-admin`, a console
> script that only exists after `pip install -e .`, which row 8 of the table above
> correctly says is not needed. A first-time operator was sent to a command that
> was not installed. Now the launcher asks, and there is nothing to skip.

**If you forget the PIN:** `dispatch.bat` → `[P] Reset PIN`. It does not ask for
the old one — it asks you to type `RESET`, then to choose a new PIN. Nothing else
is touched.

**5. Double-click `dispatch.bat` again and press `1` for Start.** You should see
`Dispatch is running (process ID …) at http://127.0.0.1:8080`.

**6. Press `2` for Open Dispatch.** The browser opens the sign-in page. Enter the
PIN from step 4.

> *(Was: a note that the login page said "Sign In — L2-COS Operations Portal",
> the old name still in the portal's own chrome. Renamed 2026-08-25 — the page is
> titled **"Sign In — Dispatch"** now, and a test keeps the old name from
> returning.)*

**7. When you are finished, press `8` to Stop**, and confirm it says
`Process ID … is gone.`

### If something goes wrong

- **"Dispatch is already running" but nothing is** → press `7`, Reset Session.
- **Port already in use** → press `4`, Settings, and `setx PORTAL_PORT "8081"`.
- **Anything else** → the log folder is on the status screen. Secrets are
  redacted before anything is written there.

---

## 6. What has not been proven

**Nothing in this guide has been run on your Windows machine.** Every screen above
came from a real run in a Linux container: start, double-start refusal, HTTP 200
from the portal, restart with the old process confirmed dead, stop, the secret
refusal, the redacted log, the missing-identity login response, and the database
appearing on first use. That is evidence of software behaviour, not proof that it
works on your machine.

Six things only your machine can answer: whether `py.exe` is installed and points
at the Python that has Flask; whether PowerShell will run
`Get-CimInstance Win32_Process` for your account; whether `taskkill` is permitted;
whether the `D:` variables reach a double-clicked `.bat`; whether Defender or
SmartScreen interferes with a detached process; and whether your console renders
the status block correctly.

`docs\readiness\LAUNCHER_PROOF_TEMPLATE.md` has all fifteen acceptance items with
the exact command for each and a blank column for what you actually see.

---

*Nothing in this guide is accepted doctrine or a Mike decision.*
