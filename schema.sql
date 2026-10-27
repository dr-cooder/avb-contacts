-- Database schema for the contacts app.
--
-- Two tables, because one contact can have many emails ("one-to-many").
-- Each row in `emails` points back to its contact through `contact_id`.
--
-- `IF NOT EXISTS` makes this file safe to run on every startup: it creates
-- the tables the first time and does nothing afterwards.

CREATE TABLE IF NOT EXISTS contacts (
    id          INTEGER PRIMARY KEY,               -- SQLite auto-assigns 1, 2, 3...
    first_name  TEXT NOT NULL CHECK (length(trim(first_name)) > 0),
    last_name   TEXT NOT NULL CHECK (length(trim(last_name)) > 0),
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS emails (
    id          INTEGER PRIMARY KEY,
    -- ON DELETE CASCADE: deleting a contact automatically deletes its emails.
    contact_id  INTEGER NOT NULL REFERENCES contacts (id) ON DELETE CASCADE,
    address     TEXT NOT NULL,
    -- Remembers the order the user put the emails in.
    position    INTEGER NOT NULL,
    -- The same contact can't list the same address twice (case-insensitive).
    -- Different contacts MAY share an address (e.g. a shared family inbox).
    UNIQUE (contact_id, address COLLATE NOCASE)
);

-- Makes "find all emails for contact X" fast, even with many contacts.
CREATE INDEX IF NOT EXISTS idx_emails_contact_id ON emails (contact_id);
