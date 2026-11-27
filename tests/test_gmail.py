from base64 import urlsafe_b64encode
from email.message import EmailMessage
import json
from types import SimpleNamespace

import pytest

from recruitment_mail import create_app
from recruitment_mail.gmail import GmailMailbox
from recruitment_mail.mailbox import MailboxUnavailable


from test_confirmation import confirm, open_preview


ACCOUNT = "dedicated@example.test"


class FakeHttpError(Exception):
    def __init__(self, status, reason):
        self.resp = SimpleNamespace(status=status)
        self.content = json.dumps({"error": {"errors": [{"reason": reason}]}}).encode()


class FakeTransport:
    def __init__(self, account=ACCOUNT):
        self.account = account
        self.calls = []
        self.inbox = {}
        self.user_labels = {}
        self.write_errors = {}

    def users(self):
        return self

    def messages(self):
        return FakeResource(self, "messages")

    def labels(self):
        return FakeResource(self, "labels")

    def getProfile(self, **params):
        return self.request("profile", params, lambda: {"emailAddress": self.account})

    def add_message(self, message_id, message):
        self.inbox[message_id] = {
            "id": message_id, "labelIds": ["INBOX", "STARRED"], "internalDate": "1764244800000",
            "raw": urlsafe_b64encode(message.as_bytes()).decode().rstrip("="),
        }

    def request(self, name, params, response):
        def execute(*, num_retries):
            assert num_retries == 0
            self.calls.append((name, params))
            return response()
        return SimpleNamespace(execute=execute)

    def mailbox(self):
        return GmailMailbox(self, ACCOUNT, http_error=FakeHttpError)


class FakeResource:
    def __init__(self, transport, name):
        self.transport = transport
        self.name = name

    def list(self, **params):
        def response():
            if self.name == "labels":
                return {"labels": list(self.transport.user_labels.values())}
            return {"messages": [{"id": key} for key in self.transport.inbox]}
        return self.transport.request(f"{self.name}.list", params, response)

    def get(self, **params):
        return self.transport.request("messages.get", params, lambda: self.transport.inbox[params["id"]])

    def create(self, **params):
        def response():
            name = params["body"]["name"]
            label = {"id": f"label-{len(self.transport.user_labels)}", "name": name, "type": "user"}
            self.transport.user_labels[name] = label
            return label
        return self.transport.request("labels.create", params, response)

    def modify(self, **params):
        def response():
            message_id = params["id"]
            error = self.transport.write_errors.get(message_id)
            if error and not isinstance(error, TimeoutError):
                raise error
            message = self.transport.inbox[message_id]
            message["labelIds"].extend(params["body"]["addLabelIds"])
            if error:
                raise error
            return message
        return self.transport.request("messages.modify", params, response)


def test_account_mismatch_stops_before_mailbox_access():
    transport = FakeTransport("other@example.test")
    with pytest.raises(MailboxUnavailable, match="does not match"):
        transport.mailbox()
    assert transport.calls == [("profile", {"userId": "me"})]


def make_message(body, *, subtype="plain"):
    message = EmailMessage()
    message["From"] = "Fictional Hiring <hiring@example.test>"
    message["Subject"] = "Hiring update"
    message.set_content(body, subtype=subtype)
    return message


def test_preview_normalizes_html_and_never_writes():
    transport = FakeTransport()
    message = make_message(
        "<p>Thank you for <b>applying</b>.</p>"
        "<script>Please complete the hiring test.</script>"
        '<div class="gmail_quote">Please schedule an interview.</div>'
        "<blockquote>Please reply.</blockquote>",
        subtype="html",
    )
    message.add_attachment("Please complete the coding exercise.", filename="old.txt")
    transport.add_message("receipt", message)
    client = create_app(transport.mailbox()).test_client()
    run, _ = open_preview(client)
    page = client.get(run).get_data(as_text=True)
    assert "Application confirmation</td>" in page
    assert "<td>No</td>" in page
    assert "Fictional Hiring &lt;hiring@example.test&gt;" in page
    assert "UTC" in page
    assert transport.calls[1] == (
        "messages.list", {"userId": "me", "labelIds": ["INBOX"], "maxResults": 50},
    )
    assert {name for name, _ in transport.calls} == {"profile", "messages.list", "messages.get", "labels.list"}


