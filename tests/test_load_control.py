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
    "control_name": "Southeast Freight Partners",
    "control_role": "broker",
    "control_phone": "904-555-0199",
    "pickup_location": "Jacksonville, FL 32202",
    "pickup_window": "2026-09-02 06:00 - 10:00",
    "delivery_location": "Publix DC Lakeland",
    "delivery_window": "2026-09-02 14:00",
    "commodity": "Mixed freight",
}


def _record(**over):
    extra = over.pop("extra_stops", None)
    return mt.to_record(dict(RUN, **over), source=mt.SOURCE_JOE,
                        taken_by="Mike", extra_stops=extra)


class TestAuthorityIsAStopLevelFact:
    def test_one_broker_over_the_whole_run_still_works(self):
        """The common case. Naming him once has to be enough, or the template
        stops getting filled in."""
        record = _record()
        control = record["stops"][0]["control"]
        assert control["name"] == "Southeast Freight Partners"
        assert control["role"] == lc.BROKER
        assert control["inherited"] is True
        assert record["load_control_varies"] is False

    def test_a_stop_can_answer_to_the_shipper_instead(self):
        """The operator's actual run: one broker, two stops, and stop 2 is the
        shipper's freight."""
        body = mt.render_stop_block(2, {
            "facility": "Winn-Dixie Orlando",
            "window": "2026-09-02 17:00",
            "control_name": "Gulf Coast Paper",
            "control_role": "shipper",
            "control_phone": "813-555-0177"})
        record = _record(extra_stops=mt.parse_stops(body))

        first = record["stops"][0]["control"]
        second = record["stops"][1]["control"]
        assert first["name"] == "Southeast Freight Partners"
        assert second["name"] == "Gulf Coast Paper"
        assert second["role"] == lc.SHIPPER
        assert second["inherited"] is False

    def test_the_record_knows_when_authority_varies(self):
        """Which is what tells the screen it must name the party per stop."""
        body = mt.render_stop_block(2, {
            "facility": "Winn-Dixie Orlando", "window": "17:00",
            "control_name": "Gulf Coast Paper", "control_role": "shipper"})
        record = _record(extra_stops=mt.parse_stops(body))
        assert record["load_control_varies"] is True

    def test_three_brokers_one_truck(self):
        """Three brokers, three companies, one run -- one Mission Record."""
        blocks = [mt.render_stop_block(i, {
            "facility": f"Consignee {i}", "window": f"1{i}:00",
            "control_name": f"Broker {i}", "control_role": "broker",
            "control_ref": f"REF-{i}"}) for i in (2, 3)]
        record = _record(extra_stops=mt.parse_stops("\n".join(blocks)))

        assert record["stop_total"] == 3
        assert record["load_control_varies"] is True
        names = [s["control"]["name"] for s in record["stops"]]
        assert names == ["Southeast Freight Partners", "Broker 2", "Broker 3"]
        assert record["stops"][2]["control"]["reference"] == "REF-3"


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

    def test_each_stop_keeps_its_own_reference_number(self):
        """Three brokers means three reference numbers, and quoting the wrong
        one at a gate is a delay."""
        body = mt.render_stop_block(2, {"facility": "X", "window": "1",
                                        "control_ref": "REF-2"})
        record = _record(extra_stops=mt.parse_stops(body))
        assert record["stops"][1]["control"]["reference"] == "REF-2"


class TestTheStopCardCarriesItThrough:
    """The bug this class exists for: `stop_list` normalised stops into a
    fixed set of keys and dropped the control fields, so every stop silently
    inherited the run default -- showing the broker on the stop that answers
    to the shipper. Exactly the failure the data was added to prevent, and
    invisible unless something asserts on stop 2 specifically."""

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

    def test_each_stop_shows_its_own_authority(self):
        from portal import cockpit

        first = cockpit.end_detail(self.RECORD, "delivery", stop_number=1)
        second = cockpit.end_detail(self.RECORD, "delivery", stop_number=2)
        assert first["control"]["name"] == "Southeast Freight Partners"
        assert second["control"]["name"] == "Gulf Coast Paper"
        assert second["control"]["role"] == lc.SHIPPER

    def test_the_stop_list_does_not_normalise_authority_away(self):
        from portal import cockpit

        stop = cockpit.selected_stop(self.RECORD, 2)
        assert stop["control_name"] == "Gulf Coast Paper"
        assert stop["control_role"] == "SHIPPER"
        assert stop["control_ref"] == "GCP-88"

    def test_the_reference_travels_with_the_stop(self):
        from portal import cockpit

        detail = cockpit.end_detail(self.RECORD, "delivery", stop_number=2)
        assert detail["control"]["reference"] == "GCP-88"

    def test_the_screen_says_it_in_the_drivers_words(self):
        from portal import joe_voice

        control = lc.control_for(self.RECORD["stops"][1], {})
        assert joe_voice.is_driver_safe(control["line"]) == []


