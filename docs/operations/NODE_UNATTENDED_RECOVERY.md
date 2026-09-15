# Node Unattended Recovery (R5) — Checklist for Mike

**What this is:** the steps that let the Dispatch node — the laptop or mini PC in the Pelican case —
come back by itself after power is lost, with no keyboard, and show that it is back on the tablet.

**The requirement** (CLAUDE.md §5A, R5, from `docs/campaign/CONOPS_v1.1.md`): *BIOS auto-power-on,
auto-login, services on boot, and a self-test reporting node status to the portal on recovery.*

**Who does this: you.** Every step below changes the machine's firmware or Windows configuration.
**Nothing in the repository performs any of them**, and no build session did. Each is written so you
can do it yourself, in order, and tick it off.

**Status: every item is `MANUAL` and `UNVERIFIED`** until you have done it and pulled the plug to
prove it (section 6).

---

## Before you start

- [ ] Dispatch starts by double-clicking `DISPATCH_START_HERE.cmd` on this machine.
- [ ] You know the Windows account Dispatch runs under, and its password.
- [ ] If the internal drive uses BitLocker, you have its **recovery key** somewhere that is not this
      machine. (A firmware change can make BitLocker ask for it on the next boot.)
- [ ] The rotating backup drives are working (`docs/operations/ROTATING_BACKUP_DRIVES.md`) and a
      backup passed today. Firmware changes are the moment a backup matters.

---

## 1. Firmware: power on when power returns

The setting's name depends on the maker. Enter setup by pressing the key shown at power-on
(commonly F2, F1, F10, Del or Esc), then look under *Power*, *Power Management* or *Advanced*.

| Machine | Look for | Set to |
|---|---|---|
| Mini PC / desktop board | *Restore on AC Power Loss*, *AC Recovery*, *After Power Failure* | **Power On** |
| Laptop (Lenovo) | *Power On with AC Attach* | **Enabled** |
| Laptop (Dell) | *Wake on AC* / *Power On* under Power Management | **Enabled** |
| Laptop (HP) | *Power on when AC detected* / *After Power Loss* | **On** |

- [ ] Setting found and changed. Write down its exact name here: ______________________
- [ ] Saved and exited (usually F10).

**If the laptop has no such setting:** a laptop with a charged battery does not switch off when
truck power drops — it runs on battery, then sleeps or hibernates at the critical level (section 2).
It will not start again by itself when power returns. That is a hardware limit worth knowing before
choosing between the laptop and a mini PC for the case.

---

## 2. Windows power settings: never sleep in the case

Settings → System → Power & battery (and Control Panel → Power Options → *Choose what closing the
lid does* for the lid).

- [ ] **Plugged in:** turn off screen after — any; **put the device to sleep after — Never**.
- [ ] **Closing the lid, plugged in:** **Do nothing** (the lid is shut inside the case).
- [ ] **Critical battery action:** **Shut down** — so that firmware power-on (section 1) is what
      brings it back, rather than a hibernated machine waiting for a button.
- [ ] Windows Update → Advanced options → **Active hours** set to cover driving hours, so an update
      restart does not land mid-load. (A restart is also a recovery test: sections 3–5 bring it back.)

---

## 3. Sign in automatically

The node must reach the desktop with no one typing. This is a security trade-off: anyone who powers
the laptop on reaches the desktop. **Read `docs/DISPATCH_SECURITY_DEFERRAL.md` before deciding** —
that document is where security decisions for this program are recorded.

One way (Windows 11):

1. Settings → Accounts → Sign-in options → turn **off** *For improved security, only allow Windows
   Hello sign-in for Microsoft accounts on this device*.
2. Press Win+R, type `netplwiz`, Enter.
3. Untick **Users must enter a user name and password to use this computer**, Apply, and enter the
   account's password twice.

- [ ] Automatic sign-in set. Restart once: the desktop appears with no typing.

If the untick box is missing even after step 1, Sysinternals *Autologon* does the same job and
stores the password encrypted. Either way the password is on the machine; that is the trade.

---

## 4. Start Dispatch when Windows signs in

Using Task Scheduler (runs as you, sees your `DISPATCH_*` settings):

1. Task Scheduler → **Create Task…**
2. **General:** Name `Dispatch start on sign-in`. **Run only when user is logged on.** Leave
   *Run with highest privileges* off.
3. **Triggers:** New → Begin the task **At log on** → *Specific user*: your account. Tick
   **Delay task for: 30 seconds** so the drives and network are up first.
4. **Actions:** New → Start a program → `D:\Dispatch\DISPATCH_START_HERE.cmd`, Start in
   `D:\Dispatch`.
5. **Settings:** untick *Stop the task if it runs longer than* (the Dispatch window stays open while
   Dispatch runs — that window is its on/off switch).

- [ ] Task created. Sign out and back in: the Dispatch window opens and Dispatch starts.

Keep the nightly backup task (`ROTATING_BACKUP_DRIVES.md` §6) separate from this one.

---

## 5. The self-test: the node reports itself on the tablet

What exists today:

- **The NODE card** at the bottom of the Driver Cockpit's Mission Actions column shows, within a
  minute of Dispatch starting: temperature (or *Temp not reported*), backup age, free space, and
  **Up _n_ min** — a small number right after a power loss is the sign it came back by itself.
- **The Node page** (`/operations/node`, Operations sign-in) shows the full report, including every
  thermal zone and the backup record.
- `python -m dispatch_launcher status` in a window on the node prints the launcher's own check.

What does **not** exist yet, stated plainly: there is **no automatic self-test run at boot** that
checks each part and records a PASS/FAIL. The card and page report state when asked; they do not
record a boot. That is an open item, not a finished one.

- [ ] After a restart, the tablet's NODE card shows *Up* a few minutes and the backup line is not old.

---

## 6. Prove it: pull the plug

Do this parked, with no load open, and a passed backup from today.

1. [ ] Dispatch running; tablet showing the Driver Cockpit.
2. [ ] Cut power to the node the way the truck would (unplug the inverter / power supply — for a
       laptop, also let it reach the critical battery level if you want to test that path).
3. [ ] Restore power. **Touch nothing on the node.**
4. [ ] Record: time power returned ______ ; time the tablet NODE card answered again ______ .
5. [ ] On the Node page: temperature line, free space, backup record all present.
6. [ ] Open the last load: its records are all there.

Write the result — date, machine, the two times, and anything that needed a hand — into
`docs/readiness/OPERATIONAL_PROOF.md` as your own entry. Until that entry exists, R5 is
`UNVERIFIED`.

---

## Temperature: what the card's number is

The number is the **hottest internal zone Windows reports** (usually the CPU), read without
administrator rights. It is **not the air temperature inside the Pelican case** — the laptop has no
sensor for that. When Windows reports nothing usable the card says *Temp not reported*; it never
shows a made-up number. The card is outlined when that zone reaches **85 °C** (change with
`setx DISPATCH_NODE_HOT_C 80`, then restart Dispatch).

If you want the case's air temperature on the tablet, that needs a separate sensor. Which one is
your decision; it has not been chosen or built.
