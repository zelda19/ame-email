import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from recruitment_mail import create_app
from recruitment_mail.gmail import connect_gmail
from recruitment_mail.mailbox import MailboxUnavailable
from test_gmail import ACCOUNT, FakeHttpError, FakeTransport


CLIENT_FILE = "/synthetic-oauth/desktop.json"


@pytest.fixture
def provider(monkeypatch):
    class OAuthError(Exception):
        pass

    class CallbackTimeout(Exception):
        pass

    transport = FakeTransport()
    desktop_config = {"installed": {"client_id": "synthetic", "client_secret": "synthetic"}}
    provider = SimpleNamespace(
        transport=transport, config=desktop_config, calls=[], callback="matched",
    )

    original_read_text = Path.read_text

    def read_text(path, *args, **kwargs):
        if str(path) == CLIENT_FILE:
            assert kwargs.get("encoding") == "utf-8"
            return json.dumps(provider.config)
        return original_read_text(path, *args, **kwargs)

    def start_flow(config, **options):
        provider.calls.append(("configure", config, options))
        return SimpleNamespace(run_local_server=receive_callback)

    def receive_callback(**options):
        provider.calls.append(("loopback", options))
        if provider.callback == "timeout":
            raise CallbackTimeout("synthetic callback details")
        state = options["state"]
        callback_state = state if provider.callback == "matched" else "invalid-state"
        if state != callback_state:
            raise OAuthError("synthetic invalid state details")
        return "synthetic-token"

    def build(api, version, **options):
        provider.calls.append(("build", api, version, options))
        return transport

    modules = {
        "google.auth.exceptions": dict(GoogleAuthError=OAuthError, RefreshError=OAuthError, TransportError=OAuthError),
        "google_auth_httplib2": dict(AuthorizedHttp=lambda credentials, **kw: (credentials, kw)),
        "google_auth_oauthlib.flow": dict(
            InstalledAppFlow=SimpleNamespace(from_client_config=start_flow), WSGITimeoutError=CallbackTimeout,
        ),
        "googleapiclient.discovery": dict(build=build),
        "googleapiclient.errors": dict(HttpError=FakeHttpError),
        "httplib2": dict(Http=lambda **kw: kw, HttpLib2Error=OSError),
        "oauthlib.oauth2": dict(OAuth2Error=OAuthError),
        "requests": dict(RequestException=OSError),
    }
    for name, exports in modules.items():
        monkeypatch.setitem(sys.modules, name, SimpleNamespace(**exports))
    monkeypatch.setattr(Path, "read_text", read_text)
    return provider


def test_connect_gmail_configures_loopback_and_verifies_before_access(provider):
    mailbox = connect_gmail(ACCOUNT, CLIENT_FILE)
    assert mailbox.account_address == ACCOUNT
    assert provider.calls[0] == (
        "configure", provider.config,
        {"scopes": ["https://www.googleapis.com/auth/gmail.modify"], "autogenerate_code_verifier": True},
    )
    options = provider.calls[1][1]
    assert (options["host"], options["port"], options["timeout_seconds"]) == ("127.0.0.1", 0, 180)
    assert options["open_browser"] is False
    assert len(options["state"]) >= 32
    mailbox.list_inbox_ids(50)
    assert [name for name, _ in provider.transport.calls] == ["profile", "messages.list"]


@pytest.mark.parametrize("callback", ["mismatched", "timeout"])
def test_rejected_callback_blocks_gmail_startup(provider, monkeypatch, callback):
    provider.callback = callback
    monkeypatch.setenv("RECRUITMENT_MAIL_MODE", "gmail")
    monkeypatch.setenv("RECRUITMENT_GMAIL_ACCOUNT", ACCOUNT)
    monkeypatch.setenv("RECRUITMENT_GMAIL_CLIENT_FILE", CLIENT_FILE)
    response = create_app().test_client().get("/")
    assert b"Gmail authorization or profile verification failed" in response.data
    assert b"synthetic" not in response.data
    assert b"Preview inbox" not in response.data
    assert [name for name, *_ in provider.calls] == ["configure", "loopback"]
    assert provider.transport.calls == []


def test_connect_gmail_rejects_web_credentials_before_starting_oauth(provider):
    provider.config = {"web": provider.config["installed"]}
    with pytest.raises(MailboxUnavailable, match="desktop OAuth credentials"):
        connect_gmail(ACCOUNT, CLIENT_FILE)
    assert provider.calls == []
    assert provider.transport.calls == []


def test_connect_gmail_rejects_wrong_profile_without_mailbox_access(provider):
    provider.transport.account = "other@example.test"
    with pytest.raises(MailboxUnavailable, match="does not match"):
        connect_gmail(ACCOUNT, CLIENT_FILE)
    assert [name for name, _ in provider.transport.calls] == ["profile"]
