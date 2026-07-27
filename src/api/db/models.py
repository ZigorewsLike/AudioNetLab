import os
from typing import Optional

from sqlalchemy import (Column, Integer, String, Float, Boolean, TIMESTAMP, DateTime,
                        ForeignKey, Index)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Separator between the parts of a composite key, a control char no tag value can hold
KEY_SEPARATOR = "\x1f"

# Articles stripped from the beginning of a name to build its sort name.
SORT_NAME_ARTICLES = ("the ", "a ", "an ")


def normalize_key(value: Optional[str]) -> str:
    """Fold a tag value into a case insensitive matching key.

    SQLite COLLATE NOCASE only folds ASCII, so "Ария" and "ария" would end up as two
    different artists. The key is therefore computed in Python with casefold() and
    stored in its own column, which also keeps the lookup index small.

    :param value: Raw tag value.
    :returns: str - Matching key, empty string when the value is missing.
    """
    if not value:
        return ""
    return " ".join(value.split()).casefold()


def make_album_key(artist_key: str, album_title: Optional[str]) -> str:
    """Build the matching key that decides which tracks belong to one album.

    The year is deliberately left out: a reissue tagged with a different year would
    otherwise split into a second album.

    :param artist_key: Normalized album artist name.
    :param album_title: Raw album title.
    :returns: str - Matching key of the album.
    """
    return f"{artist_key}{KEY_SEPARATOR}{normalize_key(album_title)}"


def normalize_path(path: str) -> str:
    """Fold a file path into the form stored in the path column.

    The path column is unique, so the same file reached through a dialog, a drop and
    a folder scan has to produce the same string. Separators are folded to forward
    slashes and the relative parts are collapsed. The case is left alone: the file
    system hands back the real case, and folding it would break the paths the player
    opens on a case sensitive volume.

    :param path: Raw path.
    :returns: str - Normalized path.
    """
    if not path:
        return ""
    return os.path.normpath(path).replace('\\', '/')


def make_sort_name(name: Optional[str]) -> str:
    """Build the name an artist is sorted by, without the leading article.

    :param name: Raw artist name.
    :returns: str - Sort name, empty string when the name is missing.
    """
    if not name:
        return ""
    stripped = " ".join(name.split())
    lowered = stripped.lower()
    for article in SORT_NAME_ARTICLES:
        if lowered.startswith(article):
            return stripped[len(article):]
    return stripped


class Cover(Base):
    """Cover image known to the library, one row per distinct image.

    The bytes are not stored here. They live in the cover cache on disk as
    pre-scaled files named after the hash, so an album shared by fifteen tracks
    is decoded and written once.
    """
    __tablename__ = 'cover'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hash = Column(String, nullable=False, unique=True, index=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    source = Column(String, nullable=True)  # 'tag' when taken from the tags, 'disk' from a neighbouring image


class Artist(Base):
    """Performer, deduplicated by the normalized form of the name."""
    __tablename__ = 'artist'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)  # As written in the tags, shown in the interface
    name_key = Column(String, nullable=False, unique=True, index=True)  # normalize_key(name)
    sort_name = Column(String, nullable=True, index=True)


class Album(Base):
    """Album, deduplicated by album artist and title.

    artist_id points at the album artist, which is the ALBUMARTIST tag when the file
    has one and the track artist otherwise. Without that a compilation would fall
    apart into one album per track.
    """
    __tablename__ = 'album'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=False)
    match_key = Column(String, nullable=False, unique=True, index=True)  # make_album_key(...)
    artist_id = Column(Integer, ForeignKey('artist.id', ondelete='SET NULL'), nullable=True, index=True)
    cover_id = Column(Integer, ForeignKey('cover.id', ondelete='SET NULL'), nullable=True)
    year = Column(Integer, nullable=True, index=True)
    sort_index = Column(Integer, nullable=True)  # Manual order in the album grid, NULL follows the chosen sorting
    dt_added = Column(TIMESTAMP, nullable=True, index=True)


class Track(Base):
    """Track known to the application, one row per file added to the library.

    The audio itself stays on disk, the database only keeps the path, the tags and
    the timestamps. Heavy per track data (feature vectors, lyrics) lives in
    data/registry/<id>.

    No relationship() is declared on purpose: widgets keep Track objects long after
    the session that loaded them is closed, and a lazy load on a detached instance
    would raise. The repository joins explicitly instead.
    """
    __tablename__ = 'track'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=False, index=True)
    title_key = Column(String, nullable=True, index=True)  # normalize_key(title), searched instead of title
    path = Column(String, nullable=False, unique=True, index=True)

    artist_id = Column(Integer, ForeignKey('artist.id', ondelete='SET NULL'), nullable=True, index=True)
    album_id = Column(Integer, ForeignKey('album.id', ondelete='SET NULL'), nullable=True, index=True)
    cover_id = Column(Integer, ForeignKey('cover.id', ondelete='SET NULL'), nullable=True)

    track_no = Column(Integer, nullable=True)
    disc_no = Column(Integer, nullable=True)
    year = Column(Integer, nullable=True)
    genre = Column(String, nullable=True)

    duration = Column(Float, nullable=True)  # Seconds
    bitrate = Column(Integer, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    bits_per_sample = Column(Integer, nullable=True)  # NULL for a lossy format like MP3

    file_size = Column(Integer, nullable=True)
    file_mtime = Column(Float, nullable=True)  # st_mtime, lets a rescan skip unchanged files
    is_missing = Column(Boolean, nullable=False, default=False, server_default='0')

    play_count = Column(Integer, nullable=False, default=0, server_default='0')
    dt_create = Column(TIMESTAMP, nullable=False)
    dt_last_opened = Column(DateTime, nullable=True)


class LibraryFolder(Base):
    """Folder the library is scanned from."""
    __tablename__ = 'library_folder'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    path = Column(String, nullable=False, unique=True, index=True)
    recursive = Column(Boolean, nullable=False, default=True, server_default='1')
    dt_last_scan = Column(DateTime, nullable=True)


# Composite index for the album page: the tracks of one album in playing order.
Index('ix_track_album_order', Track.album_id, Track.disc_no, Track.track_no)
