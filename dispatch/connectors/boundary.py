"""The boundary itself — enforced by the import graph and by a runtime seal.

Section 6.2 states the architectural position and then says how it must hold:
"A connector may never call Spine transition code, never write to
``loads.status``, and never write to any Current Reality table. **Enforce this
structurally** (module boundaries, import rules, and tests) -- not by convention
alone."

Convention was the obvious alternative and it is the one that fails. A comment
saying "connectors must not import services" survives exactly until the
afternoon somebody needs a load's status inside a connector and takes the
shortest path to it; nothing refuses, the test suite still passes, and the
boundary is gone without a single line announcing its departure. So the rule is
enforced twice, in two different ways, because the two failures are different:

**Statically, over the import graph.** :func:`verify_package` parses every file
in ``dispatch/connectors`` and refuses:

  * any import of ``dispatch.spine``, ``dispatch.services`` or ``dispatch.store``
    -- directly, or transitively through another first-party module, so wrapping
    a forbidden import in a helper does not launder it;
  * any import of ``sqlite3`` or ``dispatch.db`` outside the two files that are
    allowed to know a database exists (``audit.py`` writes the connector audit
    table; this file patches ``sqlite3.connect`` to seal it);
  * any SQL statement naming a table other than ``connector_audit``.

``tests/test_connector_boundary.py`` runs it over the real package, so the
violation surfaces as a failing test the moment the import is written, before it
can be built on.

**At runtime, with a seal.** A static scan cannot see ``importlib``, a callable
handed in at construction, or a provider SDK that opens its own connection. So
:func:`execute` -- the only sanctioned way to call a connector -- runs
``fetch()`` inside :func:`sealed`, which replaces ``sqlite3.connect`` with a
guard that raises :class:`BoundaryViolation`. Any database access at all,
Current Reality or otherwise, by any path, from inside a connector call, fails
loudly.

Two details of the seal worth stating, because both were deliberate:

*It is keyed on a ``contextvars.ContextVar``, not on the patch being installed.*
The replacement delegates to the original whenever the calling context is not
inside a sealed connector call, so a second thread -- the portal serves requests
on several -- keeps working normally while a connector call is in flight. A
blunt patch would have made a connector call briefly break the whole
application, which is a worse defect than the one being prevented.

*A violation is raised, never downgraded.* Every other failure a connector can
have comes back as a labeled ``ConnectorResult``; a boundary breach does not. It
is a programming error, not an operational condition, and turning it into a soft
refusal would hide the exact thing this module exists to make impossible to
hide. The attempt is still audited on the way out.

What the boundary does **not** do is stop a connector writing a file or calling
the network -- both are legitimate (the email transport connector writes ``.eml``
files through ``cin_lite/email_delivery.py``; a real provider will make HTTP
calls). The prohibition is on owning operational truth, and in this codebase
operational truth is the SQLite database.
"""

from __future__ import annotations

import ast
import contextvars
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

from dispatch.connectors.contract import (
    AuditRecord,
    ConnectorError,
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    redact,
)

#: Subsystems a connector may never reach, directly or transitively. Spine owns
#: lifecycle truth; services and store own Current Reality.
FORBIDDEN_MODULES: tuple[str, ...] = (
    "dispatch.spine",
    "dispatch.services",
    "dispatch.store",
)

#: The database layer. Allowed only in the two files named below.
DATABASE_MODULES: tuple[str, ...] = ("sqlite3", "dispatch.db")

#: ``audit.py`` writes the connector audit table; ``boundary.py`` patches
#: ``sqlite3.connect`` to seal it. Nothing else in the package may know a
#: database exists.
DATABASE_ALLOWED_FILES: frozenset[str] = frozenset({"audit.py", "boundary.py"})

#: The only table the connectors package may name in SQL.
ALLOWED_TABLES: frozenset[str] = frozenset({"connector_audit"})

#: Current Reality (dispatch/db.py's ``_SCHEMA``) and the Spine's six tables.
#: Listed so a violation message can say *which* operational table was named.
CURRENT_REALITY_TABLES: frozenset[str] = frozenset(
    {
        "loads", "visibility", "milestones", "evidence", "exceptions",
        "pod_packages", "retention", "rate_confirmations", "expenses",
        "settlements", "drivers", "equipment", "route_risk_events",
        "status_changes", "lane_templates", "broker_contacts",
        "maintenance_schedules", "compliance_documents",
        "work_items", "work_item_events", "approval_events",
        "audit_events", "correlations", "state_snapshots",
    }
)

#: First-party packages the transitive scan follows into. Anything else
#: (stdlib, flask) is out of scope: the rule is about Dispatch's own layering.
FIRST_PARTY_PREFIXES: tuple[str, ...] = ("dispatch", "cin_lite", "route_risk", "portal", "sync")

_PACKAGE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_DIR.parent.parent

