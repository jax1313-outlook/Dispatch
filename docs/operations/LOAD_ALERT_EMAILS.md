# Load alert emails become cards

**What this is.** Load boards can email you when a saved search finds new loads. Those
alert emails go to the Ops mailbox. A mail rule you make sorts them into one folder.
Dispatch reads that folder, **read-only**, and every load it can read becomes a scored
card on the **LOADS** screen, the same kind of card a paste makes.

**Status of this feature: IMPLEMENTED, not OPERATIONALLY PROVEN.** It is built and the
repository tests exercise it with invented sample alerts. No real board alert has been read
yet. It is proven when a real alert, sorted by your rule, becomes a card on your laptop.

Owner direction, 2026-09-15: *"i like this very much"* ... *"i will setup. can we use
Ops@l1truck .com? if we can create a small email sort to push the incoming emails from specific
senders to a box then the reader can do it's thing."*

---

## What Dispatch does and does not do

| Dispatch does | Dispatch never does |
|---|---|
| Reads the messages in one folder of one approved mailbox (Ops@l1truck.com or Admin@l1truck.com) | Send, reply, forward, move, delete, flag, or mark a message read |
| Reads only messages from the senders you list | Open a link in an alert, visit a board's website, or log into a board (D1) |
| Remembers which messages it has handled, in its own store | Create a mail rule, a folder, or a scheduled task on this laptop |
| Makes cards through the same path as PASTE A LOAD | Card a load whose pickup has already passed |
| Keeps an alert it cannot read as **needs a look** | Guess at a load it cannot read |
| Leaves a committed load exactly as it is | Change a committed load because an alert mentions the same freight |

Uncommitted cards from alerts follow the same rules as every other card: **PASS discards the
card**, and a card whose pickup time goes by uncommitted is cleared (D12).

---

## Setting it up (you do these steps)

### 1. Set up saved-search alerts on each board

On each board you use, save the searches you care about (lane, equipment, dates) and turn on
the board's **email alert** for them. Send the alerts to **Ops@l1truck.com**.

Write down, for each board, **the address the alerts come from**. You will find it on the
first alert that arrives (the "From" line). Many boards send from a fixed address such as
`alerts@...` or `noreply@...`.

### 2. Make the folder

In Outlook, in the **Ops@l1truck.com** mailbox:

1. Right-click **Ops@l1truck.com** (the top of the mailbox) or its **Inbox**.
2. Choose **New Folder**.
3. Name it exactly **Load Alerts** and press Enter.

Dispatch looks for the folder at the top of the mailbox and inside the Inbox. If you choose
another name, put the same name on the settings screen (step 4).

### 3. Make the rule that sorts the alerts

In Outlook:

1. Open one alert email from the board.
2. On the **Home** ribbon choose **Rules**, then **Create Rule...** (or **Manage Rules &
   Alerts**, then **New Rule**, then **Apply rule on messages I receive**).
3. Tick **From** and make sure it shows the board's alert address.
4. Choose **Move the item to folder** and pick **Load Alerts** in Ops@l1truck.com.
5. If you use **Advanced Options**, add each other board's alert address to the same rule
   (condition **from people or public group**), or make one rule per board.
6. Do **not** tick "mark as read", "delete", or "forward" -- Dispatch does not need them.
7. Tick **Run this rule now on messages already in the current folder** if you want existing
   alerts sorted, then **OK**.

Tip: the rule must run where Outlook runs on the laptop, or on the mail server. Either works;
Dispatch only reads the folder.

### 4. Tell Dispatch who the alerts come from

1. Open **LOADS**. In the **LOAD ALERTS** strip, press **ALERT SETTINGS**.
2. **Mailbox:** Ops@l1truck.com. **Folder:** Load Alerts.
3. **Alert senders:** one per line. Either a whole address (`alerts@board.example`) or a
   domain (`board.example`, which allows every address at that board, including
   `mail.board.example`).
4. **Check every:** leave **Off** to check by hand, or choose 5, 10, 15, 30 or 60 minutes.
5. Press **SAVE**.

Until at least one sender is listed, the strip says **UNCONFIGURED** and nothing is read.

The same settings can be given to the laptop in its environment, which wins over the page:
`DISPATCH_ALERT_MAILBOX`, `DISPATCH_ALERT_FOLDER`, `DISPATCH_ALERT_SENDERS` (comma separated),
`DISPATCH_ALERT_CHECK_MINUTES`. The settings screen says when one of these is in effect.

### 5. Check

Press **CHECK ALERTS NOW** on the LOADS screen. The line at the top of the screen says what
happened, for example:

