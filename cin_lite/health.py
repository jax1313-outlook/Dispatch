"""Health check module.

Quick diagnostic of the pipeline's operational readiness: checks that sample
data exists, archive directories are writable, the Claude API is reachable
(if configured), and SMTP is connectable (if configured). Designed for
monitoring integrations and pre-flight checks.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from pathlib import Path
from typing import Any

from cin_lite import archive
from cin_lite.rules import ALL_RULES

_SAMPLE_DIR = Path(__file__).resolve().parent / "sample_data"


def _check_sample_data() -> dict[str, Any]:
    files = list(_SAMPLE_DIR.glob("*.json")) if _SAMPLE_DIR.exists() else []
    return {
        "name": "sample_data",
        "ok": len(files) > 0,
        "detail": f"{len(files)} sample file(s) in {_SAMPLE_DIR}",
    }


def _check_archive_writable() -> dict[str, Any]:
    try:
        archive.ensure_tree()
        test_file = archive.ARCHIVE_ROOT / ".healthcheck"
        test_file.write_text("ok")
        test_file.unlink()
        return {"name": "archive", "ok": True, "detail": f"writable at {archive.ARCHIVE_ROOT}"}
    except Exception as exc:
        return {"name": "archive", "ok": False, "detail": str(exc)}


def _check_rules() -> dict[str, Any]:
    return {
        "name": "rule_modules",
        "ok": len(ALL_RULES) == 9,
        "detail": f"{len(ALL_RULES)} rule module(s) registered",
    }


def _check_claude_api() -> dict[str, Any]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"name": "claude_api", "ok": True, "detail": "not configured (deterministic mode)"}
    try:
        import anthropic
        client = anthropic.Anthropic()
        client.messages.create(
            model=os.environ.get("CIN_LITE_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=5,
            messages=[{"role": "user", "content": "ping"}],
        )
        return {"name": "claude_api", "ok": True, "detail": "reachable"}
    except ImportError:
        return {"name": "claude_api", "ok": False, "detail": "anthropic SDK not installed but API key is set"}
    except Exception as exc:
        return {"name": "claude_api", "ok": False, "detail": f"unreachable: {exc}"}


def _check_smtp() -> dict[str, Any]:
    host = os.environ.get("CIN_LITE_SMTP_HOST")
    if not host:
        return {"name": "smtp", "ok": True, "detail": "not configured (offline email mode)"}
    port = int(os.environ.get("CIN_LITE_SMTP_PORT", "587"))
    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            if os.environ.get("CIN_LITE_SMTP_STARTTLS", "1") == "1":
                server.starttls(context=ssl.create_default_context())
            server.noop()
        return {"name": "smtp", "ok": True, "detail": f"connected to {host}:{port}"}
    except Exception as exc:
        return {"name": "smtp", "ok": False, "detail": f"{host}:{port} — {exc}"}


def _check_sam_api() -> dict[str, Any]:
    key = os.environ.get("CIN_LITE_SAM_API_KEY")
    if not key:
        return {"name": "sam_api", "ok": True, "detail": "not configured (local data mode)"}
    return {"name": "sam_api", "ok": True, "detail": "API key present (live SAM.gov mode)"}


def run_checks() -> list[dict[str, Any]]:
    """Run all health checks and return a list of results."""
    return [
        _check_sample_data(),
        _check_archive_writable(),
        _check_rules(),
        _check_claude_api(),
        _check_smtp(),
        _check_sam_api(),
    ]


def is_healthy() -> bool:
    """Return True if all checks pass."""
    return all(c["ok"] for c in run_checks())


def report() -> str:
    """Return a formatted health report."""
    checks = run_checks()
    lines = ["CIN-Lite Health Check", "=" * 50]
    for c in checks:
        status = "OK" if c["ok"] else "FAIL"
        lines.append(f"  [{status:>4}] {c['name']:<20} {c['detail']}")
    overall = "HEALTHY" if all(c["ok"] for c in checks) else "DEGRADED"
    lines.append(f"\nOverall: {overall}")
    return "\n".join(lines)
