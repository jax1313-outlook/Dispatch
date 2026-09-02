"""The connector registry: what Dispatch can actually reach from here.

Every connector answers the same question -- can you do the thing, right now,
on this machine -- and answers it honestly. A connector that reports itself
working when it is not is worse than one that is absent, because the absent one
is visible.

    registry.status()      what is reachable, in the fixed vocabulary
    registry.mail()        the outbound mail connector, or None

The fixed vocabulary is the one the rest of Dispatch reports with:

    LIVE  CONFIGURED  UNCONFIGURED  SIMULATED  UNAVAILABLE  MANUAL
    ABSENT  UNVERIFIED

Those words are for engineering. They are translated into the driver's
language before they reach the glass -- see `portal/joe_voice.py`, and
`JOE_RESPONSE_MODEL.md` for why.
"""

from __future__ import annotations

from dispatch.connectors import registry  # noqa: F401  (re-exported)

__all__ = ["registry"]
