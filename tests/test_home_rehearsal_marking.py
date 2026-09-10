"""The Home screen must mark rehearsal records rather than hide or ignore them.

**Mike's ruling, 2026-09-06:** *"show both with rehearsal records marked."*

The defect these guard against is specific and was real. On 2026-09-06 the two
test loads on Mike's machine were tagged correctly in the database and the Home
screen counted them exactly as before — `rehearsal_session` reached the template
and nothing rendered it. The data said *this is rehearsal* and the screen showed
`$1,775 revenue, 100.0% margin` with no qualification.

**A row can carry a badge. A total cannot.** So there are two kinds of test here:
one that a marked row renders, and one that a mixed aggregate says so in words.
"""

from __future__ import annotations

import pytest

from dispatch import rehearsal, services
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _tagged_load(customer="Acme", label="test session"):
    """A load tagged to a real session, the way the retroactive tag did it."""
    load = services.create_load(customer=customer)
    session = rehearsal.start_session(label=label, actor_id="tester")
    rehearsal.tag("loads", load["load_id"], session_id=session["session_id"])
    return load, session["session_id"]


class TestTheShareIsCountedHonestly:
    def test_no_loads_is_not_a_rehearsal_claim(self):
        share = services.rehearsal_share()
        assert share["any"] is False
        assert share["all"] is False, "an empty board must not report itself as all rehearsal"

    def test_an_untagged_load_is_operational(self):
        services.create_load(customer="Acme")
        share = services.rehearsal_share()
        assert share == {"total": 1, "rehearsal": 0, "operational": 1,
                         "sessions": [], "any": False, "all": False}

    def test_a_tagged_load_is_counted_and_its_session_named(self):
        _, sid = _tagged_load()
        share = services.rehearsal_share()
        assert share["rehearsal"] == 1 and share["operational"] == 0
        assert share["all"] is True
        assert share["sessions"] == [sid]

    def test_a_mixed_board_is_neither_all_nor_none(self):
        _tagged_load(customer="Rehearsal Co")
        services.create_load(customer="Real Co")
        share = services.rehearsal_share()
        assert share["total"] == 2
        assert share["rehearsal"] == 1 and share["operational"] == 1
        assert share["any"] is True
        assert share["all"] is False

    def test_counting_never_removes_a_load(self):
        """`rehearsal_share` reports. It does not filter -- Mike asked to see
        both, and a helper that quietly dropped rows would be the option he
        did not choose."""
        _tagged_load()
        services.create_load(customer="Real Co")
        assert len(services.list_loads()) == 2


class TestTheScreenSaysSo:
    def test_a_clean_board_carries_no_rehearsal_banner(self, client):
        services.create_load(customer="Real Co")
        body = client.get("/home").get_data(as_text=True)
        assert "rehearsal-data-note" not in body

    def test_an_all_rehearsal_board_says_every_load(self, client):
        _tagged_load()
        body = client.get("/home").get_data(as_text=True)
        assert "rehearsal-data-note" in body
        assert "Every load on this screen is rehearsal data" in body

    def test_a_mixed_board_gives_the_count(self, client):
        _tagged_load(customer="Rehearsal Co")
        services.create_load(customer="Real Co")
        body = client.get("/home").get_data(as_text=True)
        assert "1 of 2 loads are rehearsal data" in body

    def test_the_counts_are_labelled_when_they_include_rehearsal(self, client):
        """**The one that matters.**

        A number cannot wear a badge. The Financial Snapshot this used to check
        came off Home on 2026-09-09, but the reasoning is unchanged and now
        applies to the counts that remain: if Screened Loads and Active Loads are
        computed over rehearsal records they must say so, or they state test
        figures with the same confidence they would state real ones.
        """
        load, _ = _tagged_load()
        services.confirm_rate(load["load_id"], rate_amount=1000.0)
        body = client.get("/home").get_data(as_text=True)
        assert "REHEARSAL" in body
        assert "rehearsal data" in body

    def test_the_counts_are_not_labelled_when_the_data_is_real(self, client):
        load = services.create_load(customer="Real Co")
        services.confirm_rate(load["load_id"], rate_amount=1000.0)
        body = client.get("/home").get_data(as_text=True)
        assert "rehearsal-data-note" not in body
        assert "rehearsal data" not in body

    def test_nothing_is_hidden(self, client):
        """Mike chose *show both*, not *show only real*.

        Home does not list every load, so this asserts on the count that does
        include it: a tagged load is still an Active Load. The marking must
        change how a record is *labelled*, never whether it is *counted*.
        """
        _tagged_load(customer="Zebra Freight")
        body = client.get("/home").get_data(as_text=True)
        assert "Active Loads" in body
        assert services.rehearsal_share()["total"] == 1
        # Marked, and still counted -- both halves of the ruling.
        assert "rehearsal-data-note" in body


