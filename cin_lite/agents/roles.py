"""Role definitions and permission mappings for pipeline agents.

Roles align with the Digital Office Department Map. Each role grants a
set of permitted actions; agents declare their role and BaseAgent enforces
the boundary before every execute() call.
"""

from __future__ import annotations


class Roles:
    ACQUISITION = "acquisition"
    PROCESSING = "processing"
    ROUTING = "routing"
    PUBLISHING = "publishing"
    ARCHIVING = "archiving"
    AUTOMATION = "automation"


ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    Roles.ACQUISITION: frozenset({"acquire", "fetch", "ingest"}),
    Roles.PROCESSING: frozenset({"summarize", "analyze", "score", "classify"}),
    Roles.ROUTING: frozenset({"route", "decide", "recommend"}),
    Roles.PUBLISHING: frozenset({"draft", "outline", "brief", "publish"}),
    Roles.ARCHIVING: frozenset({"store", "retrieve", "archive"}),
    Roles.AUTOMATION: frozenset({"orchestrate", "execute_workflow"}),
}


def permissions_for(role: str) -> frozenset[str]:
    """Return the permitted actions for a role, or empty set if unknown."""
    return ROLE_PERMISSIONS.get(role, frozenset())
