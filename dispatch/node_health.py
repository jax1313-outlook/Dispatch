"""Node health: what the laptop in the Pelican case can honestly say about itself (CO-11).

Owner direction, 2026-09-14: *"The game plan is to have the laptop or a mini pc running in a
temperature cooled Pelican box vented with Temp gauge loaded on tablet for monitoring."*

CLAUDE.md §5A: the node must survive power loss unattended and report its status to the portal
on recovery. This module is that report. It reads -- it never configures, never repairs, never
restarts anything.

WHAT IS REPORTED, AND HOW STRONGLY
==================================

* **Temperature** -- only where the operating system reports one. On Windows a read-only CIM
  query is run in a PowerShell subprocess with a timeout: the thermal-zone performance counter
  first (readable without administrator rights), the ACPI thermal zone class only if that gave
  nothing. A zone reporting exactly 0 °C is an unpopulated zone, not a reading. When nothing
  plausible comes back the status is ``UNAVAILABLE`` with the reason. **Never a guessed number.**
  These are the laptop's *internal* zones (CPU, chipset, battery); they are not the air
  temperature inside the case.
* **Free space** on the drive holding the portal data folder.
* **Backups** -- from ``dispatch.backup_drives.rotation_status()``: age of the newest backup that
  passed its hash check, the drive in use, and the swap reminder. Not re-derived here.
* **Joe** -- CLAUDE.md §5A names ``JOE LIVE`` / ``JOE DOWN``. **Dispatch has no live check of
  Joe's connection today**, so this reports ``UNVERIFIED`` and the time of the last audited Joe
  action. It does not invent LIVE or DOWN from that time.
* **Uptime** of the machine, and how long this portal process has been running.

The temperature probe costs seconds, so a report is cached for ``CACHE_SECONDS``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

LIVE = "LIVE"
UNAVAILABLE = "UNAVAILABLE"
UNVERIFIED = "UNVERIFIED"
ABSENT = "ABSENT"

CACHE_SECONDS = 60
TEMPERATURE_TIMEOUT_SECONDS = 12

#: The hottest internal zone at or above this is called out. Configurable because the right
#: number depends on the machine; see docs/operations/NODE_UNATTENDED_RECOVERY.md.
HOT_ENV = "DISPATCH_NODE_HOT_C"
DEFAULT_HOT_CELSIUS = 85.0

#: Free space below this fraction of the drive is called out.
LOW_DISK_FRACTION = 0.10

#: Readings outside this range are discarded as implausible rather than displayed.
_PLAUSIBLE_C = (0.5, 125.0)

_PORTAL_STARTED = time.monotonic()
_IS_WINDOWS = sys.platform == "win32"

#: One PowerShell run. Pipe-delimited lines, no ConvertTo-Json (its shape differs between
#: PowerShell editions -- see dispatch_launcher/processes.py). K = kelvin, DK = tenths of
#: kelvin, E = the query failed, with its message.
_PS_TEMPERATURE = (
    "$out = @(); "
    "try { Get-CimInstance -ClassName Win32_PerfFormattedData_Counters_ThermalZoneInformation "
    "-ErrorAction Stop | ForEach-Object { $out += ('K|' + $_.Name + '|' + $_.Temperature) } } "
    "catch { $out += ('E|thermal zone counter|' + $_.Exception.Message) }; "
    "if (-not ($out | Where-Object { $_ -like 'K|*' })) { "
    "try { Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
    "-ErrorAction Stop | ForEach-Object { $out += ('DK|' + $_.InstanceName + '|' + $_.CurrentTemperature) } } "
    "catch { $out += ('E|acpi thermal zone|' + $_.Exception.Message) } }; "
    "$out"
)

Runner = Callable[[list[str], int], "subprocess.CompletedProcess | None"]


def _stamp(moment: datetime | None = None) -> str:
    return (moment or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── temperature ────────────────────────────────────────────────────────

def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            command, capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None


def parse_temperature_lines(lines: list[str]) -> dict:
    """Turn the probe's lines into a report. Pure, so the honesty rules are testable anywhere."""
    zones, errors = [], []
    for raw in lines:
        parts = raw.strip().split("|", 2)
        if len(parts) < 3:
            continue
        kind, name, value = parts
        if kind == "E":
            errors.append(f"{name}: {value.strip()}")
            continue
        try:
            number = float(value)
        except ValueError:
            continue
        if kind == "K":
            celsius = number - 273.15
        elif kind == "DK":
            celsius = number / 10.0 - 273.15
        elif kind == "MC":  # millidegrees Celsius, as Linux reports
            celsius = number / 1000.0
        else:
            continue
        plausible = _PLAUSIBLE_C[0] <= celsius <= _PLAUSIBLE_C[1]
        zones.append({"zone": name.strip(), "celsius": round(celsius, 1), "reported": plausible})

    reporting = [z for z in zones if z["reported"]]
    if not reporting:
        reason = "; ".join(errors) if errors else (
            "the machine lists thermal zones but none reports a reading" if zones
            else "the operating system reports no temperature")
        return {"status": UNAVAILABLE, "celsius": None, "zone": None, "zones": zones, "detail": reason}
    hottest = max(reporting, key=lambda z: z["celsius"])
    return {
        "status": LIVE, "celsius": hottest["celsius"], "zone": hottest["zone"], "zones": zones,
        "detail": "hottest internal zone the operating system reports; not the air in the case",
    }


