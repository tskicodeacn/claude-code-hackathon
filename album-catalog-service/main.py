from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from typing import Optional
import uuid

app = FastAPI(
    title="Album Catalog Service",
    description="Extracted from Spring Music monolith. Fixes known bugs and removes JPA coupling.",
    version="1.0.0",
)

# In-memory store: id → album dict
# Swap for a real DB adapter without changing the HTTP layer.
_store: dict[str, dict] = {}


class AlbumRequest(BaseModel):
    id: Optional[str] = None
    title: str
    artist: str
    releaseYear: str
    genre: str
    trackCount: int = 0
    albumId: Optional[str] = None


class AlbumResponse(BaseModel):
    id: str
    title: str
    artist: str
    releaseYear: str
    genre: str
    trackCount: int
    albumId: Optional[str]


@app.get("/albums", response_model=list[AlbumResponse])
def list_albums():
    return list(_store.values())


@app.get("/albums/{album_id}", response_model=AlbumResponse)
def get_album(album_id: str):
    # FIX: monolith returns HTTP 200 + empty body for missing albums (orElse(null) bug).
    # This service returns 404 as per REST conventions (see ADR-001, Anti-Corruption Layer).
    album = _store.get(album_id)
    if album is None:
        raise HTTPException(status_code=404, detail=f"Album '{album_id}' not found")
    return album


@app.put("/albums", response_model=AlbumResponse)
def create_album(album: AlbumRequest):
    # Server always generates ID — client-supplied id is ignored, matching monolith behavior.
    new_id = str(uuid.uuid4())
    record = _to_record(new_id, album)
    _store[new_id] = record
    return record


@app.post("/albums", response_model=AlbumResponse)
def update_album(album: AlbumRequest):
    if album.id is None or album.id not in _store:
        raise HTTPException(status_code=404, detail=f"Album '{album.id}' not found")
    record = _to_record(album.id, album)
    _store[album.id] = record
    return record


@app.delete("/albums/{album_id}")
def delete_album(album_id: str):
    _store.pop(album_id, None)
    # Matches monolith: HTTP 200 with empty body regardless of whether album existed.
    return Response(status_code=200)


def _to_record(album_id: str, album: AlbumRequest) -> dict:
    return {
        "id": album_id,
        "title": album.title,
        "artist": album.artist,
        "releaseYear": album.releaseYear,
        "genre": album.genre,
        "trackCount": album.trackCount,
        "albumId": album.albumId,
    }
