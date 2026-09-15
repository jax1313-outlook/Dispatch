"""Who to call when something is wrong, stop by stop.

From the operator, describing a run he actually took:

    "Had a load that had one broker, 2 stops, different companies. One stop had
     the shipper as the load control, not the broker. That meant if issues or
     damage, call the shipper -- not the broker."

So load control is a fact about the stop, not about the run, and it is not the
same thing as who arranged the freight. One broker's run can still have the
shipper holding authority on stop 2. Three brokers can share one truck.

The failure this guards against is not cosmetic. It is standing at a dock with
damaged freight, calling the party named on the screen, and finding out they
are not responsible for it -- while the party who is has not been told.
"""

from __future__ import annotations

import pytest

from dispatch import load_control as lc, mission_template as mt


RUN = {
    "customer": "Southeast Freight Partners",
    "controlled_by": "Customer",
    "pickup_location": "Jacksonville, FL 32202",
    "pickup_window": "2026-09-02 06:00 - 10:00",
    "delivery_location": "Publix DC Lakeland",
    "delivery_window": "2026-09-02 14:00",
    "commodity": "Mixed freight",
}


def _record(**over):
    extra = over.pop("extra_stops", None)
    return mt.to_record(dict(RUN, **over), source=mt.SOURCE_JOE,
                        extra_stops=extra)


class TestTheTemplateAsksForThePick:
    """**The one-page layout, 2026-09-15.** Load control on the Mission Template
    is a two-choice pick -- *"2) yes either"* -- the Customer, or Level 1. The
    name, role, phone and per-stop detail below left the template."""

    def test_the_choices_are_customer_and_level_1(self):
        assert lc.HELD_BY == ("Customer", "Level 1")
        assert mt.LOAD_CONTROL_CHOICES == lc.HELD_BY

    def test_the_pick_reaches_the_record(self):
        assert _record()["controlled_by"] == "Customer"
        assert _record(controlled_by="Level 1")["controlled_by"] == "Level 1"

    def test_a_blank_pick_is_not_invented(self):
        assert "controlled_by" not in _record(controlled_by="")

    def test_no_stop_level_detail_is_written_any_more(self):
        """A stop block carrying the old load control lines is read for its
        stop and nothing else: those lines are no longer template fields."""
        body = mt.render_stop_block(2, {
            "facility": "Winn-Dixie Orlando", "window": "2026-09-02 17:00"})
        body += "\n  Load control: Gulf Coast Paper\n  Their reference: GCP-88\n"
        record = _record(extra_stops=mt.parse_stops(body))
        assert record["stop_total"] == 2
        assert record["stops"][1]["facility"] == "Winn-Dixie Orlando"
        for stop in record["stops"]:
            assert not any(key.startswith("control") for key in stop), stop
        assert "load_control" not in record
        assert "load_control_varies" not in record

    def test_three_stops_one_truck_is_still_one_record(self):
        """Three companies, one run -- one Mission Record."""
        blocks = [mt.render_stop_block(i, {"facility": f"Consignee {i}",
                                           "window": f"1{i}:00"}) for i in (2, 3)]
        record = _record(extra_stops=mt.parse_stops("\n".join(blocks)))
        assert record["stop_total"] == 3
        assert [s["facility"] for s in record["stops"]] == [
            "Publix DC Lakeland", "Consignee 2", "Consignee 3"]


