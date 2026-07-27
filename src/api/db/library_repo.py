from typing import Dict, List, NamedTuple, Optional

from sqlalchemy import delete, func, select, nulls_last
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from src.enums import AlbumSort, ArtistSort, TrackSort
from .models import Album, Artist, Cover, Track, normalize_key


class AlbumRow(NamedTuple):
    """One tile of the album grid."""
    id: int
    title: str
    artist: Optional[str]
    artist_id: Optional[int]
    year: Optional[int]
    cover_hash: Optional[str]
    track_count: int
    duration: Optional[float]


class ArtistRow(NamedTuple):
    """One tile of the artist grid."""
    id: int
    name: str
    album_count: int
    track_count: int
    cover_hash: Optional[str]


class TrackRow(NamedTuple):
    """One row of the track table."""
    id: int
    title: str
    path: str
    artist: Optional[str]
    album: Optional[str]
    album_id: Optional[int]
    track_no: Optional[int]
    disc_no: Optional[int]
    duration: Optional[float]
    year: Optional[int]
    cover_hash: Optional[str]
    is_missing: bool
    bitrate: Optional[int]
    sample_rate: Optional[int]
    bits_per_sample: Optional[int]
    file_ext: Optional[str]  # Uppercase codec label from the file extension, e.g. FLAC


class LibraryCounts(NamedTuple):
    """Size of the library, shown in the header of the tab."""
    tracks: int
    albums: int
    artists: int


def _search_pattern(search: Optional[str]) -> Optional[str]:
    """Turn a search string into a LIKE pattern for the normalized key columns.

    The key columns are already casefolded in Python, so the pattern is folded the
    same way. Matching against the display columns instead would use SQLite LIKE,
    which only ignores case for ASCII and would miss "ария" typed for "Ария".

    :param search: Raw search string.
    :returns: str - LIKE pattern, None when the search is empty.
    """
    key = normalize_key(search)
    if not key:
        return None
    return f"%{key}%"


def _apply_album_sort(query: Select, sort: AlbumSort) -> Select:
    """Add the ORDER BY of the album grid to a query.

    :param query: Query to order.
    :param sort: Chosen order.
    :returns: Select - Ordered query.
    """
    if sort is AlbumSort.TITLE:
        return query.order_by(Album.match_key)
    if sort is AlbumSort.YEAR:
        return query.order_by(nulls_last(Album.year.desc()), Album.match_key)
    if sort is AlbumSort.DATE_ADDED:
        return query.order_by(nulls_last(Album.dt_added.desc()), Album.id.desc())
    if sort is AlbumSort.MANUAL:
        # Tiles never dragged anywhere keep sort_index NULL and stay after the arranged ones
        return query.order_by(nulls_last(Album.sort_index.asc()), Album.match_key)
    return query.order_by(nulls_last(Artist.sort_name), nulls_last(Album.year), Album.match_key)


def _apply_track_sort(query: Select, sort: TrackSort) -> Select:
    """Add the ORDER BY of the track table to a query.

    :param query: Query to order.
    :param sort: Chosen order.
    :returns: Select - Ordered query.
    """
    if sort is TrackSort.ARTIST:
        return query.order_by(nulls_last(Artist.sort_name), nulls_last(Album.year), Album.match_key,
                              Track.disc_no, Track.track_no)
    if sort is TrackSort.ALBUM:
        return query.order_by(nulls_last(Album.match_key), Track.disc_no, Track.track_no)
    if sort is TrackSort.DURATION:
        return query.order_by(nulls_last(Track.duration.desc()))
    if sort is TrackSort.YEAR:
        return query.order_by(nulls_last(Track.year.desc()), Track.title_key)
    if sort is TrackSort.DATE_ADDED:
        return query.order_by(Track.dt_create.desc(), Track.id.desc())
    if sort is TrackSort.LAST_OPENED:
        return query.order_by(nulls_last(Track.dt_last_opened.desc()))
    return query.order_by(nulls_last(Track.title_key))


