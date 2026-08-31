"""The driver screen holds driver functions, and nothing else.

Two changes the operator asked for, pinned:

  * SWEEP is not a mode. Sweeping is an operations function -- deciding what
    work to look for -- and it does not belong on a screen read at 70mph with
    a trailer behind you. Manual activation is kept; it moved.

  * JOE has no screen. It is a three-line dock at the bottom: two lines in,
    one line out. Asking a question is something done *while* looking at the
    load, not instead of looking at it.
"""

from __future__ import annotations

import re

import pytest

from portal.app import create_app

# `/portal` redirects to the mission being worked when one exists, and renders
# directly when none does. Follow redirects, or these assert on the data rather
# than on the screen.


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def screen(client) -> str:
    return client.get("/portal", follow_redirects=True).get_data(as_text=True)


class TestThreeModes:
    @pytest.mark.parametrize("mode", ["CURRENT", "PICKUP", "DELIVERY"])
    def test_the_driver_modes_are_present(self, client, mode):
        assert f'data-mode="{mode}"' in screen(client)

    def test_sweep_is_not_a_mode(self, client):
        assert 'data-mode="SWEEP"' not in screen(client)

    def test_there_are_exactly_three_modes(self, client):
        assert len(re.findall(r'data-mode="', screen(client))) == 3

    def test_no_sweep_controls_reach_the_driver_screen(self, client):
        """Not merely unlabelled -- absent."""
        html = screen(client).lower()
        assert "start sweep now" not in html
        assert "stop scheduled sweeping" not in html


class TestSweepWasMovedNotDeleted:
    """The operator likes manual activation. It has to survive the move."""

    def test_the_panel_still_exists(self):
        from pathlib import Path

        panel = Path("portal/templates/_sweep_panel.html")
        assert panel.exists()
        markup = panel.read_text(encoding="utf-8")
        assert "START SWEEP NOW" in markup.upper()

    def test_the_sweep_api_still_works(self, client):
        assert client.get("/api/sweep/status").status_code == 200


class TestTheJoeDock:
    def test_the_dock_is_present(self, client):
        assert "joe-box" in screen(client)

    def test_there_is_no_joe_mode(self, client):
        assert 'data-mode="JOE"' not in screen(client)

    def test_two_lines_in(self, client):
        html = screen(client)
        assert 'id="joe-entry"' in html
        assert 'rows="2"' in html

    def test_one_line_out(self, client):
        assert 'class="joe-speech"' in screen(client)

    def test_the_spoken_line_is_large_non_bold_monospace(self):
        """By specification: 22-24px, non-bold, monospace.

        Asserted against the stylesheet because it is the whole point of the
        line -- a driver reads it at a glance, from further away than a desk.
        """
        from pathlib import Path

        css = Path("portal/static/joe_portal.css").read_text(encoding="utf-8")
        block = css[css.index(".joe-speech {"):]
        block = block[:block.index("}")]

        size = int(re.search(r"font-size:\s*(\d+)px", block).group(1))
        assert 22 <= size <= 24, f"spoken line is {size}px; specified 22-24"
        assert re.search(r"font-weight:\s*400", block), "must not be bold"
        assert "monospace" in block

    def test_the_dock_announces_changes_to_a_screen_reader(self, client):
        """JOE speaking is the one thing on this screen that changes by itself."""
        assert 'aria-live="polite"' in screen(client)
