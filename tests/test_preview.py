import re

from recruitment_mail import create_app
from recruitment_mail.mailbox import Message


class FakeMailbox:
    def list_inbox_ids(self, limit):
        assert limit == 50
        return ["a", "a", "b"]

    def read_message(self, message_id):
        return Message(
            message_id, "<sender>", "<subject>", "2026-11-27 09:00 UTC",
            "We received your application.",
        )

    def apply_category(self, *args):
        raise AssertionError("Preview must never write to the mailbox")


def test_mock_preview_escapes_mail_and_deduplicates_ids():
    client = create_app(FakeMailbox()).test_client()
    start = client.get("/").get_data(as_text=True)
    assert "Mock inbox" in start
    assert client.post("/preview").status_code == 403
    token = re.search(r'name="csrf_token" value="([^"]+)"', start)[1]
    response = client.post("/preview", data={"csrf_token": token}, follow_redirects=True)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for column in ("Sender", "Subject", "Received", "Proposed category", "Attention required", "Status"):
        assert f'<th scope="col">{column}</th>' in html
    assert html.count("&lt;sender&gt;") == 2
    assert html.count("&lt;subject&gt;") == 2
    assert "<sender>" not in html and "<subject>" not in html


def test_default_inbox_exercises_supported_decisions():
    client = create_app().test_client()
    start = client.get("/").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', start)[1]
    response = client.post("/preview", data={"csrf_token": token}, follow_redirects=True)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    rows = " ".join(html.split())
    for category, attention in (
        ("Application confirmation", "No"),
        ("Interview invitation", "Yes"),
        ("Assessment invitation", "Yes"),
        ("Rejection", "No"),
        ("Response request", "Yes"),
    ):
        assert f"<td>{category}</td> <td>{attention}</td>" in rows
    assert "Needs review" in html
    assert html.count(">Hiring update</td>") == 2
    assert "Weekend recipes" not in html
    assert "Scanned 7 messages." in html
