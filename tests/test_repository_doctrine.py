"""Drift tests -- the doctrine, asserted against the repository rather than trusted.

Every rule here is written down somewhere a person can read: `CLAUDE.md`,
`docs/governance/DISPATCH_AUTHORITY_AND_BOUNDARIES.md`, `DECISION_LOG.md`. Written-down
rules erode anyway. Somebody adds a module-level import for a convenience, somebody renames
a thing back, and nine months later the doctrine is a story the repository tells about
itself rather than a description of it.

So each test below pins one clause to a checkable fact. A failure here is not a style
complaint -- it means the repository stopped being what its own documents say it is, and
**any failure blocks a readiness claim** (mission Section 18).

These tests deliberately read source text and import under constrained conditions rather
than exercising behaviour. That is unusual, and it is the point: the properties being
guarded are properties of the codebase's shape.
"""

from __future__ import annotations

import ast
import builtins
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Packages Dispatch must run without. Route Risk, Mission Visibility, SAM and Assistant
#: are plug-ins by doctrine; paramiko and anthropic are optional dependencies that the
#: Version screen is expected to report `ABSENT` without anything breaking.
OPTIONAL_PACKAGES = ("route_risk", "sync", "reconciliation", "paramiko", "anthropic")

#: The eight, and only the eight. `CLAUDE.md` section 6.
TRUTH_WORDS = (
    "LIVE",
    "CONFIGURED",
    "UNCONFIGURED",
    "SIMULATED",
    "UNAVAILABLE",
    "MANUAL",
    "ABSENT",
    "UNVERIFIED",
)


def _first_party_python_files() -> list[Path]:
    packages = (
        "dispatch",
        "portal",
        "cin_lite",
        "dispatch_launcher",
        "route_risk",
        "sync",
        "reconciliation",
        "scripts",
    )
    found: list[Path] = []
    for package in packages:
        found.extend(
            path
            for path in (REPO_ROOT / package).rglob("*.py")
            if "__pycache__" not in path.parts
        )
    return found


# ── No Manager Doctrine ──────────────────────────────────────────────────────

#: Every phrase containing "manager" that is allowed to exist, and why. Anything not on
#: this list fails the test, which is the correct default: a new `manager` in the codebase
#: should require somebody to come here and justify it in writing.
MANAGER_ALLOWED = {
    "task manager": "the Windows application, named in operator instructions",
    "fleet manager": "a human job title, used in a verified_by string",
    "context manager": "the Python language construct",
    "contextmanager": "contextlib.contextmanager, the Python decorator",
    "secrets manager": "the class of product, in a limitation note",
    "proposal manager": "a human role, in a CIN-Lite checklist item",
    "package manager": "the class of tool",
    "replace manager": "the Spine docstring asserting it does not replace one",
    "not manager": "a comment asserting a capability is explicitly not Manager",
    "routed_to_manager": (
        "a legacy Spine state string, recorded as an open conflict in "
        "docs/architecture/DISPATCH_ARCHITECTURE.md section 7.1 and awaiting Mike's "
        "decision because it is persisted in the audit trail"
    ),
    "no manager": "the doctrine asserting itself",
    "manager doctrine": "the doctrine's own name",
    "manager component": "the doctrine's own wording",
    "manager decision support note": "the object named in docs/MANAGER.md, never built",
}


def _manager_phrases(text: str) -> set[str]:
    """Every `manager` occurrence reduced to the word before it, lowercased."""
    return {
        match.group(0).lower().strip()
        for match in re.finditer(r"[A-Za-z_]*[ _]?[Mm]anager\b", text)
    }