class TestTheSettingsScreenCatchesABadSessionId:
    """`active_session_id()` reads the environment variable and does not
    validate it -- it is called on every write and must stay silent and fast.

    So a typo, or a plausible-looking value like `yes`, would tag every record
    created afterwards with a string that leads nowhere. `rehearsal.py` states
    why that is worse than no tag: *"an orphan tag is worse than no tag, because
    purge cannot find it and the banner cannot explain it."*

    The check lives on the settings screen because that is where Mike looks
    before starting, and a warning he reads once beats a refusal that stops a
    start he meant to make.
    """

    def test_silence_when_the_variable_is_not_set(self, monkeypatch):
        from dispatch_launcher import settings

        monkeypatch.delenv("DISPATCH_REHEARSAL_SESSION", raising=False)
        assert settings.rehearsal_warning() == ""

    def test_silence_when_it_names_a_real_open_session(self, monkeypatch):
        from dispatch import rehearsal
        from dispatch_launcher import settings

        session = rehearsal.start_session(label="live one", actor_id="tester")
        monkeypatch.setenv("DISPATCH_REHEARSAL_SESSION", session["session_id"])
        assert settings.rehearsal_warning() == ""

    def test_a_value_that_names_nothing_is_caught(self, monkeypatch):
        from dispatch_launcher import settings

        monkeypatch.setenv("DISPATCH_REHEARSAL_SESSION", "yes")
        warning = settings.rehearsal_warning()
        assert "no rehearsal session by that name exists" in warning
        # It must say what to type, not merely that something is wrong.
        assert "set DISPATCH_REHEARSAL_SESSION=" in warning

    def test_a_closed_session_is_caught(self, monkeypatch):
        """Adding records to a rehearsal that was already closed out puts them
        in a session whose result has been recorded."""
        from dispatch import rehearsal
        from dispatch_launcher import settings

        session = rehearsal.start_session(label="finished", actor_id="tester")
        rehearsal.close_session(session["session_id"], result="PASSED", actor_id="tester")
        monkeypatch.setenv("DISPATCH_REHEARSAL_SESSION", session["session_id"])
        warning = settings.rehearsal_warning()
        assert "PASSED, not OPEN" in warning

    def test_the_warning_never_breaks_the_screen(self, monkeypatch):
        """A status screen that crashes is worse than one that says nothing.
        The check swallows its own failures on purpose."""
        from dispatch_launcher import settings

        monkeypatch.setenv("DISPATCH_REHEARSAL_SESSION", "REH-anything")
        monkeypatch.setattr("dispatch.rehearsal.get_session",
                            lambda _sid: (_ for _ in ()).throw(RuntimeError("db gone")))
        assert settings.rehearsal_warning() == ""


class TestTheSettingsScreenPrintsTheRightCommand:
    """The screen told Mike to use `setx` for every setting, including this one.

    He pasted the output on 2026-09-06 and the contradiction was visible: the
    walkthrough said *set, never setx*, and the product said `setx` beside the
    variable. The product was wrong, and it was wrong in the direction that
    costs the most -- `setx DISPATCH_REHEARSAL_SESSION` puts every future start
    in rehearsal mode, so PILOT-01's one real load would be recorded as a test.
    """

    def _row(self, name):
        from dispatch_launcher import settings

        view = settings.collect_settings()
        return next(r for r in view.rows if r.name == name)

    def test_rehearsal_gives_both_shells_and_never_setx(self):
        r"""Mike ran the session command at a `PS D:\Dispatch>` prompt on
        2026-09-06 and the walkthrough had handed him cmd syntax. In PowerShell
        `set` is an alias for Set-Variable: it sets nothing Dispatch can read,
        reports no error, and the records come out untagged looking fine."""
        command = self._row("DISPATCH_REHEARSAL_SESSION").change_command()
        assert '$env:DISPATCH_REHEARSAL_SESSION = "<value>"' in command
        assert "set DISPATCH_REHEARSAL_SESSION=<value>" in command
        assert not command.startswith("setx")
        assert "Never setx" in command

    def test_every_other_setting_still_uses_setx(self):
        """Everything else describes the machine and belongs on it permanently."""
        for name in ("DISPATCH_BACKUP_DIR", "PORTAL_PORT", "DISPATCH_MODE"):
            assert self._row(name).change_command().startswith(f'setx {name} ')

    def test_the_footer_warns_about_the_shell(self):
        """A quiet failure needs saying out loud; a loud one does not."""
        from dispatch_launcher import settings

        rendered = settings.render_settings(settings.collect_settings())
        assert "differs by shell" in rendered
        assert "sets nothing" in rendered

    def test_the_footer_names_the_exception(self):
        """A footer that says 'setx' with no exception contradicts the row above
        it, and the reader believes whichever they read second."""
        from dispatch_launcher import settings

        rendered = settings.render_settings(settings.collect_settings())
        assert "DISPATCH_REHEARSAL_SESSION is never made permanent" in rendered

    def test_the_reason_is_given_not_just_the_rule(self):
        from dispatch_launcher import settings

        rendered = settings.render_settings(settings.collect_settings())
        assert "tag your first real load as a test" in rendered
