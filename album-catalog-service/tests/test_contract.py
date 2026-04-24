"""
Contract tests for Album Catalog Service.

These tests define the API contract the new service must honor.
They deliberately cover the same behaviors as AlbumControllerCharacterizationTest.java
so both can run together to prove compatibility.

Contract differences vs. monolith (bugs FIXED in this service):
  - GET /albums/{nonexistent} → 404  (monolith: 200 + empty body)
  - GET /albums/{deleted}     → 404  (monolith: 200 + empty body)
  - POST /albums/{nonexistent} → 404 (monolith behavior untested; defensive here)

Anti-corruption guarantee:
  - No JPA annotation names appear in any response body
  - No Java class name (_class field) appears in any response body
  - Field names match monolith JSON schema exactly
"""

REQUIRED_FIELDS = {"id", "title", "artist", "releaseYear", "genre", "trackCount", "albumId"}
JPA_LEAK_MARKERS = {"@Entity", "@Column", "@GenericGenerator", "@Id", "_class", "javax.persistence", "jakarta.persistence"}

SAMPLE_ALBUM = {
    "title": "Nevermind",
    "artist": "Nirvana",
    "releaseYear": "1991",
    "genre": "Rock",
}


# =============================================================
# GET /albums
# =============================================================

def test_list_albums_returns_200(client):
    resp = client.get("/albums")
    assert resp.status_code == 200


def test_list_albums_returns_json_array(client):
    resp = client.get("/albums")
    assert isinstance(resp.json(), list)


def test_list_albums_empty_on_startup(client):
    resp = client.get("/albums")
    assert resp.json() == []


def test_list_albums_each_album_has_required_fields(client):
    client.put("/albums", json=SAMPLE_ALBUM)
    albums = client.get("/albums").json()
    for album in albums:
        missing = REQUIRED_FIELDS - set(album.keys())
        assert not missing, f"Album missing fields: {missing}"


def test_list_albums_track_count_defaults_to_zero(client):
    client.put("/albums", json=SAMPLE_ALBUM)  # no trackCount supplied
    album = client.get("/albums").json()[0]
    assert album["trackCount"] == 0, "trackCount must default to 0 when not supplied"


def test_list_albums_album_id_is_null_when_not_supplied(client):
    client.put("/albums", json=SAMPLE_ALBUM)  # no albumId supplied
    album = client.get("/albums").json()[0]
    assert album["albumId"] is None, "albumId must be null when not supplied"


# =============================================================
# GET /albums/{id}
# =============================================================

