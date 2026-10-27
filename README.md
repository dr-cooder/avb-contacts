# Contacts

A small address-book web app: list, search, view, add, edit and delete
contacts, each with any number of email addresses.

- **Frontend:** vanilla HTML/CSS/JavaScript (no framework, no build step)
- **Backend:** Python + [Flask](https://flask.palletsprojects.com/), a JSON REST API
- **Database:** SQLite through Python's built-in `sqlite3` module, with hand-written SQL (no ORM)

## Running it locally

```bash
python3 -m venv .venv               # create an isolated Python environment
source .venv/bin/activate           # use it (on Windows: .venv\Scripts\activate)
pip install -r requirements.txt     # install Flask, gunicorn, pytest

python seed.py                      # optional: add the sample contacts from the mockup
flask --app app run --debug         # start the server
```

Open <http://127.0.0.1:5000>. `--debug` reloads the server whenever you
save a Python file and shows detailed errors. Never use it in production.

Run the tests with `pytest`.

The database is a single file, `instance/contacts.db`, created
automatically. To start over, stop the server and delete that file. To
look inside it: `sqlite3 instance/contacts.db`, then e.g.
`SELECT * FROM contacts;` (quit with `.quit`).

## Project layout

```
app.py            Flask app: URL routes (the REST API), validation, error handling
db.py             All database code and SQL queries
schema.sql        Table definitions
seed.py           Loads sample data into an empty database
static/
  index.html      Page structure
  style.css       Styling (colors and font taken from the Figma mockup)
  app.js          All frontend behaviour
tests/test_api.py API tests (pytest)
```

## How a request flows through the app

Clicking **Save** on an existing contact:

1. **`app.js`**, `save()`: checks the form (names present, emails look
   valid, no duplicates). If that passes, it sends
   `PUT /api/contacts/4` with a JSON body
   `{"first_name": "...", "last_name": "...", "emails": [...]}`.
2. **`app.py`**, `update_contact()`: Flask matches the URL pattern
   `/api/contacts/<int:contact_id>` and the `PUT` method to this function,
   with `contact_id=4`. `validate_contact()` checks the data again, because
   anyone can call the API directly and skip the browser's checks. Bad data
   gets a `400` response listing what's wrong with each field.
3. **`db.py`**, `update_contact()`: inside a single transaction, it updates
   the `contacts` row, deletes that contact's old `emails` rows, and
   inserts the new ones. If any step fails, the transaction undoes all of
   them.
4. Flask turns the updated contact into JSON and responds `200`. `app.js`
   refreshes the sidebar and shows "Changes saved."

## REST API

| Method | URL                   | Does                  | Success           | Errors                     |
|--------|-----------------------|-----------------------|-------------------|----------------------------|
| GET    | `/api/contacts`       | List all contacts     | `200` + array     |                            |
| POST   | `/api/contacts`       | Create a contact      | `201` + contact   | `400` invalid              |
| GET    | `/api/contacts/<id>`  | Get one contact       | `200` + contact   | `404`                      |
| PUT    | `/api/contacts/<id>`  | Replace a contact     | `200` + contact   | `400` invalid, `404`       |
| DELETE | `/api/contacts/<id>`  | Delete a contact      | `204` (no body)   | `404`                      |

A contact looks like:

```json
{
  "id": 4,
  "first_name": "Craggy",
  "last_name": "Bramble",
  "emails": ["craggy.bramble@gmail.com", "cbramble@marcham.com"],
  "created_at": "2026-10-26 17:02:11",
  "updated_at": "2026-10-26 17:05:40"
}
```

Validation errors:

```json
{
  "error": "Please fix the highlighted fields.",
  "fields": { "last_name": "Last name is required.", "emails.1": "\"bob@\" is not a valid email address." }
}
```

`emails.1` means the second email in the submitted list, so the frontend
can highlight exactly that input.

Try it from a terminal while the server is running:

```bash
curl http://127.0.0.1:5000/api/contacts
curl -X POST http://127.0.0.1:5000/api/contacts \
     -H "Content-Type: application/json" \
     -d '{"first_name": "Ada", "last_name": "Lovelace", "emails": ["ada@example.com"]}'
```

## Database schema

```
contacts                         emails
--------------------------       --------------------------------------
id          INTEGER PK   <----   contact_id  INTEGER  FK, ON DELETE CASCADE
first_name  TEXT NOT NULL        id          INTEGER  PK
last_name   TEXT NOT NULL        address     TEXT NOT NULL
created_at  TEXT                 position    INTEGER  (keeps the user's order)
updated_at  TEXT                 UNIQUE (contact_id, address, case-insensitive)
```

- **Two tables**, because one contact has many emails. Each email row
  stores the `id` of the contact it belongs to. Packing a list of emails
  into one text column would make searching, uniqueness checks and edits
  awkward.
- **`ON DELETE CASCADE`**: deleting a contact deletes *its own* email rows.
  If two contacts share an address, each has its own row, so the other
  contact keeps its copy. A test covers this.
- **`UNIQUE (contact_id, address)`**: a contact can't list the same
  address twice, but different contacts can share one (a family inbox,
  for example).
- **`CHECK` constraints on names**: the database itself refuses blank
  names, as a last line of defence behind the Python validation.

## Decisions and their reasons

The brief asks for thinking about how the app is used, so these are the
choices made beyond the literal requirements:

**Validation**
- First and last name are required. They're checked in the browser for
  instant feedback, again on the server because the API can be called
  directly, and once more by the database.
- Leading and trailing spaces are trimmed. Blank email rows are ignored
  instead of being treated as errors, since clicking "add email" and then
  changing your mind is normal.
- A contact with **no emails is allowed**. The brief says a contact "can
  have one or more emails", and it's common to save someone's name before
  you know their address. Requiring at least one would be a one-line
  change in `validate_contact()`.
- Email format checking is deliberately loose (`something@something.tld`).
  Strict validation rejects real addresses, and only sending mail proves
  an address works.

**Not losing work**
- Switching contacts, clicking **+**, using Back, or closing the tab with
  unsaved changes asks for confirmation first.
- **Save** is disabled until something has changed. **Cancel** reverts to
  the last saved version.
- **Delete** asks for confirmation and names the contact being deleted.
- While a save is in progress the buttons are disabled, so a double-click
  can't create two contacts.

**Usability**
- Search in the sidebar matches names *and* email addresses.
- The URL reflects the open contact (`#/contacts/4`), so refresh, bookmarks
  and the Back button all work.
- Contacts are sorted by first name, as in the mockup, ignoring
  upper/lower case.
- The email remove button appears on hover as in the mockup, and also on
  keyboard focus and always on touch screens, which have no hover.
- Ctrl/Cmd+S saves. Enter in any field saves.
- On narrow screens the sidebar stacks above the form.
- Errors (server down, contact deleted in another tab, etc.) show a
  readable message instead of failing silently.

**Security**
- All SQL uses `?` placeholders, so input can't change the query (SQL
  injection). There's a test for this.