class TestNoManagerDoctrine:
    """`There is no Manager component in the current architecture.`

    The doctrine forbids restoring Manager terminology, authority, agent behaviour, or
    routing assumptions -- so the test is about the *shape* of what exists, not a word ban.
    A component would show up as a module, a class, or a database table.
    """

    def test_no_manager_module_exists(self):
        offenders = [
            path.relative_to(REPO_ROOT)
            for path in _first_party_python_files()
            if "manager" in path.stem.lower()
        ]
        assert offenders == [], (
            f"A Manager module was introduced: {offenders}. There is no Manager component "
            "in the current architecture -- see DECISION_LOG.md 2026-08-25."
        )

    def test_no_manager_class_or_function_is_defined(self):
        offenders: list[str] = []
        for path in _first_party_python_files():
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:  # pragma: no cover - would fail the whole suite anyway
                continue
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                ) and "manager" in node.name.lower():
                    offenders.append(f"{path.relative_to(REPO_ROOT)}::{node.name}")
        assert offenders == [], (
            f"Manager behaviour was defined in code: {offenders}. The doctrine forbids "
            "restoring Manager authority, agent behaviour or routing assumptions."
        )

    def test_no_manager_database_table(self):
        for db_module in ("dispatch/db.py", "dispatch/spine/db.py"):
            source = (REPO_ROOT / db_module).read_text(encoding="utf-8")
            tables = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", source)
            offenders = [name for name in tables if "manager" in name.lower()]
            assert offenders == [], (
                f"{db_module} creates a Manager-owned table: {offenders}. Manager owns no "
                "data; docs/MANAGER.md authorizes no data model."
            )

    def test_every_manager_mention_in_code_is_one_of_the_known_benign_ones(self):
        """The catch-all. A new spelling has to be justified here first."""
        unexplained: dict[str, list[str]] = {}
        for path in _first_party_python_files():
            text = path.read_text(encoding="utf-8")
            for phrase in _manager_phrases(text):
                if phrase in ("manager", "managers"):
                    # A bare word with nothing before it -- look at the line to judge.
                    continue
                if phrase in MANAGER_ALLOWED:
                    continue
                unexplained.setdefault(phrase, []).append(
                    str(path.relative_to(REPO_ROOT))
                )
        assert unexplained == {}, (
            "New Manager terminology appeared: "
            f"{unexplained}. If it is benign, add it to MANAGER_ALLOWED with the reason. "
            "If it is a component, the No Manager Doctrine forbids it."
        )

    def test_the_one_recorded_conflict_is_still_recorded(self):
        """`ROUTED_TO_MANAGER` may stay -- but only while the conflict stays written down.

        This is the shape of an honest exception: the code keeps the string, and the
        architecture document keeps the explanation, the three options and the
        recommendation. If somebody deletes the record, the exception stops being honest
        and this test says so.
        """
        states = (REPO_ROOT / "dispatch/spine/models.py").read_text(encoding="utf-8")
        architecture = (
            REPO_ROOT / "docs/architecture/DISPATCH_ARCHITECTURE.md"
        ).read_text(encoding="utf-8")
        if "ROUTED_TO_MANAGER" in states:
            assert "ROUTED_TO_MANAGER" in architecture, (
                "dispatch/spine/models.py still carries ROUTED_TO_MANAGER but "
                "docs/architecture/DISPATCH_ARCHITECTURE.md no longer records the conflict. "
                "Either resolve it with Mike's ruling, or keep the record."
            )
            assert "7.1" in architecture


# ── Plug-In Separation Doctrine ──────────────────────────────────────────────


def _run_without(packages: tuple[str, ...], snippet: str) -> subprocess.CompletedProcess:
    """Run `snippet` in a fresh interpreter where importing `packages` raises.

    A subprocess rather than monkeypatching `builtins.__import__` in-process, because the
    modules under test are already imported by the time this file runs -- `sys.modules`
    would serve them from cache and the test would prove nothing.
    """
    program = (
        "import builtins\n"
        f"BLOCKED = {set(packages)!r}\n"
        "_real = builtins.__import__\n"
        "def _guard(name, *a, **k):\n"
        "    if name.split('.')[0] in BLOCKED:\n"
        "        raise ImportError('plug-in blocked by the drift test: ' + name)\n"
        "    return _real(name, *a, **k)\n"
        "builtins.__import__ = _guard\n"
        "import os\n"
        "os.environ.setdefault('PORTAL_SECRET_KEY', 'x' * 48)\n"
        "os.environ.setdefault('DISPATCH_EMAIL_SECRET', 'y' * 48)\n"
        + snippet
    )
    return subprocess.run(
        [sys.executable, "-c", program],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )


