"""Database access: opening connections and all the SQL queries.

Keeping every query in this one file means app.py only deals with HTTP
(requests and responses) and never has to know SQL.
"""

import os
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


# --- Connection handling -----------------------------------------------------

def get_db():
    """Return the database connection for the current request.

    Flask's `g` is a scratchpad that lives for exactly one request, so each
    request opens at most one connection, and close_db() closes it at the end.
    """
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        # Return rows that act like dicts (row["first_name"]) instead of tuples.
        g.db.row_factory = sqlite3.Row
        # SQLite leaves foreign keys (and so ON DELETE CASCADE) switched off
        # unless you turn them on for each connection.
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(path):
    """Create the database file and tables if they don't already exist."""
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA_PATH.read_text())


# --- Queries -----------------------------------------------------------------
# The `?` placeholders are important: sqlite3 fills them in safely, so a name
# like  Robert'); DROP TABLE contacts;--  is stored as text and never runs as
# SQL ("SQL injection"). Never build SQL with f-strings from user input.

def _emails_by_contact(db, contact_ids):
    """Fetch the emails for several contacts in one query: {contact_id: [..]}"""
    result = {cid: [] for cid in contact_ids}
    if not contact_ids:
        return result
    placeholders = ",".join("?" * len(contact_ids))
    rows = db.execute(
        f"SELECT contact_id, address FROM emails "
        f"WHERE contact_id IN ({placeholders}) ORDER BY position",
        contact_ids,
    ).fetchall()
    for row in rows:
        result[row["contact_id"]].append(row["address"])
    return result


def _to_dict(row, emails):
    return {
        "id": row["id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "emails": emails,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_contacts():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM contacts "
        "ORDER BY first_name COLLATE NOCASE, last_name COLLATE NOCASE, id"
    ).fetchall()
    emails = _emails_by_contact(db, [r["id"] for r in rows])
    return [_to_dict(r, emails[r["id"]]) for r in rows]


def get_contact(contact_id):
    """Return one contact as a dict, or None if it doesn't exist."""
    db = get_db()
    row = db.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    if row is None:
        return None
    return _to_dict(row, _emails_by_contact(db, [contact_id])[contact_id])


def _replace_emails(db, contact_id, emails):
    """Swap a contact's emails for a new list.

    Deleting them all and inserting the new list is simpler and less
    error-prone than working out which ones were added, edited, removed or
    reordered, and it's quick at address-book scale.
    """
    db.execute("DELETE FROM emails WHERE contact_id = ?", (contact_id,))
    db.executemany(
        "INSERT INTO emails (contact_id, address, position) VALUES (?, ?, ?)",
        [(contact_id, address, i) for i, address in enumerate(emails)],
    )


def create_contact(first_name, last_name, emails):
    db = get_db()
    # `with db:` is a transaction: if anything inside fails, every change in
    # the block is undone, so you can't end up with a contact missing its
    # emails. If everything succeeds, it's committed (saved) at the end.
    with db:
        cursor = db.execute(
            "INSERT INTO contacts (first_name, last_name) VALUES (?, ?)",
            (first_name, last_name),
        )
        contact_id = cursor.lastrowid
        _replace_emails(db, contact_id, emails)
    return get_contact(contact_id)


def update_contact(contact_id, first_name, last_name, emails):
    """Update a contact. Returns the updated contact, or None if not found."""
    db = get_db()
    with db:
        cursor = db.execute(
            "UPDATE contacts SET first_name = ?, last_name = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (first_name, last_name, contact_id),
        )
        if cursor.rowcount == 0:
            return None
        _replace_emails(db, contact_id, emails)
    return get_contact(contact_id)


def delete_contact(contact_id):
    """Delete a contact (its emails go too, via ON DELETE CASCADE).

    Returns True if a contact was deleted, False if it didn't exist.
    """
    db = get_db()
    with db:
        cursor = db.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    return cursor.rowcount > 0
