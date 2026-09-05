"""Dispatch Launcher — the Windows-native operating control for the Dispatch portal.

This package exists for one reason: the only documented way to run Dispatch was
`python portal\\app.py` from a command prompt, which means the owner of the
business cannot start, stop or inspect his own operations system without typing
Python commands and reading a stack trace when it does not come up.

**This is a control, not a second Dispatch.** The distinction is load-bearing and
is enforced, not merely intended:

* It never imports `dispatch.services`, `dispatch.store` or `dispatch.spine.*`,
  and never opens the operational database. It cannot create, move or modify a
  load, a milestone, a settlement or any other operational record, because it has
  no code path that could. `tests/test_launcher.py::TestNoPathToCurrentReality`
  asserts this against a real interpreter, so the boundary breaks the build if a
  future edit crosses it.
* It observes two things only: **operating-system process state** (is a server
  process alive, which one, since when) and **configuration** (what the portal
  would resolve if it started right now). Both are read through the application's
  own resolvers -- never re-implemented here -- so the launcher cannot drift into
  reporting a database location or a port the portal does not actually use.
* Configuration is read in a *subprocess* (`dispatch_launcher.probe`), so even the
  import side effects of the application's own path resolvers happen somewhere
  other than the launcher process.

The only state it owns is a PID file and a log directory, both outside version
control, both describing processes rather than freight.

Entry points:

    dispatch.bat                    double-click, text menu (Windows)
    Dispatch.ps1                    the same, for a PowerShell console
    python -m dispatch_launcher     the same menu, any platform
    python -m dispatch_launcher status|start|stop|restart|open

Everything Windows-specific is guarded and has a POSIX counterpart, so the whole
control core is importable and unit-testable on the Linux CI that runs this
repository's test suite. What that CI *cannot* prove -- that `taskkill` and
`Get-CimInstance` behave as expected on Mike's machine -- is recorded as
UNVERIFIED in proof/launcher/LAUNCHER_PROOF.md rather than assumed.
"""

from __future__ import annotations

__all__ = [
    "backups",
    "cli",
    "control",
    "locations",
    "pidfile",
    "probe",
    "processes",
    "redaction",
    "status",
]

# Deliberately no eager submodule imports here. `import dispatch_launcher` is
# used by the boundary test to prove the package pulls in nothing operational,
# and a bare package import should stay that cheap for the .bat wrapper too.
