"""The web server: REST API endpoints plus serving the frontend files.

Run locally with:   flask --app app run --debug
Then open:          http://127.0.0.1:5000

REST API summary (all JSON):
    GET    /api/contacts        list every contact (with emails)
    POST   /api/contacts        create a contact        -> 201 + the contact
    GET    /api/contacts/<id>   get one contact         -> 200, or 404
    PUT    /api/contacts/<id>   replace a contact       -> 200, or 400/404
    DELETE /api/contacts/<id>   delete a contact        -> 204, or 404

Validation errors come back as 400 with a body like:
    {"error": "Please fix the highlighted fields.",
     "fields": {"first_name": "First name is required.",
                "emails.1": "\"bob@\" is not a valid email address."}}
"""

import os
import re

from flask import Flask, abort, jsonify, request, send_from_directory

import db

# A deliberately simple "something@something.something" check. Fully
# validating email syntax is notoriously complex; the only real proof an
# address works is sending mail to it. The same pattern is used in app.js
# so the browser and the server agree.
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 254  # the longest address the email standards allow
MAX_EMAILS = 50         # a sanity limit, not a business rule


def create_app(database_path=None):
    """Build and configure the Flask app.

    Wrapping setup in a function ("app factory") lets the tests create a
    separate app pointing at a throwaway database.
    """
    app = Flask(__name__, static_folder="static", static_url_path="")
    app.config["DATABASE"] = database_path or os.environ.get(
        "DATABASE_PATH", os.path.join(app.root_path, "instance", "contacts.db")
    )
    db.init_db(app.config["DATABASE"])
    app.teardown_appcontext(db.close_db)  # close the DB at the end of each request

    # --- Frontend ------------------------------------------------------------

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    # --- API -----------------------------------------------------------------
    # `<int:contact_id>` captures a number from the URL and passes it to the
    # function. Something like /api/contacts/abc doesn't match, so it 404s.

    @app.get("/api/contacts")
    def list_contacts():
        return jsonify(db.list_contacts())

    @app.get("/api/contacts/<int:contact_id>")
    def get_contact(contact_id):
        contact = db.get_contact(contact_id)
        if contact is None:
            abort(404, description="Contact not found.")
        return jsonify(contact)

    @app.post("/api/contacts")
    def create_contact():
        data = validate_contact(request.get_json(silent=True))
        contact = db.create_contact(**data)
        return jsonify(contact), 201  # 201 = "Created"

    @app.put("/api/contacts/<int:contact_id>")
    def update_contact(contact_id):
        data = validate_contact(request.get_json(silent=True))
        contact = db.update_contact(contact_id, **data)
        if contact is None:
            abort(404, description="Contact not found. It may have been deleted.")
        return jsonify(contact)

    @app.delete("/api/contacts/<int:contact_id>")
    def delete_contact(contact_id):
        if not db.delete_contact(contact_id):
            abort(404, description="Contact not found. It may already have been deleted.")
        return "", 204  # 204 = "No Content": it worked, nothing to send back

    # --- Errors --------------------------------------------------------------
    # By default Flask answers errors with an HTML page. The frontend expects
    # JSON, so API errors are converted to {"error": "..."}.

    @app.errorhandler(ValidationError)
    def handle_validation_error(err):
        return jsonify(error="Please fix the highlighted fields.", fields=err.fields), 400

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(405)
    def handle_http_error(err):
        return jsonify(error=err.description), err.code

    @app.errorhandler(500)
    def handle_server_error(_err):
        return jsonify(error="Something went wrong on the server. Please try again."), 500

    return app


class ValidationError(Exception):
    """Raised when submitted contact data is invalid.

    `fields` maps a field name to a message the user can read. Emails are
    keyed "emails.<index>" so the frontend can highlight the exact input.
    """

    def __init__(self, fields):
        super().__init__("invalid contact data")
        self.fields = fields


def validate_contact(payload):
    """Check and clean the JSON sent by the browser.

    Never trust the browser: app.js validates too, but anyone can send
    requests to the API directly (with curl, say), skipping app.js entirely.
    Returns a clean dict ready for the database, or raises ValidationError.
    """
    if not isinstance(payload, dict):
        abort(400, description="Request body must be a JSON object.")

    errors = {}
    clean = {}

    for field, label in (("first_name", "First name"), ("last_name", "Last name")):
        value = payload.get(field)
        value = value.strip() if isinstance(value, str) else ""
        if not value:
            errors[field] = f"{label} is required."
        elif len(value) > MAX_NAME_LENGTH:
            errors[field] = f"{label} must be {MAX_NAME_LENGTH} characters or fewer."
        clean[field] = value

    raw_emails = payload.get("emails", [])
    if not isinstance(raw_emails, list):
        errors["emails"] = "Emails must be a list."
        raw_emails = []
    elif len(raw_emails) > MAX_EMAILS:
        errors["emails"] = f"A contact can have at most {MAX_EMAILS} emails."

    emails = []
    seen = set()
    for i, value in enumerate(raw_emails):
        value = value.strip() if isinstance(value, str) else ""
        if not value:
            continue  # blank rows (e.g. "add email" clicked but left empty) are ignored
        key = f"emails.{i}"
        if len(value) > MAX_EMAIL_LENGTH:
            errors[key] = "That email address is too long."
        elif not EMAIL_RE.match(value):
            errors[key] = f'"{value}" is not a valid email address.'
        elif value.lower() in seen:
            errors[key] = "This email is already listed for this contact."
        else:
            seen.add(value.lower())
            emails.append(value)
    clean["emails"] = emails

    if errors:
        raise ValidationError(errors)
    return clean


# `flask --app app run` and production servers (gunicorn app:app) look for
# a variable called `app`.
app = create_app()