def list_albums(session: Session,
                search: Optional[str] = None,
                artist_id: Optional[int] = None,
                sort: AlbumSort = AlbumSort.ARTIST) -> List[AlbumRow]:
    """Read the albums for the grid.

    The rows come back as tuples rather than ORM objects on purpose: the grid model
    holds all of them at once, and an ORM instance costs an order of magnitude more
    memory and build time per row.

    :param session: Open session.
    :param search: Filter on the album title and the artist name.
    :param artist_id: Keep only the albums of one artist.
    :param sort: Order of the result.
    :returns: List[AlbumRow] - Albums in the requested order.
    """
    query = (
        select(Album.id, Album.title, Artist.name, Album.artist_id, Album.year, Cover.hash,
               func.count(Track.id), func.sum(Track.duration))
        .select_from(Album)
        .outerjoin(Artist, Artist.id == Album.artist_id)
        .outerjoin(Cover, Cover.id == Album.cover_id)
        .outerjoin(Track, Track.album_id == Album.id)
        .group_by(Album.id)
    )
    pattern = _search_pattern(search)
    if pattern is not None:
        # match_key is "artist key + separator + title key", so one LIKE covers both
        query = query.where(Album.match_key.like(pattern))
    if artist_id is not None:
        query = query.where(Album.artist_id == artist_id)
    query = _apply_album_sort(query, sort)
    return [AlbumRow(*row) for row in session.execute(query).all()]


def list_artists(session: Session,
                 search: Optional[str] = None,
                 sort: ArtistSort = ArtistSort.NAME) -> List[ArtistRow]:
    """Read the artists for the grid.

    :param session: Open session.
    :param search: Filter on the artist name.
    :param sort: Order of the result.
    :returns: List[ArtistRow] - Artists in the requested order.
    """
    # The tile shows the cover of one of the artist albums, min() picks it deterministically
    query = (
        select(Artist.id, Artist.name,
               func.count(func.distinct(Album.id)),
               func.count(func.distinct(Track.id)),
               func.min(Cover.hash))
        .select_from(Artist)
        .outerjoin(Album, Album.artist_id == Artist.id)
        .outerjoin(Cover, Cover.id == Album.cover_id)
        .outerjoin(Track, Track.artist_id == Artist.id)
        .group_by(Artist.id)
    )
    pattern = _search_pattern(search)
    if pattern is not None:
        query = query.where(Artist.name_key.like(pattern))
    if sort is ArtistSort.ALBUM_COUNT:
        query = query.order_by(func.count(func.distinct(Album.id)).desc(), Artist.sort_name)
    else:
        query = query.order_by(nulls_last(Artist.sort_name))
    return [ArtistRow(*row) for row in session.execute(query).all()]


def list_tracks(session: Session,
                search: Optional[str] = None,
                album_id: Optional[int] = None,
                artist_id: Optional[int] = None,
                sort: TrackSort = TrackSort.TITLE,
                limit: Optional[int] = None) -> List[TrackRow]:
    """Read the tracks for the table or for an album page.

    :param session: Open session.
    :param search: Filter on the track title, the album title and the artist name.
    :param album_id: Keep only the tracks of one album.
    :param artist_id: Keep only the tracks of one artist.
    :param sort: Order of the result.
    :param limit: Maximum number of rows.
    :returns: List[TrackRow] - Tracks in the requested order.
    """
    query = (
        select(Track.id, Track.title, Track.path, Artist.name, Album.title, Track.album_id,
               Track.track_no, Track.disc_no, Track.duration, Track.year,
               Cover.hash, Track.is_missing,
               Track.bitrate, Track.sample_rate, Track.bits_per_sample)
        .select_from(Track)
        .outerjoin(Artist, Artist.id == Track.artist_id)
        .outerjoin(Album, Album.id == Track.album_id)
        # Track cover wins over the album cover; the join matches one row, so no grouping
        .outerjoin(Cover, Cover.id == func.coalesce(Track.cover_id, Album.cover_id))
    )
    pattern = _search_pattern(search)
    if pattern is not None:
        query = query.where(
            Track.title_key.like(pattern)
            | Album.match_key.like(pattern)
            | Artist.name_key.like(pattern)
        )
    if album_id is not None:
        query = query.where(Track.album_id == album_id)
    if artist_id is not None:
        query = query.where(Track.artist_id == artist_id)
    query = _apply_track_sort(query, sort)
    if limit is not None:
        query = query.limit(limit)
    return [_track_row(row) for row in session.execute(query).all()]


def _track_row(row) -> TrackRow:
    """Build a TrackRow from a query row, deriving the codec label from the path.

    :param row: Query row with the track columns in select order.
    :returns: TrackRow - The typed row.
    """
    path = row[2]
    extension = path.rsplit(".", 1)[-1].upper() if path and "." in path else None
    return TrackRow(*row, file_ext=extension)


