import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Message:
    id: str
    sender: str
    subject: str
    received: str
    text: str
    labels: tuple[str, ...] = ()


class Mailbox(Protocol):
    def list_inbox_ids(self, limit: int) -> list[str]: ...
    def read_message(self, message_id: str) -> Message: ...


class MockMailbox:
    def __init__(self):
        fixture = Path(__file__).with_name("fixtures") / "inbox.json"
        messages = (Message(**row) for row in json.loads(fixture.read_text(encoding="utf-8")))
        self.messages = {message.id: message for message in messages}

    def list_inbox_ids(self, limit):
        return list(self.messages)[:limit]

    def read_message(self, message_id):
        return self.messages[message_id]
