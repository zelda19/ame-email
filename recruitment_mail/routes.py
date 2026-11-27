from collections import Counter
from secrets import compare_digest, token_urlsafe

from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for

from .workflow import OUTCOMES, SCAN_LIMIT, InvalidSelection, RunExpired, RunMissing


pages = Blueprint("pages", __name__)


@pages.errorhandler(RunMissing)
def missing(_error):
    return render_template("start.html", limit=SCAN_LIMIT, error="Preview unavailable. Start a fresh preview."), 404


@pages.errorhandler(RunExpired)
def expired(_error):
    return render_template("start.html", limit=SCAN_LIMIT, error="Preview expired. Start a fresh preview."), 410


@pages.errorhandler(403)
def invalid_csrf(_error):
    return render_template("start.html", limit=SCAN_LIMIT, error="Form expired or invalid. Start a fresh preview."), 403


def require_csrf():
    token = session.get("csrf_token")
    submitted = request.form.get("csrf_token", "").encode()
    if not token or not compare_digest(token.encode(), submitted):
        abort(403)
    return token


def workflow():
    return current_app.extensions["workflow"]


def redirect_to_run(run_id):
    return redirect(url_for("pages.run", run_id=run_id), code=303)


@pages.get("/")
def start():
    if "csrf_token" not in session:
        session["csrf_token"] = token_urlsafe(32)
    return render_template("start.html", limit=SCAN_LIMIT)


@pages.post("/preview")
def preview():
    owner = require_csrf()
    try:
        run_id = workflow().preview(owner)
    except OSError:
        return render_template(
            "start.html", limit=SCAN_LIMIT,
            error="The mock inbox could not be read. Try previewing again.",
        ), 503
    return redirect_to_run(run_id)


@pages.get("/runs/<run_id>")
def run(run_id):
    saved = workflow().get(session.get("csrf_token"), run_id)
    if saved.state == "pending":
        return render_template("preview.html", run=saved)
    counts = Counter(outcome.status for outcome in saved.outcomes)
    return render_template("results.html", run=saved, counts=counts, statuses=OUTCOMES)


@pages.post("/runs/<run_id>/confirm")
def confirm(run_id):
    owner = require_csrf()
    try:
        workflow().confirm(owner, run_id, request.form.getlist("selected"))
    except InvalidSelection:
        saved = workflow().get(owner, run_id)
        return render_template("preview.html", run=saved, error="Select at least one eligible message."), 400
    return redirect_to_run(run_id)


@pages.post("/runs/<run_id>/cancel")
def cancel(run_id):
    owner = require_csrf()
    if workflow().cancel(owner, run_id):
        return redirect(url_for("pages.start"), code=303)
    return redirect_to_run(run_id)