class TestPlugInSeparationDoctrine:
    """`Dispatch must not require their presence for core operation.`

    And the standing rule it serves: **degradation is permitted, incapacity is not.**
    """

    def test_dispatch_imports_with_every_plug_in_absent(self):
        result = _run_without(OPTIONAL_PACKAGES, "import dispatch\nprint('OK')\n")
        assert result.returncode == 0, (
            "`import dispatch` failed with the optional plug-ins absent.\n"
            f"{result.stderr}"
        )

    def test_the_portal_starts_and_serves_with_every_plug_in_absent(self):
        """The one that matters. This test exists because it used to fail.

        `portal/routes/driver_portal.py` imported `dispatch.route_risk` at module scope,
        which imported the standalone `route_risk` engine at module scope. With the engine
        uninstalled, blueprint registration raised and `create_app()` never returned -- so
        an absent *optional risk advisor* took down every driver surface, every load and
        every milestone. That is the incapacity the doctrine forbids.
        """
        result = _run_without(
            OPTIONAL_PACKAGES,
            "from portal.app import create_app\n"
            "app = create_app()\n"
            "response = app.test_client().get('/login')\n"
            "assert response.status_code == 200, response.status_code\n"
            "print('OK')\n",
        )
        assert result.returncode == 0, (
            "The portal could not start with the optional plug-ins absent. Dispatch must "
            "remain complete and operational without optional plug-ins "
            "(General Contractor Doctrine, DECISION_LOG.md 2026-08-25).\n"
            f"{result.stderr}"
        )

    def test_route_risk_degrades_to_a_truth_word_rather_than_crashing(self):
        result = _run_without(
            ("route_risk",),
            "from dispatch import route_risk as m\n"
            "assert m.engine_status() == 'ABSENT', m.engine_status()\n"
            "reading = m.get_route_risk('L-1')\n"
            "assert reading['available'] is False\n"
            "assert reading['engine_status'] == 'ABSENT'\n"
            "assert 'ABSENT' in reading['summary']\n"
            "print('OK')\n",
        )
        assert result.returncode == 0, result.stderr

    def test_a_route_risk_write_refuses_loudly_rather_than_degrading(self):
        """Reads degrade. Writes do not.

        Silently discarding a hazard somebody recorded would leave the operator believing
        a condition was logged when nothing was -- the same failure shape as the milestone
        gate that swallowed refused transitions.
        """
        result = _run_without(
            ("route_risk",),
            "from dispatch import route_risk as m\n"
            "try:\n"
            "    m.record_route_risk_event(load_id='L-1')\n"
            "except m.RouteRiskUnavailable as exc:\n"
            "    assert 'NOT' in str(exc)\n"
            "    print('OK')\n"
            "else:\n"
            "    raise AssertionError('a write silently succeeded with no engine')\n",
        )
        assert result.returncode == 0, result.stderr

    def test_engine_status_is_a_truth_word(self):
        from dispatch import route_risk

        assert route_risk.engine_status() in TRUTH_WORDS

    # The subprocess tests above prove the real import path degrades. These exercise the
    # same branches in-process so they are covered and measured rather than only observed
    # through a subprocess exit code -- a subprocess that returns 0 tells you a program ran,
    # not which lines it took.

    def test_the_absent_reading_names_the_absence_without_implying_a_clear_route(
        self, monkeypatch
    ):
        from dispatch import route_risk

        monkeypatch.setattr(route_risk, "rr", None)
        monkeypatch.setattr(route_risk, "ENGINE_STATUS", "ABSENT")

        reading = route_risk.get_route_risk("LOAD-1")
        assert reading["available"] is False
        assert reading["engine_status"] == "ABSENT"
        assert reading["is_live_data"] is False
        assert reading["latest_event"] is None
        # The distinction the summary has to carry: "nothing was assessed" is not the
        # same claim as "the route is clear", and a Level 0 with no explanation reads
        # like the second.
        assert "This is not a statement that the route is clear." in reading["summary"]
        assert route_risk.engine_status() == "ABSENT"
        # Same keys as the engine's own no-events reading, so no caller learns a second
        # shape.
        assert set(reading) >= {
            "load_id",
            "available",
            "risk_level",
            "consequence_level",
            "summary",
            "estimated_delay_minutes",
            "delivery_commitment_status",
            "source_label",
            "map_visual_placeholder",
            "checked_at",
            "is_live_data",
            "latest_event",
        }

    def test_recorded_events_stay_retrievable_with_the_engine_uninstalled(
        self, monkeypatch
    ):
        """Losing sight of a hazard somebody logged is not an acceptable degradation.

        The events live in Dispatch's own `route_risk_events` table; the engine
        contributes no logic to reading them.
        """
        from dispatch import route_risk

        seen: list[str | None] = []

        def _fake_load(load_id):
            seen.append(load_id)
            return [{"route_risk_event_id": "RRE-1"}]

        monkeypatch.setattr(route_risk, "rr", None)
        monkeypatch.setattr(route_risk, "_load_events", _fake_load)

        assert route_risk.list_route_risk_events("LOAD-1") == [
            {"route_risk_event_id": "RRE-1"}
        ]
        assert seen == ["LOAD-1"]

    def test_a_write_with_no_engine_raises_and_says_nothing_was_saved(self, monkeypatch):
        from dispatch import route_risk

        monkeypatch.setattr(route_risk, "rr", None)

        with pytest.raises(route_risk.RouteRiskUnavailable) as caught:
            route_risk.record_route_risk_event(load_id="LOAD-1")

        message = str(caught.value)
        assert "NOT recorded" in message
        assert "Nothing has been saved" in message

    def test_assistant_has_no_module_and_therefore_no_write_authority(self):
        """`No direct Dispatch write authority may be granted to Assistant.`

        Assistant is not integrated. The cheapest guarantee that it holds no write
        authority is that it holds no code here at all.
        """
        offenders = [
            path.relative_to(REPO_ROOT)
            for path in _first_party_python_files()
            if "assistant" in path.stem.lower()
        ]
        assert offenders == [], (
            f"An Assistant module appeared: {offenders}. Assistant is a separately bounded "
            "plug-in and may not be embedded into Dispatch."
        )


