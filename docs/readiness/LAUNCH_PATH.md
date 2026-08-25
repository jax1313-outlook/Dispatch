# Dispatch — The Launch Path

**Question this document answers:** what, exactly, does Mike click?

**Investigated:** 2026-08-25 · **Commit:** `43a49ef` (before this mission's changes)
**Method:** repository evidence and commands actually run. Nothing here is inferred from a
document that says a thing exists.

---

## 1. The finding

`dispatch.bat` exists, is current, works, and **is not findable.** That is not a user error
and it is not a small problem — a launch file nobody can find is a launch file that does not
exist.

Three things cause it, and all three are measurable rather than matters of opinion:

**The root folder holds 82 visible entries** — 13 folders and 69 files. Sixty of the files
are Markdown documents, most of them named `DISPATCH_SOMETHING.md`.

**Windows hides known file extensions by default**, so `dispatch.bat` displays as
**`dispatch`** — and there is a folder in the same directory also displaying as **`dispatch`**
(the Python package). `Dispatch.ps1` displays as **`Dispatch`** too. Three items, one visible
name.

**Explorer sorts folders above files.** So the first `dispatch` Mike sees is the folder. He
clicks it, gets a directory of `.py` files, and reasonably concludes he is in the wrong place.

```
[DIR ] dispatch            <-- displays as "dispatch". Python source. Useless to click.
[DIR ] dispatch_launcher
   ... 11 more folders ...
   ... 8 files ...
[FILE] dispatch.bat         <-- displays as "dispatch". THIS is the launcher.
[FILE] Dispatch.ps1         <-- displays as "Dispatch".
[FILE] DISPATCH_ARCHITECTURE_CONFORMANCE_REPORT.md
   ... ~40 more DISPATCH_*.md files ...
```

Everything downstream of "nobody has ever double-clicked `dispatch.bat`" follows from this.
The launcher was never the blocker. Finding it was.

---

## 2. Every launcher in the repository, and what each is

Found by searching for `*.bat`, `*.cmd`, `*.ps1`, `*.exe`, `*.lnk`, `*.vbs`, `*.sh`
across the whole repository. **All six live at the root; there are no others anywhere.**

| File | Exact path | Status | What it does |
|---|---|---|---|
| **`DISPATCH_START_HERE.cmd`** | `<repo>\DISPATCH_START_HERE.cmd` | **CURRENT — start here** | One double-click: sets up, starts, opens the browser. Created by this mission |
| `dispatch.bat` | `<repo>\dispatch.bat` | **CURRENT — the Control Center** | Opens the eight-item menu. Correct for somebody who already runs Dispatch |
| `Dispatch.ps1` | `<repo>\Dispatch.ps1` | CURRENT — alternate | Same as `dispatch.bat` for a PowerShell user |
| `run_portal.bat` | `<repo>\run_portal.bat` | **SUPERSEDED** | Runs `python portal\app.py` directly. No Stop, no Restart, no status, no PID handling. Its own first comment says it is superseded |
| `run_sync.bat` | `<repo>\run_sync.bat` | Utility, not a launcher | Pulls approved records from a VPS |
| `run_bootstrap_d_drive.bat` | `<repo>\run_bootstrap_d_drive.bat` | Utility, not a launcher | One-time `D:` migration |
| `setup_dispatch_folders.ps1` | `<repo>\setup_dispatch_folders.ps1` | Setup, not a launcher | Persists the storage roots with `setx` |

**Is `dispatch.bat` obsolete? No.** It is current and it works — proven in §4. It is simply
not the right *first* contact, for the reason in §5.

**Is there more than one launcher? Yes — three**, and until now nothing said which to use.

---

## 3. What actually starts Dispatch

Neither batch file starts anything itself. Both hand over immediately:

```
DISPATCH_START_HERE.cmd  ->  python -m dispatch_launcher start-here
dispatch.bat             ->  python -m dispatch_launcher            (menu)
                                        |
                                        v
                             dispatch_launcher/control.py  start()
                                        |
                                        v
                             python portal/app.py          (detached, PID recorded)
                                        |
                                        v
                             Flask serving http://127.0.0.1:8080
```

This is deliberate and it is written into `dispatch.bat` itself: *"A batch file cannot be
tested, so a batch file is not allowed to hold logic."* Every decision — whether Dispatch is
running, which process is the server, whether a second start is safe — lives in Python the
test suite exercises.

---

## 4. Proof — commands run, output as printed

Run on this build container against commit `43a49ef`, `PORTAL_PORT=8123`. **This is Linux
evidence. It is proof the control core works; it is not proof about Windows.** Nothing here
moves any item in `docs/readiness/OPERATIONAL_PROOF.md` §3 off `UNVERIFIED`.

**Start**

```
$ python -m dispatch_launcher start
  Dispatch is running (process ID 4401) at http://127.0.0.1:8123
      Log directory: /home/user/Dispatch/logs
EXIT=0
```

**Start again — must refuse, and must say how it knows**

```
$ python -m dispatch_launcher start
  Dispatch is already running (process ID 4401). Nothing was started.
      Process ID 4401 is the Dispatch server this launcher started
      (confirmed by process start time and command line).
EXIT=0
```

Identity, not just a PID number. A recycled PID has a different start time.

**Is it actually serving?**

```
$ curl http://127.0.0.1:8123/login
HTTP 200
```

**Stop**

```
$ python -m dispatch_launcher stop
  Dispatch has stopped. Process ID 4401 is gone.
EXIT=0

$ curl --max-time 3 http://127.0.0.1:8123/login
connection refused
```

**The new one-click path, on a machine with no secrets configured**

```
$ python -m dispatch_launcher start-here          # what DISPATCH_START_HERE.cmd calls

  DISPATCH

    [OK  ] Dispatch folder
           /home/user/Dispatch
    [OK  ] Security settings  (changed)
           Created 2 security setting(s) ... The values are not shown anywhere, by design.
    [OK  ] Flask
           Already installed.
    [OK  ] Start
           Dispatch is running (process ID 8013) at http://127.0.0.1:8124
    [OK  ] Desktop shortcut
           Not created: desktop shortcuts are a Windows feature and this is not Windows.
    [NOTE] Open in browser
           The browser could not be opened automatically. Go to http://127.0.0.1:8124

    Dispatch is RUNNING at http://127.0.0.1:8124
EXIT=0

$ curl http://127.0.0.1:8124/login
HTTP 200
```

**The failure path, with the port deliberately held by another process**

```
    [STOP] Start
           Dispatch could not start because port 8126 is already in use.

    DISPATCH DID NOT START.

    What to do:
      Something else on this computer is using the address Dispatch wants.
      Usually that is a copy of Dispatch that was left running.

      Try this first: close every black Dispatch window, wait ten seconds,
      and double-click DISPATCH_START_HERE again.

      If that does not work, restart the computer and try once more.
EXIT=1
```

One sentence, then instructions. No traceback on screen — the trace goes to the launcher log.

---

## 5. Why a second launch file, rather than fixing the first

`dispatch.bat` is correct for what it is and was not changed. It fails as a *first* contact
for two reasons that only appear on a real first attempt:

**It presents a menu, not a result.** Mike double-clicks and Dispatch has not started; it is
waiting for him to type a number. "One click, Dispatch starts" is a different promise from
"one click, a menu appears".

**On a fresh machine it refuses to start, correctly, and he cannot fix it.** `portal/config.py`
blocks an operational start while `PORTAL_SECRET_KEY` or `DISPATCH_EMAIL_SECRET` still hold
the values published in this repository — anyone who can read the source could otherwise
forge a session cookie or mint a stakeholder link. Refusing is the only defensible behaviour.
But the documented remedy is `setx` in a Command Prompt, and requiring that of a
non-developer means Dispatch never starts at all.

`DISPATCH_START_HERE.cmd` does what an installer does: generates real per-machine secrets,
persists them with `setx`, checks the dependency, starts, and opens the browser.

**It does not weaken the refusal — it satisfies it.** The published defaults stay rejected;
`tests/test_first_run.py` asserts exactly that. What changes is that the machine now has
values of its own. The generated values are never printed, logged, or returned, and there is
no flag that reveals them.

---

## 6. What Mike does

### The first time

1. Open the Dispatch folder.
2. Double-click **`DISPATCH_START_HERE`**.
3. Wait. A black window opens and prints a short list.
4. The browser opens at `http://127.0.0.1:8080`.

Everything else is automatic: security settings created, Flask installed if missing, a
**Dispatch icon placed on the Desktop.**

### Every time after that

**Double-click the Dispatch icon on the Desktop.** The repository folder never has to be
opened again — which is the point, since not being able to find it was the whole defect.

### How he knows it is running

- The black window says `Dispatch is RUNNING at http://127.0.0.1:8080`.
- The browser opens and shows the Dispatch sign-in page.
- The window stays open. **Open window = Dispatch is running.**

### How he knows it failed

- The window says `DISPATCH DID NOT START` in those words.
- A line marked `[STOP]` names what stopped it.
- `What to do:` lists the steps, in plain language.
- **The window does not close.** Every failure path ends in a `pause`, because a window that
  vanishes instantly reads as "nothing happened".

`[NOTE]` is not a failure. It means something optional did not work and Dispatch is running
anyway — a browser that would not open is the usual one.

### How he stops it

Press any key in the black window. It stops Dispatch and confirms the process is gone.

---

## 7. What must exist on his machine

| | Required? | If missing |
|---|---|---|
| **Python 3.11+** | **Yes** | `DISPATCH_START_HERE.cmd` says so and links python.org, naming the **"Add Python to PATH"** checkbox — off by default, and the difference between working and appearing broken |
| **Flask** | **Yes** | Installed automatically on first run. If that fails, the exact command to type is printed |
| The Dispatch folder | **Yes** | Nothing to run |
| `paramiko`, `anthropic` | No | Reported `ABSENT`. Dispatch runs |
| `pip install -e .` | **No** | Not required. Verified |
| Storage roots (`DISPATCH_*_ROOT`) | No | Reported `UNCONFIGURED` with the fallback named. Dispatch runs |
| `PORTAL_SECRET_KEY`, `DISPATCH_EMAIL_SECRET` | Yes, and **created automatically** | Would block an operational start. This is what `DISPATCH_START_HERE.cmd` fixes |
| Internet | Only if Flask is missing | pip needs it once |

---

## 8. Control Center — verified by running it, not by reading about it

All eight controls exist. Confirmed by rendering the real menu from `dispatch_launcher/cli.py`
and by `python -m dispatch_launcher --help` listing each as a subcommand:

```
  [1] ▶ Start          -> python -m dispatch_launcher start
  [2] 🌐 Open Dispatch  -> python -m dispatch_launcher open
  [3] 🔄 Refresh Status -> python -m dispatch_launcher status
  [4] ⚙ Settings       -> python -m dispatch_launcher settings
  [5] ℹ Version        -> python -m dispatch_launcher version
  [6] ↻ Restart        -> python -m dispatch_launcher restart
  [7] ⎌ Reset Session  -> python -m dispatch_launcher reset-session
  [8] ■ Stop Dispatch  -> python -m dispatch_launcher stop
  [Q] Quit
```

**Missing: none.** Order and glyphs match the Control Center v1 specification. The icons drop
cleanly on a console that cannot encode them, rather than printing mojibake or crashing.

---

## 9. What remains UNVERIFIED

**Everything in §6 and §7, on Windows.** Section 4's evidence is Linux. No Windows-specific
call — `py.exe` resolution, `setx`, `taskkill`, `tasklist`, `Get-CimInstance Win32_Process`,
detached process creation from a double-clicked file, WScript.Shell shortcut creation — has
been executed anywhere.

Specifically unverified:

1. That double-clicking `DISPATCH_START_HERE.cmd` opens a window at all.
2. That `py -3` resolves to an interpreter that can reach Flask.
3. That `setx` succeeds for this user, and that a **new** window sees the value.
4. That the Desktop shortcut is created, and that clicking it works.
5. That Defender or SmartScreen does not block a detached process from a double-clicked file.
6. That the console renders the status block and the menu glyphs.
7. That `pip install flask` succeeds on that machine and network.

The fifteen first-start acceptance items in `docs/readiness/LAUNCHER_PROOF_TEMPLATE.md`
remain `UNVERIFIED`. This mission changed what Mike clicks; it did not, and from a build
container cannot, prove what happens when he clicks it.

---

## 10. The exact next step

> **Open the Dispatch folder on the laptop, double-click `DISPATCH_START_HERE`, and write
> down what happens — including if nothing does.**

Three outcomes, all useful:

- **A browser opens on the Dispatch sign-in page.** The launch path is proven. Item 1 of the
  fifteen moves to `LIVE`, and the load proof becomes reachable.
- **A window opens and says `DISPATCH DID NOT START`.** Send the window's contents. The
  reason is named there in plain language.
- **Nothing happens at all.** That is the most informative answer of the three, and it means
  Windows would not run the file — Python missing, or a security policy. Say so exactly.

There is no step before this one, and no way to do it from a build container.