@pytest.mark.parametrize("existing", [False, True])
def test_confirmation_adds_only_the_selected_category(existing):
    transport = FakeTransport()
    name = "Recruitment - Application confirmation"
    if existing:
        transport.user_labels[name] = {"id": "existing-label", "name": name, "type": "user"}
    transport.user_labels["Recruitment - application confirmation"] = {
        "id": "different-case", "name": "Recruitment - application confirmation", "type": "user",
    }
    receipt = make_message("We received your application.")
    receipt.add_alternative("<p>Please complete the coding exercise.</p>", subtype="html")
    transport.add_message("selected", receipt)
    transport.add_message("deselected", make_message("Thank you for applying."))
    mailbox = transport.mailbox()
    client = create_app(mailbox).test_client()
    run, token = open_preview(client)
    assert client.post(run + "/cancel", data={"csrf_token": token}).status_code == 303
    run, token = open_preview(client)
    assert confirm(client, run, token, ["selected", "deselected", "forged"]).status_code == 400
    assert not any(method.endswith((".create", ".modify")) for method, _ in transport.calls)
    with pytest.raises(ValueError):
        mailbox.apply_category("selected", "STARRED")

    assert confirm(client, run, token, ["selected"]).status_code == 303
    assert "Applied: 1" in client.get(run).get_data(as_text=True)
    assert confirm(client, run, token, ["selected"]).status_code == 303
    label_id = "existing-label" if existing else "label-1"
    writes = [
        (method, params) for method, params in transport.calls if method.endswith((".create", ".modify"))
    ]
    expected = [] if existing else [("labels.create", {"userId": "me", "body": {"name": name}})]
    expected.append((
        "messages.modify", {"userId": "me", "id": "selected", "body": {"addLabelIds": [label_id]}},
    ))
    assert writes == expected
    assert transport.inbox["selected"]["labelIds"] == ["INBOX", "STARRED", label_id]
    assert transport.inbox["deselected"]["labelIds"] == ["INBOX", "STARRED"]


@pytest.mark.parametrize("status,reason", [(401, "authError"), (403, "userRateLimitExceeded"), (429, "rateLimitExceeded")])
def test_auth_or_rate_failure_stops_remaining_gmail_writes(status, reason):
    transport = FakeTransport()
    for key in ("success", "interrupted", "remaining"):
        transport.add_message(key, make_message("We received your application."))
    transport.write_errors["interrupted"] = FakeHttpError(status, reason)
    client = create_app(transport.mailbox()).test_client()
    run, token = open_preview(client)
    assert confirm(client, run, token, ["success", "interrupted", "remaining"]).status_code == 303
    results = client.get(run).get_data(as_text=True)
    for count in ("Applied: 1", "Unverified: 1", "Unprocessed: 1"):
        assert count in results
    assert [params["id"] for method, params in transport.calls if method == "messages.modify"] == [
        "success", "interrupted",
    ]


def test_timed_out_gmail_write_is_reconciled_on_rescan():
    transport = FakeTransport()
    transport.add_message("receipt", make_message("We received your application."))
    transport.write_errors["receipt"] = TimeoutError("synthetic lost response")
    client = create_app(transport.mailbox()).test_client()
    run, token = open_preview(client)
    assert confirm(client, run, token, ["receipt"]).status_code == 303
    assert "Unverified: 1" in client.get(run).get_data(as_text=True)
    next_run, _ = open_preview(client)
    preview = client.get(next_run).get_data(as_text=True)
    assert "Already labeled" in preview
    assert 'name="selected" value="receipt"' not in preview
    assert len([name for name, _ in transport.calls if name == "messages.modify"]) == 1


def test_explicit_gmail_mode_with_missing_configuration_blocks_preview(monkeypatch):
    monkeypatch.setenv("RECRUITMENT_MAIL_MODE", "gmail")
    monkeypatch.delenv("RECRUITMENT_GMAIL_ACCOUNT", raising=False)
    monkeypatch.delenv("RECRUITMENT_GMAIL_CLIENT_FILE", raising=False)
    client = create_app().test_client()
    page = client.get("/").get_data(as_text=True)
    assert "Dedicated Gmail test account" in page
    assert "Configure the dedicated Gmail test account" in page
    assert "Preview inbox" not in page
    with client.session_transaction() as session:
        token = session["csrf_token"]
    assert client.post("/preview", data={"csrf_token": token}).status_code == 503


