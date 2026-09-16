"""Short labels, and the section headings that keep them unambiguous.

**Owner ruling, 2026-09-16:** *"The document is too busy and wordy to be
functional. It needs to be more simple and direct in the field labels."*

Under a heading that already says PICKUP, a label reading "Pickup facility and
address" says pickup twice and address once too often. The labels are now the
word and nothing else -- Facility, Appointment, Contact, Phone, Access -- which
means the same word appears under PICKUP and again under DELIVERY. That
repetition is the point, and the section above them is what makes it readable.

It is also what the email parser has to read, because the returned template is
plain text and "Phone: 904-555-0100" on its own does not say which end of the
run it belongs to.
"""

from __future__ import annotations

from dispatch import mission_template as mt


class TestTheLabelsAreTheWordAndNothingElse:
    def test_no_label_repeats_its_own_section(self):
        """NOTES is exempt: it holds one field, so the heading and the label are
        the same word said once, not twice."""
        for field in mt.TEMPLATE:
            if len(mt.fields_in(field.section)) == 1:
                continue
            first = field.section.split()[0].lower()
            assert not field.label.lower().startswith(first), (
                "%s says %s twice" % (field.label, first))

    def test_the_labels_are_short(self):
        """Three words is a label. More than that is a sentence, and a sentence
        beside every box is what made the document unreadable."""
        for field in mt.TEMPLATE:
            assert len(field.label.split()) <= 3, field.label

    def test_the_customer_is_the_customer(self):
        """**Vocabulary ruled 2026-09-06:** *"I use Shipper/Broker synonymously,
        they are interchangeable, because I have no idea which is booking the
        load."* The label said all three for months."""
        field = next(f for f in mt.TEMPLATE if f.key == "customer")
        assert field.label == "Customer"

    def test_the_two_ends_ask_the_same_words(self):
        pickup = [f.label for f in mt.TEMPLATE if f.section == "PICKUP"]
        delivery = [f.label for f in mt.TEMPLATE if f.section == "DELIVERY"]
        assert set(pickup) < set(delivery), (
            "the delivery end asks everything the pickup end asks, in the same "
            "words, plus its own consignee and BOL")


class TestAReturnedTemplateStillParses:
    def test_each_end_keeps_its_own_phone(self):
        filled = mt.render_email({
            "pickup_location": "Gulf Coast Paper, Jacksonville, FL",
            "pickup_phone": "904-555-0100",
            "delivery_location": "Harbor Receiving, Savannah, GA",
            "delivery_phone": "912-555-0199",
        })

        values = mt.parse_email(filled)

        assert values["pickup_phone"] == "904-555-0100"
        assert values["delivery_phone"] == "912-555-0199"
        assert values["pickup_location"] == "Gulf Coast Paper, Jacksonville, FL"
        assert values["delivery_location"] == "Harbor Receiving, Savannah, GA"

    def test_every_field_survives_the_round_trip(self):
        typed = {f.key: "value for %s" % f.key
                 for f in mt.TEMPLATE if not f.assigned}

        values = mt.parse_email(mt.render_email(typed))

        assert values == dict(mt.blank_template(), **typed)

    def test_a_template_sent_before_the_labels_changed_still_comes_back(self):
        """A driver answers on Thursday a template that was emailed on Tuesday.
        Losing his work because the form was tidied in between is not a trade
        worth making."""
        old = "\n".join([
            "PICKUP",
            "------",
            "Pickup facility and address: Gulf Coast Paper, Jacksonville, FL",
            "Pickup phone: 904-555-0100",
            "",
            "DELIVERY",
            "--------",
            "Delivery facility and address: Harbor Receiving, Savannah, GA",
            "Delivery phone: 912-555-0199",
            "Customer / Shipper / Broker: Gulf Coast Paper Mill",
        ])

        values = mt.parse_email(old)

        assert values["pickup_phone"] == "904-555-0100"
        assert values["delivery_phone"] == "912-555-0199"
        assert values["customer"] == "Gulf Coast Paper Mill"

    def test_a_phone_reply_with_quote_markers_still_parses(self):
        quoted = "\n".join([
            "> PICKUP",
            "> -------",
            ">   Phone: 904-555-0100",
            "> DELIVERY",
            ">   Phone: 912-555-0199",
        ])

        values = mt.parse_email(quoted)

        assert values["pickup_phone"] == "904-555-0100"
        assert values["delivery_phone"] == "912-555-0199"