def read_temperature(runner: Runner | None = None) -> dict:
    run = runner or _run
    if _IS_WINDOWS or runner is not None:
        completed = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_TEMPERATURE],
                        TEMPERATURE_TIMEOUT_SECONDS)
        if completed is None:
            return {"status": UNAVAILABLE, "celsius": None, "zone": None, "zones": [],
                    "detail": f"the temperature query did not answer within {TEMPERATURE_TIMEOUT_SECONDS} s "
                              "or could not be started"}
        return parse_temperature_lines((completed.stdout or "").splitlines())

    lines = []
    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        try:
            kind = (zone / "type").read_text().strip() or zone.name
            lines.append(f"MC|{kind}|{(zone / 'temp').read_text().strip()}")
        except OSError:
            continue
    return parse_temperature_lines(lines)


def hot_threshold() -> float:
    try:
        return float(os.environ.get(HOT_ENV, "") or DEFAULT_HOT_CELSIUS)
    except ValueError:
        return DEFAULT_HOT_CELSIUS


# ── disk ───────────────────────────────────────────────────────────────

def disk_space(path: Path | str | None = None) -> dict:
    if path is None:
        from portal.models import get_data_dir

        path = get_data_dir()
    probe = Path(path)
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    try:
        usage = shutil.disk_usage(probe)
    except OSError as exc:
        return {"status": UNAVAILABLE, "path": str(path), "detail": str(exc),
                "free_bytes": None, "total_bytes": None, "free_fraction": None}
    fraction = usage.free / usage.total if usage.total else None
    return {
        "status": LIVE, "path": str(path), "drive": probe.anchor or str(probe),
        "free_bytes": usage.free, "total_bytes": usage.total,
        "free_fraction": round(fraction, 3) if fraction is not None else None,
        "detail": "",
    }


# ── uptime ─────────────────────────────────────────────────────────────

def node_uptime_seconds() -> float | None:
    if sys.platform == "win32":  # pragma: no cover - Windows-only branch
        try:
            import ctypes

            tick = ctypes.windll.kernel32.GetTickCount64
            tick.restype = ctypes.c_uint64
            return tick() / 1000.0
        except Exception:  # noqa: BLE001
            return None
    try:
        return float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None


# ── backups and Joe: reuse, never re-derive ────────────────────────────

def backup_summary() -> dict:
    try:
        from dispatch import backup_drives

        return backup_drives.rotation_status().to_dict()
    except Exception as exc:  # noqa: BLE001 - a health page must not fall over on one part
        return {"state": UNAVAILABLE, "recorded": False, "stale": True, "swap_due": False,
                "warnings": [f"backup record could not be read: {exc}"],
                "newest_pass_age_hours": None, "drives": []}