class TestAnOlderRecordsAuthorityStillReads:
    """Records written before 2026-09-15 keep their stop-level load control.
    `control_for` still reads it exactly as it did; nothing was rewritten."""

    DEFAULT = {"control_name": "Southeast Freight Partners",
               "control_role": "broker", "control_phone": "904-555-0199"}

    def test_one_broker_over_the_whole_run_still_resolves(self):
        control = lc.control_for({"facility": "Publix DC Lakeland"}, self.DEFAULT)
        assert control["name"] == "Southeast Freight Partners"
        assert control["role"] == lc.BROKER
        assert control["inherited"] is True

    def test_a_stop_that_answered_to_the_shipper_still_does(self):
        stops = [{"facility": "Publix DC Lakeland"},
                 {"facility": "Winn-Dixie Orlando", "control_name": "Gulf Coast Paper",
                  "control_role": "shipper", "control_phone": "813-555-0177",
                  "control_ref": "REF-2"}]
        second = lc.control_for(stops[1], self.DEFAULT)
        assert second["name"] == "Gulf Coast Paper"
        assert second["role"] == lc.SHIPPER
        assert second["inherited"] is False
        assert second["reference"] == "REF-2"
        assert lc.differs_across(stops, self.DEFAULT) is True


class TestItDoesNotGuessAuthority:
    def test_an_unknown_role_stays_unknown(self):
        """Defaulting to BROKER is exactly wrong on the stop where it is not."""
        assert lc.normalise_role("whoever") == ""
        assert lc.normalise_role("") == ""

    def test_it_says_so_when_nobody_has_been_named(self):
        control = lc.control_for({}, {})
        assert control["known"] is False
        assert control["line"] == "Load control not recorded"

    def test_the_dock_contact_is_never_offered_as_load_control(self):
        """A dock contact receives freight. He is not who you call about
        damage, and the two being adjacent on a card is how they get confused."""
        control = lc.control_for({"poc": "Dock 7 - K. Mills",
                                  "phone": "863-555-0114"}, {})
        assert control["known"] is False
        assert "Mills" not in control["line"]

    @pytest.mark.parametrize("raw,expected", [
        ("broker", lc.BROKER), ("Shipper", lc.SHIPPER),
        ("receiver", lc.CONSIGNEE), ("3PL", lc.BROKER),
        ("customer", lc.CUSTOMER), ("vendor", lc.SHIPPER)])
    def test_roles_are_read_the_way_they_get_written_down(self, raw, expected):
        assert lc.normalise_role(raw) == expected


class TestWhatTheDriverReads:
    def test_the_line_carries_name_role_and_number(self):
        control = lc.control_for({"control_name": "Gulf Coast Paper",
                                  "control_role": "shipper",
                                  "control_phone": "813-555-0177"}, {})
        assert control["line"] == "Gulf Coast Paper (Shipper) · 813-555-0177"

    def test_a_missing_number_does_not_produce_a_dangling_separator(self):
        control = lc.control_for({"control_name": "Gulf Coast Paper",
                                  "control_role": "shipper"}, {})
        assert control["line"] == "Gulf Coast Paper (Shipper)"

    def test_the_pick_is_the_whole_line(self):
        """Owner ruling, 2026-09-15, asked whether a Customer pick should also
        show the customer's name and phone: *"no redunat not needed. Less is
        more."* The pick, and nothing beside it."""
        assert lc.held_by({"controlled_by": "Level 1"}) == {
            "known": True, "line": "Level 1"}
        record = {"controlled_by": "Customer", "customer": "Southeast Freight Partners",
                  "customer_phone": "904-555-0199", "broker": "Southeast Freight Partners",
                  "broker_phone": "904-555-0199"}
        assert lc.held_by(record) == {"known": True, "line": "Customer"}
        assert lc.held_by({})["known"] is False


