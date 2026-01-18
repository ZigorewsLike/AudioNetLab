import uuid

from sqlalchemy import Column, Integer, String, Float, Boolean, UUID, TIMESTAMP, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column

Base = declarative_base()


class Track(Base):
    __tablename__ = 'track'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=False, index=True)
    path = Column(String, nullable=False, index=True)
    dt_create = Column(TIMESTAMP, nullable=False)
    dt_last_opened: Mapped[TIMESTAMP | None] = mapped_column(DateTime(), nullable=True)