class TestAPaidAtTheDockLoadSaysSoOnTheChecklist:
    """From the operator: this run is frequently a cash load, paid by check by
    Mayo Clinic Jacksonville, rate negotiated by calling XPO dispatch.

    A load paid at the dock is a load a driver can leave without being paid
    for. That is not a billing note -- it is a step at the delivery, and it
    belongs where he is already looking.
    """

    def _checklist(self, terms="", cod=""):
        from portal import cockpit

        record = {"card_data": {"load_id": "ROC-2026-884471"},
                  "payment_terms": terms, "cod": cod}
        return [i["label"] for i in
                cockpit.document_checklist(record, cockpit.MODE_DELIVERY)]

    def test_the_cod_field_decides_not_the_phrasing(self):
        """Whether he leaves the dock with money is too consequential to depend
        on somebody having written 'check' rather than 'cheque'."""
        labels = self._checklist(terms="", cod="Check - Mayo Clinic Jacksonville")
        assert any(l.startswith("C.O.D. collected") for l in labels)

    def test_the_amount_is_on_the_item_itself(self):
        from portal import cockpit

        record = {"card_data": {}, "cod": "$1,150 check"}
        item = [i for i in cockpit.document_checklist(record, cockpit.MODE_DELIVERY)
                if i["label"].startswith("C.O.D.")][0]
        assert "$1,150 check" in item["label"]

    def test_no_cod_and_no_collect_terms_adds_nothing(self):
        assert not any(l.startswith("C.O.D.") for l in
                       self._checklist(terms="Invoice net 30", cod=""))

    def test_a_check_on_delivery_becomes_a_checklist_item(self):
        assert "Payment collected" in self._checklist(
            "Check on delivery - Mayo Clinic Jacksonville")

    @pytest.mark.parametrize("terms", ["Cash load", "COD", "Collect at delivery",
                                       "Driver collects check"])
    def test_it_reads_the_phrasings_a_driver_actually_uses(self, terms):
        assert "Payment collected" in self._checklist(terms)

    @pytest.mark.parametrize("terms", ["Invoice to broker net 30",
                                       "Invoiced monthly", ""])
    def test_an_invoiced_load_gains_no_item(self, terms):
        """A checklist step that is never the driver's job teaches him to tick
        without reading."""
        assert "Payment collected" not in self._checklist(terms)

    def test_the_terms_travel_with_the_item(self):
        from portal import cockpit

        record = {"card_data": {}, "payment_terms": "Check by Mayo Clinic Jax"}
        item = [i for i in cockpit.document_checklist(record, cockpit.MODE_DELIVERY)
                if i["label"] == "Payment collected"][0]
        assert item["note"] == "Check by Mayo Clinic Jax"
        assert item["done"] is False

    def test_pickup_never_asks_for_payment(self):
        from portal import cockpit

        record = {"card_data": {}, "payment_terms": "Check on delivery"}
        labels = [i["label"] for i in
                  cockpit.document_checklist(record, cockpit.MODE_PICKUP)]
        assert "Payment collected" not in labels


class TestPodRequirementsVaryByCustomer:
    """Ruled by the operator, 1 September 2026: POD varies by customer.

    The fixed list put "Invoice To Broker" on a load with no broker that pays
    by check at the dock. A checklist item that cannot be completed on this
    load teaches a driver to tick without reading, which costs him the items
    that do matter.
    """

    def _labels(self, record):
        from portal import cockpit

        return [i["label"] for i in
                cockpit.document_checklist(record, cockpit.MODE_DELIVERY)]

    def test_a_stated_requirement_replaces_the_default_list(self):
        labels = self._labels({"card_data": {},
                               "pod_required": "Scanned signed BOL and packing list"})
        assert "Scanned signed BOL" in labels
        assert "Packing list" in labels
        assert "Invoice To Broker" not in labels

    def test_no_stated_requirement_leaves_the_default_alone(self):
        """Every existing mission keeps the list it had."""
        from portal import cockpit

        assert self._labels({"card_data": {}}) == list(cockpit.DELIVERY_ARTIFACTS)

    def test_the_arrival_notice_always_leads(self):
        """Dispatch generated and sent it. It is not the customer's to drop."""
        from portal import cockpit

        labels = self._labels({"card_data": {}, "pod_required": "Signed BOL"})
        assert labels[0] == cockpit.ARRIVAL_NOTICE

    def test_condition_photos_survive_a_shorter_list(self):
        """They are the driver's protection against a damage claim, not a
        document the receiver asked for. A customer wanting less does not make
        him need them less."""
        from portal import cockpit

        labels = self._labels({"card_data": {}, "pod_required": "Signed BOL"})
        assert cockpit.DRIVERS_OWN_RECORD in labels

    def test_it_does_not_duplicate_photos_the_customer_also_wants(self):
        labels = self._labels({"card_data": {},
                               "pod_required": "Signed BOL, delivery photos"})
        assert sum(1 for l in labels if "photo" in l.lower()) == 1

    def test_the_requirement_is_split_the_way_a_driver_writes_it(self):
        from portal import cockpit

        for stated in ("Signed BOL and packing list",
                       "Signed BOL, packing list",
                       "Signed BOL; packing list."):
            got = cockpit.pod_artifacts({"pod_required": stated})
            assert "Signed BOL" in got, stated
            assert "Packing list" in got, stated

    def test_cod_still_rides_on_top_of_whatever_the_list_is(self):
        labels = self._labels({"card_data": {}, "pod_required": "Signed BOL",
                               "cod": "Check - Mayo Clinic Jacksonville"})
        assert any(l.startswith("C.O.D. collected") for l in labels)

    def test_pickup_is_untouched_by_any_of_this(self):
        from portal import cockpit

        record = {"card_data": {}, "pod_required": "Signed BOL", "cod": "Check"}
        labels = [i["label"] for i in
                  cockpit.document_checklist(record, cockpit.MODE_PICKUP)]
        assert labels == list(cockpit.PICKUP_ARTIFACTS)