# Case-SENSITIVE on purpose. SQL keywords are uppercase everywhere in this
# repository, and a case-insensitive scan would read ordinary prose as SQL --
# "select a provider ... from" inside a docstring would produce a table name and
# a spurious violation. Matching only the uppercase form keeps the scan strict
# about code and blind to English.
_SQL_TABLE_PATTERN = re.compile(
    r"(?s)\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|FROM|JOIN|"
    r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?|"
    r"CREATE\s+INDEX(?:\s+IF\s+NOT\s+EXISTS)?\s+\w+\s+ON)\s+([a-z_][a-z0-9_]*)"
)
_SQL_KEYWORD_PATTERN = re.compile(
    r"(?s)\b(?:INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|SELECT\s+.+?\s+FROM|"
    r"CREATE\s+TABLE|CREATE\s+INDEX)\b"
)


class BoundaryViolation(RuntimeError):
    """A connector crossed the line Section 6.2 draws around it."""


# --------------------------------------------------------------------------- static scan


def _module_file(module_name: str) -> Path | None:
    """Resolve a first-party module name to a file, without importing it.

    Deliberately path-based rather than ``importlib.util.find_spec``: the scan
    must be able to run over a module it would be wrong to import (importing
    ``dispatch.services`` to prove nothing imports it is its own small joke),
    and a find_spec walk executes package ``__init__`` files.
    """
    parts = module_name.split(".")
    candidate = _REPO_ROOT.joinpath(*parts).with_suffix(".py")
    if candidate.is_file():
        return candidate
    package_init = _REPO_ROOT.joinpath(*parts, "__init__.py")
    if package_init.is_file():
        return package_init
    return None


def module_imports(path: Path) -> set[str]:
    """Every module name imported by one file, as written."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Relative import: resolve against the file's own package so a
                # `from .. import store` cannot slip past a name-prefix check.
                # A file outside the repository has no package path to resolve
                # against, so its relative imports are recorded as written --
                # enough for the scan to report, and it keeps the scanner usable
                # on an arbitrary file (which is how its own tests exercise it).
                try:
                    package_parts = path.resolve().relative_to(_REPO_ROOT).parts[:-1]
                except ValueError:
                    package_parts = ()
                base = list(package_parts[: len(package_parts) - node.level + 1])
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            if module:
                found.add(module)
                for alias in node.names:
                    found.add(f"{module}.{alias.name}")
    return found


def _matches(module: str, prefixes: Iterable[str]) -> str | None:
    for prefix in prefixes:
        if module == prefix or module.startswith(prefix + "."):
            return prefix
    return None


def transitive_first_party_imports(path: Path, *, _seen: set[Path] | None = None) -> set[str]:
    """Every first-party module reachable from one file's imports.

    Bounded by :data:`FIRST_PARTY_PREFIXES` and by the files that actually exist
    in this repository, so the walk terminates and never leaves the tree.
    """
    seen = _seen if _seen is not None else set()
    resolved = path.resolve()
    if resolved in seen:
        return set()
    seen.add(resolved)

    reachable: set[str] = set()
    for module in module_imports(resolved):
        if _matches(module, FIRST_PARTY_PREFIXES) is None:
            continue
        reachable.add(module)
        if _matches(module, DATABASE_MODULES) or _matches(module, FORBIDDEN_MODULES):
            # Do not walk *through* the database layer. ``dispatch/db.py`` is
            # where every subsystem registers its schema initializer -- Spine's
            # included -- so following it would report the entire application as
            # transitively reachable and say nothing. Who may touch it at all is
            # already settled by the direct-import rule above. Forbidden modules
            # are likewise not walked: they are reported where they are named.
            continue
        child = _module_file(module)
        if child is not None:
            reachable |= transitive_first_party_imports(child, _seen=seen)
    return reachable


def sql_tables(path: Path) -> set[str]:
    """Table names appearing in SQL string literals in one file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tables: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
            if not _SQL_KEYWORD_PATTERN.search(text):
                continue
            for match in _SQL_TABLE_PATTERN.finditer(text):
                tables.add(match.group(1).lower())
    return tables


def verify_file(path: Path) -> list[str]:
    """Every boundary violation in one connectors-package file, as sentences."""
    violations: list[str] = []
    name = path.name

    direct = module_imports(path)
    for module in sorted(direct):
        hit = _matches(module, FORBIDDEN_MODULES)
        if hit:
            violations.append(
                f"{name} imports {module}. Section 6.2: a connector may never call Spine "
                f"transition code or reach Current Reality through {hit}."
            )
        if name not in DATABASE_ALLOWED_FILES and _matches(module, DATABASE_MODULES):
            violations.append(
                f"{name} imports {module}. Only {', '.join(sorted(DATABASE_ALLOWED_FILES))} "
                "may know a database exists; a connector transports and normalizes, it does "
                "not persist."
            )

    for module in sorted(transitive_first_party_imports(path)):
        hit = _matches(module, FORBIDDEN_MODULES)
        if hit:
            violations.append(
                f"{name} reaches {module} transitively. Routing a forbidden import through a "
                "helper module does not put it outside the boundary."
            )

    for table in sorted(sql_tables(path)):
        if table in ALLOWED_TABLES:
            continue
        where = "a Current Reality table" if table in CURRENT_REALITY_TABLES else "a table"
        violations.append(
            f"{name} contains SQL naming {table!r}, {where}. The connectors package writes "
            f"only {', '.join(sorted(ALLOWED_TABLES))}."
        )

    return violations


