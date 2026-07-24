import datetime
import threading
from contextlib import contextmanager
from typing import Optional, Any, List, Iterator

from sqlalchemy import create_engine, Engine, event
from sqlalchemy import text as sql_text
from sqlalchemy.orm import sessionmaker, Session

from src.core.log_system import print_d
from .migrations import migrate
from .models import Track, normalize_path

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
        track_object = Track(title=title, path=path, dt_create=datetime.datetime.now(),
                             dt_last_opened=datetime.datetime.now())
        self.session.add(track_object)
        self.flush()  # Needed to read back the generated id
        if commit:
            self.commit()
        return track_object.id

    def get_all_track(self) -> List[Track]:
        """Read the whole track list, most recently opened first.

        :returns: List[Track] - Track rows.
        """
        assert self.is_connected, "Database is not connected"
        return self.session.query(Track).order_by(Track.dt_last_opened.desc()).all()

    def get_track_by_path(self, path: str) -> Optional[Track]:
        """Find a track by its file path.

        :param path: Path to the audio file, normalized before the lookup.
        :returns: Track - Track row, None when the file is not in the list.
        """
        assert self.is_connected, "Database is not connected"
        return self.session.query(Track).filter(Track.path == normalize_path(path)).first()

    def delete_track(self, track: Track, commit: bool = True) -> None:
        """Remove a track from the list.

        :param track: Track row to delete.
        :param commit: Commit the transaction right away.
        :returns: None.
        """
        assert self.is_connected, "Database is not connected"
        self.session.delete(track)
        self.flush()
        if commit:
            self.commit()

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
