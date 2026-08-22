from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from vayujit_api.core.config import get_settings


class Base(DeclarativeBase):
    """Base for module-owned SQLAlchemy mappings."""


settings = get_settings()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout_seconds,
    pool_recycle=settings.database_pool_recycle_seconds,
)


@event.listens_for(engine, "connect")
def _set_statement_timeout(dbapi_connection: object, _connection_record: object) -> None:
    if settings.database_statement_timeout_ms <= 0:
        return
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute(f"SET statement_timeout = {settings.database_statement_timeout_ms}")
    finally:
        cursor.close()


SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with SessionFactory() as session:
        yield session
