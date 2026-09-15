# Log a load by voice — the TALK card on the Driver Cockpit

**What it is for:** reading load board listings aloud through the headset so each one is
logged as a card for deciding on later. It only logs loads. It never books a load, passes on
one or sends anything.

**What it is not:** a phone line, a chat with Joe, or a recording. **The tablet turns your
voice into words. Only the words go to Dispatch.** No sound is sent to Dispatch or stored by
it.

Status of this feature: **IMPLEMENTED, not OPERATIONALLY PROVEN.** It has been exercised by the
repository tests and in a desktop browser on sandbox data. It has not yet been used on the
tablet, with the headset, on the truck.

---

## 1. Set up the tablet once

### Headset
1. Pair the headset with the tablet (the tablet's Bluetooth settings), or plug it in.
2. Open any voice memo or dictation app and check the tablet hears the headset microphone,
   not its own built-in microphone.

### Keyboard dictation (this works everywhere, and it is the fallback)
The TALK drawer always has a words box. Tapping it opens the keyboard; the keyboard's
**microphone key** turns speech into words in the box.

- **Android tablet:** Settings → System → Keyboard → on-screen keyboard → your keyboard →
  Voice typing: **on**. Then, in the same voice typing settings → **Offline speech
  recognition** (or "Languages" → download) → download **English (US)**.
- **iPad:** Settings → General → Keyboard → **Enable Dictation: on**. On recent iPads English
  dictation runs on the device once the language has downloaded; leave the iPad on Wi-Fi and
  power for a while after turning dictation on.

**Why the offline English pack matters:** with it downloaded, keyboard dictation keeps working
with no cell signal, where the device supports offline dictation. Without it, dictation stops
when signal stops. Check this before you rely on it: put the tablet in airplane mode, open the
TALK drawer, tap the box, tap the microphone key and talk. If words appear, offline dictation
works on this tablet.

### The TAP TO TALK button
TAP TO TALK uses the browser's own listening, when the browser offers it. It appears only in a
browser that has it.

- It usually **needs signal** — most browsers send the sound to their own service to turn it
  into words. The drawer says so if it cannot listen. Use the microphone key instead.
- It is **only allowed on a secure address.** When the tablet opens the cockpit from the laptop
  over the truck network by a plain `http://` address, the browser refuses to listen and the
  drawer says *"Listening is not allowed on this screen."* The keyboard microphone key still
  works. (Recorded as an open item: see the decision-log proposal for this feature.)
- The first time, the browser asks to use the microphone. Allow it.

---

## 2. Log loads

1. On the Driver Cockpit, tap **TALK — Log a load by voice** in Mission Actions. It works with
   or without a mission on the screen.
2. Either tap **TAP TO TALK**, or tap the words box and tap the keyboard's microphone key.
3. Read the listing. The fast order is the Mission Card's order:
   **city to city, equipment, rate, pickup, delivery, broker, notes.**

   > *"Jacksonville Florida to Savannah Georgia, dry van, twenty two hundred, pickup
   > Thursday six a.m., broker is Coastal."*

   Order is a help, not a rule. **City to city and the rate are what a load needs.** Anything
   not placed is kept in the card's notes rather than dropped.
4. **Say "next" between loads.** One go can log several loads, in the order read:

   > *"Tampa to Miami, nine hundred. Next. Orlando to Atlanta, fourteen hundred. Next.
   > Dallas to Houston, seven fifty."*

   "Next load" and "next one" also work. "Next Tuesday" or "next week" is read as a date, not
   as a new load. Typing: put **next** on its own line.
5. TAP TO TALK stops when you tap it again or stop talking for a few seconds, then logs what it
   heard. With the words box, tap **LOG IT**.

---

## 3. What the read-back means

Each load gets one line, in the JOE line and in the list in the drawer. With **READ-BACK: ON**
it is also spoken in the headset. The spoken line leaves out the record number; the screen keeps
it.

| You hear / see | Means |
|---|---|
| `LOGGED. OPPORTUNITY OPP-…. TAMPA TO MIAMI, $900.` | Logged, and a card is on the Loads screen |
| `… FLAGGED POSSIBLE DUPLICATE.` | Logged as its own card; it looks like another load on the same lane at different money, so you decide whether they are the same |
| `MERGED INTO EXISTING. …` | Same lane, rate and pickup as a load already logged: it filled in what that card was missing and overwrote nothing |
| `SAVANNAH TO ATLANTA. RATE?` | **Nothing is logged yet.** The rate was not heard. Say or type the rate, and it is logged. Say **skip** to leave that load out |
| `NOT LOGGED. LANE NOT HEARD.` | No city to city was heard. Nothing was logged. Read that listing again |
| `NOT LOGGED. THE WORDS ARE STILL IN THE BOX.` | The laptop did not answer. Nothing was logged; the words are kept to try again |
| `NOTHING HEARD.` | Nothing was sent |

**One question at a time.** If several loads each miss a rate, the others are logged and the
first question is asked; the next question comes after that one is answered.

**READ-BACK: ON / OFF** mutes the spoken line. The choice is remembered on this tablet.

---

## 4. What it never does

- It never books, passes, discards or sends a load.
- **Known gap, being closed separately:** today a voice capture that matches a load already
  committed can fill in blanks on that load's card (it never overwrites what is there). A guard
  that leaves committed cards untouched is being added to the card code on another branch.
- It never keeps sound. Dispatch receives words only.
- It never uses the Joe machine contract or its token; the tablet holds no standing secret.
