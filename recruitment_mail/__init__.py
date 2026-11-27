from os import getenv
from secrets import token_hex

from flask import Flask

from .mailbox import Mailbox, MailboxUnavailable, MockMailbox
from .routes import pages
from .workflow import Workflow


def create_app(mailbox: Mailbox | None = None, *, clock=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=token_hex(32), SESSION_COOKIE_SAMESITE="Lax")
    mode = getenv("RECRUITMENT_MAIL_MODE", "mock") if mailbox is None else "mock"
    startup_error = None
    if mode == "gmail":
        from .gmail import connect_gmail

        try:
            mailbox = connect_gmail(
                getenv("RECRUITMENT_GMAIL_ACCOUNT", ""),
                getenv("RECRUITMENT_GMAIL_CLIENT_FILE", ""),
            )
        except MailboxUnavailable as error:
            startup_error = str(error)
    elif mode != "mock":
        raise ValueError("RECRUITMENT_MAIL_MODE must be 'mock' or 'gmail'.")
    elif mailbox is None:
        mailbox = MockMailbox()

    account_address = getattr(mailbox, "account_address", None)
    app.config.update(
        GMAIL_MODE=mode == "gmail" or account_address is not None,
        GMAIL_ADDRESS=account_address,
        MAILBOX_STARTUP_ERROR=startup_error,
    )
    if mailbox is not None:
        # The workflow keeps this verified mailbox for the lifetime of every run.
        app.extensions["workflow"] = Workflow(mailbox, clock=clock)
    app.register_blueprint(pages)
    return app
