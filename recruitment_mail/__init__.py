from secrets import token_hex

from flask import Flask

from .mailbox import Mailbox, MockMailbox
from .routes import pages


def create_app(mailbox: Mailbox | None = None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=token_hex(32), SESSION_COOKIE_SAMESITE="Lax")
    app.extensions["mailbox"] = mailbox if mailbox is not None else MockMailbox()
    app.extensions["previews"] = {}
    app.register_blueprint(pages)
    return app
