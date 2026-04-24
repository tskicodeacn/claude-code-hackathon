"""
Anti-Corruption Layer (The Fence) — tests for album-catalog-service.

These tests enforce the boundary between the Spring Music monolith and the new service.
They MUST fail loudly when the boundary is crossed, so the root cause is immediately obvious.

Design rule: The monolith's implementation details (JPA annotations, Spring framework,
Java class names, Hibernate specifics) must NEVER appear in:
  - The new service's HTTP API responses
  - The new service's OpenAPI schema
  - The new service's source code

Why tests AND a hook:
  Tests catch runtime leakage (API responses).
  The PreToolUse hook catches authoring leakage (source code).
  Both are needed: the hook is a hard stop, the tests are a regression net.

See: spring-music-master/docs/adr/002-fence-hook-vs-prompt.md
"""

import ast
import os
import json
import pytest
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from main import app, _store

# --- Marker sets -----------------------------------------------------------

JPA_ANNOTATIONS = ["@Entity", "@Table", "@Column", "@Id", "@GeneratedValue", "@GenericGenerator", "@MappedSuperclass"]
SPRING_ANNOTATIONS = ["@SpringBootApplication", "@RestController", "@RequestMapping", "@Autowired", "@Service", "@Repository", "@Component"]
JAVA_IMPORTS = ["javax.persistence", "jakarta.persistence", "org.springframework", "org.hibernate"]
MONOLITH_INTERNALS = ["CrudRepository", "JpaAlbumRepository", "RedisAlbumRepository", "MongoAlbumRepository", "RandomIdGenerator"]
ALL_LEAK_MARKERS = JPA_ANNOTATIONS + SPRING_ANNOTATIONS + JAVA_IMPORTS + MONOLITH_INTERNALS + ["_class"]

SAMPLE = {"title": "Blue Train", "artist": "John Coltrane", "releaseYear": "1957", "genre": "Jazz"}


@pytest.fixture(autouse=True)
def reset_store():
    _store.clear()
    yield
    _store.clear()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# =============================================================
# API response fence — runtime checks
# =============================================================

def test_get_albums_response_contains_no_jpa_annotations(client):
    client.put("/albums", json=SAMPLE)
    body = client.get("/albums").text
    for marker in JPA_ANNOTATIONS:
        assert marker not in body, (
            f"\n\nFENCE VIOLATION: JPA annotation '{marker}' found in GET /albums response.\n"
            f"This is a monolith-internal detail that must NOT appear in the new service's API.\n"
            f"The Album Catalog Service must define its own domain model without JPA coupling.\n"
            f"Offending response body snippet: {body[:300]}"
        )


def test_get_albums_response_contains_no_spring_annotations(client):
    client.put("/albums", json=SAMPLE)
    body = client.get("/albums").text
    for marker in SPRING_ANNOTATIONS:
        assert marker not in body, (
            f"\n\nFENCE VIOLATION: Spring annotation '{marker}' found in GET /albums response.\n"
            f"Spring MVC/DI annotations are monolith internals. The new service uses FastAPI.\n"
            f"Offending response body snippet: {body[:300]}"
        )


def test_get_albums_response_contains_no_java_package_names(client):
    client.put("/albums", json=SAMPLE)
    body = client.get("/albums").text
    for marker in JAVA_IMPORTS:
        assert marker not in body, (
            f"\n\nFENCE VIOLATION: Java package '{marker}' found in GET /albums response.\n"
            f"Java package names must not leak into the Python service's API.\n"
            f"Offending response body snippet: {body[:300]}"
        )


def test_get_single_album_response_contains_no_jpa_leak(client):
    album_id = client.put("/albums", json=SAMPLE).json()["id"]
    body = client.get(f"/albums/{album_id}").text
    for marker in ALL_LEAK_MARKERS:
        assert marker not in body, (
            f"\n\nFENCE VIOLATION: '{marker}' found in GET /albums/{{id}} response.\n"
            f"Monolith internal detail must not appear in new service API.\n"
            f"Offending response body snippet: {body[:300]}"
        )


def test_put_album_response_contains_no_leak(client):
    body = client.put("/albums", json=SAMPLE).text
    for marker in ALL_LEAK_MARKERS:
        assert marker not in body, (
            f"\n\nFENCE VIOLATION: '{marker}' found in PUT /albums response.\n"
            f"Create response must be clean of monolith implementation details.\n"
            f"Offending response body snippet: {body[:300]}"
        )


