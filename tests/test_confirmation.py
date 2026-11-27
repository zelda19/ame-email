from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

import re

from recruitment_mail import create_app
from recruitment_mail.mailbox import MockMailbox


def open_preview(client):
    page = client.get("/").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page)[1]
    response = client.post("/preview", data={"csrf_token": token})
    return response.location, token


def confirm(client, run, token, ids):
    return client.post(run + "/confirm", data={"csrf_token": token, "selected": ids})


def test_confirmation_only_applies_selected_message():
    mailbox = MockMailbox()
    client = create_app(mailbox).test_client()
    run, token = open_preview(client)
    assert confirm(client, run, token, ["receipt", "receipt"]).status_code == 303
    assert "Applied: 1" in client.get(run).get_data(as_text=True)
    assert mailbox.read_message("receipt").labels == ("Recruitment - Application confirmation",)
    assert mailbox.read_message("interview").labels == ()


@pytest.mark.parametrize("ids", [[], ["missing"], ["receipt", "ambiguous"]])
def test_invalid_selection_cannot_partially_apply(ids):
    mailbox = MockMailbox()
    client = create_app(mailbox).test_client()
    run, token = open_preview(client)
    assert confirm(client, run, token, ids).status_code == 400
    assert mailbox.read_message("receipt").labels == ()


def test_cancel_invalidates_preview_and_checks_csrf_and_owner():
    mailbox = MockMailbox()
    app = create_app(mailbox)
    owner = app.test_client()
    stranger = app.test_client()
    run, token = open_preview(owner)
    _, stranger_token = open_preview(stranger)
    assert stranger.get(run).status_code == 404
    assert confirm(stranger, run, stranger_token, ["receipt"]).status_code == 404
    assert confirm(owner, run, "forged", ["receipt"]).status_code == 403
    assert owner.post(run + "/cancel", data={"csrf_token": "forged"}).status_code == 403
    assert owner.post(run + "/cancel", data={"csrf_token": token}).status_code == 303
    assert confirm(owner, run, token, ["receipt"]).status_code == 404
    assert mailbox.read_message("receipt").labels == ()


def test_preview_expires_after_fifteen_minutes():
    now = [0]
    mailbox = MockMailbox()
    client = create_app(mailbox, clock=lambda: now[0]).test_client()
    run, token = open_preview(client)
    now[0] = 899
    assert client.get(run).status_code == 200
    now[0] = 900
    assert confirm(client, run, token, ["receipt"]).status_code == 410
    assert mailbox.read_message("receipt").labels == ()


class FailOnceMailbox(MockMailbox):
    def __init__(self):
        super().__init__()
        self.attempts = []

    def apply_category(self, message_id, category):
        self.attempts.append(message_id)
        if message_id == "assessment" and self.attempts.count(message_id) == 1:
            raise OSError("synthetic failure")
        super().apply_category(message_id, category)


def test_mixed_result_rechecks_labels_and_rescan_retries_only_unresolved():
    mailbox = FailOnceMailbox()
    client = create_app(mailbox).test_client()
    run, token = open_preview(client)
    mailbox.apply_category("interview", "Interview invitation")
    mailbox.apply_category("rejection", "Response request")
    assert confirm(client, run, token, ["receipt", "interview", "assessment", "rejection"]).status_code == 303
    results = client.get(run).get_data(as_text=True)
    for count in ("Selected: 4", "Applied: 1", "Already labeled: 1", "Failed: 1", "Unverified: 0", "Unprocessed: 1"):
        assert count in results
    assert mailbox.attempts == ["interview", "rejection", "receipt", "assessment"]
    assert confirm(client, run, token, ["receipt", "assessment"]).status_code == 303
    assert client.get(run).get_data(as_text=True) == results
    retry, token = open_preview(client)
    preview = client.get(retry).get_data(as_text=True)
    assert "Already labeled" in preview and "Conflicting label" in preview
    for message_id in ("receipt", "interview", "rejection"):
        assert f'name="selected" value="{message_id}"' not in preview
    assert 'name="selected" value="assessment" checked' in preview
    assert confirm(client, retry, token, ["assessment"]).status_code == 303
    assert mailbox.attempts == ["interview", "rejection", "receipt", "assessment", "assessment"]
    assert "Applied: 1" in client.get(retry).get_data(as_text=True)
    assert client.get(run).status_code == 404


def test_concurrent_confirmation_claims_run_once():
    entered = Event()
    release = Event()

    class SlowMailbox(MockMailbox):
        attempts = 0

        def apply_category(self, message_id, category):
            self.attempts += 1
            entered.set()
            assert release.wait(5)
            super().apply_category(message_id, category)

    mailbox = SlowMailbox()
    app = create_app(mailbox)
    first = app.test_client()
    second = app.test_client()
    run, token = open_preview(first)
    second.set_cookie("session", first.get_cookie("session").value)
    with ThreadPoolExecutor(max_workers=1) as executor:
        in_flight = executor.submit(confirm, first, run, token, ["receipt"])
        try:
            assert entered.wait(5)
            assert confirm(second, run, token, ["receipt"]).status_code == 303
            assert "Confirmation is in progress." in second.get(run).get_data(as_text=True)
        finally:
            release.set()
        assert in_flight.result(timeout=5).status_code == 303
    assert mailbox.attempts == 1
    assert "Applied: 1" in second.get(run).get_data(as_text=True)


def test_timeout_is_reconciled_and_mailbox_wide_failure_stops_remaining_writes():
    from recruitment_mail.mailbox import MailboxUnavailable

    class InterruptedMailbox(MockMailbox):
        def apply_category(self, message_id, category):
            if message_id == "interview":
                raise MailboxUnavailable("synthetic access loss")
            super().apply_category(message_id, category)
            if message_id == "receipt":
                raise TimeoutError("synthetic lost response")

    mailbox = InterruptedMailbox()
    client = create_app(mailbox).test_client()
    run, token = open_preview(client)
    assert confirm(client, run, token, ["receipt", "interview", "assessment"]).status_code == 303
    results = client.get(run).get_data(as_text=True)
    assert "Unverified: 2" in results and "Unprocessed: 1" in results
    assert mailbox.read_message("assessment").labels == ()
    retry, _ = open_preview(client)
    assert 'name="selected" value="receipt"' not in client.get(retry).get_data(as_text=True)


def test_confirmation_skips_message_that_left_inbox():
    from dataclasses import replace

    class MovedMailbox(MockMailbox):
        moved = False

        def read_message(self, message_id):
            message = super().read_message(message_id)
            if self.moved and message_id == "receipt":
                return replace(message, in_inbox=False)
            return message

    mailbox = MovedMailbox()
    client = create_app(mailbox).test_client()
    run, token = open_preview(client)
    mailbox.moved = True
    assert confirm(client, run, token, ["receipt", "assessment"]).status_code == 303
    results = client.get(run).get_data(as_text=True)
    assert "Message left the inbox." in results
    assert "Unprocessed: 1" in results and "Applied: 1" in results
    assert mailbox.read_message("receipt").labels == ()
