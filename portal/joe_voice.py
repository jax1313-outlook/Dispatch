"""What JOE says, in the driver's language.

    MISSION FIRST. TECHNICAL DETAILS SECOND.

The driver is talking to JOE. He is not talking to a mail transport, a
connector, a module or a configuration file, and he does not care that one of
them is missing. Those are system concerns, and the driver must never become
part of the troubleshooting chain.

So this module exists to answer one question -- **how can JOE still accomplish
the driver's objective?** -- and never the other one, which is how to explain
why a subsystem failed.

Three rules hold here:

1. **Translate, do not expose.** A system condition becomes operational
   language before it reaches the glass. "UNCONFIGURED" is a fact about a
   build; "I couldn't send it" is a fact about his day.

2. **Never stop at the failure.** Every line JOE says about something it could
   not do carries the thing it *can* do next. A driver told only that
   something failed has been handed a problem; a driver told what happens
   instead has been handed a mission.

3. **Translate, do not lie.** Hiding complexity is not the same as claiming
   success. If a notice did not go out, JOE says so -- in words about the
   notice, not about the transport. The driver acts on what this screen says,
   and a comfortable falsehood gets acted on too.

The vocabulary in `ENGINEERING_WORDS` is what must never reach a driver. It is
enforced by test against the rendered screen, not left to good intentions.
"""

from __future__ import annotations

#: Words that belong to the system and never to the driver. A rendered driver
#: screen containing any of these is a defect -- see
#: `tests/test_joe_speaks_to_the_driver.py`, which fails on it.
ENGINEERING_WORDS = (
    "SMTP", "connector", "transmission", "UNCONFIGURED", "CONFIGURED",
    "SIMULATED", "UNVERIFIED", "registry", "traceback", "exception",
    "null", "NoneType", "stacktrace", "endpoint", "subsystem",
)

#: The system conditions JOE has to speak about. Same fixed vocabulary the rest
#: of Dispatch reports with -- translated here, not renamed at the source,
#: because engineering still needs the precise word.
LIVE = "LIVE"
CONFIGURED = "CONFIGURED"
UNCONFIGURED = "UNCONFIGURED"
SIMULATED = "SIMULATED"
UNAVAILABLE = "UNAVAILABLE"
MANUAL = "MANUAL"
ABSENT = "ABSENT"
UNVERIFIED = "UNVERIFIED"

#: Conditions under which something JOE would normally send does not go out.
_CANNOT_SEND = (UNCONFIGURED, UNAVAILABLE, ABSENT, MANUAL, SIMULATED)


def can_send(status: str) -> bool:
    """Whether a thing JOE would send actually leaves the truck."""
    return str(status or "").upper() in (LIVE, CONFIGURED)


def sending(status: str, *, what: str, instead: str) -> dict:
    """How JOE reports on something it was meant to send.

    `what` is the thing in the driver's words -- "the arrival notice", not "the
    notice payload". `instead` is what happens now, and it is required: a line
    that reports a failure and stops there hands the driver a problem to solve.
    """
    state = str(status or "").upper()
    if can_send(state):
        return {"sent": True, "line": f"{what.capitalize()} sent.", "instead": ""}

    if state == SIMULATED:
        line = f"Practice run. {what.capitalize()} was not sent."
    elif state == MANUAL:
        line = f"{what.capitalize()} is yours to send."
    else:
        # UNCONFIGURED, UNAVAILABLE, ABSENT and anything unrecognised all mean
        # the same thing to a driver: it did not go out. The distinction
        # between them is an engineering distinction.
        line = f"I couldn't send {what} myself."

    return {"sent": False, "line": line, "instead": instead}


def offer(headline: str, *, could_not: str = "", now: str = "",
          question: str = "") -> dict:
    """JOE answering a request it could not satisfy the expected way.

        MISSION TEMPLATE READY
        I couldn't deliver it by email.
        Here's your Mission Template now.

    The headline leads with the objective met, not the method missed, because
    the method was always secondary to what the driver actually asked for.
    """
    return {
        "headline": headline.upper(),
        "could_not": could_not,
        "now": now,
        "question": question,
    }


def template_ready(*, delivered_by_email: bool, offer_to_fill: bool = False,
                   first_question: str = "") -> dict:
    """The answer to "Joe email me a Mission Template."

    The driver's intent is *I need a Mission Template*. The email was the
    method, and a method that is unavailable does not cancel the intent.
    """
    if delivered_by_email:
        return offer("MISSION TEMPLATE SENT",
                     now="Check your mail. Send it back when it's filled in.")
    if offer_to_fill:
        return offer("MISSION TEMPLATE READY",
                     could_not="I couldn't deliver it by email.",
                     now="Let's complete it together now.",
                     question=first_question or "Who is the broker?")
    return offer("MISSION TEMPLATE READY",
                 could_not="I couldn't deliver it by email.",
                 now="Here's your Mission Template now.")


def spoken(response: dict) -> str:
    """One block of what JOE says, for the dialog box or a voice line."""
    parts = [response.get("headline", "")]
    for key in ("could_not", "now", "question"):
        if response.get(key):
            parts.append(response[key])
    return "\n".join(p for p in parts if p)


def is_driver_safe(text: str) -> list:
    """Every engineering word found in driver-facing text. Empty is the pass.

    Used by the tests against the rendered screen, so the rule is enforced by
    the build rather than by remembering it.
    """
    lowered = (text or "").lower()
    return [w for w in ENGINEERING_WORDS if w.lower() in lowered]
