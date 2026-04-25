"""STUB — Person E owns. SQLite session helpers.

TODO: implement engine creation, session context manager, init_db().
"""

from sqlmodel import Session, SQLModel, create_engine

from cubist.config import settings

_engine = create_engine(settings.database_url, echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(_engine)


def get_session() -> Session:
    return Session(_engine)
