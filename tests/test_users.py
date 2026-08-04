"""User API tests."""

from __future__ import annotations

import uuid

from app.extensions import db
from tests.factories import UserFactory

BASE = "/api/v1/users"


def test_create_user_returns_201_without_leaking_the_hash(client):
    resp = client.post(
        BASE,
        json={"email": "ada@example.com", "full_name": "Ada Lovelace", "password": "s3cret-pass"},
    )
    assert resp.status_code == 201

    body = resp.get_json()
    assert body["email"] == "ada@example.com"
    assert body["is_active"] is True
    assert "password" not in body
    assert "password_hash" not in body
    uuid.UUID(body["id"])  # id is a well-formed UUID


def test_create_user_rejects_a_duplicate_email(client):
    payload = {"email": "dup@example.com", "full_name": "Dup", "password": "s3cret-pass"}
    assert client.post(BASE, json=payload).status_code == 201

    resp = client.post(BASE, json=payload)
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "conflict"


def test_create_user_rejects_a_short_password(client):
    resp = client.post(
        BASE, json={"email": "x@example.com", "full_name": "X", "password": "short"}
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "validation_failed"


def test_create_user_rejects_unknown_fields(client):
    resp = client.post(
        BASE,
        json={
            "email": "x@example.com",
            "full_name": "X",
            "password": "s3cret-pass",
            "is_admin": True,
        },
    )
    assert resp.status_code == 422


def test_get_user_returns_404_for_an_unknown_id(client):
    resp = client.get(f"{BASE}/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "not_found"


def test_get_user_is_served_from_the_redis_cache_on_the_second_call(app, client):
    with app.app_context():
        user = UserFactory()
        user_id = user.id

    first = client.get(f"{BASE}/{user_id}")
    assert first.status_code == 200

    # Delete the row outright: a second 200 can only come from the cache.
    with app.app_context():
        db.session.execute(db.text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        db.session.commit()

    second = client.get(f"{BASE}/{user_id}")
    assert second.status_code == 200
    assert second.get_json() == first.get_json()


def test_list_users_paginates(app, client):
    with app.app_context():
        UserFactory.create_batch(25)

    resp = client.get(BASE, query_string={"page": 2, "per_page": 10})
    assert resp.status_code == 200

    body = resp.get_json()
    assert len(body["items"]) == 10
    assert body["total"] == 25
    assert body["pages"] == 3
    assert body["page"] == 2


def test_list_users_rejects_an_oversized_page_size(client):
    resp = client.get(BASE, query_string={"per_page": 5000})
    assert resp.status_code == 422


def test_list_users_can_filter_to_active_only(app, client):
    with app.app_context():
        UserFactory.create_batch(3, is_active=True)
        UserFactory.create_batch(2, is_active=False)

    resp = client.get(BASE, query_string={"active_only": "true"})
    assert resp.get_json()["total"] == 3


def test_update_user_applies_a_partial_patch_and_busts_the_cache(app, client):
    with app.app_context():
        user_id = UserFactory(full_name="Old Name").id

    client.get(f"{BASE}/{user_id}")  # warm the cache

    resp = client.patch(f"{BASE}/{user_id}", json={"full_name": "New Name"})
    assert resp.status_code == 200
    assert resp.get_json()["full_name"] == "New Name"

    assert client.get(f"{BASE}/{user_id}").get_json()["full_name"] == "New Name"


def test_update_user_rejects_an_email_taken_by_someone_else(app, client):
    with app.app_context():
        UserFactory(email="taken@example.com")
        user_id = UserFactory(email="mine@example.com").id

    resp = client.patch(f"{BASE}/{user_id}", json={"email": "taken@example.com"})
    assert resp.status_code == 409


def test_update_user_rehashes_a_new_password(app, client):
    with app.app_context():
        user = UserFactory()
        user_id, old_hash = user.id, user.password_hash

    assert client.patch(f"{BASE}/{user_id}", json={"password": "brand-new-pass"}).status_code == 200

    with app.app_context():
        from app.models import User

        refreshed = db.session.get(User, user_id)
        assert refreshed.password_hash != old_hash
        assert refreshed.verify_password("brand-new-pass")


def test_delete_user_returns_204_then_404(app, client):
    with app.app_context():
        user_id = UserFactory().id

    assert client.delete(f"{BASE}/{user_id}").status_code == 204
    assert client.get(f"{BASE}/{user_id}").status_code == 404


def test_unknown_route_returns_the_json_error_envelope(client):
    resp = client.get("/api/v1/nope")
    assert resp.status_code == 404
    assert "error" in resp.get_json()