def test_start_displays_verified_account_without_putting_it_in_session():
    transport = FakeTransport()
    client = create_app(transport.mailbox()).test_client()
    page = client.get("/").get_data(as_text=True)
    assert "Dedicated Gmail test account" in page
    assert ACCOUNT in page
    with client.session_transaction() as session:
        assert set(session) == {"csrf_token"}
    assert transport.calls == [("profile", {"userId": "me"})]


def test_each_preview_reuses_label_map_and_confirmation_checks_a_fresh_map():
    transport = FakeTransport()
    for key in ("receipt", "second"):
        transport.add_message(key, make_message("We received your application."))
    client = create_app(transport.mailbox()).test_client()
    run, token = open_preview(client)
    assert [name for name, _ in transport.calls].count("labels.list") == 1

    conflict = "Recruitment - Rejection"
    transport.user_labels[conflict] = {"id": "new-label", "name": conflict, "type": "user"}
    transport.inbox["receipt"]["labelIds"].append("new-label")
    assert confirm(client, run, token, ["receipt"]).status_code == 303
    assert "Message has a conflicting label." in client.get(run).get_data(as_text=True)
    assert [name for name, _ in transport.calls].count("labels.list") == 2
    assert not any(name in {"labels.create", "messages.modify"} for name, _ in transport.calls)

    refreshed, _ = open_preview(client)
    assert "Conflicting label" in client.get(refreshed).get_data(as_text=True)
    assert [name for name, _ in transport.calls].count("labels.list") == 3


@pytest.mark.parametrize("subtype", ["plain", "html"])
def test_preview_flags_indirect_interview_availability_request(subtype):
    request_text = "Could you confirm whether you’re available on Tuesday?"
    body = request_text if subtype == "plain" else f"<p>{request_text}</p>"
    message = make_message(body, subtype=subtype)
    message.replace_header("Subject", "Interview invitation")
    transport = FakeTransport()
    transport.add_message("interview", message)
    mailbox = transport.mailbox()

    assert request_text in mailbox.read_message("interview").text
    client = create_app(mailbox).test_client()
    run, _ = open_preview(client)
    page = " ".join(client.get(run).get_data(as_text=True).split())
    assert "<td>Interview invitation</td> <td>Yes</td>" in page


@pytest.mark.parametrize(("creation_error", "creation_reason"), [
    (True, "HTTP 503"),
    (False, "unexpected label response"),
])
def test_confirmation_distinguishes_unverified_creation_and_modification(creation_error, creation_reason):
    class InterruptedTransport(FakeTransport):
        def request(self, name, params, response):
            if name == "labels.create":
                def interrupted_creation():
                    if creation_error:
                        raise FakeHttpError(503, "synthetic provider body")
                    result = dict(response())
                    del result["type"]
                    return result

                return super().request(name, params, interrupted_creation)
            return super().request(name, params, response)

    transport = InterruptedTransport()
    receipt_label = "Recruitment - Application confirmation"
    transport.user_labels[receipt_label] = {"id": "receipt-label", "name": receipt_label, "type": "user"}
    transport.add_message("receipt", make_message("We received your application."))
    transport.add_message("interview", make_message("Please schedule your interview."))
    transport.write_errors["receipt"] = TimeoutError("synthetic transport details")
    client = create_app(transport.mailbox()).test_client()
    run, token = open_preview(client)
    assert confirm(client, run, token, ["interview", "receipt"]).status_code == 303
    page = client.get(run).get_data(as_text=True)
    for count in ("Selected: 2", "Applied: 0", "Already labeled: 0", "Failed: 0", "Unverified: 2", "Unprocessed: 0"):
        assert count in page
    assert f"Gmail label creation was unverified ({creation_reason})." in page
    assert "Gmail message modification was unverified (transport timed out)." in page
    assert "synthetic" not in page
    assert [name for name, _ in transport.calls if name in {"labels.create", "messages.modify"}] == [
        "labels.create", "messages.modify",
    ]
