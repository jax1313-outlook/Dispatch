"""Dispatch Security Foundation -- Identity, PIN, Session, Role, Audit.

Scope is deliberately narrow, per DISPATCH_STAGE7_SECURITY_FOUNDATION_DESIGN_v1.md
(Claude-3 repository): this module provides working, tested login/PIN/
session/role/audit infrastructure. It does not, by itself, gate any
existing Portal page or action -- only /settings and the new /login,
/logout routes (portal/routes/security.py) use it in this build.
Deciding which other pages/actions require login is "Portal-Wide
Enforcement," a separate, later, not-yet-approved stage.

Lives under dispatch/, not portal/, mirroring dispatch/spine/'s
placement -- a deliberate implementation-time correction to the
design document's literal "portal/security/" path: dispatch/db.py
needs to import this module's schema-init function from the existing
_init_db() pass, and every other file in this codebase has portal/
depend on dispatch/, never the reverse. Placing this package under
dispatch/ keeps that one-directional dependency intact instead of
inverting it. Portal's routes and templates (the actual login/logout
UI) still live under portal/, consuming this module the same way
portal/routes/pages.py already consumes dispatch/services.py.

Persistence: same dispatch.db SQLite file as everything else (see
dispatch/security/db.py), following the exact pattern dispatch/spine/
established in Stage 4.
"""
