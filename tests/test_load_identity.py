"""Load identity: the number a person uses, and the number the system trusts.

Two fields, on purpose (GAP_ANALYSIS G-02 / G-03):

``load_number``
    Dispatch's own. ``L1-0001``. Assigned once at creation, unique by
    construction, never reissued, never absent. This is identity.

``broker_load_number``
    Whatever the broker calls it. Optional, unconstrained, may duplicate, may be
    corrected or reissued by the broker without consequence. Never identity.

The Load Number Doctrine's Rules 1 and 2 -- use the broker's number when there is
one, generate one when there is not -- are satisfied at the **display** layer by
``operational_number()``. Identity is not a display question, and a third party's
number cannot carry it: a broker correcting a number would otherwise change the
identity of a load already in motion.

**Open for Mike** (directive questions 1-7, unruled): whether the broker's number
should be primary for identity too. Both fields exist either way.
"""

from __future__ import annotations

import pytest

from dispatch import services, store
from dispatch.models import Load, operational_number


class TestEveryLoadGetsANumber:
    def test_a_new_load_is_numbered_without_being_asked(self):
        load = services.create_load(customer="Acme")
        assert load["load_number"].startswith("L1-")

    def test_numbers_are_sequential(self):
        first = services.create_load(customer="One")["load_number"]
        second = services.create_load(customer="Two")["load_number"]
        assert int(second.split("-")[1]) == int(first.split("-")[1]) + 1

    def test_the_number_is_zero_padded_to_four(self):
        assert services.create_load(customer="Acme")["load_number"].split("-")[1] == "0001"

    def test_it_keeps_counting_past_four_digits(self):
        """A zero-padded minimum, not a fixed width. Load 10,000 must still work."""
        from dispatch.db import get_connection

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO load_number_sequence (id, last_issued) VALUES (1, 9999) "
                "ON CONFLICT(id) DO UPDATE SET last_issued = 9999"
            )
            assert store._next_load_number(conn) == "L1-10000"
            assert store._next_load_number(conn) == "L1-10001"

    def test_a_supplied_number_is_not_overwritten(self):
        load = Load(customer="Acme", load_number="L1-4242")
        assert store.create_load(load)["load_number"] == "L1-4242"


class TestTheNumberIsIdentityAndNeverReused:
    def test_two_loads_cannot_share_a_number(self):
        services.create_load(customer="One")
        from dispatch.db import get_connection

        with get_connection() as conn:
            taken = conn.execute("SELECT load_number FROM loads").fetchone()[0]

        with pytest.raises(Exception):
            store.create_load(Load(customer="Two", load_number=taken))

    def test_a_deleted_load_does_not_return_its_number(self):
        """A number that comes back means two loads share an identity in someone's
        records -- the broker's, the shipper's, the accountant's."""
        first = services.create_load(customer="One")
        second = services.create_load(customer="Two")
        assert second["load_number"] == "L1-0002"

        services.delete_load(second["load_id"])
        third = services.create_load(customer="Three")

        assert third["load_number"] != second["load_number"]
        assert first["load_number"] != third["load_number"]


class TestTheBrokerNumberIsNotIdentity:
    def test_it_is_optional(self):
        assert services.create_load(customer="Acme")["broker_load_number"] == ""

    def test_it_is_stored_as_given(self):
        load = services.create_load(customer="Acme", broker_load_number="TQL-458721")
        assert load["broker_load_number"] == "TQL-458721"

    def test_two_loads_may_carry_the_same_broker_number(self):
        """Brokers reuse numbers. That is their business, not Dispatch's, and
        refusing the second load would be Dispatch policing someone else's
        namespace -- directive question 4, answered by not constraining it."""
        a = services.create_load(customer="One", broker_load_number="TQL-458721")
        b = services.create_load(customer="Two", broker_load_number="TQL-458721")

        assert a["broker_load_number"] == b["broker_load_number"]
        assert a["load_number"] != b["load_number"], "identity is still distinct"

    def test_surrounding_whitespace_is_trimmed(self):
        load = services.create_load(customer="Acme", broker_load_number="  TQL-1  ")
        assert load["broker_load_number"] == "TQL-1"


class TestTheOperationalNumberIsWhatAPersonSays:
    def test_the_broker_number_wins_when_there_is_one(self):
        load = services.create_load(customer="Acme", broker_load_number="TQL-458721")
        assert operational_number(load) == "TQL-458721"

    def test_dispatchs_own_number_is_used_when_there_is_not(self):
        load = services.create_load(customer="Acme")
        assert operational_number(load) == load["load_number"]

    def test_it_reads_a_dataclass_and_a_dict_the_same_way(self):
        load = Load(customer="Acme", load_number="L1-0007")
        assert operational_number(load) == "L1-0007"
        assert operational_number(load.to_dict()) == "L1-0007"

    def test_it_never_returns_the_uuid_key(self):
        """`load_id` is `LOAD-20260904-A3F91B2C`. Nobody says that over a phone."""
        load = services.create_load(customer="Acme")
        assert load["load_id"] not in operational_number(load)


class TestOlderLoadsCanBeBackfilled:
    def test_it_numbers_loads_that_predate_the_column(self):
        from dispatch.db import get_connection

        services.create_load(customer="One")
        services.create_load(customer="Two")
        with get_connection() as conn:
            conn.execute("UPDATE loads SET load_number = ''")

        assert services.backfill_load_numbers() == 2

        for load in services.list_loads():
            assert load["load_number"].startswith("L1-")

    def test_running_it_twice_changes_nothing(self):
        services.create_load(customer="Acme")
        assert services.backfill_load_numbers() == 0

    def test_it_leaves_an_existing_number_alone(self):
        from dispatch.db import get_connection

        kept = services.create_load(customer="Keeper")["load_number"]
        services.create_load(customer="Other")
        with get_connection() as conn:
            conn.execute("UPDATE loads SET load_number = '' WHERE customer = 'Other'")

        services.backfill_load_numbers()

        assert services.get_load_by_number(kept) is not None if hasattr(
            services, "get_load_by_number"
        ) else True
        numbers = {l["customer"]: l["load_number"] for l in services.list_loads()}
        assert numbers["Keeper"] == kept
