from __future__ import annotations

from base64 import urlsafe_b64decode
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from functools import partial
from html.parser import HTMLParser
import json
import logging
from pathlib import Path
from secrets import token_urlsafe
import re
from threading import Lock

from .classify import LABELS
from .mailbox import MailboxUnavailable, Message, UnverifiedWrite


_SCOPE = "https://www.googleapis.com/auth/gmail.modify"


def connect_gmail(expected_address: str, client_file: str) -> GmailMailbox:
    if not expected_address.strip():
        raise MailboxUnavailable("Configure the dedicated Gmail test account address and restart.")
    if not client_file.strip():
        raise MailboxUnavailable("Configure an external desktop OAuth client file and restart.")
    try:
        path = Path(client_file).expanduser().resolve()
        if path.is_relative_to(Path.cwd()) or path.is_relative_to(Path(__file__).resolve().parents[1]):
            raise MailboxUnavailable("Keep the desktop OAuth client file outside the project directory.")
    except MailboxUnavailable:
        raise
    except (OSError, RuntimeError, ValueError):
        raise MailboxUnavailable("Configure a valid external desktop OAuth client file and restart.") from None

    try:
        from google.auth.exceptions import GoogleAuthError, RefreshError, TransportError
        from google_auth_httplib2 import AuthorizedHttp
        from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from httplib2 import Http, HttpLib2Error
        from oauthlib.oauth2 import OAuth2Error
        from requests import RequestException
    except ImportError:
        raise MailboxUnavailable("Install the optional Gmail dependencies and restart.") from None

    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or not isinstance(config.get("installed"), dict):
            raise ValueError
        flow = InstalledAppFlow.from_client_config(
            {"installed": config["installed"]}, scopes=[_SCOPE], autogenerate_code_verifier=True,
        )
    except (OSError, ValueError, KeyError, TypeError):
        raise MailboxUnavailable("Check that the external file contains Google desktop OAuth credentials and restart.") from None

    # The loopback handler logs the callback URL, which contains the authorization code.
    logger = logging.getLogger("google_auth_oauthlib.flow")
    was_disabled = logger.disabled
    logger.disabled = True
    try:
        credentials = flow.run_local_server(
            host="127.0.0.1", port=0, timeout_seconds=180, open_browser=False,
            login_hint=expected_address.strip(), state=token_urlsafe(32),
            success_message="Authorization response received. Check the app for account verification.",
        )
        http = AuthorizedHttp(credentials, http=Http(timeout=15), max_refresh_attempts=0)
        service = build("gmail", "v1", http=http, cache_discovery=False, static_discovery=True)
        return GmailMailbox(
            service, expected_address, http_error=HttpError, auth_error=RefreshError,
            transport_error=(TransportError, HttpLib2Error),
        )
    except MailboxUnavailable:
        raise
    except (
        OSError, ValueError, LookupError, OAuth2Error, RequestException,
        GoogleAuthError, WSGITimeoutError, HttpError, HttpLib2Error,
    ):
        raise MailboxUnavailable("Gmail authorization or profile verification failed. Check the desktop client and test account access, then restart.") from None
    finally:
        logger.disabled = was_disabled


