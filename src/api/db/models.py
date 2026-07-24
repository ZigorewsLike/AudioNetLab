from sqlalchemy import Column, Integer, String, TIMESTAMP, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column

Base = declarative_base()


class Track(Base):
    """Track known to the application, one row per file added to the list.

    The audio itself stays on disk, the database only keeps the path and the timestamps.
    Heavy per track data (tags, cover, feature cache) lives in data/registry/<id>.
    """
    __tablename__ = 'track'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=False, index=True)
    path = Column(String, nullable=False, index=True)
    dt_create = Column(TIMESTAMP, nullable=False)
    dt_last_opened: Mapped[TIMESTAMP | None] = mapped_column(DateTime(), nullable=True)