- User data reaches the page only through `textContent`, never `innerHTML`,
  so a name containing HTML or script tags shows up as text (XSS).
- No login, as the brief requires. That means anyone with the URL can
  edit the data, which is fine for a demo but would need authentication
  for real use.

## Deploying

The app is one Python process serving both the API and the static files.
It needs a host with a **persistent disk**, because SQLite is a file. On
hosts whose disk resets with every deploy or restart, the data would
vanish.

### Option A: PythonAnywhere (free, simplest, keeps SQLite data)

1. Push this repo to GitHub (see below), then sign up at
   <https://www.pythonanywhere.com>.
2. Open a **Bash console** there and run:
   ```bash
   git clone https://github.com/<you>/<repo>.git contacts
   cd contacts
   python3.10 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python seed.py
   ```
3. **Web** tab, then **Add a new web app**, then **Manual configuration**,
   then Python 3.10.
4. On the web app page:
   - **Virtualenv**: `/home/<username>/contacts/.venv`
   - Click the **WSGI configuration file** link and replace its contents with:
     ```python
     import sys
     sys.path.insert(0, "/home/<username>/contacts")
     from app import app as application
     ```
5. Click **Reload**. The app is live at `https://<username>.pythonanywhere.com`.

To update later: `git pull` in the console, then **Reload**.

### Option B: Render, Railway, Fly.io, etc.

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
- Attach a persistent disk/volume and set the environment variable
  `DATABASE_PATH` to a file on it (e.g. `/data/contacts.db`). Without
  that, data is lost on every deploy.

`gunicorn` is a production web server. `flask run` is meant for
development only.

## Publishing the code

```bash
git init
git add .
git status          # check: reference/, .venv/ and instance/ must NOT be listed
git commit -m "Contacts app"
```

Then create an empty repository on GitHub and follow its instructions to
`git remote add origin ...` and `git push`. The `.gitignore` keeps
`reference/` (which holds private files), the virtualenv and the database
out of the repo.

## Possible next steps

- Warn (without blocking) when an email already belongs to another contact
- More fields: phone numbers, address, notes, photo
- Detect conflicting edits from two tabs (compare `updated_at` before saving)
- Undo after delete instead of a confirmation dialog
- Pagination or virtual scrolling for very large address books
