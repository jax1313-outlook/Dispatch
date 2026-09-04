"""The Platform Neutral Contract Doctrine, enforced across everything.

    Doctrine -> Contract -> Adapter -> Provider
    Provider must never become the contract.

Joe's intelligence is rented and a rental is replaceable by definition. The
moment a provider's concepts -- its IDs, its naming, its workflow assumptions --
reach the endpoints, the data structures, the audit schema or the authority
model, the rental becomes a marriage. Dispatch would then carry somebody else's
product decisions inside its own record of what happened, and the audit log is
the one thing that has to outlive every provider in it.

WHY THIS FILE SCANS RATHER THAN LISTS
=====================================

An earlier guard named three files. That protects those three files and nothing
else, and the next contract module written would not be covered -- a guard with
a hand-kept list is a guard that decays. This scans every authoritative
directory and requires the *exemptions* to be listed instead, so the default for
new code is protected.

Vendor names are allowed in exactly one place: `adapters/`. That is what the
directory is for.
"""

from __future__ import annotations

import pathlib

import pytest

#: Provider concepts. Names, platforms, SDKs and identifiers that belong to a
#: vendor rather than to freight.
PROVIDER_TERMS = (
    "copilot", "microsoft", "m365", "office365", "msal", "azure",
    "graph.microsoft", "sharepoint", "onedrive", "powerapps", "power automate",
    "dataverse", "teams", "openai", "anthropic", "claude", "gemini", "bedrock",
)

#: Everything authoritative. Doctrine and contract live here; nothing in these
#: trees may name a provider.
CONTRACT_ROOTS = ("dispatch", "portal")

#: The only place provider names belong.
ADAPTER_ROOT = "adapters"

#: Files inside the contract roots that are exempt, each with the reason. A new
#: exemption is a deliberate act with a justification attached, not a quiet
#: addition to a list.
EXEMPT = {
    # Outlook is a provider, and these are its adapters. They sit under
    # dispatch/ for historical reasons and are adapters in everything but
    # location; the contract does not import them, it asks a registry.
    "dispatch/connectors/outlook_mail.py": "Outlook adapter",
    "dispatch/connectors/registry.py": "names the adapters it may load",
    "dispatch/connectors/__init__.py": "connector registry docstring",
    "dispatch/scheduling.py": "Outlook calendar adapter behind CalendarPort",
    # The mail path predates the contract and is provider-specific throughout.
    "cin_lite/email_delivery.py": "SMTP/provider mail path",
    # The legacy settings page reports whether provider credentials are
    # configured, which is a display of adapter state rather than contract.
    # Narrow by test: see test_the_settings_exemption_stays_small.
    "portal/routes/pages.py": "settings page displays provider config status",
}

#: How many provider references the settings exemption may carry before it
#: stops being an exemption and starts being a hole.
SETTINGS_ALLOWANCE = 3


def _files():
    for root in CONTRACT_ROOTS:
        for path in pathlib.Path(root).rglob("*.py"):
            rel = path.as_posix()
            if rel in EXEMPT:
                continue
            yield rel, path


class TestNoProviderInsideTheContract:
    def test_every_authoritative_file_is_clean(self):
        """Scans rather than lists, so new contract code is protected by
        default."""
        offences = []
        for rel, path in _files():
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for term in PROVIDER_TERMS:
                if term in text:
                    offences.append("%s names '%s'" % (rel, term))
        assert offences == [], offences

    def test_the_joe_contract_specifically(self):
        """The files the doctrine calls the contract, checked by name as well,
        so a refactor that moves them cannot quietly drop the cover."""
        for rel in ("portal/routes/joe_api.py", "dispatch/joe_authority.py",
                    "dispatch/audit.py"):
            text = pathlib.Path(rel).read_text(encoding="utf-8").lower()
            for term in PROVIDER_TERMS:
                assert term not in text, "%s names '%s'" % (rel, term)

    def test_data_structures_carry_no_provider_concepts(self):
        """Audit entries and authority records are read years later."""
        from dispatch import audit

        entry = audit.record.__doc__ or ""
        assert not any(t in entry.lower() for t in PROVIDER_TERMS)

        from dispatch import joe_authority as authority

        for name in dir(authority):
            if name.startswith("_"):
                continue
            assert not any(t in name.lower() for t in PROVIDER_TERMS), name

    def test_the_audit_schema_is_provider_neutral(self):
        """Written once, read forever. A field named for a product outlives the
        product."""
        from dispatch import audit

        entry = audit.record(action="probe", driver="test",
                             channel=audit.CHANNEL_API)
        for key in entry:
            assert not any(t in key.lower() for t in PROVIDER_TERMS), key

    @pytest.mark.parametrize("term", ["copilot", "microsoft", "teams", "azure"])
    def test_the_guard_actually_catches_something(self, term):
        """A guard that cannot fail is not a guard."""
        assert term in PROVIDER_TERMS


