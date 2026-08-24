"""The connector registry — exactly the eight Section 6.4 names, and no more.

A registry rather than eight imports scattered through the application, for two
reasons that are really the same reason.

**One place answers "what can Dispatch talk to".** An operator asking that
question -- or an auditor asking the harder version, "and which of those are
actually connected" -- gets one list with one truth word per row, from
:func:`status_board`. There is no second inventory to fall out of date, and a
connector that exists but is not registered is not reachable by the application
at all.

**The count is asserted.** Section 6.4 says "exactly these eight", and
:data:`CONNECTOR_IDS` is a fixed tuple the tests check by name and by length.
Adding a ninth connector is therefore a deliberate act that changes a test and,
per ``docs/connectors/PROVIDER_INSERTION.md``, requires Mike's decision -- rather
than something that happens because a module was added.

The mock (``dispatch/connectors/mock.py``) is deliberately **not** registered. It
is reachable through :func:`mock_connector` for tests and demonstrations, and
keeping it out of the registry means no surface iterating the registry can ever
render simulated route conditions as one of Dispatch's integrations.

Instances are constructed per call rather than held as singletons. Connectors
read their configuration from the environment at the moment they are asked, so a
cached instance would report yesterday's answer after an operator sets a key --
and "I set the variable and it still says UNCONFIGURED" is exactly the kind of
small lie this whole subsystem exists to prevent.
"""

from __future__ import annotations

from typing import Callable

from dispatch.connectors.accounting_connector import AccountingConnector
from dispatch.connectors.contract import Connector
from dispatch.connectors.email_transport_connector import EmailTransportConnector
from dispatch.connectors.future_intelligence_connector import (
    FutureExternalIntelligenceConnector,
)
from dispatch.connectors.load_board_connector import LoadBoardConnector
from dispatch.connectors.mapping_connector import MappingAndRoutingConnector
from dispatch.connectors.outlook_connector import OutlookConnector
from dispatch.connectors.route_risk_connector import RouteRiskConnector
from dispatch.connectors.scanner_connector import ScannerConnector

#: Section 6.4's eight, in the order the mission lists them.
CONNECTOR_IDS: tuple[str, ...] = (
    "route_risk",
    "accounting",
    "scanner",
    "outlook",
    "email_transport",
    "load_board",
    "mapping",
    "future_intelligence",
)

_FACTORIES: dict[str, Callable[[], Connector]] = {
    "route_risk": RouteRiskConnector,
    "accounting": AccountingConnector,
    "scanner": ScannerConnector,
    "outlook": OutlookConnector,
    "email_transport": EmailTransportConnector,
    "load_board": LoadBoardConnector,
    "mapping": MappingAndRoutingConnector,
    "future_intelligence": FutureExternalIntelligenceConnector,
}


class UnknownConnector(KeyError):
    """Asked for a connector that is not one of the eight."""


def get(connector_id: str) -> Connector:
    """One connector, freshly constructed.

    Refuses an unknown id rather than returning None: a caller that receives
    None writes ``if connector:`` and silently does nothing, which is the silent
    degradation Section 6.7 forbids.
    """
    factory = _FACTORIES.get(connector_id)
    if factory is None:
        raise UnknownConnector(
            f"{connector_id!r} is not a Dispatch connector. The eight are: "
            f"{', '.join(CONNECTOR_IDS)}."
        )
    return factory()


def all_connectors() -> list[Connector]:
    """All eight, in Section 6.4's order."""
    return [get(cid) for cid in CONNECTOR_IDS]


def status_board() -> list[dict]:
    """Every connector with its truth word, for a consuming surface.

    Each row comes from ``BaseConnector.status_summary()``, which puts
    ``connector_status`` at the top level, so a template rendering this list
    cannot show a connector without showing what it actually is.
    """
    return [c.status_summary() for c in all_connectors()]


def mock_connector(**kwargs):
    """The Section 6.6 mock, which is not part of the registry.

    Imported inside the function so that importing the registry -- which the
    application does -- never pulls simulated data into the same namespace as
    the real eight.
    """
    from dispatch.connectors.mock import MockRouteRiskConnector

    return MockRouteRiskConnector(**kwargs)
