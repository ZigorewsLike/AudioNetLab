import datetime
from typing import Optional, Any, List

from sqlalchemy import create_engine, Engine, event
from sqlalchemy import text as sql_text
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, Track


@event.listens_for(Engine, "connect")
def set_sqlite_pragmas(dbapi_connection, connection_record):
    """Apply the SQLite pragmas on every new connection.

    WAL keeps reads from blocking writes while the player writes in the background.

    :param dbapi_connection: Raw DBAPI connection.
    :param connection_record: SQLAlchemy connection record.
    :returns: None.
    """
    print("SQLite pragmas has been set")
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class DBHandler:
    """Access layer for the local SQLite database with the track list (storage.db)."""

    def __init__(self):
        """Prepare the handler, no connection is opened yet.

        :returns: None.
        """
        self.databae_url: str = f'sqlite:///./storage.db'
        self.engine: Optional[Engine] = None
        self.session: Optional[Session] = None
        self._session_factory: Optional[sessionmaker] = None

    def connect(self) -> Session:
        """Open a session and create the missing tables.

        :returns: Session - Active sqlalchemy session.
        """
        # check_same_thread is off because workers touch the database from other threads
        self.engine = create_engine(self.databae_url, connect_args={"check_same_thread": False})
        self._session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
        )

        Base.metadata.create_all(bind=self.engine)
        self.session = self._session_factory()
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
        assert self.is_connected, "База данных не подключена"
        return self.session.execute(sql_text(query)).fetchall()

    def commit(self) -> None:
        """Commit the current transaction.

        :returns: None.
        """
        assert self.is_connected, "База данных не подключена"
        self.session.commit()

    def flush(self) -> None:
        """Flush the pending object changes to the database.

        :returns: None.
        """
        assert self.is_connected, "База данных не подключена"
        self.session.flush()

    def add_track(self, title: str, path: str, commit: bool = True) -> Optional[int]:
        """Add a track to the list, skipping paths that are already there.

        :param title: Track title.
        :param path: Path to the audio file, used as the uniqueness key.
        :param commit: Commit the transaction right away.
        :returns: int - Id of the new track, None when the path is already known.
        """
        assert self.is_connected, "База данных не подключена"
        existing_track = self.session.query(Track).filter(Track.path == path).all()
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
        assert self.is_connected, "База данных не подключена"
        return self.session.query(Track).order_by(Track.dt_last_opened.desc()).all()

    def delete_track(self, track: Track, commit: bool = True) -> None:
        """Remove a track from the list.

        :param track: Track row to delete.
        :param commit: Commit the transaction right away.
        :returns: None.
        """
        assert self.is_connected, "База данных не подключена"
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
        assert self.is_connected, "База данных не подключена"
        self.session.query(Track).filter(Track.id == track_id).update({"dt_last_opened": datetime.datetime.now()})
        if commit:
            self.commit()


if __name__ == '__main__':
    db = DBHandler()
    db.connect()
    db.add_track(title="Aboba", path="/home/user/Desktop/audio.mp3")
    db.add_track(title="345345", path="/home/user/Desktop/audio2.mp3")
    db.commit()
    print(db.get_all_track())
    db.disconnect()