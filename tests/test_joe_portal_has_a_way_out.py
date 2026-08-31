"""Every mission screen must offer a way back.

The JOE Portal shipped with exactly two links: a stylesheet and the broker's
phone number. From a mission screen the only exits were the browser's Back
button and typing a URL, which the operator hit in real use and had to ask about.

A screen with no exit is the same defect as a launcher nobody can find, and it
fails the same test: it works perfectly for whoever built it.
"""

from __future__ import annotations

import pytest

from portal.app import create_app


# `/portal` redirects to the mission being worked when one exists and renders
# directly when none does, so every request here follows redirects. Without
# that these tests pass or fail on whether a load happens to be accepted --
# which is a property of the data, not of the screen.


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestTheWayOut:
    def test_the_mission_screen_offers_a_link_home(self, client):
        html = client.get("/portal", follow_redirects=True).get_data(as_text=True)
        assert 'class="way-out"' in html

    def test_it_points_at_the_main_dispatch_screen(self, client):
        html = client.get("/portal", follow_redirects=True).get_data(as_text=True)
        assert 'href="/home"' in html

    def test_it_says_where_it_goes_rather_than_just_back(self, client):
        """'Back' tells a driver nothing about where he will land."""
        html = client.get("/portal", follow_redirects=True).get_data(as_text=True)
        assert "Dispatch" in html

    def test_the_target_exists(self, client):
        """A back button to a 404 is worse than none: it teaches distrust."""
        assert client.get("/home", follow_redirects=False).status_code in (200, 302)

    def test_it_survives_every_view(self, client):
        """The four toggles swap the panel; none of them may remove the exit."""
        for view in ("CURRENT", "PICKUP", "DELIVERY", "SWEEP"):
            html = client.get(f"/portal?view={view}", follow_redirects=True).get_data(as_text=True)
            assert 'class="way-out"' in html, view
