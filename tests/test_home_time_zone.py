"""The business day belongs to the home terminal.

**Owner ruling, 2026-09-08:** *"All IFTA and HOS logs are based on the declared
HOME location and never altered to accommodate the crossing of time zones. My
HOME location is Eastern Time Zone."*

Dispatch stamped every date from UTC, so between 8pm and midnight Eastern it
disagreed with the business about what day it was. These tests are written
against the hour that breaks it rather than against noon, because noon proves
nothing: UTC and Eastern agree at noon, which is why this survived so long.
"""

from __future__ import annotations

import os
import pathlib
import re
from datetime import date, datetime, timezone

import pytest

from dispatch import clock, store
from dispatch.models import ComplianceDocument, IFTATripLeg

#: 9pm Eastern on 31 March 2026 -- the last hour of the first quarter, and one
#: hour into 1 April in UTC. Mike's case, exactly.
LAST_HOUR_OF_Q1 = datetime(2026, 4, 1, 1, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def default_home(monkeypatch):
    """Every test here runs against the declared home unless it says otherwise.

    A machine with `DISPATCH_HOME_TIMEZONE` already set would otherwise make
    these pass or fail for reasons that have nothing to do with the code -- the
    same fault that kept three tests red in CI for three days.
    """
    monkeypatch.delenv(clock.HOME_ZONE_VAR, raising=False)


class TestTheDayBelongsToTheHomeTerminal:
    def test_nine_pm_eastern_on_the_thirty_first_is_still_the_thirty_first(self):
        """The whole ruling in one assertion."""
        assert LAST_HOUR_OF_Q1.astimezone(clock.home_zone()).date() == date(2026, 3, 31)

    def test_and_utc_would_have_called_it_april(self):
        """The defect, kept as a test so nobody has to take the story on trust.
        Both lines describe the same instant."""
        assert LAST_HOUR_OF_Q1.date() == date(2026, 4, 1)

    def test_a_leg_driven_in_that_hour_files_into_the_first_quarter(self):
        """**The consequence that costs money.** An IFTA return filed a quarter
        late for one leg is a return that was wrong twice."""
        assert clock.home_quarter("2026-03-31") == (2026, 1)
        assert clock.home_quarter("2026-04-01") == (2026, 2)

    def test_the_default_home_is_the_one_mike_declared(self):
        assert clock.home_zone_name() == "America/New_York"

    def test_a_declared_home_overrides_the_default(self, monkeypatch):
        """Because Level 1 Transport is not the only shape this program takes,
        and because the setup screen will write here."""
        monkeypatch.setenv(clock.HOME_ZONE_VAR, "America/Denver")
        assert clock.home_zone_name() == "America/Denver"
        assert LAST_HOUR_OF_Q1.astimezone(clock.home_zone()).date() == date(2026, 3, 31)


class TestTimestampsDidNotMove:
    """The line the whole design rests on: **a timestamp orders events, a date
    says what day it was.** Moving timestamps off UTC would reorder an audit
    trail twice a year, which is a far worse defect than the one being fixed."""

    def test_created_at_is_still_utc(self):
        leg = IFTATripLeg(jurisdiction="FL", miles=100)
        assert leg.created_at.endswith("Z")
        assert leg.created_at[:10] == datetime.now(timezone.utc).date().isoformat()

    def test_the_date_is_the_home_date(self, monkeypatch):
        monkeypatch.setattr(clock, "home_today", lambda: "2026-03-31")
        assert IFTATripLeg(jurisdiction="FL", miles=100).date == "2026-03-31"

    def test_a_supplied_date_is_never_overwritten(self):
        assert IFTATripLeg(jurisdiction="FL", miles=100,
                           date="2025-01-15").date == "2025-01-15"


class TestEverythingThatAsksWhatDayItIs:
    """Twelve call sites, one rule. These are the ones a person would notice."""

    def test_a_document_expiring_today_is_not_expired_yet(self, monkeypatch):
        """It read expired from 8pm the night before. A driver checking his own
        CDL at 9pm would have been told it had already lapsed."""
        monkeypatch.setattr(clock, "home_today", lambda: "2026-03-31")
        doc = ComplianceDocument(entity_type="driver", entity_id="D-1",
                                 doc_type="cdl", expiry_date="2026-03-31")
        assert doc.is_expired is False

    def test_a_document_that_expired_yesterday_is_expired(self, monkeypatch):
        monkeypatch.setattr(clock, "home_today", lambda: "2026-03-31")
        doc = ComplianceDocument(entity_type="driver", entity_id="D-1",
                                 doc_type="cdl", expiry_date="2026-03-30")
        assert doc.is_expired is True

    def test_days_until_expiry_counts_from_the_home_day(self, monkeypatch):
        monkeypatch.setattr(clock, "home_today", lambda: "2026-03-31")
        doc = ComplianceDocument(entity_type="driver", entity_id="D-1",
                                 doc_type="cdl", expiry_date="2026-04-10")
        assert doc.days_until_expiry == 10


class TestABrokenZoneDegradesAndSaysSo:
    """*Degradation is permitted. Incapacity is not.* A bad zone name must not
    stop Dispatch starting -- and must not pass unremarked either, because a
    date that is silently four hours wrong is the defect being fixed."""

    def test_an_unknown_zone_falls_back_to_utc(self, monkeypatch):
        monkeypatch.setenv(clock.HOME_ZONE_VAR, "Mars/Olympus_Mons")
        assert clock.home_zone() is timezone.utc
        assert clock.home_today()  # it still answers

    def test_and_names_the_problem_rather_than_hiding_it(self, monkeypatch):
        monkeypatch.setenv(clock.HOME_ZONE_VAR, "Mars/Olympus_Mons")
        problem = clock.zone_problem()
        assert "Mars/Olympus_Mons" in problem
        assert "UTC" in problem

    def test_a_good_zone_reports_no_problem(self):
        assert clock.zone_problem() == ""


class TestItCannotComeBack:
    def test_no_calendar_date_is_derived_from_utc_anywhere(self):
        """**The guard.** `_utc_now()[:10]` is how this defect was written twelve
        times, and a rule that lives only in a commit message is a rule that gets
        rewritten by the next person in a hurry.

        `clock.py` may name it, in the docstring that explains why it is gone.
        """
        root = pathlib.Path(__file__).resolve().parent.parent
        offenders = []
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts or path.name == "clock.py":
                continue
            if path.resolve() == pathlib.Path(__file__).resolve():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for number, line in enumerate(text.splitlines(), 1):
                if re.search(r"_utc_now\(\)\s*\[\s*:\s*10\s*\]", line):
                    offenders.append("%s:%d" % (path.relative_to(root), number))
        assert not offenders, (
            "a calendar date derived from UTC -- use clock.home_today(): "
            + ", ".join(offenders))
