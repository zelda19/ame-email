from dataclasses import dataclass

from .classify import Decision, classify
from .mailbox import Mailbox


SCAN_LIMIT = 50


@dataclass(frozen=True)
class PreviewRow:
    sender: str
    subject: str
    received: str
    decision: Decision


def preview_inbox(mailbox: Mailbox):
    ids = dict.fromkeys(mailbox.list_inbox_ids(SCAN_LIMIT)[:SCAN_LIMIT])
    rows = []
    unreadable = 0
    for message_id in ids:
        try:
            message = mailbox.read_message(message_id)
        except (LookupError, OSError):
            unreadable += 1
            continue
        decision = classify(message.subject, message.text)
        if decision.disposition != "unrelated":
            rows.append(PreviewRow(message.sender, message.subject, message.received, decision))
    return len(ids), unreadable, rows