# ── Outlook remains the scheduling authority ─────────────────────────────────


class TestSchedulingAuthority:
    """`Dispatch must not create a separate competing scheduling system.`"""

    def test_no_calendar_table_exists_anywhere_in_the_schema(self):
        """The Driver Portal Calendar presents Outlook data. It is not a database.

        A `calendar_events` table would be exactly the second scheduling truth the mission
        forbids -- and it would be invisible from the interface, because a calendar backed
        by its own table looks identical to one that is a window.
        """
        for db_module in ("dispatch/db.py", "dispatch/spine/db.py"):
            source = (REPO_ROOT / db_module).read_text(encoding="utf-8")
            tables = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", source)
            offenders = [
                name
                for name in tables
                if "calendar" in name.lower() or "schedule_event" in name.lower()
            ]
            assert offenders == [], (
                f"{db_module} creates an independent calendar store: {offenders}. Outlook "
                "is the scheduling authority; the Driver Portal Calendar is a presentation "
                "layer over it."
            )

    def test_the_outlook_connector_still_refuses_to_create_an_event(self):
        source = (REPO_ROOT / "dispatch/connectors/outlook_connector.py").read_text(
            encoding="utf-8"
        )
        assert "no event was created" in source, (
            "The Outlook connector no longer states that it creates no event. Dispatch may "
            "read, present and request schedule information; it may not become a second "
            "scheduling truth."
        )


# ── Authority ────────────────────────────────────────────────────────────────

MIKE_ATTRIBUTIONS = (
    "Verified by Mike Zachary",
    "Approved by Mike Zachary",
    "Accepted by Mike Zachary",
    "Authorized by Mike Zachary",
    "Confirmed by Mike Zachary",
)


def _attribution_hits(paths):
    """Every (path, line number, line) carrying one of the five forbidden phrases."""
    for path in paths:
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if any(phrase in line for phrase in MIKE_ATTRIBUTIONS):
                yield path, number, line


