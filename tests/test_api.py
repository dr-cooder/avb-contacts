"""API tests. Run with:  pytest

Each test gets a brand-new empty database in a temporary folder, so tests
can't interfere with each other or with your real data.
"""

import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(database_path=str(tmp_path / "test.db"))
    return app.test_client()  # sends fake requests without starting a server


def make(client, first="Craggy", last="Bramble", emails=None):
    response = client.post(
        "/api/contacts",
        json={"first_name": first, "last_name": last, "emails": emails or []},
    )
    assert response.status_code == 201, response.json
    return response.json


def test_create_and_get(client):
    created = make(client, emails=["craggy@example.com", "c@marcham.com"])
    assert created["first_name"] == "Craggy"
    assert created["emails"] == ["craggy@example.com", "c@marcham.com"]

    fetched = client.get(f"/api/contacts/{created['id']}").json
    assert fetched == created


def test_list_is_sorted_by_name(client):
    make(client, "Tudor", "Marcham")
    make(client, "andra", "Inde")
    make(client, "Berk", "Carruth")
    names = [c["first_name"] for c in client.get("/api/contacts").json]
    assert names == ["andra", "Berk", "Tudor"]


def test_names_are_required(client):
    response = client.post("/api/contacts", json={"first_name": "  ", "emails": []})
    assert response.status_code == 400
    assert set(response.json["fields"]) == {"first_name", "last_name"}


def test_whitespace_is_trimmed_and_blank_emails_skipped(client):
    created = make(client, "  Fifi ", " Soitoux  ", ["", "  fifi@example.fr ", "   "])
    assert created["first_name"] == "Fifi"
    assert created["last_name"] == "Soitoux"
    assert created["emails"] == ["fifi@example.fr"]


def test_invalid_email_reports_its_position(client):
    response = client.post(
        "/api/contacts",
        json={"first_name": "A", "last_name": "B", "emails": ["ok@example.com", "not-an-email"]},
    )
    assert response.status_code == 400
    assert "emails.1" in response.json["fields"]


def test_duplicate_email_on_same_contact_rejected(client):
    response = client.post(
        "/api/contacts",
        json={"first_name": "A", "last_name": "B", "emails": ["x@example.com", "X@Example.com"]},
    )
    assert response.status_code == 400
    assert "emails.1" in response.json["fields"]


def test_update_replaces_fields_and_emails(client):
    contact = make(client, emails=["a@example.com", "b@example.com"])
    response = client.put(
        f"/api/contacts/{contact['id']}",
        json={"first_name": "Craig", "last_name": "Bramble", "emails": ["b@example.com", "c@example.com"]},
    )
    assert response.status_code == 200
    assert response.json["first_name"] == "Craig"
    assert response.json["emails"] == ["b@example.com", "c@example.com"]  # order kept


def test_delete(client):
    contact = make(client, emails=["a@example.com"])
    assert client.delete(f"/api/contacts/{contact['id']}").status_code == 204
    assert client.get(f"/api/contacts/{contact['id']}").status_code == 404
    assert client.delete(f"/api/contacts/{contact['id']}").status_code == 404


def test_shared_email_survives_when_other_contact_changes(client):
    """Two contacts can share an address; removing it from one, or deleting
    one, must leave the other's copy alone."""
    a = make(client, "Craggy", "Bramble", ["shared@marcham.com"])
    b = make(client, "Tudor", "Marcham", ["shared@marcham.com"])

    client.put(f"/api/contacts/{a['id']}", json={"first_name": "Craggy", "last_name": "Bramble", "emails": []})
    assert client.get(f"/api/contacts/{b['id']}").json["emails"] == ["shared@marcham.com"]

    client.delete(f"/api/contacts/{a['id']}")
    assert client.get(f"/api/contacts/{b['id']}").json["emails"] == ["shared@marcham.com"]


def test_missing_contact_returns_json_404(client):
    response = client.put("/api/contacts/999", json={"first_name": "A", "last_name": "B"})
    assert response.status_code == 404
    assert "error" in response.json


def test_non_json_body_rejected(client):
    response = client.post("/api/contacts", data="hello", content_type="text/plain")
    assert response.status_code == 400
    assert "error" in response.json


def test_sql_injection_is_stored_as_plain_text(client):
    nasty = "Robert'); DROP TABLE contacts;--"
    contact = make(client, nasty, "Tables")
    assert client.get(f"/api/contacts/{contact['id']}").json["first_name"] == nasty
    assert len(client.get("/api/contacts").json) == 1
