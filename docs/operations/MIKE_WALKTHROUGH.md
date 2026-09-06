# THE LAST SIX ITEMS — WALKTHROUGH

**For:** Mike Zachary · **2026-09-05** · Have this open beside you at the laptop.

Six items are left: **1, 9, 10, 14, 15** need your hands, and **8** needs the external drive.
Budget about an hour for the five, five minutes for the drive.

---

## BEFORE YOU START — TWO THINGS THAT WILL TRIP YOU UP

**1. Type `py -3`, never `python`.**
On your machine `python` is the Microsoft Store stub. It answers *"Python was not found"* and looks
like a broken install. It isn't. Every command below already says `py -3`.

**2. Check your Desktop for an old `Dispatch` shortcut.**
If one is there from August it points at `C:\Dispatch\` — a different copy with **its own separate
database**. You would prove the wrong copy and not know it. I already moved the stale one to the
vault, so you should find none. If one is there, delete it.

**How to record a result:** each item has a `Result` field reading `UNVERIFIED`. Replace it with
**`LIVE`** or **`UNAVAILABLE`** — no other word — and paste what you actually saw into `Observed`.
The file is `D:\Dispatch\docs\readiness\LAUNCHER_PROOF_TEMPLATE.md`. Open it in Notepad.

---

# ITEM 1 — The launcher opens without typing anything

**Do this:**

1. Open `D:\Dispatch` in File Explorer.
2. **Double-click `DISPATCH_START_HERE.cmd`.**

**What you should see:** a black console window with a status block headed
`DISPATCH - Operations Control`, then a numbered menu — Start, Stop, Restart, Open Portal,
Refresh status, Settings, Reset Session, Quit.

**What proves it:** that it opened *from a double-click*. You typed nothing.

**Record:** select the first 25 lines of the window, right-click to copy, paste into `Observed`.
Set `Result` to `LIVE`.

> **Copying from a console window:** click the window, press `Ctrl+A`, then `Ctrl+C`. If that does
> nothing, right-click the title bar → Edit → Select All, then Edit → Copy.

---

# ITEMS 9 AND 10 — The menu itself

You are already looking at the menu from item 1. **Do not close the window.**

**Item 9 — all eight controls, in order.** Read the menu. There must be eight rows, in this order:

```
  [1] Start          [5] Refresh status
  [2] Stop           [6] Settings
  [3] Restart        [7] Reset Session
  [4] Open Portal    [8] Quit
```

If all eight are there in that order → `LIVE`. If any is missing or out of order, paste exactly
what you see and leave it `UNVERIFIED` — that is a real finding and I will fix it.

**Item 10 — the icons.** Each row may show a small icon before the label.

**This is the one that looks like a failure and is not.** If your console is set to a legacy code
page, the rows show plain `[1] Start` with **no icon at all**. That is **correct behaviour** — the
requirement is that icons either render properly *or are cleanly absent*. What would be a failure is
garbage characters like `â–¶` or `?` boxes where an icon should be.

- Icons render, or are cleanly absent → `LIVE`
- Garbled characters → paste them, leave `UNVERIFIED`

---

# ITEM 14 — Reset Session must REFUSE while Dispatch is running

**This is the most important item on the list.** The blueprint calls it "the one that matters most."

Clearing the session record while the server is alive is exactly how the orphan that ended your
August session was created: the process keeps holding the port, and the Control Center can no
longer stop it because it no longer knows the process exists.

**Do this:**

1. In the menu, press **`1`** and Enter — Start. Wait for it to report a process ID.
2. Now press **`7`** and Enter — Reset Session.

**What must happen:** it **refuses**, and it **names the process ID**. Something in the shape of
*"Dispatch is running (process ID 96532). The session record was not cleared."*

**If it refuses and names the ID → `LIVE`.** Paste the refusal into `Observed`.

**If it clears the record instead — stop.** Do not continue to item 15. Paste exactly what it said
and tell me. That is a serious defect and I need to see the wording.

---

# ITEM 15 — Reset Session clears a stale record, and nothing else

**Do this, in this order:**

1. Press **`2`** and Enter — Stop. Wait for it to confirm the process is gone.
2. Press **`7`** and Enter — Reset Session. **This time it should succeed** and say the record was
   cleared.
3. Press **`1`** — Start again.
4. Press **`4`** — Open Portal. Your browser opens.
5. **Look at the data.** There must still be **one load, one milestone, one rate confirmation, and
   one visibility record.** They were there before you started.

**What this proves:** Reset Session clears the *session record* — the note saying which process is
running — and touches **no freight data**. If the load is gone, the command is destroying operational
data and that is a stop-everything defect.

- Record cleared, load still present → `LIVE`
- Load missing → paste what you see, tell me immediately

**When you are done:** press **`2`** to stop Dispatch, then **`8`** to quit.

---

# ITEM 8 — The external drive

Two steps, and the first one is the one people skip.

## Step A — give the drive a permanent letter

Windows hands external drives whatever letter is free that day. If Dispatch is told to back up to
`T:\` and the drive mounts as `F:\` next week, the launcher will report `ABSENT` while the drive is
plugged in and spinning. **Pin the letter once and it never drifts.**

1. Plug in the 4 TB drive.
2. Press **`Windows key + X`**, choose **Disk Management**.
3. Find the 4 TB drive in the lower panel. Confirm the size — do not guess by name.
4. **Right-click its partition → Change Drive Letter and Paths… → Change…**
5. Pick a letter far from the ones Windows hands out automatically. **`T:` is free on your machine**
   (only `C:` and `D:` are in use) and `T` for *truck* is easy to remember.
6. OK, then Yes to the warning.

## Step B — tell Dispatch where it is

Open **Command Prompt** and run:

```
setx DISPATCH_BACKUP_DIR "T:\DispatchBackups"
```

`setx` saves it permanently to your account. **Close that window and open a new one** — `setx` does
not affect the window it was typed in.

Then create the folder and check what Dispatch now reports:

```
mkdir T:\DispatchBackups
py -3 -m dispatch_launcher status
```

**What you should see in the Backup block:** `ABSENT` — the folder is set, no archive in it yet.
That is the correct reading and it is honest.

## Step C — tell me

That is where you stop. **I run the backup, verify the hashes, restore it, and write the
verification record.** The mechanism is already proven — I ran it end to end today into scratch
space: 598,139 bytes captured, every hash verified, the restored database identical to the original
(35 tables, `integrity=ok`, row counts matching).

Only after a real restore is proven does the status change from `UNVERIFIED` to `VERIFIED`.
**Dispatch will never call a backup valid on the strength of the file existing.** That is the rule,
and it is why item 8 cannot be closed by simply making a copy.

---

# WHEN ALL SIX ARE DONE

Fifteen of fifteen recorded. That unlocks the **twenty-step rehearsal** — six of its twenty steps
are human-only by design — and then **PILOT-01**, one real load carried end to end.

**PILOT-01 is the completion gate.** Nothing counts as finished until a real load runs on your
laptop.

---

# IF SOMETHING GOES WRONG

Paste what you actually saw. Do not summarise it and do not clean it up — the exact wording is the
evidence. A failure recorded honestly is worth more than a pass recorded loosely, and every item
above is written so that an honest `UNAVAILABLE` is an acceptable answer.

The one exception is **item 14**. If Reset Session clears the record while Dispatch is running, stop
and tell me before doing anything else.