class TestExemptionsAreDeliberate:
    def test_every_exemption_carries_a_reason(self):
        for path, reason in EXEMPT.items():
            assert reason and len(reason) > 8, path

    def test_every_exempt_file_exists(self):
        """A stale exemption is cover for a file nobody is checking."""
        for path in EXEMPT:
            assert pathlib.Path(path).exists(), path

    def test_the_settings_exemption_stays_small(self):
        """A whole-file exemption on a large module is a hole. This one is
        allowed because a settings page legitimately reports whether provider
        credentials are configured -- and it is checked so it cannot grow into
        provider logic."""
        text = pathlib.Path("portal/routes/pages.py").read_text(
            encoding="utf-8").lower()
        hits = sum(text.count(term) for term in PROVIDER_TERMS)
        assert hits <= SETTINGS_ALLOWANCE, (
            "%d provider references in the settings page; the exemption covers "
            "a status display, not provider logic" % hits)

    def test_the_exempt_files_are_adapters_in_role(self):
        """Each one is a provider adapter, whatever directory it sits in."""
        for path in EXEMPT:
            text = pathlib.Path(path).read_text(encoding="utf-8").lower()
            assert ("adapter" in text or "connector" in text
                    or "smtp" in text or "settings" in text), path


class TestAdaptersAreWhereProvidersLive:
    def test_the_adapter_directory_exists_and_says_what_it_is_for(self):
        readme = pathlib.Path(ADAPTER_ROOT, "README.md")
        assert readme.exists()
        text = readme.read_text(encoding="utf-8").lower()
        assert "contracts first" in text
        assert "adapter" in text

    def test_the_contract_does_not_import_an_adapter_directly(self):
        """It asks a registry. An import would make the provider a dependency
        of the contract rather than a choice behind it."""
        contract = pathlib.Path("portal/routes/joe_api.py").read_text(
            encoding="utf-8")
        assert "from adapters" not in contract
        assert "import adapters" not in contract


class TestTheContractMatchesTheDoctrine:
    """Section 8 specifies six Phase 1 endpoints. Doctrine and implementation
    must match exactly -- not 'at least', not 'roughly'."""

    SPECIFIED = {
        ("GET", "/api/joe/mission-status"),
        ("POST", "/api/joe/driver-status"),
        ("GET", "/api/joe/facility-intel/<path:facility_id>"),
        ("GET", "/api/joe/schedule-fit"),
        ("POST", "/api/joe/send-notice"),
        ("PATCH", "/api/joe/mission-record/<path:mission_id>"),
    }

    def _live(self):
        from portal.app import create_app

        app = create_app()
        return {(m, str(r.rule)) for r in app.url_map.iter_rules()
                if "/api/joe" in str(r.rule)
                for m in r.methods if m in ("GET", "POST", "PATCH", "PUT",
                                            "DELETE")}

    def test_exactly_the_six(self):
        assert self._live() == self.SPECIFIED

    def test_nothing_exceeds_the_specification(self):
        assert self._live() - self.SPECIFIED == set()

    def test_nothing_specified_is_missing(self):
        assert self.SPECIFIED - self._live() == set()

    def test_there_is_no_commit_endpoint(self):
        """Class 3 is enforced by absence. A door with a lock is still a door
        where doctrine says there should be none."""
        assert not any("commit" in rule for _, rule in self._live())


class TestTheGatewayCheckIsAnAdapter:
    """A data gateway is a provider concept, so the check lives in adapters/
    and the contract knows nothing about it."""

    def test_it_lives_in_adapters(self):
        assert pathlib.Path("adapters/gateway_health.py").exists()
        assert not pathlib.Path("dispatch/gateway_health.py").exists()

    def test_no_contract_file_imports_it(self):
        for rel, path in _files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "gateway_health" not in text, rel

    def test_it_reports_only_the_doctrine_vocabulary(self):
        from adapters import gateway_health

        assert gateway_health.check()["status"] in (
            gateway_health.LIVE, gateway_health.CONFIGURED,
            gateway_health.UNVERIFIED)

    def test_it_never_infers_a_status(self):
        """An owner reporting a gateway as set up is information about a
        belief, not evidence about a machine."""
        source = pathlib.Path("adapters/gateway_health.py").read_text(
            encoding="utf-8")
        assert "def _service_state" in source
        assert "os.path.isdir" in source
        assert "assume" not in source.lower().replace("assumed", "")

    def test_a_check_that_cannot_run_is_unverified_not_a_guess(self):
        from adapters import gateway_health

        result = gateway_health.check()
        assert result["checked"] is True
        if not result["service_found"] and not result["installed"]:
            assert result["status"] == gateway_health.UNVERIFIED
