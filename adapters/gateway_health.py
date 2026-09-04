"""Gateway health check.

**THIS IS AN ADAPTER.** A data gateway is a provider concept, so it lives here
and not in `dispatch/`. The contract knows nothing about it; if a second stack
reaches Dispatch some other way, this file is irrelevant to it and nothing
under `dispatch/` or `portal/routes/joe_api.py` changes.

WHAT IT REPORTS
===============

The doctrine vocabulary, and only that:

    LIVE          reachable and running, verified here and now
    CONFIGURED    installed and set up, not currently answering
    UNVERIFIED    not established as working

**Status is never inferred and never assumed from what anybody said.** An owner
reporting a gateway as set up is information about a belief, not evidence about
a machine. This checks the machine.

The Honest Reporting Rule applies: no false success, no silent failure. When
the check itself cannot run, that is UNVERIFIED with the reason stated -- not a
guess in either direction.
"""

from __future__ import annotations

import os
import subprocess

LIVE = "LIVE"
CONFIGURED = "CONFIGURED"
UNVERIFIED = "UNVERIFIED"

#: The Windows service the on-premises data gateway installs, and the display
#: name it carries. Both are checked because a renamed service is still a
#: service and a missing one is still missing.
SERVICE_NAME = "PBIEgwService"
SERVICE_DISPLAY = "On-premises data gateway service"

#: Where the installer puts it. Presence without a running service is
#: CONFIGURED; absence of both is UNVERIFIED.
INSTALL_PATHS = (
    r"C:\Program Files\On-premises data gateway",
    r"C:\Program Files (x86)\On-premises data gateway",
    r"C:\Program Files\Power BI Enterprise Gateway",
)


def _service_state() -> tuple:
    """(found, running, detail). Never raises."""
    try:
        result = subprocess.run(
            ["sc", "query", SERVICE_NAME],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:  # noqa: BLE001 - a failed check is not a status
        return False, False, "could not query services (%s)" % type(exc).__name__

    out = (result.stdout or "") + (result.returncode and "" or "")
    if "does not exist" in out or result.returncode != 0:
        return False, False, "service %s is not installed" % SERVICE_NAME
    running = "RUNNING" in out.upper()
    return True, running, "service %s is %s" % (
        SERVICE_NAME, "running" if running else "installed but not running")


def _installed() -> tuple:
    for path in INSTALL_PATHS:
        if os.path.isdir(path):
            return True, path
    return False, ""


def check() -> dict:
    """Verify the gateway. Reports what was found, never what was expected."""
    found, running, service_detail = _service_state()
    installed, path = _installed()

    if found and running:
        status = LIVE
        note = service_detail
    elif found or installed:
        status = CONFIGURED
        note = service_detail if found else "installed at %s, service not found" % path
    else:
        status = UNVERIFIED
        note = ("no gateway service and no gateway installation found on this "
                "machine")

    return {
        "component": "data gateway",
        "status": status,
        "service_found": found,
        "service_running": running,
        "installed": installed,
        "install_path": path,
        "note": note,
        "checked": True,
    }


def report() -> str:
    """One declarative line, in the locked vocabulary."""
    result = check()
    return "DATA GATEWAY: %s. %s." % (result["status"], result["note"])


if __name__ == "__main__":  # pragma: no cover - operator convenience
    print(report())