class TestTheCockpitShowsThePickNotTheRemovedDetail:
    """**One-page layout, 2026-09-15.** The Driver Cockpit's LOAD CONTROL line
    reads the record's pick. The stop-level name, role, phone and reference an
    older record stores are no longer shown -- and the cockpit still renders
    that record, stop by stop, without them."""

    RECORD = {
        "card_data": {"load_id": "847261"},
        "load_control": {"control_name": "Southeast Freight Partners",
                         "control_role": "BROKER",
                         "control_phone": "904-555-0199"},
        "stops": [
            {"number": 1, "label": "STOP 1", "facility": "Publix DC Lakeland"},
            {"number": 2, "label": "STOP 2", "facility": "Winn-Dixie Orlando",
             "control_name": "Gulf Coast Paper", "control_role": "SHIPPER",
             "control_phone": "813-555-0177", "control_ref": "GCP-88"},
        ],
        "stop_total": 2,
        "load_control_varies": True,
    }

    def test_an_older_record_still_renders_each_stop(self):
        from portal import cockpit

        first = cockpit.end_detail(self.RECORD, "delivery", stop_number=1)
        second = cockpit.end_detail(self.RECORD, "delivery", stop_number=2)
        assert first["address"] == "Publix DC Lakeland"
        assert second["address"] == "Winn-Dixie Orlando"

    def test_the_removed_stop_detail_is_not_shown(self):
        from portal import cockpit

        for number in (1, 2):
            detail = cockpit.end_detail(self.RECORD, "delivery", stop_number=number)
            assert detail["control"]["known"] is False
            assert "reference" not in detail["control"]
            assert "control_varies" not in detail
        stop = cockpit.selected_stop(self.RECORD, 2)
        assert not any(key.startswith("control") for key in stop)

    def test_the_stored_detail_is_left_exactly_as_it_was(self):
        from portal import cockpit

        cockpit.end_detail(self.RECORD, "delivery", stop_number=2)
        assert self.RECORD["stops"][1]["control_ref"] == "GCP-88"
        assert self.RECORD["load_control"]["control_name"] == "Southeast Freight Partners"

    def test_the_pick_is_what_the_line_shows(self):
        from portal import cockpit

        record = dict(self.RECORD, controlled_by="Customer")
        detail = cockpit.end_detail(record, "delivery", stop_number=2)
        assert detail["control"]["known"] is True
        assert detail["control"]["line"] == "Customer"

    def test_the_cockpit_line_carries_only_the_pick_through_its_route(self, tmp_path,
                                                                     monkeypatch):
        """Through /portal/mission, as the driver sees it: LOAD CONTROL and the
        pick, with no customer name, phone or reference beside it. The CUSTOMER
        fact row on the glass is unchanged and still names the customer."""
        import re

        from portal.app import create_app
        from portal.models import sandbox

        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="LC-1", title="Load control probe",
            card_data={"load_id": "LC-1", "broker": "Southeast Freight Partners",
                       "broker_phone": "904-555-0199"}, summary="")
        data = sandbox._load()
        data[entry["id"]]["controlled_by"] = "Customer"
        sandbox._save(data)

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as client:
            html = client.get(f"/portal/mission/{entry['id']}?view=DELIVERY").get_data(as_text=True)

        blocks = re.findall(r'<div class="load-control[^"]*">(.*?)</div>', html, re.S)
        assert blocks, "the load control line is shown"
        for block in blocks:
            text = re.sub(r"<[^>]+>", " ", block).split()
            assert text == ["LOAD", "CONTROL", "Customer"], text
        assert "control-ref" not in html
        glass = html[:html.index("<aside")]
        assert "Southeast Freight Partners" in glass

    def test_the_screen_says_it_in_the_drivers_words(self):
        from portal import joe_voice

        for pick in lc.HELD_BY:
            assert joe_voice.is_driver_safe(lc.held_by({"controlled_by": pick})["line"]) == []
        control = lc.control_for(self.RECORD["stops"][1], {})
        assert joe_voice.is_driver_safe(control["line"]) == []