class TestAuthority:
    """`Mike Zachary remains final authority.`"""

    def test_no_shipped_code_manufactures_a_mike_attribution(self):
        """Not as a default, a seed, a fixture, or an inference.

        `_attribution_hits` is deliberately dumb -- it reports every line carrying one of
        the five phrases, and the exceptions are named individually below rather than
        inferred. An inferred exception ("skip it if the surrounding text looks like a
        prohibition") is a rule that quietly widens: the next author writes something that
        happens to match and their line is skipped too, which is the exact failure this
        test exists to catch.

        Test files are excluded from the sweep: `tests/test_rehearsal_and_proof.py` holds
        these strings on purpose, to assert that Dispatch refuses to write them.
        """
        allowed = {
            # The connector's docstring, stating that it will not do this. The doctrine
            # asserting itself in the code is where it belongs.
            "dispatch/connectors/outlook_connector.py": 'manufacturing "Approved by',
        }
        offenders: list[str] = []
        for path, number, line in _attribution_hits(_first_party_python_files()):
            relative = str(path.relative_to(REPO_ROOT))
            excerpt = allowed.get(relative)
            if excerpt is not None and excerpt in line:
                continue
            offenders.append(f"{relative}:{number}: {line.strip()[:90]}")
        assert offenders == [], (
            "Shipped code manufactures a Mike Zachary attribution:\n"
            + "\n".join(offenders)
            + "\nNo record may carry one unless Mike personally performed an authenticated "
            "action that produced it."
        )

    def test_the_attribution_detector_actually_detects(self, tmp_path):
        """Proves the test above is not vacuous.

        A sweep that finds nothing is indistinguishable from a sweep that looks nowhere.
        This feeds the detector a file that violates the rule and requires it to say so.
        """
        planted = tmp_path / "planted.py"
        planted.write_text(
            'APPROVAL_DEFAULT = "Approved by Mike Zachary"\n', encoding="utf-8"
        )
        hits = list(_attribution_hits([planted]))
        assert len(hits) == 1
        assert hits[0][1] == 1
        assert "Approved by Mike Zachary" in hits[0][2]

    def test_the_recommendation_closing_string_is_intact(self):
        from dispatch.spine import models

        assert models.REQUIRED_CLOSING == (
            "This is a recommendation only. No action is authorized. Mike decides."
        )


# ── Truth vocabulary ─────────────────────────────────────────────────────────


class TestTruthVocabulary:
    """Eight words, no synonyms. The convention only works if nothing drifts past it."""

    def test_the_readiness_module_uses_exactly_the_eight(self):
        from dispatch import readiness

        assert tuple(readiness.TRUTH_WORDS) == TRUTH_WORDS

    def test_the_connector_status_enum_uses_exactly_the_eight(self):
        from dispatch.connectors.contract import ConnectorStatus

        assert {status.value for status in ConnectorStatus} == set(TRUTH_WORDS)

    def test_the_cold_start_brief_documents_exactly_the_eight(self):
        """A builder reads `CLAUDE.md`, not the enum. The two must agree."""
        brief = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        table = brief[brief.index("## 6."): brief.index("### IMPLEMENTED is not")]
        for word in TRUTH_WORDS:
            assert f"`{word}`" in table, f"CLAUDE.md section 6 no longer documents {word}"

    def test_no_simulated_capability_is_labelled_live(self):
        """The mock reports SIMULATED. Nothing unconfigured reports LIVE."""
        from dispatch.connectors import mock
        from dispatch.connectors.contract import ConnectorStatus

        source = Path(mock.__file__).read_text(encoding="utf-8")
        assert "SIMULATED" in source
        assert "ConnectorStatus.LIVE" not in source, (
            "The mock connector reports LIVE. A simulated capability labelled live is the "
            "single most dangerous status this repository can print."
        )
        assert ConnectorStatus.SIMULATED.value == "SIMULATED"


# ── Repository Doctrine and the cold-start handoff ───────────────────────────

