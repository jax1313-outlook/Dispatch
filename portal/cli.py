"""One-time bootstrap CLI for the DISPATCH_PIN Authority identity.

Run on the server, directly at the terminal -- never through chat or a logged session
transcript, matching the practice established fixing DISPATCH_EMAIL_SECRET this session. Refuses
to run if an identity already exists (portal.models.identity.bootstrap_authority).
"""

from __future__ import annotations

import getpass
import sys


def init_admin() -> None:
    from portal.models import identity as identity_model

    if identity_model.has_any_identity():
        print("An identity already exists. init-admin only runs once.", file=sys.stderr)
        sys.exit(1)

    user_id = input("Authority user_id (short identifier, e.g. 'mike'): ").strip()
    display_name = input("Display name: ").strip()

    pin = getpass.getpass("Set PIN (min 4 characters, not echoed): ")
    confirm = getpass.getpass("Confirm PIN: ")
    if pin != confirm:
        print("PINs did not match. Nothing created.", file=sys.stderr)
        sys.exit(1)

    try:
        identity_model.bootstrap_authority(user_id, display_name, pin)
    except identity_model.IdentityError as exc:
        print(f"Could not create identity: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Authority identity '{user_id}' created. Portal login is now required.")


if __name__ == "__main__":
    init_admin()
