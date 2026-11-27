import pytest


@pytest.fixture(autouse=True)
def isolate_mailbox_environment(monkeypatch):
    monkeypatch.setenv("RECRUITMENT_MAIL_MODE", "mock")
    monkeypatch.delenv("RECRUITMENT_GMAIL_ACCOUNT", raising=False)
    monkeypatch.delenv("RECRUITMENT_GMAIL_CLIENT_FILE", raising=False)