#: Documents a cold-start builder needs, and the marker proving each is the real thing
#: rather than a placeholder somebody added to make this test pass.
REQUIRED_DOCUMENTS = {
    "CLAUDE.md": "cold-start brief",
    "README.md": "Dispatch",
    "DECISION_LOG.md": "No Manager Doctrine",
    "DISPATCH_FIRST_START_GUIDE.md": "dispatch.bat",
    "DISPATCH_PURPOSE_STATEMENT.md": "See Reality",
    "DRIVER_FIRST_DOCTRINE_v2.md": "70 MPH Test",
    "docs/architecture/DISPATCH_ARCHITECTURE.md": "document map",
    "docs/governance/DISPATCH_AUTHORITY_AND_BOUNDARIES.md": "final authority",
    "docs/operations/DISPATCH_OPERATOR_GUIDE.md": "Reset Session",
    "docs/maintenance/DISPATCH_MAINTENANCE_GUIDE.md": "restore-verification.json",
    "docs/operations/GET_DISPATCH_ONTO_YOUR_LAPTOP.md": "Add Python to PATH",
    "docs/readiness/LAUNCH_PATH.md": "DISPATCH_START_HERE",
    "docs/readiness/OPERATIONAL_PROOF.md": "OPERATIONALLY PROVEN",
    "docs/readiness/KNOWN_LIMITATIONS.md": "next operational blocker",
    "docs/readiness/CONTROL_CENTER.md": "Reset Session",
    "docs/readiness/COMPLETION_REPORT.md": "Readiness statement",
    "docs/connectors/PROVIDER_INSERTION.md": "connector",
}


class TestRepositoryCanBriefAColdStartBuilder:
    """`The repository is the durable source of ... context.`

    Mission Section 18: *the repository can brief a future authorized builder cold.* The
    handoff between a website session and a desktop session is the pushed repository and
    nothing else -- conversation context does not survive. If one of these documents goes
    missing, the next builder reconstructs doctrine by guessing.
    """

    @pytest.mark.parametrize(
        ("relative_path", "marker"), sorted(REQUIRED_DOCUMENTS.items())
    )
    def test_the_document_exists_and_says_what_it_is_for(self, relative_path, marker):
        path = REPO_ROOT / relative_path
        assert path.is_file(), (
            f"{relative_path} is missing. A cold-start builder needs it; the Repository "
            "Handoff Rule says the repository is the whole handoff."
        )
        text = path.read_text(encoding="utf-8")
        assert len(text) > 1000, f"{relative_path} is a stub, not a briefing."
        assert marker.lower() in text.lower(), (
            f"{relative_path} no longer covers what it exists to cover "
            f"(looked for {marker!r})."
        )

    def test_the_cold_start_brief_carries_every_load_bearing_rule(self):
        brief = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        for clause in (
            "General Contractor",
            "System of Record",
            "70 MPH Test",
            "final authority",
            "no Manager component",
            "Degradation is permitted",
            "OPERATIONALLY PROVEN",
            "Outlook",
        ):
            assert clause in brief, (
                f"CLAUDE.md no longer states {clause!r}. It is the first file a cold-start "
                "builder reads; a rule missing from it is a rule that will be broken."
            )


# ── The visible interface ────────────────────────────────────────────────────


class TestTheProgramIsCalledDispatch:
    """Section 10 item 3: *a visible and usable Dispatch interface.*

    The portal called itself "L2-COS Operations Portal" in its own chrome long after the
    program was named Dispatch -- recorded as gap 10 in the readiness completion report and
    fixed on 2026-08-25. Two names for one program is how an operator stops trusting what
    a screen tells them.
    """

    def test_no_portal_source_carries_the_superseded_program_name(self):
        offenders: list[str] = []
        for path in list((REPO_ROOT / "portal").rglob("*.py")) + list(
            (REPO_ROOT / "portal").rglob("*.html")
        ):
            if "__pycache__" in path.parts:
                continue
            if "L2-COS" in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(REPO_ROOT)))
        assert offenders == [], (
            f"The superseded program name came back in: {offenders}. The program is "
            "Dispatch and its own chrome must say so."
        )

    def test_the_chrome_says_dispatch(self):
        base = (REPO_ROOT / "portal/templates/base.html").read_text(encoding="utf-8")
        assert "<h2>Dispatch</h2>" in base
        assert "{% block title %}Dispatch{% endblock %}" in base
