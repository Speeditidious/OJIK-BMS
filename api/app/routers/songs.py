"""Song list and detail endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.song import Song

router = APIRouter(prefix="/songs", tags=["songs"])


class SongRead(BaseModel):
    id: str
    md5: str | None
    sha256: str | None
    title: str | None
    artist: str | None
    bpm: float | None
    total_notes: int | None
    youtube_url: str | None
    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=list[SongRead])
async def list_songs(
    title: str | None = Query(None, description="Filter by title (partial match)"),
    artist: str | None = Query(None, description="Filter by artist (partial match)"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[SongRead]:
    """List songs with optional filtering."""
    query = select(Song)

    if title:
        query = query.where(Song.title.ilike(f"%{title}%"))
    if artist:
        query = query.where(Song.artist.ilike(f"%{artist}%"))

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    songs = result.scalars().all()

    return [
        SongRead(
            id=str(s.id),
            md5=s.md5,
            sha256=s.sha256,
            title=s.title,
            artist=s.artist,
            bpm=s.bpm,
            total_notes=s.total_notes,
            youtube_url=s.youtube_url,
        )
        for s in songs
    ]


@router.get("/{sha256}", response_model=SongRead)
async def get_song_by_sha256(
    sha256: str,
    db: AsyncSession = Depends(get_db),
) -> SongRead:
    """Get a song by SHA256 hash."""
    result = await db.execute(select(Song).where(Song.sha256 == sha256))
    song = result.scalar_one_or_none()

    if song is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song not found")

    return SongRead(
        id=str(song.id),
        md5=song.md5,
        sha256=song.sha256,
        title=song.title,
        artist=song.artist,
        bpm=song.bpm,
        total_notes=song.total_notes,
        youtube_url=song.youtube_url,
    )
