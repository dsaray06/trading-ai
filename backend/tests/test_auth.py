"""Tests for JWT auth (register / login / me)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


def _client(db_session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_register_login_me_flow(db_session):
    try:
        client = _client(db_session)
        r = client.post("/auth/register", json={"email": "a@b.com", "password": "password123"})
        assert r.status_code == 201
        assert r.json()["email"] == "a@b.com"

        r = client.post("/auth/login", json={"email": "a@b.com", "password": "password123"})
        assert r.status_code == 200
        token = r.json()["access_token"]
        assert r.json()["token_type"] == "bearer"

        r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["email"] == "a@b.com"
    finally:
        app.dependency_overrides.clear()


def test_duplicate_email_conflicts(db_session):
    try:
        client = _client(db_session)
        client.post("/auth/register", json={"email": "dup@b.com", "password": "password123"})
        r = client.post("/auth/register", json={"email": "dup@b.com", "password": "password123"})
        assert r.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_login_wrong_password(db_session):
    try:
        client = _client(db_session)
        client.post("/auth/register", json={"email": "c@b.com", "password": "password123"})
        r = client.post("/auth/login", json={"email": "c@b.com", "password": "wrongpass1"})
        assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_me_requires_token(db_session):
    try:
        client = _client(db_session)
        assert client.get("/auth/me").status_code == 401
        assert client.get("/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    finally:
        app.dependency_overrides.clear()
