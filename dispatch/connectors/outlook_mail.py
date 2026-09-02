"""Outbound mail, through the Outlook already running on this machine.

    Dispatch does not become a mail server.

There is no SMTP host here and no password stored anywhere. Outlook is already
installed and already authenticated with the operator's own accounts, so mail
goes out the way he sends mail: from his profile, from the right mailbox, into
his Sent Items where he can see it.

Two operations, and the difference between them is the whole authority model:

    send()     the Arrival Notice. Auto-sent, blind-copied to the office,
               because its purpose is on-time arrival evidence that does not
               depend on a gate guard logging anything.

    draft()    the final delivery packet. Prepared, placed in Drafts, and
               left there. **A person reads it and a person presses send.**

`draft()` is not a lesser `send()`. Preparing a packet and committing it to a
broker are different acts, and the machinery keeps them different so that
completing a checklist can never become an outbound message.

When Outlook is not answering, both say so and return without sending. Silence
that looks like success is the one outcome worth engineering against.
"""

from __future__ import annotations

from datetime import datetime, timezone

STATUS_LIVE = "LIVE"
STATUS_UNAVAILABLE = "UNAVAILABLE"

#: Mail leaves from the operations mailbox, not from a personal account. A
#: broker receiving arrival evidence from a private address has been given a
#: reason to wonder who he is dealing with.
DEFAULT_FROM = "Ops@l1truck.com"

#: Approved mailboxes. Anything else is refused rather than silently
#: substituted -- sending from the wrong account is not a formatting error.
APPROVED_MAILBOXES = ("Ops@l1truck.com", "Admin@l1truck.com")

_OL_MAIL_ITEM = 0


def _outlook_is_running() -> bool:
    """Whether Outlook is open right now.

    Checked before any COM call. Attaching to a running Outlook is instant;
    asking COM to start one produces a headless instance that wedges every
    call after it, and a hang on a driver's screen is worse than an error he
    can act on.

    GetActiveObject would be the obvious way to attach-only and does not work:
    Outlook does not reliably register in the running-object table, so it
    reports unavailable while Outlook sits open on the screen.
    """
    try:
        import subprocess

        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq OUTLOOK.EXE", "/NH"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return "OUTLOOK.EXE" in (result.stdout or "").upper()
    except Exception:  # noqa: BLE001 - a failed check means do not attempt COM
        return False


class MailError(Exception):
    """Mail could not be handled, and says why."""


