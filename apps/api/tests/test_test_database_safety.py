from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from vayujit_api.core.config import Settings
from vayujit_api.core.test_database import (
    PROJECT_MARKER,
    UnsafeTestDatabaseError,
    assert_safe_test_database,
    require_test_database_url,
    safe_target,
)


def connection(database: str, marker: str = PROJECT_MARKER) -> Mock:
    value = Mock()
    value.scalar.side_effect = [database, marker]
    return value


def assert_rejected(url: str, environment: str = "test") -> str:
    target = safe_target(url)
    with patch("vayujit_api.core.test_database.inspect") as inspection:
        inspection.return_value.has_table.return_value = True
        with pytest.raises(UnsafeTestDatabaseError) as caught:
            assert_safe_test_database(
                connection(target.database), database_url=url, environment=environment
            )
    return str(caught.value)


def test_development_database_is_rejected_without_leaking_password() -> None:
    message = assert_rejected("postgresql+psycopg://user:super-secret@localhost/vayujit")
    assert "super-secret" not in message
    assert "localhost/vayujit" in message


def test_missing_test_database_url_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VAYUJIT_TEST_DATABASE_URL", raising=False)
    with pytest.raises(UnsafeTestDatabaseError, match="is required"):
        require_test_database_url()


def test_postgres_database_is_rejected() -> None:
    assert "approved disposable" in assert_rejected(
        "postgresql+psycopg://user:password@localhost/postgres"
    )


def test_development_environment_cannot_reset_test_database() -> None:
    assert "environment=test" in assert_rejected(
        "postgresql+psycopg://user:password@localhost/vayujit_test", "development"
    )


def test_unknown_environment_is_rejected_by_configuration() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="preview")


def test_correctly_named_unmarked_database_is_rejected() -> None:
    url = "postgresql+psycopg://user:password@localhost/vayujit_test"
    with patch("vayujit_api.core.test_database.inspect") as inspection:
        inspection.return_value.has_table.return_value = False
        with pytest.raises(UnsafeTestDatabaseError, match="marker is missing"):
            assert_safe_test_database(
                connection("vayujit_test"), database_url=url, environment="test"
            )


def test_invalid_marker_is_rejected() -> None:
    url = "postgresql+psycopg://user:password@localhost/vayujit_test"
    with patch("vayujit_api.core.test_database.inspect") as inspection:
        inspection.return_value.has_table.return_value = True
        with pytest.raises(UnsafeTestDatabaseError, match="marker is invalid"):
            assert_safe_test_database(
                connection("vayujit_test", "another-project"),
                database_url=url,
                environment="test",
            )


def test_marked_disposable_database_passes() -> None:
    url = "postgresql+psycopg://user:password@localhost/vayujit_workflow_test"
    with patch("vayujit_api.core.test_database.inspect") as inspection:
        inspection.return_value.has_table.return_value = True
        target = assert_safe_test_database(
            connection("vayujit_workflow_test"), database_url=url, environment="test"
        )
    assert target.display == "localhost/vayujit_workflow_test"


def test_connection_database_must_match_url() -> None:
    url = "postgresql+psycopg://user:password@localhost/vayujit_test"
    with patch("vayujit_api.core.test_database.inspect") as inspection:
        inspection.return_value.has_table.return_value = True
        with pytest.raises(UnsafeTestDatabaseError, match="does not match"):
            assert_safe_test_database(connection("vayujit"), database_url=url, environment="test")
