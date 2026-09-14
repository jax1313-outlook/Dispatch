"""Portal entry through the Library PIN Service.

Mike Zachary, 2026-09-13: the Operations, Driver and Customer portals all ask
one question of the Library -- "is this PIN good for this portal?" -- and get
back Authenticated with a role and who, or Denied. Library owns the records
(dispatch_library.catalog.pins); Joe does the work. Dispatch only asks. There
is no authentication system here.

    Operations  a PIN authorized by Mike Zachary, by voice or in the dialog box
                with Joe.
    Driver      four characters, entered twice at the PIN window and held. Any
                held driver PIN opens the Driver portal: "it does not matter
                who is assigned what." No other information is asked.
    Customer    the load number from the load card -- the Mission Visibility
                Key (playbook Section 4A), not an account or login -- sent to
                the customer's email on file when the load is committed.

The PIN Service is used when DISPATCH_LIBRARY_CATALOG names the Library
catalog. When it does, it is the only door: a PIN the service denies is not
retried against the older stores (identity.json, driver_pin_registry.json).
When the catalog is not configured, the portals keep their older sign-in, so
nobody is locked out before the catalog is set.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

LIBRARY_CATALOG_ENV = "DISPATCH_LIBRARY_CATALOG"

OPERATIONS = "OPERATIONS"
DRIVER = "DRIVER"
CUSTOMER = "CUSTOMER"
OPERATIONS_AUTHORITY = "Mike Zachary"
DRIVER_PIN_LENGTH = 4


class PinServiceUnavailable(RuntimeError):
    """The catalog is configured but the Library cannot be reached."""


class PinRefused(ValueError):
    """The Library refused PIN work, and said why. The reason never contains a PIN."""


def configured() -> bool:
    return bool(os.environ.get(LIBRARY_CATALOG_ENV, "").strip())


@contextmanager
def _service():
    from portal.models import ensure_library_importable

    ensure_library_importable()
    try:
        from dispatch_library.catalog import open_pin_service
    except ImportError as exc:
        raise PinServiceUnavailable(
            f"{LIBRARY_CATALOG_ENV} is set, but the Library (dispatch_library) cannot be imported: {exc}"
        ) from exc
    try:
        service = open_pin_service(os.environ[LIBRARY_CATALOG_ENV].strip())
    except Exception as exc:
        raise PinServiceUnavailable(f"The Library catalog could not be opened: {exc}") from exc
    try:
        yield service
    except (ValueError, KeyError) as exc:  # CatalogRefusal and NotFound
        raise PinRefused(str(exc).strip("'\"")) from exc
    finally:
        service.db.close()


def validate(portal: str, pin: str, client_key: str | None) -> dict | None:
    """The Authenticated answer for this portal, or None for Denied."""
    with _service() as service:
        result = service.validate(portal, pin or "", client_key=client_key)
    return result.answer() if result.authenticated else None


def add_driver_pin(pin: str) -> dict:
    """Hold four characters that open the Driver portal."""
    with _service() as service:
        return service.add_driver_pin(pin)


def add_customer_load(customer: str, load_number: str, *, requested_by: str, channel: str) -> dict:
    with _service() as service:
        return service.add_customer_load(customer, load_number, requested_by=requested_by, channel=channel)


def operations_users() -> list[dict]:
    with _service() as service:
        return service.identities(OPERATIONS)


def create_operations_pin(name: str, pin: str, *, authorized_by: str, channel: str) -> dict:
    with _service() as service:
        return service.create_pin(OPERATIONS, name, pin, requested_by=authorized_by, channel=channel)


def reset_operations_pin(name: str, pin: str, *, authorized_by: str, channel: str) -> dict:
    with _service() as service:
        return service.reset_pin(OPERATIONS, name, pin, requested_by=authorized_by, channel=channel)


def customer_key(name: str | None) -> str:
    """How a customer name is compared: case and spacing do not matter, spelling does."""
    return " ".join(str(name or "").split()).casefold()


def is_operations_authority(name: str | None) -> bool:
    return customer_key(name) == OPERATIONS_AUTHORITY.casefold()