class GmailMailbox:
    def __init__(self, service, expected_address: str, *, http_error=(), auth_error=(), transport_error=()):
        expected = expected_address.strip().casefold()
        if not expected:
            raise MailboxUnavailable("Configure the dedicated Gmail test account address.")
        self._users = service.users()
        self._http_error = http_error
        self._auth_error = auth_error
        self._transport_errors = (OSError, *transport_error)
        self._lock = Lock()
        profile = self._execute(self._users.getProfile(userId="me"))
        address = profile.get("emailAddress", "")
        if not isinstance(address, str) or address.casefold() != expected:
            raise MailboxUnavailable("The authorized Gmail address does not match the dedicated test account. Restart and select the correct account.")
        self.account_address = address

    def _execute(self, request, *, write_operation=None):
        try:
            # The Google client's HTTP transport is shared by Flask request threads.
            with self._lock:
                return request.execute(num_retries=0)
        except self._auth_error:
            raise MailboxUnavailable("Gmail authorization expired. Restart and authorize the dedicated account.") from None
        except self._http_error as error:
            status = error.resp.status
            if status in (401, 403, 429):
                raise MailboxUnavailable("Gmail denied access or rate-limited the account. Check access or wait and try again.") from None
            if status == 404:
                raise LookupError("Gmail resource no longer exists.") from None
            if write_operation and (status >= 500 or status == 408):
                raise UnverifiedWrite(f"Gmail {write_operation} was unverified (HTTP {status}).") from None
            raise OSError("Gmail rejected the request.") from None
        except self._transport_errors as error:
            if write_operation:
                reason = "transport timed out" if isinstance(error, TimeoutError) else "transport error"
                raise UnverifiedWrite(f"Gmail {write_operation} was unverified ({reason}).") from None
            raise OSError("Gmail could not be reached.") from None

    def list_inbox_ids(self, limit: int) -> list[str]:
        try:
            result = self._execute(self._users.messages().list(
                userId="me", labelIds=["INBOX"], maxResults=limit,
            ))
        except LookupError:
            raise MailboxUnavailable("Gmail could not locate the inbox. Restart and verify the test account.") from None
        return [item["id"] for item in result.get("messages", ())][:limit]

    def _user_labels(self):
        try:
            result = self._execute(self._users.labels().list(userId="me"))
        except LookupError:
            raise MailboxUnavailable("Gmail could not read the account labels.") from None
        return {item["name"]: item["id"] for item in result.get("labels", ()) if item["type"] == "user"}

    def preview_reader(self):
        return partial(self._read_message, label_map=self._user_labels())

    def read_message(self, message_id: str) -> Message:
        return self._read_message(message_id, self._user_labels())

    def _read_message(self, message_id: str, label_map: dict[str, str]) -> Message:
        result = self._execute(self._users.messages().get(userId="me", id=message_id, format="raw"))
        try:
            raw = result["raw"]
            mime = BytesParser(policy=policy.default).parsebytes(urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
            received = datetime.fromtimestamp(int(result["internalDate"]) / 1000, tz=timezone.utc)
            text = _message_text(mime)
            sender = str(mime.get("From", ""))
            subject = str(mime.get("Subject", ""))
        except (LookupError, ValueError, TypeError, OverflowError):
            raise OSError("Gmail returned an unreadable message.") from None
        label_ids = result.get("labelIds", ())
        labels = tuple(name for name, label_id in label_map.items() if label_id in label_ids)
        return Message(
            message_id, sender, subject, received.strftime("%Y-%m-%d %H:%M UTC"),
            text, labels, "INBOX" in label_ids,
        )

    def apply_category(self, message_id: str, category: str) -> None:
        if category not in LABELS:
            raise ValueError("Unsupported recruitment category.")
        name = LABELS[category]
        label_id = self._user_labels().get(name)
        if label_id is None:
            created = self._execute(
                self._users.labels().create(userId="me", body={"name": name}),
                write_operation="label creation",
            )
            if created.get("name") != name or created.get("type") != "user" or not created.get("id"):
                raise UnverifiedWrite("Gmail label creation was unverified (unexpected label response).")
            label_id = created["id"]
        self._execute(self._users.messages().modify(
            userId="me", id=message_id, body={"addLabelIds": [label_id]},
        ), write_operation="message modification")


_QUOTE_BOUNDARY = re.compile(
    r"^\s*(?:On [^\n]*(?:\n[^\n]*)? wrote:|[-_]{2,}\s*(?:Original|Forwarded) Message\s*[-_]{2,})\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _body_parts(part):
    if part.get_content_disposition() == "attachment" or part.get_filename():
        return
    if part.get_content_type() in ("text/plain", "text/html"):
        yield part
    elif part.get_content_maintype() == "multipart":
        if part.get_content_subtype() == "related":
            root = part.get_body(preferencelist=("plain", "html"))
            if root is not None:
                yield from _body_parts(root)
        else:
            for child in part.iter_parts():
                yield from _body_parts(child)


def _message_text(mime):
    parts = list(_body_parts(mime))
    part = next((part for part in parts if part.get_content_type() == "text/plain"), None)
    if part is None:
        if not parts:
            return ""
        parser = _VisibleText()
        parser.feed(parts[0].get_content())
        parser.close()
        text = "".join(parser.fragments)
    else:
        text = part.get_content()
    current = _QUOTE_BOUNDARY.split(text, maxsplit=1)[0]
    return "\n".join(line for line in current.splitlines() if not line.lstrip().startswith(">"))


class _VisibleText(HTMLParser):
    _blocks = {"br", "div", "hr", "li", "p", "table", "td", "tr", "section", "h1", "h2", "h3"}
    _void = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.fragments = []
        self.hidden_tag = None
        self.hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if self.hidden_tag:
            if tag == self.hidden_tag:
                self.hidden_depth += 1
            return
        attributes = dict(attrs)
        quote_classes = {"gmail_quote", "gmail_attr", "yahoo_quoted", "moz-cite-prefix"}
        if tag not in self._void and (
            tag in {"blockquote", "head", "script", "style", "template"}
            or "hidden" in attributes
            or quote_classes.intersection((attributes.get("class") or "").split())
            or re.search(r"(?:display:none|visibility:hidden)", re.sub(r"\s+", "", (attributes.get("style") or "").lower()))
        ):
            self.hidden_tag = tag
            self.hidden_depth = 1
        elif tag in self._blocks:
            self.fragments.append("\n")

    def handle_endtag(self, tag):
        if self.hidden_tag:
            if tag == self.hidden_tag:
                self.hidden_depth -= 1
                if not self.hidden_depth:
                    self.hidden_tag = None
        elif tag in self._blocks:
            self.fragments.append("\n")

    def handle_data(self, data):
        if not self.hidden_tag:
            self.fragments.append(data)
