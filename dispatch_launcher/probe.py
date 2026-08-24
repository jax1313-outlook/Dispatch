"""Read the portal's real runtime configuration, without becoming the portal.

Every display in the launcher's status screen has to be the value the portal
would actually use, not a value the launcher believes. The only way to guarantee
that is to ask the application's own resolvers: `portal.config.Config`,
`portal.config.development_host`, `dispatch.db.get_db_path`,
`portal.models.get_memory_dir` / `get_archive_dir`, `cin_lite.archive`. Nothing
here re-implements a path or a default.

Two rules shape how that is done.

*Nothing operational is imported.* The resolvers above pull in `os`, `pathlib`
and `sqlite3` and nothing else -- none of them reaches `dispatch.services`,
`dispatch.store` or `dispatch.spine.*`. The one display that would have required
crossing that line is the evidence-upload directory, which the portal resolves
through `dispatch.services._get_upload_dir`; it is deliberately **not** shown
here. A launcher that imported the service layer to print a folder name would
have a live code path into Current Reality for the sake of one line of text.

*The import happens somewhere else.* `collect()` is normally executed in a child
interpreter (`python -m dispatch_launcher.probe --json`), not in the launcher
process. That matters because these resolvers are not purely functional:
`dispatch.db.get_db_path()` creates the portal data directory as a side effect of
resolving it. Running the probe out-of-process keeps every such effect in a
process that exits immediately, keeps the launcher's own memory free of
application modules, and means the facts reported are the facts a freshly started
server would see rather than the facts cached in a long-lived menu process.

`collect()` is still an ordinary importable function so the test suite can drive
it directly and assert against real resolved values.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

#: Reported wherever a fact could not be established. Part of the program's
#: fixed truth vocabulary -- never softened into "unknown" or "n/a".
UNVERIFIED = "UNVERIFIED"
UNAVAILABLE = "UNAVAILABLE"

#: How long the child interpreter gets to report. Generous: a cold import of
#: flask-free config modules is fast, but Windows Defender can make first-run
#: process creation slow enough to matter.
PROBE_TIMEOUT_SECONDS = 30.0


@dataclass
class RuntimeFacts:
    """Everything the status screen shows that comes from configuration.

    Every field is either a real resolved value or an explicit truth-vocabulary
    marker. There are no defaults standing in for unknowns: a field the probe
    could not establish says so.
    """

    version: str = UNVERIFIED
    version_source: str = UNVERIFIED
    commit: str = UNVERIFIED
    commit_source: str = UNVERIFIED

    requested_host: str = UNVERIFIED
    host: str = UNVERIFIED
    port: int | None = None
    host_pinned: bool = False

    database_path: str = UNVERIFIED
    portal_data_dir: str = UNVERIFIED
    contract_archive_root: str = UNVERIFIED

    operations_root: str | None = None
    archive_root: str | None = None
    memory_root: str | None = None

    mode: str = UNVERIFIED
    dispatch_mode_setting: str | None = None

    weak_secret_names: list[str] = field(default_factory=list)
    secrets_block_start: bool = False

    backup_dir: str | None = None

    probe_ok: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        """The address to open in a browser, or a marker when unknown."""
        if self.host == UNVERIFIED or self.port is None:
            return UNVERIFIED
        host = "127.0.0.1" if self.host in ("0.0.0.0", "::") else self.host
        return f"http://{host}:{self.port}"

    @classmethod
    def from_dict(cls, data: dict) -> "RuntimeFacts":
        """Tolerant reconstruction from the child interpreter's JSON.

        Unknown keys are ignored and missing keys keep their declared default,
        so a probe from a newer or older checkout degrades instead of raising.
        """
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def to_dict(self) -> dict:
        return asdict(self)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _git_commit(root: Path) -> tuple[str, str]:
    """Return (commit, source). Degrades to UNVERIFIED, never raises.

    Git is not installed on every Windows machine and a copied folder is not a
    repository, so this failing is an ordinary condition, not an error worth
    surfacing as one.
    """
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return UNVERIFIED, "git is not available on this machine"
    if completed.returncode != 0:
        return UNVERIFIED, "this folder is not a git checkout"
    commit = completed.stdout.strip()
    return (commit, "git rev-parse HEAD") if commit else (UNVERIFIED, "git returned no commit")


def _version(root: Path) -> tuple[str, str]:
    """Application version, preferring the package the portal itself reports."""
    try:
        import portal  # noqa: PLC0415 -- deliberately lazy; see module docstring

        version = getattr(portal, "__version__", "")
        if version:
            return version, "portal.__version__"
    except Exception:  # pragma: no cover - only when the checkout is broken
        pass

    pyproject = root / "pyproject.toml"
    try:
        import tomllib  # noqa: PLC0415

        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        version = str(data.get("project", {}).get("version", ""))
        if version:
            return version, "pyproject.toml"
    except Exception:
        pass
    return UNVERIFIED, "no version could be read"


def collect() -> dict:
    """Resolve every configuration fact, through the application's own code.

    Returns a plain dict so it can cross a process boundary as JSON. Each block
    is guarded separately: one unreadable setting degrades one line of the status
    screen instead of blanking the whole thing.
    """
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    facts: dict = {"errors": [], "probe_ok": True}

    version, version_source = _version(root)
    facts["version"] = version
    facts["version_source"] = version_source

    commit, commit_source = _git_commit(root)
    facts["commit"] = commit
    facts["commit_source"] = commit_source

    try:
        from portal.config import (  # noqa: PLC0415
            Config,
            _PUBLISHED_DEFAULTS,
            development_host,
            is_development_mode,
        )

        requested = Config.HOST
        resolved = development_host(requested)
        facts["requested_host"] = requested
        facts["host"] = resolved
        facts["port"] = int(Config.PORT)
        facts["host_pinned"] = resolved != requested
        facts["portal_data_dir"] = str(Path(Config.DATA_DIR).resolve())

        development = is_development_mode()
        facts["mode"] = "development" if development else "operational"
        facts["dispatch_mode_setting"] = os.environ.get("DISPATCH_MODE")

        # Read straight from the application's own table of published defaults
        # rather than keeping a second copy here. If a third secret is added to
        # portal/config.py, the launcher reports it the same day, with no edit.
        #
        # Only NAMES are collected. check_secrets() is deliberately not called:
        # in operational mode it raises, and a status screen must be able to
        # report "this would refuse to start" without itself refusing to run.
        weak = [
            name
            for name, published in _PUBLISHED_DEFAULTS.items()
            if os.environ.get(name, published) == published
        ]
        facts["weak_secret_names"] = sorted(weak)
        facts["secrets_block_start"] = bool(weak) and not development
    except Exception as exc:
        facts["errors"].append(f"portal configuration could not be read: {exc}")
        facts["probe_ok"] = False

    try:
        from dispatch.db import get_db_path  # noqa: PLC0415

        facts["database_path"] = str(Path(get_db_path()).resolve())
    except Exception as exc:
        facts["errors"].append(f"database location could not be resolved: {exc}")
        facts["probe_ok"] = False

    try:
        from cin_lite import archive as cin_archive  # noqa: PLC0415

        facts["contract_archive_root"] = str(cin_archive.ARCHIVE_ROOT.resolve())
    except Exception as exc:
        facts["errors"].append(f"contract archive root could not be resolved: {exc}")

    # The three storage roots are reported as the operator set them -- unset is a
    # real, reportable state ("using defaults"), not a value to fill in.
    facts["operations_root"] = os.environ.get("DISPATCH_OPERATIONS_ROOT")
    facts["archive_root"] = os.environ.get("DISPATCH_ARCHIVE_ROOT")
    facts["memory_root"] = os.environ.get("DISPATCH_MEMORY_ROOT")
    facts["backup_dir"] = os.environ.get("DISPATCH_BACKUP_DIR")

    try:
        from portal.models import get_archive_dir, get_memory_dir  # noqa: PLC0415

        if not facts["archive_root"]:
            facts["archive_root"] = str(get_archive_dir().resolve())
        if not facts["memory_root"]:
            facts["memory_root"] = str(get_memory_dir().resolve())
    except Exception as exc:
        facts["errors"].append(f"archive/memory roots could not be resolved: {exc}")

    return facts


def probe_runtime(*, use_subprocess: bool = True) -> RuntimeFacts:
    """Collect the runtime facts, out of process by default.

    `use_subprocess=False` runs `collect()` inline. That exists for tests and for
    the (unlikely) machine where spawning a child interpreter fails; the inline
    path imports application configuration modules into the caller, which is why
    it is not the default.
    """
    if not use_subprocess:
        return RuntimeFacts.from_dict(collect())

    root = _repo_root()
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "dispatch_launcher.probe", "--json"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return RuntimeFacts(errors=["configuration probe timed out"], probe_ok=False)
    except OSError as exc:
        return RuntimeFacts(errors=[f"configuration probe could not run: {exc}"], probe_ok=False)

    if completed.returncode != 0:
        detail = (completed.stderr or "").strip().splitlines()
        tail = detail[-1] if detail else "no error text"
        return RuntimeFacts(
            errors=[f"configuration probe failed: {tail}"], probe_ok=False
        )
    try:
        return RuntimeFacts.from_dict(json.loads(completed.stdout))
    except (ValueError, TypeError) as exc:
        return RuntimeFacts(
            errors=[f"configuration probe returned unreadable output: {exc}"], probe_ok=False
        )


def main(argv: list[str] | None = None) -> int:
    """`python -m dispatch_launcher.probe --json` -- the child-process entry point."""
    argv = list(sys.argv[1:] if argv is None else argv)
    facts = collect()
    if "--json" in argv or not argv:
        print(json.dumps(facts, indent=None, sort_keys=True))
        return 0
    for key in sorted(facts):
        print(f"{key}: {facts[key]}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main())