class OutlookMailAdapter:
    """The real connection, over Outlook's COM interface on this machine."""

    name = "outlook_mail"

    BLOCKER = (
        "Outlook is not answering on this machine. Nothing was sent, and "
        "nothing was drafted."
    )

    NOT_RUNNING = (
        "Outlook is not open on this machine. Mail goes out through Outlook, "
        "so nothing was sent and nothing was drafted."
    )

    def _app(self):
        """A COM connection on this thread, or None and the reason.

        Initialised per call: Flask serves on worker threads, COM is
        per-thread, and a handle cached from another thread fails in ways that
        look like Outlook being broken.
        """
        try:
            import pythoncom
            import win32com.client
        except ImportError:
            return None, "The Outlook connection is not installed on this machine."

        if not _outlook_is_running():
            return None, self.NOT_RUNNING

        try:
            pythoncom.CoInitialize()
            return win32com.client.Dispatch("Outlook.Application"), ""
        except Exception:  # noqa: BLE001 - COM raises many shapes
            return None, self.NOT_RUNNING

    def _release(self):
        try:
            import pythoncom

            pythoncom.CoUninitialize()
        except Exception:  # noqa: BLE001 - releasing must never raise
            pass

    def probe(self) -> dict:
        app, blocker = self._app()
        if app is None:
            return {"name": self.name, "status": STATUS_UNAVAILABLE,
                    "live": False, "blocker": blocker, "accounts": []}
        try:
            accounts = [str(a.SmtpAddress) for a in
                        app.GetNamespace("MAPI").Accounts]
            return {"name": self.name, "status": STATUS_LIVE, "live": True,
                    "blocker": "", "accounts": accounts,
                    "sends_from": self._resolve_from(accounts, DEFAULT_FROM)}
        except Exception as exc:  # noqa: BLE001
            return {"name": self.name, "status": STATUS_UNAVAILABLE,
                    "live": False, "accounts": [],
                    "blocker": "%s (%s)" % (self.BLOCKER, type(exc).__name__)}
        finally:
            self._release()

    @staticmethod
    def _resolve_from(accounts, wanted: str) -> str:
        """The mailbox mail will actually leave from.

        Returns empty when the wanted account is not on this machine, rather
        than falling back to whichever account happens to be first -- a silent
        substitution puts a personal address on a broker's arrival notice.
        """
        for address in accounts or []:
            if str(address).strip().lower() == str(wanted).strip().lower():
                return str(address)
        return ""

    def _compose(self, app, to, subject, body, *, bcc="", cc="",
                 send_from=DEFAULT_FROM, attachments=None):
        if str(send_from).strip().lower() not in [
                m.lower() for m in APPROVED_MAILBOXES]:
            raise MailError(
                "%s is not an approved mailbox. Approved: %s"
                % (send_from, ", ".join(APPROVED_MAILBOXES)))

        recipients = to if isinstance(to, str) else "; ".join(to or [])
        if not recipients.strip():
            raise MailError("No recipient. Nothing was sent or drafted.")

        item = app.CreateItem(_OL_MAIL_ITEM)
        item.To = recipients
        item.Subject = str(subject or "")
        item.Body = str(body or "")
        if cc:
            item.CC = cc if isinstance(cc, str) else "; ".join(cc)
        if bcc:
            item.BCC = bcc if isinstance(bcc, str) else "; ".join(bcc)

        # Send from the operations mailbox when it is present on this machine.
        # When it is not, the message is still composed and the caller is told
        # which account it will leave from -- guessing is worse than saying.
        accounts = app.GetNamespace("MAPI").Accounts
        for account in accounts:
            if str(account.SmtpAddress).strip().lower() == send_from.lower():
                item.SendUsingAccount = account
                break

        for path in attachments or []:
            try:
                item.Attachments.Add(str(path))
            except Exception as exc:  # noqa: BLE001
                raise MailError("Could not attach %s (%s)"
                                % (path, type(exc).__name__)) from exc
        return item

    def draft(self, to, subject, body, *, bcc="", cc="",
              send_from=DEFAULT_FROM, attachments=None) -> dict:
        """Prepare it and leave it in Drafts. **Nothing is sent.**

        This is the final delivery packet's path. A person reads it and a
        person presses send, which is why this cannot become `send()` by
        accident: they are different methods with different names in the
        record.
        """
        app, blocker = self._app()
        if app is None:
            return {"ok": False, "sent": False, "drafted": False,
                    "status": STATUS_UNAVAILABLE, "blocker": blocker}
        try:
            item = self._compose(app, to, subject, body, bcc=bcc, cc=cc,
                                 send_from=send_from, attachments=attachments)
            item.Save()
            return {"ok": True, "sent": False, "drafted": True,
                    "status": STATUS_LIVE, "blocker": "",
                    "subject": str(subject or ""),
                    "note": "In your Drafts. Read it, then send it yourself.",
                    "prepared_at": datetime.now(timezone.utc).isoformat()}
        except MailError as exc:
            return {"ok": False, "sent": False, "drafted": False,
                    "status": STATUS_LIVE, "blocker": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "sent": False, "drafted": False,
                    "status": STATUS_UNAVAILABLE,
                    "blocker": "%s (%s)" % (self.BLOCKER, type(exc).__name__)}
        finally:
            self._release()

    def send(self, to, subject, body, *, bcc="", cc="",
             send_from=DEFAULT_FROM, attachments=None) -> dict:
        """Send it now. Used by the Arrival Notice and by nothing else yet.

        The notice auto-sends because its purpose is on-time arrival evidence
        independent of the warehouse gate. Everything else in the closeout
        sequence goes through `draft()`.
        """
        app, blocker = self._app()
        if app is None:
            return {"ok": False, "sent": False, "drafted": False,
                    "status": STATUS_UNAVAILABLE, "blocker": blocker}
        try:
            item = self._compose(app, to, subject, body, bcc=bcc, cc=cc,
                                 send_from=send_from, attachments=attachments)
            item.Send()
            return {"ok": True, "sent": True, "drafted": False,
                    "status": STATUS_LIVE, "blocker": "",
                    "subject": str(subject or ""),
                    "sent_at": datetime.now(timezone.utc).isoformat()}
        except MailError as exc:
            return {"ok": False, "sent": False, "drafted": False,
                    "status": STATUS_LIVE, "blocker": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "sent": False, "drafted": False,
                    "status": STATUS_UNAVAILABLE,
                    "blocker": "%s (%s)" % (self.BLOCKER, type(exc).__name__)}
        finally:
            self._release()
