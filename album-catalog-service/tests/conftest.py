import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import app, _store


@pytest.fixture()
def client():
    """Fresh TestClient with empty in-memory store for each test."""
    _store.clear()
    with TestClient(app) as c:
        yield c
    _store.clear()


@pytest.fixture()
def client_with_album(client):
    """Client pre-populated with one album. Returns (client, album_id)."""
    resp = client.put("/albums", json={
        "title": "Kind of Blue",
        "artist": "Miles Davis",
        "releaseYear": "1959",
        "genre": "Jazz",
    })
    assert resp.status_code == 200
    album_id = resp.json()["id"]
    return client, album_id
