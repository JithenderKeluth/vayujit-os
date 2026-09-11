"""Fail-closed safeguards for destructive PostgreSQL test operations."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from sqlalchemy import Connection, Engine, MetaData, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

PROJECT_MARKER = "vayujit-os-disposable-test-database-v1"
MARKER_TABLE = "test_database_marker"
APPROVED_DATABASE = re.compile(r"^vayujit(?:_[a-z0-9]+)*_test$")
DENIED_DATABASES = {"postgres", "template0", "template1", "vayujit"}
DENIED_HOSTS = {"0.0.0.0"}


class UnsafeTestDatabaseError(RuntimeError):
    """Raised before an unsafe or unrecognized test database can be changed."""


@dataclass(frozen=True)
class SafeDatabaseTarget:
    host: str
    database: str

    @property
    def display(self) -> str:
        return f"{self.host}/{self.database}"


def safe_target(database_url: str) -> SafeDatabaseTarget:
    parsed = make_url(database_url)
    return SafeDatabaseTarget(parsed.host or "local", parsed.database or "")


def require_test_database_url() -> str:
    value = os.environ.get("VAYUJIT_TEST_DATABASE_URL")
    if not value:
        raise UnsafeTestDatabaseError(
            "VAYUJIT_TEST_DATABASE_URL is required for PostgreSQL integration tests."
        )
    return value


def assert_safe_test_database(
    connection: Connection, *, database_url: str, environment: str
) -> SafeDatabaseTarget:
    target = safe_target(database_url)
    if environment != "test":
        raise UnsafeTestDatabaseError(
            f"Destructive test operation requires environment=test; target={target.display}"
        )
    if target.host in DENIED_HOSTS:
        raise UnsafeTestDatabaseError(f"Test database host is denied; target={target.display}")
    if target.database in DENIED_DATABASES or not APPROVED_DATABASE.fullmatch(target.database):
        raise UnsafeTestDatabaseError(
            f"Database name is not an approved disposable test name; target={target.display}"
        )
    actual_database = connection.scalar(text("select current_database()"))
    if actual_database != target.database:
        raise UnsafeTestDatabaseError(
            f"Connected database does not match configured test target; target={target.display}"
        )
    if not inspect(connection).has_table(MARKER_TABLE):
        raise UnsafeTestDatabaseError(f"Disposable test marker is missing; target={target.display}")
    marker = connection.scalar(
        text(f"select project_identifier from {MARKER_TABLE} where marker_id = 1")
    )
    if marker != PROJECT_MARKER:
        raise UnsafeTestDatabaseError(f"Disposable test marker is invalid; target={target.display}")
    return target


def terminate_test_database_sessions(database_url: str) -> int:
    """Terminate only sessions connected to this approved disposable test database.

    This helper is intentionally test-only. It connects to the local maintenance
    database, targets one validated database name, and never touches production
    or any unrelated PostgreSQL database.
    """
    environment = os.environ.get("VAYUJIT_ENV", "")
    target = safe_target(database_url)
    if environment != "test":
        raise UnsafeTestDatabaseError(
            f"Session termination requires environment=test; target={target.display}"
        )
    if target.host in DENIED_HOSTS or target.database in DENIED_DATABASES:
        raise UnsafeTestDatabaseError(f"Database target is denied; target={target.display}")
    if not APPROVED_DATABASE.fullmatch(target.database):
        raise UnsafeTestDatabaseError(f"Database name is not approved; target={target.display}")
    parsed = make_url(database_url).set(database="postgres")
    maintenance = create_engine(parsed, poolclass=NullPool)
    try:
        with maintenance.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :database
                      AND pid <> pg_backend_pid()
                    """
                ),
                {"database": target.database},
            )
            return sum(bool(row[0]) for row in rows)
    finally:
        maintenance.dispose()


def reset_test_schema(engine: Engine, metadata: MetaData, *, database_url: str) -> None:
    """Reset one approved disposable database after closing stale sessions."""
    environment = os.environ.get("VAYUJIT_ENV", "")
    with engine.connect() as connection:
        target = assert_safe_test_database(
            connection, database_url=database_url, environment=environment
        )
        print(f"Safety checks passed for disposable test database: {target.display}")
    # Close this engine before terminating any other connection to the same DB.
    engine.dispose()
    terminated = terminate_test_database_sessions(database_url)
    if terminated:
        print(f"Terminated {terminated} stale disposable test-database session(s).")
    with engine.begin() as connection:
        metadata.drop_all(connection)
        metadata.create_all(connection)