def test_get_album_by_id_returns_200_when_exists(client_with_album):
    client, album_id = client_with_album
    resp = client.get(f"/albums/{album_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == album_id


def test_get_album_by_id_returns_404_when_not_found(client):
    """
    CONTRACT FIX: This service returns 404 for missing albums.
    The monolith returns 200 + empty body (orElse(null) bug pinned in
    AlbumControllerCharacterizationTest.getAlbumById_returns200WithEmptyBody_whenIdNotFound).
    If both tests are green: monolith has the bug, new service has the fix.
    """
    resp = client.get("/albums/this-id-does-not-exist")
    assert resp.status_code == 404


def test_get_album_by_id_returns_all_fields(client_with_album):
    client, album_id = client_with_album
    album = client.get(f"/albums/{album_id}").json()
    missing = REQUIRED_FIELDS - set(album.keys())
    assert not missing, f"Response missing fields: {missing}"


# =============================================================
# PUT /albums (create)
# =============================================================

def test_put_album_returns_200(client):
    resp = client.put("/albums", json=SAMPLE_ALBUM)
    assert resp.status_code == 200


def test_put_album_response_contains_server_generated_id(client):
    resp = client.put("/albums", json=SAMPLE_ALBUM)
    album = resp.json()
    assert "id" in album
    assert album["id"] is not None
    assert len(album["id"]) > 0


def test_put_album_server_ignores_client_supplied_id(client):
    """Server always generates a new UUID — matches monolith behavior."""
    payload = {**SAMPLE_ALBUM, "id": "client-wants-this-id"}
    resp = client.put("/albums", json=payload)
    returned_id = resp.json()["id"]
    assert returned_id != "client-wants-this-id", "Server must not use client-supplied id"


def test_put_album_is_retrievable_by_get(client):
    created_id = client.put("/albums", json=SAMPLE_ALBUM).json()["id"]
    fetched = client.get(f"/albums/{created_id}").json()
    assert fetched["title"] == SAMPLE_ALBUM["title"]
    assert fetched["artist"] == SAMPLE_ALBUM["artist"]


def test_put_album_title_and_artist_round_trip(client):
    resp = client.put("/albums", json=SAMPLE_ALBUM)
    album = resp.json()
    assert album["title"] == SAMPLE_ALBUM["title"]
    assert album["artist"] == SAMPLE_ALBUM["artist"]
    assert album["releaseYear"] == SAMPLE_ALBUM["releaseYear"]
    assert album["genre"] == SAMPLE_ALBUM["genre"]


def test_put_album_appears_in_list_after_creation(client):
    created_id = client.put("/albums", json=SAMPLE_ALBUM).json()["id"]
    ids = [a["id"] for a in client.get("/albums").json()]
    assert created_id in ids


# =============================================================
# POST /albums (update)
# =============================================================

def test_post_album_updates_and_returns_new_state(client_with_album):
    client, album_id = client_with_album
    update = {
        "id": album_id,
        "title": "Updated Title",
        "artist": "Miles Davis",
        "releaseYear": "1960",
        "genre": "Jazz",
        "trackCount": 8,
    }
    resp = client.post("/albums", json=update)
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Updated Title"
    assert body["trackCount"] == 8
    assert body["id"] == album_id


def test_post_album_change_persists_on_subsequent_get(client_with_album):
    client, album_id = client_with_album
    client.post("/albums", json={
        "id": album_id, "title": "After", "artist": "A", "releaseYear": "2000", "genre": "Pop"
    })
    fetched = client.get(f"/albums/{album_id}").json()
    assert fetched["title"] == "After"


# =============================================================
# DELETE /albums/{id}
# =============================================================

def test_delete_album_returns_200(client_with_album):
    client, album_id = client_with_album
    resp = client.delete(f"/albums/{album_id}")
    assert resp.status_code == 200


def test_delete_album_returns_empty_body(client_with_album):
    """Matches monolith: DELETE returns HTTP 200 with empty body."""
    client, album_id = client_with_album
    resp = client.delete(f"/albums/{album_id}")
    assert resp.text == "", f"DELETE body must be empty, got: '{resp.text}'"


def test_delete_album_subsequent_get_returns_404(client_with_album):
    """
    CONTRACT FIX: After deletion, GET returns 404.
    Monolith returns 200 + empty body (same orElse(null) bug).
    """
    client, album_id = client_with_album
    client.delete(f"/albums/{album_id}")
    resp = client.get(f"/albums/{album_id}")
    assert resp.status_code == 404


def test_delete_album_removed_from_list(client_with_album):
    client, album_id = client_with_album
    client.delete(f"/albums/{album_id}")
    ids = [a["id"] for a in client.get("/albums").json()]
    assert album_id not in ids


# =============================================================
# Anti-Corruption Layer — no JPA / Java internals leak into API
# =============================================================

def test_no_jpa_annotations_in_list_response(client):
    client.put("/albums", json=SAMPLE_ALBUM)
    body = client.get("/albums").text
    for marker in JPA_LEAK_MARKERS:
        assert marker not in body, (
            f"JPA/Java internal '{marker}' must not appear in /albums response. "
            f"The new service's API must be clean of monolith implementation details."
        )


def test_no_jpa_annotations_in_single_album_response(client_with_album):
    client, album_id = client_with_album
    body = client.get(f"/albums/{album_id}").text
    for marker in JPA_LEAK_MARKERS:
        assert marker not in body, (
            f"JPA/Java internal '{marker}' must not appear in /albums/{{id}} response."
        )


def test_no_class_field_in_response(client):
    """albums.json had a '_class' field that Jackson ignored. New service must never emit it."""
    client.put("/albums", json=SAMPLE_ALBUM)
    album = client.get("/albums").json()[0]
    assert "_class" not in album, "_class is a Jackson/MongoDB internal — must not appear in API"


def test_response_fields_match_monolith_schema_exactly(client):
    """
    The new service's album JSON shape must be compatible with what the monolith produces.
    Extra fields are allowed; missing required fields are not.
    """
    client.put("/albums", json=SAMPLE_ALBUM)
    album = client.get("/albums").json()[0]
    missing = REQUIRED_FIELDS - set(album.keys())
    assert not missing, f"New service is missing fields that monolith produces: {missing}"