def joe_summary() -> dict:
    last = None
    try:
        from dispatch import audit

        found = audit.entries(limit=1)
        last = found[-1].get("timestamp") if found else None
    except Exception:  # noqa: BLE001
        last = None
    return {
        "status": UNVERIFIED,
        "last_audited_action_at": last,
        "detail": "Dispatch has no live check of Joe's connection yet, so JOE LIVE / JOE DOWN "
                  "is not shown. The time is the last Joe action in the audit log.",
    }


# ── the report ─────────────────────────────────────────────────────────

_cache_lock = threading.Lock()
_cache: tuple[float, dict] | None = None


def collect(*, runner: Runner | None = None, refresh: bool = False) -> dict:
    """The full node report, cached for CACHE_SECONDS unless *refresh*."""
    global _cache
    with _cache_lock:
        if not refresh and runner is None and _cache is not None \
                and time.monotonic() - _cache[0] < CACHE_SECONDS:
            return _cache[1]

    temperature = read_temperature(runner)
    disk = disk_space()
    backups = backup_summary()
    report = {
        "checked_at": _stamp(),
        "temperature": temperature,
        "hot_threshold_celsius": hot_threshold(),
        "disk": disk,
        "backup": backups,
        "joe": joe_summary(),
        "uptime": {"node_seconds": node_uptime_seconds(),
                   "portal_seconds": round(time.monotonic() - _PORTAL_STARTED)},
    }
    report["attention"] = attention(report)
    if runner is None:
        with _cache_lock:
            _cache = (time.monotonic(), report)
    return report


def attention(report: dict) -> list[str]:
    """What an operator should act on, in plain words, most urgent first."""
    items = []
    temp = report["temperature"]
    if temp.get("status") == LIVE and temp["celsius"] >= report["hot_threshold_celsius"]:
        items.append(f"Node is running hot: {temp['celsius']:.0f} °C ({temp['zone']}).")
    disk = report["disk"]
    if disk.get("free_fraction") is not None and disk["free_fraction"] < LOW_DISK_FRACTION:
        items.append(f"Data drive is nearly full: {_gb(disk['free_bytes'])} free.")
    backup = report["backup"]
    if backup.get("stale"):
        items.append("No checked backup in the last 24 hours.")
    if backup.get("swap_due"):
        items.append("Time to swap backup drives.")
    return items


def _gb(value: int | None) -> str:
    return "unknown" if value is None else f"{value / 1_000_000_000:.0f} GB"


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    minutes = int(seconds // 60)
    days, rem = divmod(minutes, 1440)
    hours, mins = divmod(rem, 60)
    if days:
        return f"{days} d {hours} h"
    if hours:
        return f"{hours} h {mins} min"
    return f"{mins} min"


def driver_card(report: dict) -> dict:
    """The NODE card on the Driver Cockpit: short lines in the driver's words.

    No status vocabulary and no engineering words (tests/test_joe_speaks_to_the_driver.py). What
    is not known is said as not known -- "Temp not reported" -- never filled in.
    """
    lines = []
    temp = report["temperature"]
    if temp.get("status") == LIVE:
        lines.append(f"Temp {temp['celsius']:.0f}°C")
    else:
        lines.append("Temp not reported")

    backup = report["backup"]
    age = backup.get("newest_pass_age_hours")
    if age is None:
        lines.append("No backup yet")
    elif backup.get("stale"):
        lines.append(f"Backup {age:.0f} h old")
    elif age < 1:
        lines.append("Backup under 1 h ago")
    else:
        lines.append(f"Backup {age:.0f} h ago")
    if backup.get("swap_due"):
        lines.append("Swap backup drive")

    disk = report["disk"]
    if disk.get("free_bytes") is not None:
        lines.append(f"{_gb(disk['free_bytes'])} free")
    lines.append(f"Up {_duration(report['uptime'].get('node_seconds'))}")

    return {"title": "NODE", "lines": lines, "attention": bool(report.get("attention")),
            "checked_at": report["checked_at"]}
