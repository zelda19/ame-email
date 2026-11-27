from __future__ import annotations

from dataclasses import dataclass, replace
from secrets import token_urlsafe
from threading import Lock
from time import monotonic

from .classify import LABELS, Decision, classify
from .mailbox import Mailbox, MailboxUnavailable, Message


SCAN_LIMIT = 50
PREVIEW_SECONDS = 15 * 60
OUTCOMES = ("Applied", "Already labeled", "Failed", "Unverified", "Unprocessed")
MANAGED_LABELS = frozenset(LABELS.values())


@dataclass(frozen=True)
class PreviewRow:
    sender: str
    subject: str
    received: str
    decision: Decision
    status: str


@dataclass
class Run:
    id: str
    expires_at: float
    count: int
    unreadable: int
    rows: dict[str, PreviewRow]
    state: str = "pending"
    outcomes: tuple[Outcome, ...] = ()


@dataclass(frozen=True)
class Outcome:
    row: PreviewRow
    status: str
    reason: str = ""


class RunMissing(Exception):
    pass


class RunExpired(Exception):
    pass


class InvalidSelection(Exception):
    pass


def label_status(message: Message, category: str) -> str:
    if LABELS[category] in message.labels:
        return "Already labeled"
    if MANAGED_LABELS.intersection(message.labels):
        return "Conflicting label"
    return "Proposed"


class Workflow:
    def __init__(self, mailbox: Mailbox, *, clock=None):
        self.mailbox = mailbox
        self.clock = monotonic if clock is None else clock
        self.runs: dict[str, Run] = {}
        self.lock = Lock()
        self.write_lock = Lock()

    def preview(self, owner: str) -> str:
        ids = dict.fromkeys(self.mailbox.list_inbox_ids(SCAN_LIMIT)[:SCAN_LIMIT])
        rows = {}
        unreadable = 0
        for message_id in ids:
            try:
                message = self.mailbox.read_message(message_id)
            except MailboxUnavailable:
                raise
            except (LookupError, OSError):
                unreadable += 1
                continue
            if not message.in_inbox:
                continue
            decision = classify(message.subject, message.text)
            if decision.disposition == "unrelated":
                continue
            status = label_status(message, decision.category) if decision.category else "Needs review"
            rows[message_id] = PreviewRow(
                message.sender, message.subject, message.received, decision, status,
            )
        with self.lock:
            current = self.runs.get(owner)
            if current and current.state == "processing":
                return current.id
            run = Run(token_urlsafe(24), self.clock() + PREVIEW_SECONDS, len(ids), unreadable, rows)
            self.runs[owner] = run
            return run.id

    def _lookup(self, owner, run_id):
        run = self.runs.get(owner)
        if run is None or run.id != run_id:
            raise RunMissing
        if run.state == "pending" and self.clock() >= run.expires_at:
            run.rows = {}
            raise RunExpired
        return run

    def get(self, owner, run_id):
        with self.lock:
            return replace(self._lookup(owner, run_id))

    def cancel(self, owner, run_id):
        with self.lock:
            run = self._lookup(owner, run_id)
            if run.state != "pending":
                return False
            del self.runs[owner]
            return True

    def confirm(self, owner, run_id, selection):
        with self.lock:
            run = self._lookup(owner, run_id)
            if run.state != "pending":
                return
            selected = dict.fromkeys(selection)
            if not selected or any(
                key not in run.rows or run.rows[key].status != "Proposed" for key in selected
            ):
                raise InvalidSelection
            run.state = "processing"
        outcomes = []
        interrupted = False
        try:
            # Serialize rechecks and writes across browser sessions sharing this mailbox.
            with self.write_lock:
                for key in selected:
                    row = run.rows[key]
                    if interrupted:
                        outcomes.append(Outcome(row, "Unprocessed", "Mailbox access was interrupted."))
                        continue
                    outcome, interrupted = self._apply(key, row)
                    outcomes.append(outcome)
        finally:
            with self.lock:
                for key in list(selected)[len(outcomes):]:
                    outcomes.append(Outcome(run.rows[key], "Unverified", "Confirmation was interrupted."))
                run.outcomes = tuple(outcomes)
                run.state = "complete"

    def _apply(self, message_id, row):
        category = row.decision.category
        try:
            message = self.mailbox.read_message(message_id)
        except MailboxUnavailable:
            return Outcome(row, "Unprocessed", "Mailbox access was interrupted."), True
        except LookupError:
            return Outcome(row, "Unprocessed", "Message could not be found."), False
        except OSError:
            return Outcome(row, "Unprocessed", "Message could not be checked."), False
        if not message.in_inbox:
            return Outcome(row, "Unprocessed", "Message left the inbox."), False
        status = label_status(message, category)
        if status == "Already labeled":
            return Outcome(row, status), False
        if status == "Conflicting label":
            return Outcome(row, "Unprocessed", "Message has a conflicting label."), False
        try:
            self.mailbox.apply_category(message_id, category)
        except MailboxUnavailable:
            return Outcome(row, "Unverified", "Mailbox access was interrupted during the write."), True
        except TimeoutError:
            return Outcome(row, "Unverified", "The label operation timed out."), False
        except LookupError:
            return Outcome(row, "Unprocessed", "Message could not be found."), False
        except OSError:
            return Outcome(row, "Failed", "The mailbox rejected the label."), False
        return Outcome(row, "Applied"), False
