# TURNING REHEARSAL MODE ON AND OFF

**For:** Mike Zachary · **2026-09-06** · Have this open at the laptop.

Rehearsal mode makes rule 1 of your own doctrine true: **tagged at creation.** With it on, every
load, milestone and evidence record you create is stamped with a session id and marked on screen.
With it off, records are live.

---

## THE ONE THING THAT WILL BITE YOU

**Use `set`, never `setx`.**

| | |
|---|---|
| **`set`** | Lasts until you close that window. **This is what you want.** |
| **`setx`** | **Permanent.** Every future start of Dispatch is in rehearsal mode — including PILOT-01 |

`setx` is right for the backup folder, which never changes. It is wrong here. Rehearsal mode is
something you switch on for an afternoon of testing and off again, and a permanent setting would
tag your real first load as a rehearsal — the exact opposite of the reason you asked for it.

**If you only remember one line from this page: `set`, not `setx`.**

---

## TURNING IT ON

### Step 1 — create a session

Open **Command Prompt** in `D:\Dispatch` and run this, changing the label to whatever you are about
to test:

```
py -3 -c "from dispatch import rehearsal; s = rehearsal.start_session(label='Tab walk testing', actor_id='mike'); print(s['session_id'])"
```

It prints one line, an id shaped like this:

```
REH-20260906-1568E597
```

**Copy that id.** It is the only thing you need from this step.

### Step 2 — point the variable at it

**In the same window**, paste your id in place of the example:

```
set DISPATCH_REHEARSAL_SESSION=REH-20260906-1568E597
```

No quotes. No spaces around the `=`.

### Step 3 — check it before you start

```
py -3 -m dispatch_launcher settings
```

**What you want to see:** `DISPATCH_REHEARSAL_SESSION` with `status CONFIGURED` and your id as the
value, and **no** `*** REHEARSAL SETTING PROBLEM ***` block at the top.

If that block appears, it tells you exactly what is wrong and what to type. It catches a mistyped id
and a session that has already been closed — both of which would otherwise tag every record with a
string that leads nowhere.

### Step 4 — start Dispatch from that same window

```
py -3 -m dispatch_launcher start
```

**It must be that window.** A window opened later, or the desktop shortcut, does not carry the
setting — `set` only reaches the window it was typed in and anything started from it.

**How you know it worked:** every page in the portal carries a wide red band across the top reading
**REHEARSAL MODE — THIS IS NOT A LIVE MISSION**, with the session id on it. You cannot miss it, and
that is deliberate.

---

## TURNING IT OFF

### Step 1 — stop Dispatch

Menu option `[2]`, or close the launcher window.

### Step 2 — close the session

```
py -3 -c "from dispatch import rehearsal; rehearsal.close_session('REH-20260906-1568E597', result='PASSED', actor_id='mike', note='Tab walk testing')"
```

`result` must be **`PASSED`**, **`FAILED`** or **`ABANDONED`** — nothing else is accepted. Use
`ABANDONED` if you simply stopped partway; it is not a failure, it means the rehearsal did not run
to a conclusion.

### Step 3 — clear the variable

```
set DISPATCH_REHEARSAL_SESSION=
```

Nothing after the `=`. Or simply **close the window** — with `set`, that is enough, which is the
whole reason for using it.

### Step 4 — confirm you are back on live

```
py -3 -m dispatch_launcher settings
```

`DISPATCH_REHEARSAL_SESSION` should read `UNCONFIGURED <-- not set`, and under it
*"without it — no rehearsal; records are live."*

**Do this before PILOT-01.** It is the check that stops your one real load being recorded as a test.

---

## SEEING WHAT YOU HAVE DONE

**List every session, past and present:**

```
py -3 scripts/dispatch_proof.py sessions
```

**See what removing one would delete — this only reports, it removes nothing:**

```
py -3 scripts/dispatch_proof.py purge-plan REH-20260906-1568E597
```

**Actually deleting a session's records is deliberately not a command you can run by accident.** It
refuses without an explicit confirmation, because purging data on your machine is your decision. Ask
me when you want one done and I will show you the plan first.

---

## WHAT REHEARSAL MODE DOES NOT DO

**It does not hide anything.** You ruled *show both with rehearsal records marked*, so rehearsal
loads still appear on every screen, still count in the Active Loads card, and still land in the
Financial Snapshot — labelled, never removed.

**It does not stop email.** ARRIVE still sends. If you are testing the arrival notice, the notice
goes to whatever address is on the record. **Use a test record with your own address on it**, not a
real broker's.

**It does not tag what already exists.** Only records created while the session is active. The two
test loads from before today were tagged by hand afterwards, and that is a separate operation.

---

## THE SHORT VERSION

```
py -3 -c "from dispatch import rehearsal; s = rehearsal.start_session(label='testing', actor_id='mike'); print(s['session_id'])"
set DISPATCH_REHEARSAL_SESSION=<the id it printed>
py -3 -m dispatch_launcher settings          <-- no PROBLEM block
py -3 -m dispatch_launcher start             <-- red band on every page

...test...

py -3 -m dispatch_launcher stop
set DISPATCH_REHEARSAL_SESSION=
```

**`set`, not `setx`.**
