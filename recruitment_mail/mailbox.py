import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from .classify import LABELS


@dataclass(frozen=True)
class Message:
    id: str
    sender: str
    subject: str
    received: str
    text: str
    labels: tuple[str, ...] = ()
    in_inbox: bool = True


class MailboxUnavailable(OSError):
    """A mailbox-wide failure that prevents further writes."""


class Mailbox(Protocol):
    def list_inbox_ids(self, limit: int) -> list[str]: ...
    def read_message(self, message_id: str) -> Message: ...
    def apply_category(self, message_id: str, category: str) -> None: ...


class MockMailbox:
    def __init__(self):
        fixture = Path(__file__).with_name("fixtures") / "inbox.json"
        messages = (Message(**row) for row in json.loads(fixture.read_text(encoding="utf-8")))
        self.messages = {message.id: message for message in messages}

    def list_inbox_ids(self, limit):
        return [message.id for message in self.messages.values() if message.in_inbox][:limit]

    def read_message(self, message_id):
        return self.messages[message_id]

    def apply_category(self, message_id: str, category: str) -> None:
        label = LABELS[category]
        message = self.read_message(message_id)
        if label not in message.labels:
            self.messages[message_id] = replace(message, labels=(*message.labels, label))