> Load alerts LIVE: 3 new cards, 0 merged, 1 ignored sender, 1 needs a look.

---

## Testing with a forwarded alert

You can test before the rule has caught a live alert:

1. Add **your own address** to the sender list (step 4) as well as the board's address.
2. **Forward** a real alert to Ops@l1truck.com, without editing it.
3. In Outlook, drag the forwarded message into **Load Alerts** (your rule only catches the
   board's own address, so a forward from you will not be sorted by it).
4. Press **CHECK ALERTS NOW**.

Dispatch reads the board's address out of the forwarded header, so the card names the board.
A forward is only read when the board that wrote it is also on the list -- your own address on
the list does not turn every forward into a card.

**Take your own address off the list when you are done testing.**

---

## Scheduled checking

With **Check every** set, Dispatch checks the folder on its own, in the background, one check
at a time. It starts when Dispatch starts (`DISPATCH_START_HERE.cmd` or `portal/app.py`) and
changing the setting takes effect within about half a minute, without a restart.

**It needs Outlook open on the node.** Dispatch reads mail through the Outlook already
signed in on this laptop. When Outlook is closed the strip says **UNAVAILABLE** and why;
open Outlook and the next check reads normally. Nothing is lost while Outlook is closed: each
check looks back over the last 24 hours and skips what it already handled.

Each check is written to the audit log (action `load-alert-check`, channel `EMAIL`).

---

## What the strip says

| Word | Means |
|---|---|
| `UNCONFIGURED` | No sender is listed, or the mailbox or folder is not set. Nothing is read. |
| `CONFIGURED` | Settings are in place; no check has run yet. |
| `LIVE` | The last check read the folder successfully. |
| `UNAVAILABLE` | The last check could not read the folder, with the reason: Outlook is not open, the mailbox is not in Outlook on this laptop, or there is no folder by that name. |

The counts are for the last check:

| Count | Means |
|---|---|
| **new cards** | Loads that became new cards |
| **merged** | Loads already on a card; the card was filled in, nothing on it was overwritten |
| **possible duplicates** | Same lane but the rate or date did not agree; a new card flagged POSSIBLE DUPLICATE |
| **ignored senders** | Messages in the folder from someone not on the list. Never read, never carded |
| **need a look** | Alerts that could not be read into a load. The subject and sender are listed; open the email and use PASTE A LOAD |
| **past pickup, not carded** | Loads whose pickup had already gone by |
| **matched a committed load** | Loads matching a load you already committed. The committed load was left alone |

### Why an alert "needs a look"

- **No load could be read in it** -- for example an alert that only says "log in to see loads".
- **It seems to hold several loads but they could not be told apart** -- Dispatch does not
  cut an alert apart by guesswork.

**A load with no rate is a card, not a needs a look.** Many board alerts leave the rate out.
Since the Owner rulings of 2026-09-15 such a load becomes a card with the rate shown as `*`,
scored on everything except the rate and marked `* rate pending`. A load missing its pickup
or delivery city is carded the same way, with what the alert did say.

---

## When a board's alerts read wrong

Every alert is read by the same generic reader PASTE A LOAD uses. It splits an alert into
loads at separator lines (`-----`) or at each line that names two places (`Tampa, FL ...
Miami, FL`). When a board's alerts need help, add **board reading hints** on the settings
screen, keyed by the board's sender domain:

```json
{
  "board.example": {
    "name": "Board name as it should show on the card",
    "split": "^Load \\d+:",
    "kind": "listing",
    "labels": {"Orig": "origin", "Dest": "destination", "Amt": "rate", "Avail": "pickup_date"},
    "ignore_after": ["Similar loads you may like"]
  }
}
```

- `split` -- a pattern matching the line that starts each load.
- `labels` -- the board's own words, paired with facts the reader knows: `origin`,
  `destination`, `pickup`, `delivery`, `pickup_date`, `delivery_date`, `rate`, `miles`,
  `weight`, `equipment`, `contact`, `phone`, `email`, `load_number`, `commodity`, `pieces`,
  `notes`.
- `ignore_after` -- a line where the useful part of the alert ends.
- `kind` -- `email` if the board's alert reads like a broker's offer email rather than a listing.

Every hint is optional. The page refuses hints it cannot read and saves nothing.

---

## What to send so the reader can be tuned

Forward to the build (not to Ops) **two or three real alerts from each board**, unedited:

- one alert holding **a single load**;
- one alert holding **several loads**;
- if the board has one, an alert **with a rate** and one **without**.

With those, each board gets tested against its real alert format, and hints are added only
where the generic reader gets something wrong.