def get_album(session: Session, album_id: int) -> Optional[AlbumRow]:
    """Read one album for its detail page.

    :param session: Open session.
    :param album_id: Album id.
    :returns: AlbumRow - The album, None when it is gone.
    """
    query = (
        select(Album.id, Album.title, Artist.name, Album.artist_id, Album.year, Cover.hash,
               func.count(Track.id), func.sum(Track.duration))
        .select_from(Album)
        .outerjoin(Artist, Artist.id == Album.artist_id)
        .outerjoin(Cover, Cover.id == Album.cover_id)
        .outerjoin(Track, Track.album_id == Album.id)
        .where(Album.id == album_id)
        .group_by(Album.id)
    )
    row = session.execute(query).first()
    return AlbumRow(*row) if row is not None else None


def get_track_nav_ids(session: Session, track_id: int) -> tuple:
    """Read the album and artist a track belongs to, for jumping to them from the player.

    :param session: Open session.
    :param track_id: Track id.
    :returns: tuple - (album_id, artist_id), each None when unset or the track is gone.
    """
    row = session.execute(
        select(Track.album_id, Track.artist_id).where(Track.id == track_id)
    ).first()
    return (row[0], row[1]) if row is not None else (None, None)


def get_album_track_ids(session: Session, album_id: int) -> List[int]:
    """Read the track ids of an album in playing order, for the play queue.

    :param session: Open session.
    :param album_id: Album id.
    :returns: List[int] - Track ids ordered by disc and track number.
    """
    query = (
        select(Track.id)
        .where(Track.album_id == album_id)
        .order_by(nulls_last(Track.disc_no), nulls_last(Track.track_no), Track.title_key)
    )
    return list(session.scalars(query).all())


class PathEntry(NamedTuple):
    """What the scanner needs to know about a path already in the library."""
    track_id: int
    mtime: float
    is_missing: bool


def get_path_index(session: Session) -> Dict[str, PathEntry]:
    """Read every known path with the state the scanner diffs against.

    The scanner loads this once and compares the file system to it, which is what
    keeps a rescan of an unchanged library down to a directory walk.

    :param session: Open session.
    :returns: Dict[str, PathEntry] - Track id, modification time and missing flag per path.
    """
    rows = session.execute(select(Track.path, Track.id, Track.file_mtime, Track.is_missing)).all()
    return {path: PathEntry(track_id, mtime or 0.0, bool(is_missing))
            for path, track_id, mtime, is_missing in rows}


def delete_orphans(session: Session) -> tuple:
    """Remove every album and artist that no track references any more.

    A whole-library sweep, unlike the targeted cleanup on a single delete. The caller
    commits.

    :param session: Open session.
    :returns: tuple - Number of albums and artists removed.
    """
    used_albums = select(Track.album_id).where(Track.album_id.is_not(None))
    albums = session.execute(delete(Album).where(Album.id.not_in(used_albums))).rowcount
    used_artists = select(Track.artist_id).where(Track.artist_id.is_not(None))
    artists = session.execute(delete(Artist).where(Artist.id.not_in(used_artists))).rowcount
    return albums, artists


class QueueTrack(NamedTuple):
    """Display fields of one queued track."""
    id: int
    title: str
    artist: Optional[str]
    duration: Optional[float]


def get_queue_tracks(session: Session, track_ids: List[int]) -> dict:
    """Read the display fields of a set of tracks, for the queue panel.

    Returned as a mapping so the caller can lay the rows out in queue order without a
    query per track.

    :param session: Open session.
    :param track_ids: Track ids to read.
    :returns: dict - QueueTrack per id, missing ids simply absent.
    """
    if not track_ids:
        return {}
    query = (
        select(Track.id, Track.title, Artist.name, Track.duration)
        .select_from(Track)
        .outerjoin(Artist, Artist.id == Track.artist_id)
        .where(Track.id.in_(track_ids))
    )
    return {row[0]: QueueTrack(*row) for row in session.execute(query).all()}


def get_counts(session: Session) -> LibraryCounts:
    """Count what the library holds.

    :param session: Open session.
    :returns: LibraryCounts - Number of tracks, albums and artists.
    """
    tracks = session.scalar(select(func.count(Track.id))) or 0
    albums = session.scalar(select(func.count(Album.id))) or 0
    artists = session.scalar(select(func.count(Artist.id))) or 0
    return LibraryCounts(tracks=tracks, albums=albums, artists=artists)
