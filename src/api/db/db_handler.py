import datetime
import threading
from contextlib import contextmanager
from typing import Optional, Any, List, Iterator

from sqlalchemy import create_engine, Engine, event, func
from sqlalchemy import text as sql_text
from sqlalchemy.orm import sessionmaker, Session

from src.core.log_system import print_d
from .migrations import migrate
from .models import Album, Artist, Track, normalize_key, normalize_path

DATABASE_URL = "sqlite:///./storage.db"

# The engine owns the connection pool, so it is created once for the whole process.
# Building one per query, as the first version did, reopened the file and re-ran the
# pragmas on every list refresh.
_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None
_engine_lock = threading.Lock()


@event.listens_for(Engine, "connect")
def set_sqlite_pragmas(dbapi_connection, connection_record):
    """Apply the SQLite pragmas on every new connection.

    WAL keeps reads from blocking writes while the player writes in the background.
    busy_timeout matters once the library scanner writes from its own thread: without
    it a connection that meets a held write lock fails immediately instead of waiting.

    :param dbapi_connection: Raw DBAPI connection.
    :param connection_record: SQLAlchemy connection record.
    :returns: None.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()


def get_engine() -> Engine:
    """Return the process wide engine, creating and migrating the database once.

    :returns: Engine - Shared engine.
    """
    global _engine, _session_factory
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is None:
            # check_same_thread is off because workers touch the database from other threads
            engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
            version = migrate(engine)
            print_d(f"Database ready, schema version {version}")
            _session_factory = sessionmaker(
                bind=engine,
                autocommit=False,
                autoflush=False,
                # Widgets keep Track objects after their session is closed and read the
                # attributes while painting. Expiring on commit would turn those reads
                # into lazy loads against a dead session.
                expire_on_commit=False,
            )
            _engine = engine
    return _engine


def get_session_factory() -> sessionmaker:
    """Return the shared session factory.

    :returns: sessionmaker - Factory bound to the shared engine.
    """
    get_engine()
    return _session_factory


def create_session() -> Session:
    """Open a session for the calling thread.

    Every thread needs its own session, a Session is not safe to share.

    :returns: Session - New session.
    """
    return get_session_factory()()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Run a block in a session that commits on success and rolls back on an error.

    :returns: Iterator[Session] - The session for the duration of the block.
    """
    session = create_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class DBHandler:
    """Access layer for the local SQLite database with the track list (storage.db)."""

    def __init__(self):
        """Prepare the handler, no session is opened yet.

        :returns: None.
        """
        self.databae_url: str = DATABASE_URL
        self.session: Optional[Session] = None

    @property
    def engine(self) -> Engine:
        """Engine shared by the whole process.

        :returns: Engine - Shared engine.
        """
        return get_engine()

    def connect(self) -> Session:
        """Open a session on the shared engine.

        Calling it again while a session is open returns the same session instead of
        leaking the previous one.

        :returns: Session - Active sqlalchemy session.
        """
        if self.session is not None and self.session.is_active:
            return self.session
        self.session = create_session()
        return self.session

    def disconnect(self):
        """Close the active session.

        :returns: None.
        """
        if self.session is not None:
            self.session.close()
            self.session = None

    @property
    def is_connected(self) -> bool:
        """Whether an active session is available.

        :returns: bool - True when queries can be executed.
        """
        return self.session is not None and self.session.is_active

    def execute(self, query: str) -> Optional[Any]:
        """Run a raw SQL query.

        :param query: SQL text.
        :returns: Fetched rows.
        """
        assert self.is_connected, "Database is not connected"
        return self.session.execute(sql_text(query)).fetchall()

    def commit(self) -> None:
        """Commit the current transaction.

        :returns: None.
        """
        assert self.is_connected, "Database is not connected"
        self.session.commit()

    def flush(self) -> None:
        """Flush the pending object changes to the database.

        :returns: None.
        """
        assert self.is_connected, "Database is not connected"
        self.session.flush()

    def add_track(self, title: str, path: str, commit: bool = True) -> Optional[int]:
        """Add a track to the list, skipping paths that are already there.

        :param title: Track title.
        :param path: Path to the audio file, used as the uniqueness key.
        :param commit: Commit the transaction right away.
        :returns: int - Id of the new track, None when the path is already known.
        """
        assert self.is_connected, "Database is not connected"
        path = normalize_path(path)
        existing_track = self.session.query(Track.id).filter(Track.path == path).first()
        if existing_track:
            return None
        # title_key mirrors what the scanner writes, so a track added one at a time is
        # found by the library search the same as a scanned one
        track_object = Track(title=title, title_key=normalize_key(title), path=path,
                             dt_create=datetime.datetime.now(),
                             dt_last_opened=datetime.datetime.now())
        self.session.add(track_object)
        self.flush()  # Needed to read back the generated id
        if commit:
            self.commit()
        return track_object.id

    def get_all_track(self) -> List[Track]:
        """Read the whole track list, most recently added or opened first.

        A track imported by the scanner has never been opened, so its dt_last_opened
        is NULL and it would sink below every opened track, out of sight at the bottom
        of the list. Ordering on the add time as a fallback keeps a freshly imported
        track where the user expects it, at the top.

        :returns: List[Track] - Track rows.
        """
        assert self.is_connected, "Database is not connected"
        recency = func.coalesce(Track.dt_last_opened, Track.dt_create)
        return self.session.query(Track).order_by(recency.desc()).all()

    def get_track_by_path(self, path: str) -> Optional[Track]:
        """Find a track by its file path.

        :param path: Path to the audio file, normalized before the lookup.
        :returns: Track - Track row, None when the file is not in the list.
        """
        assert self.is_connected, "Database is not connected"
        return self.session.query(Track).filter(Track.path == normalize_path(path)).first()

    def delete_track(self, track: Track, commit: bool = True) -> None:
        """Remove a track from the list and drop its album and artist if they empty out.

        The album and artist rows live independently of the tracks, so removing the
        last track of an album would otherwise leave a ghost tile in the library that
        shows nothing and cannot be played. They are cleaned up here in the same
        transaction.

        :param track: Track row to delete, may come from a closed session.
        :param commit: Commit the transaction right away.
        :returns: None.
        """
        assert self.is_connected, "Database is not connected"
        # Rebind by id: the widgets hold tracks loaded in an earlier, now closed session
        db_track = self.session.get(Track, track.id)
        if db_track is None:
            return
        album_id = db_track.album_id
        artist_id = db_track.artist_id
        self.session.delete(db_track)
        self.flush()
        self._delete_if_orphaned(album_id, artist_id)
        if commit:
            self.commit()

    def _delete_if_orphaned(self, album_id: Optional[int], artist_id: Optional[int]) -> None:
        """Drop an album or artist that no track references any more.

        :param album_id: Album the deleted track belonged to, or None.
        :param artist_id: Artist the deleted track belonged to, or None.
        :returns: None.
        """
        if album_id is not None:
            still_used = self.session.query(Track.id).filter(Track.album_id == album_id).first()
            if still_used is None:
                self.session.query(Album).filter(Album.id == album_id).delete()
        if artist_id is not None:
            still_used = self.session.query(Track.id).filter(Track.artist_id == artist_id).first()
            if still_used is None:
                self.session.query(Artist).filter(Artist.id == artist_id).delete()

    def update_track_last_opened(self, track_id: int, commit: bool = True) -> None:
        """Stamp the track as opened now, which also reorders the list.

        :param track_id: Track id.
        :param commit: Commit the transaction right away.
        :returns: None.
        """
        assert self.is_connected, "Database is not connected"
        self.session.query(Track).filter(Track.id == track_id).update({"dt_last_opened": datetime.datetime.now()})
        if commit:
            self.commit()