class TestCodIsAFieldNotAKindOfMission:
    """Ruled by the operator, 1 September 2026, reversing a dynamic checklist
    this had grown:

        KISS is a survivability doctrine.

    An earlier version derived the delivery list from a per-customer POD
    requirement so a direct-pay run would not be asked for an invoice to a
    broker. That was wrong twice. Wrong on the freight -- XPO is still in the
    transaction chain on a Mayo C.O.D. run, still receives the POD packet, and
    still reconciles. And wrong on the architecture, which matters more: a
    checklist that branches per customer is a branch to be remembered, tested
    and explained years from now, in a one-truck business with no maintenance
    budget.

    The Mission Template encodes the payment arrangement once. The data
    changes; the workflow does not. C.O.D. adds exactly one line, and it
    exists to prevent one failure: pulling away from the dock without the
    check.
    """

    def _labels(self, **record):
        from portal import cockpit

        record.setdefault("card_data", {})
        return [i["label"] for i in
                cockpit.document_checklist(record, cockpit.MODE_DELIVERY)]

    def test_the_delivery_list_is_the_same_on_every_mission(self):
        from portal import cockpit

        standard = list(cockpit.DELIVERY_ARTIFACTS)
        assert self._labels() == standard
        assert self._labels(payment_type="Broker Invoice") == standard
        assert self._labels(pod_required="Signed BOL only") == standard

    def test_the_invoice_to_broker_survives_a_cod_load(self):
        """XPO is still in the chain. Mayo hands over the check; XPO still
        gets the packet and reconciles on their side."""
        assert "Invoice To Broker" in self._labels(
            payment_type="C.O.D.", payor="Mayo Clinic Jacksonville")

    def test_cod_adds_exactly_one_line(self):
        from portal import cockpit

        plain = self._labels()
        cod = self._labels(payment_type="C.O.D.", payor="Mayo Clinic Jacksonville")
        assert len(cod) == len(plain) + 1
        assert cod[:-1] == plain
        assert cod[-1] == "C.O.D. Collected - Mayo Clinic Jacksonville"

    def test_a_broker_invoice_load_adds_nothing(self):
        from portal import cockpit

        assert self._labels(payment_type="Broker Invoice") == list(
            cockpit.DELIVERY_ARTIFACTS)

    def test_the_line_says_the_one_thing_it_is_for(self):
        from portal import cockpit

        record = {"card_data": {}, "payment_type": "C.O.D.",
                  "payor": "Mayo Clinic Jacksonville"}
        item = [i for i in cockpit.document_checklist(record, cockpit.MODE_DELIVERY)
                if i["label"].startswith("C.O.D.")][0]
        assert item["note"] == "Do not leave the dock without it."

    def test_the_amount_rides_on_the_line_when_there_is_one(self):
        assert self._labels(payment_type="COD", payor="Mayo",
                            amount="$1,150")[-1] == "C.O.D. Collected - Mayo - $1,150"

    def test_pickup_never_asks_for_payment(self):
        from portal import cockpit

        record = {"card_data": {}, "payment_type": "C.O.D.", "payor": "Mayo"}
        labels = [i["label"] for i in
                  cockpit.document_checklist(record, cockpit.MODE_PICKUP)]
        assert labels == list(cockpit.PICKUP_ARTIFACTS)


class TestBalanceGoesToZeroWhenCollected:
    """The record carries the difference. Nothing else does."""

    def test_the_balance_is_the_amount_until_it_is_collected(self):
        from portal import cockpit

        cod = cockpit.cod_for({"payment_type": "C.O.D.", "amount": "1150.00"})
        assert cod["balance_due"] == "1150.00"
        assert cod["collected"] is False

    def test_collecting_zeroes_it(self):
        from portal import cockpit

        cod = cockpit.cod_for({"payment_type": "C.O.D.", "amount": "1150.00",
                               "payment_collected_at": "2026-09-02T12:10:00"})
        assert cod["balance_due"] == "0.00"
        assert cod["collected"] is True

    def test_a_non_cod_load_has_no_balance_to_carry(self):
        from portal import cockpit

        assert cockpit.cod_for({"payment_type": "Broker Invoice"})["is_cod"] is False

    def test_records_written_before_payment_type_existed_still_work(self):
        from portal import cockpit

        cod = cockpit.cod_for({"cod": "Check - Mayo Clinic Jacksonville"})
        assert cod["is_cod"] is True
        assert cod["payor"] == "Check - Mayo Clinic Jacksonville"
