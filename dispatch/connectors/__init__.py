"""External-system connectors: a governed boundary, built before any provider exists.

Operational Readiness Mission Section 6. Read ``contract.py`` first -- it defines
the shape everything here speaks, and the construction-time rules that make a
false connection claim hard to write. ``boundary.py`` explains how the
architectural position is enforced rather than asserted, and
``docs/connectors/PROVIDER_INSERTION.md`` covers what has to happen, and what
Mike has to decide, before any of these connectors talks to anything real.

Nothing in this package is connected to an external system today. Seven of the
eight report ``UNCONFIGURED``; the email transport reports ``SIMULATED`` or
``CONFIGURED`` depending on whether an SMTP relay is set, because that one wraps
a transport Dispatch genuinely has.
"""

from __future__ import annotations

from dispatch.connectors.audit import init_connector_schema
from dispatch.connectors.contract import (
    AuditRecord,
    AuthenticationStatus,
    BaseConnector,
    CapabilityDeclaration,
    ConfigurationStatus,
    Connector,
    ConnectorError,
    ConnectorIdentity,
    ConnectorRefusal,
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    ExchangeEvidence,
    HealthStatus,
    NormalizedPayload,
    Provenance,
    RetryStatus,
    TRUTH_WORDS,
    UnlabeledDisplayError,
    assert_labeled_display,
    parse_status,
    redact,
    require_payload,
)

__all__ = [
    "registry",
    "AuditRecord",
    "AuthenticationStatus",
    "BaseConnector",
    "CapabilityDeclaration",
    "ConfigurationStatus",
    "Connector",
    "ConnectorError",
    "ConnectorIdentity",
    "ConnectorRefusal",
    "ConnectorRequest",
    "ConnectorResult",
    "ConnectorStatus",
    "ExchangeEvidence",
    "HealthStatus",
    "NormalizedPayload",
    "Provenance",
    "RetryStatus",
    "TRUTH_WORDS",
    "UnlabeledDisplayError",
    "assert_labeled_display",
    "init_connector_schema",
    "parse_status",
    "redact",
    "require_payload",
]

# The registry is re-exported so `from dispatch.connectors import registry`
# keeps working for the JOE Presentation Layer. Merged from `joe-portal`.
from dispatch.connectors import registry  # noqa: F401  (re-exported)