def test_no_class_field_in_any_album_response(client):
    """
    albums.json (monolith seed data) had a '_class' field for MongoDB type discrimination.
    Jackson ignored it on read. The new service must never emit it.
    If '_class' appears: someone copied the monolith's MongoDB serialization config.
    """
    client.put("/albums", json=SAMPLE)
    album = client.get("/albums").json()[0]
    assert "_class" not in album, (
        "\n\nFENCE VIOLATION: '_class' field found in API response.\n"
        "'_class' is a MongoDB/Jackson type discriminator from the monolith's seed data.\n"
        "The new service must not emit this field. It leaks the monolith's persistence strategy."
    )


# =============================================================
# OpenAPI schema fence — schema-level checks
# =============================================================

def test_openapi_schema_contains_no_jpa_type_references(client):
    schema = client.get("/openapi.json").text
    for marker in JPA_ANNOTATIONS + JAVA_IMPORTS:
        assert marker not in schema, (
            f"\n\nFENCE VIOLATION: '{marker}' found in OpenAPI schema.\n"
            f"The service's public contract (OpenAPI) must not reference JPA or Java types.\n"
            f"This would expose monolith implementation details to API consumers."
        )


def test_openapi_schema_album_fields_match_monolith_contract(client):
    """
    The new service's AlbumResponse schema must expose the same field names as the monolith.
    Extra fields allowed. Missing required fields are a contract break.
    """
    required_fields = {"id", "title", "artist", "releaseYear", "genre", "trackCount", "albumId"}
    schema = json.loads(client.get("/openapi.json").text)

    album_response_schema = (
        schema.get("components", {})
              .get("schemas", {})
              .get("AlbumResponse", {})
    )
    assert album_response_schema, "AlbumResponse schema not found in OpenAPI spec"

    schema_fields = set(album_response_schema.get("properties", {}).keys())
    missing = required_fields - schema_fields
    assert not missing, (
        f"\n\nFENCE VIOLATION: AlbumResponse schema is missing fields: {missing}\n"
        f"The new service's OpenAPI schema must be compatible with the monolith's JSON output.\n"
        f"Consumers depend on these field names. Missing fields break the migration contract."
    )


# =============================================================
# Source code fence — static analysis
# =============================================================

def _read_service_source() -> str:
    src_path = os.path.join(os.path.dirname(__file__), "..", "main.py")
    with open(src_path) as f:
        return f.read()


def test_source_code_contains_no_java_imports():
    source = _read_service_source()
    java_markers = ["import javax", "import jakarta", "import org.springframework", "import org.hibernate"]
    for marker in java_markers:
        assert marker not in source, (
            f"\n\nFENCE VIOLATION: Java import '{marker}' found in album-catalog-service/main.py.\n"
            f"The new service is Python. Java imports cannot work here and signal a copy-paste\n"
            f"from the monolith. Remove immediately and rewrite using Python equivalents."
        )


def test_source_code_contains_no_jpa_annotation_strings():
    source = _read_service_source()
    for annotation in JPA_ANNOTATIONS:
        # Check as a string (comments, strings) not just imports
        assert annotation not in source, (
            f"\n\nFENCE VIOLATION: JPA annotation string '{annotation}' found in main.py.\n"
            f"Even as a comment or string constant, JPA annotations in the new service\n"
            f"indicate the monolith model is bleeding across the boundary."
        )


def test_source_code_does_not_reference_monolith_class_names():
    source = _read_service_source()
    for class_name in MONOLITH_INTERNALS:
        assert class_name not in source, (
            f"\n\nFENCE VIOLATION: Monolith class '{class_name}' referenced in main.py.\n"
            f"The new service must not depend on or reference the monolith's internal classes.\n"
            f"Define equivalent abstractions in the new service."
        )


def test_source_code_is_valid_python():
    """Meta-test: if the fence breaks this, someone introduced a syntax error while bypassing it."""
    source = _read_service_source()
    try:
        ast.parse(source)
    except SyntaxError as e:
        pytest.fail(
            f"\n\nSOURCE INVALID: main.py has a Python syntax error: {e}\n"
            f"This may indicate a partial copy-paste from Java source."
        )
