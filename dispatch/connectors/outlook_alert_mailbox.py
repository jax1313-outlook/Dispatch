"""Load-board alert emails, read out of one Outlook folder on this machine. READ-ONLY.

The adapter behind `dispatch/connectors/alert_mailbox.py`. Outlook is already
installed and signed in to the operations mailbox, so the alerts are read the
way he reads them: from his own profile, out of the folder his own rule sorts
them into. There is no password here and no mail server.

**Read-only, and the shape of the code is what holds it.** This module reads
properties -- sender, subject, received time, body, the message's id -- and
calls nothing that changes a message or a folder: no send, reply, forward,
move, copy, delete, save, flag, category or read/unread change. Reading a
property does not mark a message read in Outlook. Which messages Dispatch has
handled is remembered in Dispatch's own store. `tests/test_load_alerts.py`
scans this file for every write call Outlook offers and fails if one appears.

**Never starts Outlook.** Attaching to a running Outlook is instant; asking COM
to start one produces a headless instance that wedges every call after it, so
`_outlook_is_running` is checked before anything touches COM -- the same guard
`outlook_mail.py` and `scheduling.py` use, and the one tests patch to False.

It creates no Outlook rule and no folder. Mike makes the rule and the folder
himself (`docs/operations/LOAD_ALERT_EMAILS.md`); when the folder is not there,
this says so.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dispatch.connectors.alert_mailbox import (
    STATUS_LIVE,
    STATUS_UNAVAILABLE,
    STATUS_UNCONFIGURED,
    AlertMailboxPort,
    answer,
    strip_html,
)

#: Outlook's item class for a mail message. Meeting requests, read receipts and
#: delivery reports in the folder are not alerts and are passed over.
_OL_MAIL = 43

#: Outlook's constant for a mailbox's Inbox, where a rule's folder often lives.
_OL_INBOX = 6


def _outlook_is_running() -> bool:
    """Whether Outlook is open right now. Checked before any COM call.

    The same check as `outlook_mail._outlook_is_running`, kept here rather than
    imported so this adapter can be lifted out on its own (THE MIKE RULE) and so
    a test patches the guard of the adapter it is exercising.
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AlertFolderAdapter(AlertMailboxPort):
    """Reads one folder of one approved mailbox, through Outlook on this machine."""

    name = "outlook_alert_folder"

    NOT_RUNNING = ("Outlook is not open on this machine. Load alerts are read through "
                   "Outlook, so nothing was checked. Open Outlook and check again.")
    NOT_INSTALLED = "The Outlook connection is not installed on this machine."

    def read_since(self, *, mailbox: str, folder: str, since=None, limit: int = 200,
                   known=()) -> dict:
        mailbox = str(mailbox or "").strip()
        folder = str(folder or "").strip()
        if not mailbox or not folder:
            return answer(STATUS_UNCONFIGURED, mailbox=mailbox, folder=folder,
                          reason="No mailbox or folder is set for load alerts.",
                          checked_at=_now_iso())

        from dispatch.connectors.outlook_mail import APPROVED_MAILBOXES

        if mailbox.lower() not in [m.lower() for m in APPROVED_MAILBOXES]:
            return answer(STATUS_UNCONFIGURED, mailbox=mailbox, folder=folder,
                          reason="%s is not an approved mailbox. Approved: %s"
                          % (mailbox, ", ".join(APPROVED_MAILBOXES)),
                          checked_at=_now_iso())

        if not _outlook_is_running():
            return answer(STATUS_UNAVAILABLE, mailbox=mailbox, folder=folder,
                          reason=self.NOT_RUNNING, checked_at=_now_iso())
        try:
            import pythoncom
            import win32com.client
        except ImportError:
            return answer(STATUS_UNAVAILABLE, mailbox=mailbox, folder=folder,
                          reason=self.NOT_INSTALLED, checked_at=_now_iso())

        try:
            pythoncom.CoInitialize()
        except Exception:  # noqa: BLE001
            return answer(STATUS_UNAVAILABLE, mailbox=mailbox, folder=folder,
                          reason=self.NOT_RUNNING, checked_at=_now_iso())
        try:
            namespace = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
            target, why = self._find_folder(namespace, mailbox, folder)
            if target is None:
                return answer(STATUS_UNAVAILABLE, mailbox=mailbox, folder=folder,
                              reason=why, checked_at=_now_iso())
            messages = self._messages(target, since=since, limit=limit, known=known)
            return answer(STATUS_LIVE, mailbox=mailbox, folder=folder,
                          messages=messages, checked_at=_now_iso())
        except Exception as exc:  # noqa: BLE001 - COM raises many shapes
            return answer(STATUS_UNAVAILABLE, mailbox=mailbox, folder=folder,
                          reason="Outlook did not answer while reading the %s folder (%s). "
                          "Nothing was changed." % (folder, type(exc).__name__),
                          checked_at=_now_iso())
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:  # noqa: BLE001 - releasing must never raise
                pass

    # ----------------------------------------------------------------- reads

    @staticmethod
    def _find_folder(namespace, mailbox: str, folder: str):
        """The named folder in the named mailbox, looked for where a rule puts it.

        Directly under the mailbox, or under its Inbox. Nothing is created: a
        missing folder is reported, with where it was looked for.
        """
        wanted_box = mailbox.lower()
        wanted = folder.lower()
        root = None
        for store in namespace.Stores:
            if str(store.DisplayName).strip().lower() == wanted_box:
                root = store.GetRootFolder()
                break
        if root is None:
            for top in namespace.Folders:
                if str(top.Name).strip().lower() == wanted_box:
                    root = top
                    break
        if root is None:
            return None, ("The mailbox %s is not open in Outlook on this machine." % mailbox)

        places = [root]
        for child in root.Folders:
            if str(child.Name).strip().lower() == wanted:
                return child, ""
            if str(child.Name).strip().lower() == "inbox":
                places.append(child)
        for place in places[1:]:
            for child in place.Folders:
                if str(child.Name).strip().lower() == wanted:
                    return child, ""
        return None, ("There is no folder named \"%s\" in %s (looked at the top of the "
                      "mailbox and inside its Inbox). Make the folder and the rule, then "
                      "check again." % (folder, mailbox))

    @staticmethod
    def _sender(item) -> str:
        try:
            if str(item.SenderEmailType or "").upper() == "EX":
                user = item.Sender.GetExchangeUser()
                if user is not None and user.PrimarySmtpAddress:
                    return str(user.PrimarySmtpAddress)
        except Exception:  # noqa: BLE001 - fall through to the plain address
            pass
        return str(item.SenderEmailAddress or "")

    @staticmethod
    def _body(item) -> str:
        text = ""
        try:
            text = str(item.Body or "")
        except Exception:  # noqa: BLE001
            text = ""
        if text.strip():
            return text
        try:
            return strip_html(str(item.HTMLBody or ""))
        except Exception:  # noqa: BLE001
            return ""

    @classmethod
    def _messages(cls, target, *, since=None, limit: int = 200, known=()) -> list:
        known = set(known or ())
        items = target.Items
        items.Sort("[ReceivedTime]", True)
        if since is not None:
            # Outlook's filter reads local time, to the minute. A minute of
            # overlap is harmless: what was handled is remembered by id.
            local = since.astimezone() if since.tzinfo else since
            local = local - timedelta(minutes=1)
            items = items.Restrict("[ReceivedTime] >= '%s'"
                                   % local.strftime("%m/%d/%Y %I:%M %p"))
        found = []
        for item in items:
            if len(found) >= int(limit):
                break
            try:
                if int(item.Class) != _OL_MAIL:
                    continue
                received = item.ReceivedTime
                message_id = str(item.EntryID)
                found.append({
                    "message_id": message_id,
                    "sender": cls._sender(item),
                    "subject": str(item.Subject or ""),
                    "received_at": received.strftime("%Y-%m-%d %H:%M:%S"),
                    # Already handled: the body is not needed, so it is not read.
                    "body": "" if message_id in known else cls._body(item),
                })
            except Exception:  # noqa: BLE001 - one unreadable item is not a failed read
                continue
        return found
