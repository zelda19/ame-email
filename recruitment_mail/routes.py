from secrets import compare_digest, token_urlsafe

from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for

from .workflow import SCAN_LIMIT, preview_inbox


pages = Blueprint("pages", __name__)


@pages.get("/")
def start():
    if "csrf_token" not in session:
        session["csrf_token"] = token_urlsafe(32)
    return render_template("start.html", limit=SCAN_LIMIT)


@pages.post("/preview")
def preview():
    token = session.get("csrf_token")
    submitted = request.form.get("csrf_token", "").encode()
    if not token or not compare_digest(token.encode(), submitted):
        abort(403)
    try:
        preview_data = preview_inbox(current_app.extensions["mailbox"])
    except OSError:
        return render_template(
            "start.html", limit=SCAN_LIMIT,
            error="The mock inbox could not be read. Try previewing again.",
        ), 503
    run_id = token_urlsafe(24)
    current_app.extensions["previews"][token] = (run_id, preview_data)
    return redirect(url_for("pages.run", run_id=run_id), code=303)


@pages.get("/runs/<run_id>")
def run(run_id):
    saved = current_app.extensions["previews"].get(session.get("csrf_token"))
    if saved is None or saved[0] != run_id:
        abort(404)
    count, unreadable, rows = saved[1]
    return render_template("preview.html", count=count, unreadable=unreadable, rows=rows)
