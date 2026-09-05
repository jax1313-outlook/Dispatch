"""Operating-system process facts, using nothing but the standard library.

`psutil` is not a dependency of this repository and the mission forbids adding
one, so everything here is built from `os`, `signal`, `socket`, `subprocess` and
the two places an operating system already publishes process facts: `/proc` on
Linux and `Get-CimInstance Win32_Process` on Windows.

Three things are needed, and only three:

*Is this process alive?* Cheap and reliable everywhere.

*Is it OUR process?* This is the one that matters. A PID is reused. A PID file
written before a crash can name a process that is now a text editor, and sending
it a termination signal because a file said "8123" would be the launcher doing
real damage. So liveness alone is never treated as identity: the launcher records
a process's command line and creation time when it starts it, and compares both
before it will act on that PID. When the platform cannot supply either, the
answer is UNVERIFIED and the caller refuses to act -- see `control.stop()`.

*Is something already on the port?* A plain TCP connect. It is the difference
between "Dispatch could not start because port 8080 is already in use" and a
Werkzeug traceback, and it needs no privileges on any platform.

Everything Windows-specific is behind `os.name == "nt"` and has a POSIX
counterpart, so this module imports and runs on the Linux CI. The Windows
branches are exercised in tests through their parsers with recorded output; that
they invoke correctly on Windows is UNVERIFIED until Mike runs it.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

UNAVAILABLE = "UNAVAILABLE"

IS_WINDOWS = os.name == "nt"

#: How long a platform query may take before it is treated as unavailable. These
#: are local queries; anything slower than this is a sick machine, and a status
#: screen that hangs is worse than one that says UNAVAILABLE.
QUERY_TIMEOUT_SECONDS = 15.0

#: Substrings that identify a Dispatch portal server process by its command line.
#: Both must be present: "app.py" alone would match any Python script.
_PORTAL_MARKERS = ("portal", "app.py")


@dataclass(frozen=True)
class ProcessFacts:
    """What the operating system will tell us about one PID."""

    pid: int
    alive: bool
    command_line: str | None = None
    #: Opaque, platform-specific creation token. Only ever compared for equality
    #: against a token recorded by this same launcher on this same machine --
    #: never parsed, never displayed as a date.
    created_token: str | None = None
    #: Where the facts came from: "proc", "ps", "cim", "tasklist", or UNAVAILABLE.
    source: str = UNAVAILABLE

    @property
    def looks_like_portal(self) -> bool:
        if not self.command_line:
            return False
        lowered = self.command_line.lower()
        return all(marker in lowered for marker in _PORTAL_MARKERS)


def _run(command: list[str]) -> subprocess.CompletedProcess | None:
    """Run a short platform query. Returns None when it cannot run at all."""
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=QUERY_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None


# ── liveness ───────────────────────────────────────────────────────────

def _reap_if_own_child(pid: int) -> None:
    """Collect the exit status of *pid* when it is one of our own children.

    Without this, a stopped server would look alive forever whenever the
    launcher outlives it -- which is exactly what happens when the menu stays
    open. A terminated child that nobody has waited on remains in the process
    table as a zombie: `os.kill(pid, 0)` still succeeds and `/proc/<pid>` still
    exists, so a naive liveness check reports a dead server as running and Stop
    reports failure for a stop that worked.

    Raises nothing. A PID that is not our child raises ChildProcessError, which
    is the ordinary case (the server is usually reparented to init long before
    anyone asks) and is simply ignored.
    """
    if IS_WINDOWS:  # pragma: no cover - Windows-only branch
        return
    try:
        os.waitpid(pid, os.WNOHANG)
    except (ChildProcessError, OSError):
        return


def _is_zombie(pid: int) -> bool:
    """True when *pid* has exited but has not yet been collected by its parent.

    A zombie is not a running server. Reported as dead, because that is what an
    operator means by "is it still running".
    """
    try:
        stat_text = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
    except OSError:
        return False
    close = stat_text.rfind(")")
    if close == -1:
        return False
    fields = stat_text[close + 2:].split()
    return bool(fields) and fields[0] == "Z"


def pid_alive(pid: int) -> bool:
    """True when a process with this PID currently exists and is still running.

    On POSIX, signal 0 performs the existence and permission check without
    delivering anything. `PermissionError` means the process exists but belongs
    to someone else -- still alive, and still not ours to kill. An exited but
    uncollected child is not alive; see `_reap_if_own_child`.
    """
    if pid <= 0:
        return False
    if IS_WINDOWS:  # pragma: no cover - Windows-only branch
        return _windows_facts(pid).alive
    _reap_if_own_child(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return not _is_zombie(pid)


# ── identity ───────────────────────────────────────────────────────────

def parse_proc_stat_starttime(stat_text: str) -> str | None:
    """Field 22 of /proc/<pid>/stat: the process start time in clock ticks.

    The second field is the executable name in parentheses and may itself contain
    spaces and parentheses, so the line is split after the LAST ')' rather than
    on whitespace -- splitting naively is the classic way this parse goes wrong
    for a process called `(my program)`.
    """
    close = stat_text.rfind(")")
    if close == -1:
        return None
    fields = stat_text[close + 2:].split()
    # After the ')' the fields are 3..N, so field 22 is index 19.
    if len(fields) < 20:
        return None
    return fields[19]


def _posix_facts(pid: int) -> ProcessFacts:
    _reap_if_own_child(pid)
    proc = Path("/proc") / str(pid)
    if proc.is_dir() and not _is_zombie(pid):
        command_line = None
        created = None
        try:
            raw = (proc / "cmdline").read_bytes()
            command_line = raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip() or None
        except OSError:
            pass
        try:
            created = parse_proc_stat_starttime((proc / "stat").read_text(encoding="utf-8"))
        except OSError:
            pass
        return ProcessFacts(
            pid=pid, alive=True, command_line=command_line,
            created_token=created, source="proc",
        )

    # No /proc (macOS, some hardened containers). `ps` is POSIX-standard and
    # gives both facts in one call.
    completed = _run(["ps", "-p", str(pid), "-o", "lstart=,args="])
    if completed is not None and completed.returncode == 0 and completed.stdout.strip():
        line = completed.stdout.strip()
        # lstart is a fixed-width 24-character date; everything after it is argv.
        created, _, command_line = line.partition(" ")
        parts = line.split(None, 5)
        if len(parts) == 6:
            created, command_line = " ".join(parts[:5]), parts[5]
        return ProcessFacts(
            pid=pid, alive=True, command_line=command_line.strip() or None,
            created_token=created.strip() or None, source="ps",
        )

    alive = pid_alive(pid) if not proc.parent.is_dir() else False
    return ProcessFacts(pid=pid, alive=alive, source=UNAVAILABLE if alive else "proc")


def parse_cim_line(line: str) -> tuple[str | None, str | None]:
    """Parse the `pid|created|commandline` line the PowerShell query emits.

    Kept as its own function so the parse is testable on Linux with recorded
    Windows output. The command line may itself contain '|', so the split is
    limited to two separators.
    """
    if not line or "|" not in line:
        return None, None
    parts = line.strip().split("|", 2)
    if len(parts) < 3:
        return None, None
    created = parts[1].strip() or None
    command_line = parts[2].strip() or None
    return created, command_line


#: One line out, pipe-delimited. `ConvertTo-Json` is deliberately avoided: it
#: renders CIM datetimes as `/Date(...)/` on Windows PowerShell 5.1 and as an
#: ISO string on PowerShell 7, and a launcher that parses two shapes to display
#: one token is complexity for nothing.
_CIM_TEMPLATE = (
    "Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\" | "
    "ForEach-Object {{ "
    "$_.ProcessId.ToString() + '|' + $_.CreationDate.ToString('o') + '|' + $_.CommandLine "
    "}}"
)


def _powershell(command: str) -> subprocess.CompletedProcess | None:
    return _run([
        "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-Command", command,
    ])


def _windows_facts(pid: int) -> ProcessFacts:  # pragma: no cover - Windows-only branch
    completed = _powershell(_CIM_TEMPLATE.format(pid=pid))
    if completed is not None and completed.returncode == 0 and completed.stdout.strip():
        created, command_line = parse_cim_line(completed.stdout.strip().splitlines()[0])
        if command_line or created:
            return ProcessFacts(
                pid=pid, alive=True, command_line=command_line,
                created_token=created, source="cim",
            )

    # PowerShell blocked or missing. tasklist still answers "does it exist",
    # which is enough for liveness and explicitly NOT enough for identity.
    completed = _run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"])
    if completed is not None and completed.returncode == 0 and f'"{pid}"' in completed.stdout:
        return ProcessFacts(pid=pid, alive=True, source="tasklist")
    if completed is None:
        return ProcessFacts(pid=pid, alive=False, source=UNAVAILABLE)
    return ProcessFacts(pid=pid, alive=False, source="tasklist")


def process_facts(pid: int) -> ProcessFacts:
    """Everything the operating system will say about *pid*."""
    if pid <= 0:
        return ProcessFacts(pid=pid, alive=False, source=UNAVAILABLE)
    if IS_WINDOWS:  # pragma: no cover - Windows-only branch
        return _windows_facts(pid)
    return _posix_facts(pid)


# ── termination ────────────────────────────────────────────────────────

def terminate(pid: int, *, force: bool = False) -> bool:
    """Ask *pid* to exit. Returns False when the request could not be delivered.

    Returning True means the request was accepted, NOT that the process is gone.
    Confirming that is `wait_until_gone`'s job, and every caller does it -- a stop
    that reports success on the strength of a delivered signal is exactly the
    kind of aspirational safety this launcher is not allowed to have.
    """
    if pid <= 0:
        return False
    if IS_WINDOWS:  # pragma: no cover - Windows-only branch
        command = ["taskkill", "/PID", str(pid)]
        if force:
            command.insert(1, "/F")
        completed = _run(command)
        return completed is not None and completed.returncode == 0
    try:
        os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        return True  # already gone: the desired end state
    except (PermissionError, OSError):
        return False
    return True


def wait_until_gone(pid: int, timeout: float, *, interval: float = 0.2) -> bool:
    """Poll until *pid* no longer exists, or *timeout* elapses."""
    deadline = time.monotonic() + timeout
    while True:
        if not pid_alive(pid):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


# ── ports ──────────────────────────────────────────────────────────────

def port_in_use(host: str, port: int, *, timeout: float = 0.5) -> bool:
    """True when something is already accepting connections on host:port.

    A connect test rather than a bind test on purpose: binding to check would
    briefly occupy the port the server is about to want, and on Windows a bind
    test can succeed against a port that is in TIME_WAIT and therefore lie.
    """
    target = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    try:
        with socket.create_connection((target, port), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def wait_until_listening(host: str, port: int, timeout: float, *, interval: float = 0.25) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        if port_in_use(host, port):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


# ── orphan discovery ───────────────────────────────────────────────────

def find_portal_processes(*, exclude: tuple[int, ...] = ()) -> list[ProcessFacts] | None:
    """Every process whose command line looks like a Dispatch portal server.

    Returns None -- meaning UNAVAILABLE, not "none found" -- when the platform
    will not enumerate processes. The difference matters: "there is no orphan"
    and "I could not look" must never render as the same sentence.
    """
    if IS_WINDOWS:  # pragma: no cover - Windows-only branch
        return _windows_portal_processes(exclude)
    return _posix_portal_processes(exclude)


def _posix_portal_processes(exclude: tuple[int, ...]) -> list[ProcessFacts] | None:
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return None
    found: list[ProcessFacts] = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid in exclude or pid == os.getpid():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue  # the process exited between listdir and read
        command_line = raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()
        facts = ProcessFacts(pid=pid, alive=True, command_line=command_line, source="proc")
        if facts.looks_like_portal:
            found.append(facts)
    return found


_CIM_SCAN = (
    "Get-CimInstance Win32_Process | "
    "ForEach-Object { "
    "$_.ProcessId.ToString() + '|' + $_.CreationDate.ToString('o') + '|' + $_.CommandLine "
    "}"
)


def _windows_portal_processes(  # pragma: no cover - Windows-only branch
    exclude: tuple[int, ...],
) -> list[ProcessFacts] | None:
    completed = _powershell(_CIM_SCAN)
    if completed is None or completed.returncode != 0:
        return None
    found: list[ProcessFacts] = []
    for line in completed.stdout.splitlines():
        pid_text, _, _rest = line.partition("|")
        if not pid_text.strip().isdigit():
            continue
        pid = int(pid_text.strip())
        if pid in exclude or pid == os.getpid():
            continue
        created, command_line = parse_cim_line(line)
        facts = ProcessFacts(
            pid=pid, alive=True, command_line=command_line,
            created_token=created, source="cim",
        )
        if facts.looks_like_portal:
            found.append(facts)
    return found
