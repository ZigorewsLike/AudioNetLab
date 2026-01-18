import datetime
from typing import Optional, Any, List

from sqlalchemy import create_engine, or_, Engine, event
from sqlalchemy import text as sql_text
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, Track


@event.listens_for(Engine, "connect")
def set_sqlite_pragmas(dbapi_connection, connection_record):
    print("SQLite pragmas has been set")
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class DBHandler:
    def __init__(self):
        self.databae_url: str = f'sqlite:///./storage.db'
        self.engine: Optional[Engine] = None
        self.session: Optional[Session] = None
        self._session_factory: Optional[sessionmaker] = None

    def connect(self) -> Session:
        """
        Подключение к БД

        :return: Сессия sqlalchemy (Session)
        """
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
        """
        Отключение от БД

        :return:
        """
        if self.session is not None:
            self.session.close()
            self.session = None

    @property
    def is_connected(self) -> bool:
        """
        Подключена ли БД

        :return: bool
        """
        return self.session is not None and self.session.is_active

    def execute(self, query: str) -> Optional[Any]:
        """
        Выполнение запроса

        :param query: Запрос
        :return: Ответ БД
        """
        assert self.is_connected, "База данных не подключена"
        return self.session.execute(sql_text(query)).fetchall()

    def commit(self) -> None:
        """
        Flush pending changes and commit the current transaction

        :return:
        """
        assert self.is_connected, "База данных не подключена"
        self.session.commit()

    def flush(self) -> None:
        """
        Flush all the object changes to the database

        :return:
        """
        assert self.is_connected, "База данных не подключена"
        self.session.flush()

    def add_track(self, title: str, path: str, commit: bool = True) -> Optional[int]:
        assert self.is_connected, "База данных не подключена"
        existing_track = self.session.query(Track).filter(Track.path == path).all()
        if existing_track:
            return None
        track_object = Track(title=title, path=path, dt_create=datetime.datetime.now(),
                             dt_last_opened=datetime.datetime.now())
        self.session.add(track_object)
        self.flush()
        if commit:
            self.commit()
        return track_object.id

    def get_all_track(self) -> List[Track]:
        assert self.is_connected, "База данных не подключена"
        return self.session.query(Track).order_by(Track.dt_last_opened.desc()).all()

    def delete_track(self, track: Track, commit: bool = True) -> None:
        assert self.is_connected, "База данных не подключена"
        self.session.delete(track)
        self.flush()
        if commit:
            self.commit()

    def update_track_last_opened(self, track_id: int, commit: bool = True) -> None:
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


