# Getting Dispatch onto your laptop

**For:** Mike. **You need:** a Windows laptop and about fifteen minutes.
**You do not need:** any developer knowledge.

This is **step one**. Everything else in this repository assumes Dispatch is already on
your machine — this is the part that makes that true. Do it once.

> Everything below is written from what the repository contains and how Windows behaves. It
> has **not** been performed on your laptop — nobody has done this yet. If a screen does not
> match what is written here, the screen is right and this document is wrong; tell me what
> you actually saw.

---

## Part 1 — Install Python (once, ~5 minutes)

Dispatch is written in Python, so Windows needs Python before it can run Dispatch. It is
free and you only ever do this once.

1. Go to **https://www.python.org/downloads/**
2. Click the big yellow **Download Python** button.
3. Run the file it downloads (it lands in your **Downloads** folder).
4. **On the very first screen, tick the box that says "Add Python to PATH."**

   It is at the bottom, it is **off by default**, and it is easy to miss. If you miss it,
   Dispatch will not find Python and will look broken when it is not. If you are unsure
   whether you ticked it, that is fine — install again and tick it.
5. Click **Install Now** and let it finish.

You do not need to open Python. You will never type a Python command. Windows just needs it
present.

---

## Part 2 — Download Dispatch

1. Go to **https://github.com/jax1313-outlook/Dispatch**
2. Click the green **`Code`** button near the top right.
3. Click **Download ZIP** at the bottom of the little menu.
4. It saves to your **Downloads** folder as `Dispatch-main.zip`.

### Then do this before you open it — it matters

Windows marks every file downloaded from the internet as untrusted, and that mark is what
makes it refuse to run things later.

1. Find `Dispatch-main.zip` in Downloads.
2. **Right-click it → Properties.**
3. At the bottom of the General tab, if you see a checkbox or button saying **Unblock**,
   tick it.
4. Click **OK**.

If there is no Unblock option, that is fine — it means Windows did not mark it. Carry on.

---

## Part 3 — Put it somewhere sensible

1. Right-click `Dispatch-main.zip` → **Extract All…**
2. Where it asks for a location, clear the box and type exactly:

   ```
   C:\
   ```

3. Click **Extract**.

You now have a folder at **`C:\Dispatch-main`**.

4. Rename it: right-click the folder → **Rename** → type `Dispatch` → Enter.

You now have **`C:\Dispatch`**. That is where Dispatch lives.

### Why `C:\` and not Desktop or Documents

Not fussiness — these cause real failures:

- **OneDrive.** Your Desktop and Documents folders are usually synced to OneDrive. OneDrive
  moves files, locks them mid-write, and can make them "online only". Dispatch keeps a live
  database open; that combination corrupts data.
- **Long paths and spaces.** `C:\Users\Mike Zachary\OneDrive - Something\Documents\...` is
  long and contains spaces. Both still cause problems on Windows.
- **Finding it again.** `C:\Dispatch` you can type from memory.

### One thing that catches everybody

Open `C:\Dispatch` and look. **Do you see another folder inside called `Dispatch-main`?**

If you do, the extraction nested one level too deep. Open it, select everything inside
(`Ctrl+A`), cut (`Ctrl+X`), go back up to `C:\Dispatch`, paste (`Ctrl+V`), and delete the now
empty `Dispatch-main` folder.

You want `C:\Dispatch` to contain `DISPATCH_START_HERE`, `README`, and folders named
`portal`, `dispatch`, `docs` — **not** a single folder.

---

## Part 4 — Start it

1. Open **`C:\Dispatch`**.
2. Find **`DISPATCH_START_HERE`**.

   Windows normally hides file extensions, so it shows as `DISPATCH_START_HERE` rather than
   `DISPATCH_START_HERE.cmd`. Its icon is a small window with gears.

   **Careful:** there is also a *folder* named `dispatch` in there. That is Dispatch's
   internal code and clicking it does nothing useful. The one you want is the one that says
   **START_HERE**.
3. **Double-click it.**

### Windows will probably warn you. This is expected.

You are likely to see a blue box: **"Windows protected your PC"**.

That is SmartScreen. It appears because this file came from the internet and is not
digitally signed — not because anything is wrong with it.

- Click **More info**
- Then click **Run anyway**

If you click "Don't run", nothing happens and Dispatch will not start. Windows shows this
warning for every unsigned downloaded file; you will see it once.

### It will ask you to choose a PIN

The first time only, the black window stops and asks:

```
  Dispatch needs a PIN before you can sign in.
  You choose it now, you only do this once, and nothing is shown as you type.
  It must be at least 4 characters. Digits are fine.

  Choose a PIN:
  Type it again:
```

**Nothing appears as you type — not even dots.** That is deliberate, not a frozen window.
Type your PIN, press Enter, type it again, press Enter.

Pick something you will remember. Dispatch stores it scrambled and **cannot show it back to
you** — nobody can, including me. If you forget it there is a way back in (`[P] Reset PIN`
in the Control Center), but it is easier not to need it.

### What should happen next

A black window opens and prints a short list. Then your browser opens on the Dispatch
sign-in page — **enter the PIN you just chose**.

The black window will also tell you it has put a **Dispatch icon on your Desktop.** From
then on, that icon is how you start Dispatch — you never need to open `C:\Dispatch` again.

---

## Part 5 — How to tell what happened

### It worked

- The black window says **`Dispatch is RUNNING at http://127.0.0.1:8080`**
- Your browser shows a Dispatch sign-in page
- **Your PIN gets you in**
- The black window stays open

**Open black window = Dispatch is running.** To stop Dispatch, press any key in it.

Lines marked `[NOTE]` are **not** problems — something optional did not work and Dispatch is
running anyway. A browser that did not open by itself is the usual one; just open your
browser and go to `http://127.0.0.1:8080`.

### It did not work

- The window says **`DISPATCH DID NOT START`** in those words
- A line marked **`[STOP]`** names what stopped it
- Underneath, **`What to do:`** lists the steps

**The window will not close on its own.** Read it, follow the steps, and double-click again.

### Nothing happened at all

If double-clicking does nothing — no window, no flicker — Windows would not run the file.
Almost always that means Python is missing (go back to Part 1) or a security policy blocked
it.

**Tell me that this is what happened.** "Nothing happened" is genuinely useful information
and is not a non-answer.

---

## What to send me either way

Whatever happens, this tells me everything:

1. **A photo of the black window**, or its text. Right-click the window's title bar →
   Edit → Select All → Copy, then paste it.
2. **What the browser showed**, if it opened.
3. **Whether a Dispatch icon appeared on your Desktop.**
4. **Whether your PIN got you past the sign-in page.**

**Never send me the PIN itself.** I do not need it and should not have it. "It worked" or
"it said incorrect PIN" is the whole answer.

If it did not work, that is not a wasted attempt — a failure that names its reason is the
first real information anybody has had about how Dispatch behaves on your machine.

---

## Later: getting a newer version

There is no update button. To take a newer version:

1. Rename `C:\Dispatch` to `C:\Dispatch-old`.
2. Do Parts 2 and 3 again.
3. Start it and confirm it works.
4. Once you are sure, delete `C:\Dispatch-old`.

**Keep the old folder until the new one is proven.** If you have been using Dispatch for
real work by then, read `docs/maintenance/DISPATCH_MAINTENANCE_GUIDE.md` first — it covers
backing up your data before an upgrade, which matters once there is data worth losing.