def package_files() -> list[Path]:
    return sorted(p for p in _PACKAGE_DIR.glob("*.py"))


def verify_package() -> dict[str, list[str]]:
    """Scan the whole package. Empty dict means the boundary holds."""
    findings: dict[str, list[str]] = {}
    for path in package_files():
        violations = verify_file(path)
        if violations:
            findings[path.name] = violations
    return findings


def assert_package_clean() -> None:
    findings = verify_package()
    if findings:
        lines = [f"  {name}: {v}" for name, items in findings.items() for v in items]
        raise BoundaryViolation(
            "The connector boundary is broken:\n" + "\n".join(lines)
        )


_verified_modules: set[str] = set()


def assert_module_clean(module_name: str) -> None:
    """Verify one connector's own module, once per process.

    Called by :func:`execute` before the connector runs. The scan is cheap and
    cached, and running it here means a connector added at runtime -- a plugin,
    a test double defined outside the package -- is held to the same rule as one
    checked in.
    """
    if module_name in _verified_modules:
        return
    if not module_name.startswith("dispatch.connectors"):
        raise BoundaryViolation(
            f"{module_name} is not part of dispatch.connectors. Connectors live inside the "
            "package the boundary scan covers; one defined elsewhere has no boundary at all."
        )
    path = _module_file(module_name)
    if path is None:  # pragma: no cover - only for a module with no file on disk
        raise BoundaryViolation(f"Cannot locate the source of {module_name} to verify it.")
    violations = verify_file(path)
    if violations:
        raise BoundaryViolation("; ".join(violations))
    _verified_modules.add(module_name)


# --------------------------------------------------------------------------- runtime seal


_SEAL: contextvars.ContextVar[str] = contextvars.ContextVar(
    "dispatch_connector_seal", default=""
)


def sealed_connector() -> str:
    """The connector id currently holding the seal in this context, or ''."""
    return _SEAL.get()


@contextmanager
def sealed(connector_id: str) -> Iterator[None]:
    """Run a block with every database connection refused for this context.

    ``sqlite3.connect`` is the single chokepoint: ``dispatch.db.get_connection``
    looks it up on the module at call time, so patching it here catches Spine,
    services, store, the token ledger and any provider SDK that opens its own
    connection, without this module needing to import any of them.
    """
    original_connect = sqlite3.connect

    def guarded_connect(*args, **kwargs):
        holder = _SEAL.get()
        if holder:
            raise BoundaryViolation(
                f"Connector {holder!r} attempted to open a database connection. Connectors "
                "transport and normalize information; they do not own lifecycle transitions, "
                "human decisions or any Current Reality table. Return a NormalizedPayload and "
                "let Spine, COMI or a human act on it."
            )
        return original_connect(*args, **kwargs)

    token = _SEAL.set(connector_id)
    sqlite3.connect = guarded_connect
    try:
        yield
    finally:
        sqlite3.connect = original_connect
        _SEAL.reset(token)


# --------------------------------------------------------------------------- execution


def execute(connector, request: ConnectorRequest, *, audit_sink=None) -> ConnectorResult:
    """Call a connector through the boundary, and audit the attempt.

    This is the only sanctioned entry point. Calling ``connector.fetch()``
    directly still works -- it must, or the connector could not be unit tested --
    but it runs unsealed and unaudited, and every consumer inside Dispatch goes
    through here.
    """
    from dispatch.connectors import audit as audit_module

    assert_module_clean(type(connector).__module__)
    identity = connector.identity()
    sink = audit_sink if audit_sink is not None else audit_module.record

    try:
        with sealed(identity.connector_id):
            result = connector.fetch(request)
    except BoundaryViolation as exc:
        sink(
            AuditRecord(
                connector_id=identity.connector_id,
                provider=identity.provider_label,
                operation=request.operation,
                status=ConnectorStatus.UNAVAILABLE,
                outcome="refused",
                reason=redact(str(exc)),
                attempts=1,
            )
        )
        raise
    except Exception as exc:  # noqa: BLE001 - a crashing provider is an operational condition
        result = ConnectorResult(
            status=ConnectorStatus.UNAVAILABLE,
            connector_id=identity.connector_id,
            connector_name=identity.connector_name,
            operation=request.operation,
            error=ConnectorError(
                "provider_error",
                f"{identity.connector_name} raised {type(exc).__name__} instead of returning a "
                "result. Treated as UNAVAILABLE.",
                retryable=True,
                detail=str(exc),
            ),
        )

    if not isinstance(result, ConnectorResult):  # pragma: no cover - defensive
        raise BoundaryViolation(
            f"{identity.connector_name} returned {type(result).__name__}, not a ConnectorResult. "
            "Every connector answers in the contract's shape."
        )

    entry = audit_module.audit_for(result, provider=identity.provider_label)
    sink(entry)
    return result.with_audit(entry)
