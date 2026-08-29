# The JOE Presentation Layer

The Driver Portal, evolved. Built 29 August 2026 on branch `joe-portal`.

---

## Open it

```
py run_joe_portal.py
```

Then `http://127.0.0.1:8080/portal`, or **JOE Portal** at the top of the
cockpit sidebar.

The portal opens on the mission being worked. If nothing has been accepted, it
opens on Sweep Control instead — because with no mission, the next useful act
is to go and find one.

---

## What it is

One Mission Record. Three deterministic views. A Sweep Control area. A JOE line
along the bottom.

    Portal owns display and interaction.
    Dispatch owns workflow.
    The Mission Record owns mission data.
    JOE owns communication.

It is the prototype Mike supplied — Planning Mode v1.0 — carried forward. The
colour vocabulary, card system, badge grammar, tab mechanism and radar sweep
are his; the original is kept at `portal/prototype/` so the lineage is
checkable. What changed is what it is pointed at: mission phase instead of
planning tabs, and real Mission Record data instead of static markup.

---

## One record

The Intelligence sweep creates an **Opportunity Record**. When you press
**ACCEPT LOAD**, that same record becomes the **Mission Record**. Its purpose
changes, its workflow state changes, its displayed name changes. Its identity
does not.

This used to work the other way. `create_load()` minted a fresh `load_id` and
copied the card's broker, origin, destination, windows and equipment into it.
From that moment two records existed, joined one way by `engine_load_id`, and
everything learned during acquisition — research, scoring, negotiation history,
Route Risk — stopped travelling with the mission it had produced.

Now the operational row is opened under the record's **own id**
(`create_load_with_id`). Nothing is minted, so a second record cannot exist. A
record whose `engine_load_id` equals its own id has not been copied anywhere.

Held by `tests/test_mission_record.py::TestOneRecord`.

---

## Two numbers, never confused

| | |
| --- | --- |
| **Mission 1847** | ours. Internal, machine-generated, numeric, four digits at most. Short enough to say on the phone. |
| **Load 847261** | theirs. The broker's own reference, preserved exactly as received. The number on the rate confirmation, the BOL, and the invoice. |

They appear side by side in the header, each labelled. The external number is
read only from the card and is **never** defaulted to the internal one —
quoting our tracking number where an invoice expects theirs is how a payment
goes missing.

Mission numbers fill gaps rather than marching upward, so they stay short for
years instead of reaching five digits.

---

## Three views, one read

**CURRENT** is not stored anywhere. It resolves from the record's own status to
either PICKUP or DELIVERY. It is never a third branch — a third branch is how
one record quietly becomes three.

| view | answers |
| ---- | ------- |
| **CURRENT** | What am I working? What matters now? What is the next action? Where next, what time, who do I call, what is unresolved? |
| **PICKUP** | Where, when, contact, the reference to quote at the gate, facility intelligence, and the buttons to record arrival, loading and departure. |
| **DELIVERY** | The same at the other end, plus POD. |

`filter_bundle()` reveals facets; it never deletes any, and it performs no I/O.
All three views cost **one** store read — asserted by
`TestManyViewsOneRead::test_all_three_views_cost_one_store_read`, which is the
guard that stops "many views" becoming "many records" when someone adds a
feature in a hurry.

Open exceptions show in every phase. A problem is not irrelevant because you
moved down the road.

---

## Two activation events

**START SWEEP** — Sweep Control lives in the portal, not in a config file and
not on the public website. Start now, enable or disable the timer, set the
daily time, and read the real state: last run, next run, and any failure in
plain words (*"The load board did not answer. That is usually signal, not the
program."*). A sweep creates or enriches Opportunity Records. **It never
creates a Mission.**

**ACCEPT LOAD** — the human commitment event, and the only thing that turns an
Opportunity into a Mission.

---

## Boundaries: what is real, and what is not

Stated plainly so nothing here is mistaken for a working integration.

| | state |
| --- | --- |
| Mission Record, milestones, evidence, exceptions, detention, POD, financials | **real** — existing Dispatch store |
| Sweep execution | **real** — `dispatch/acquisition.py` |
| Sweep *scheduling* | **boundary.** Nothing in this repository runs continuously. `next_run()` reports the next due time honestly and `due()` says whether it has passed, so whatever runs the process can ask. A timer that claimed to fire while the program was closed would be a lie. |
| Outlook calendar | **boundary + labelled demonstration adapter.** Dispatch has no route to Outlook. `OutlookCalendarAdapter` reports `UNAVAILABLE`; `DemonstrationAdapter` marks every payload `demonstration: True` and says DEMONSTRATION on its face. Accepting a load never silently fails to schedule — it tells you to put it in your calendar yourself. |
| COMI communication display | **not built.** COMI has no producer in this codebase. |
| JOE panel | **a line, not a conversation yet.** The footer is the seam. JOE reads mission data through the existing REST API and holds nothing. |

---

## It works without signal

The prototype loaded Tailwind, Lucide and Google Fonts from three CDNs. In a
truck that renders unstyled. All three are vendored into
`portal/static/vendor/`, and fonts fall back to faces Windows already has.

`TestPortalRenders::test_the_portal_works_without_a_network` fails if any CDN
hostname reappears in the markup.

---

## It is worked by a thumb

Every control a driver presses is at least 44px. The mode bar is sticky, so it
never has to be hunted for after scrolling. Reading panels stay dense; only the
things you press grow.

The prototype's own filter buttons were `.btn-xs` — about 18px. The mechanism
was copied; the sizing deliberately was not.

---

## What is not finished

- **COMI display** — designed for, not built. No producer exists.
- **The JOE panel is a status line**, not yet a conversation.
- **Voice** — JOE owns it, and it is not wired into this portal. JOE's own
  voice input is still unproven on the driver's machine.
- **`brief.html` is untouched.** It remains the pre-commitment view — *should I
  take this?* — while the portal answers *how is this mission going?*
- **The `loads` table still carries descriptive columns** filled at commitment.
  Same id, one authoritative origin, and `merge_record()` always prefers the
  opportunity's value — but they are a denormalised cache for readers not yet
  moved across. Emptying them is a larger change to existing views and is
  Mike's call, not a silent one.

---

## Files

| file | what |
| ---- | ---- |
| `dispatch/mission.py` | the doctrine: purpose, numbering, phase resolution, the view filter |
| `dispatch/sweep.py` | Sweep Control — start, schedule, plain-language state |
| `dispatch/scheduling.py` | the Outlook boundary and its labelled demonstration adapter |
| `portal/routes/joe_portal.py` | routes; assembles and renders, decides nothing |
| `portal/templates/joe_portal.html` | the portal itself |
| `portal/static/joe_portal.css` | the prototype's stylesheet, plus touch sizing |
| `portal/static/vendor/` | Tailwind and Lucide, vendored for offline use |
| `portal/prototype/` | Mike's original, preserved |
| `run_joe_portal.py` | launcher |
| `tests/test_mission_record.py` | the doctrine, held by tests |

**Mike Zachary remains final authority.**
