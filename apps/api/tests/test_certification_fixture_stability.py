from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool

from vayujit_api.core.database import Base
from vayujit_api.core.test_database import reset_test_schema

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.certification_infrastructure


@pytest.mark.parametrize("run_number", range(1, 21))
def test_disposable_fixture_lifecycle_is_stable(
    client: TestClient,
    run_number: int,
) -> None:
    del run_number
    response = client.get("/health")
    assert response.status_code == 200


def test_migrated_supplier_assessment_dependencies_survive_repeated_reset() -> None:
    """The reset path preserves migration-only portfolio FK relationships.

    ``metadata.drop_all`` cannot see the migration-created pointer from the
    portfolio context to its assessment version.  This regression exercises
    the disposable reset repeatedly and proves that the migrated dependency
    graph remains present instead of relying on a blanket DDL exception.
    """

    database_url = os.environ.get("VAYUJIT_TEST_DATABASE_URL")
    assert database_url
    engine = create_engine(database_url, poolclass=NullPool)
    try:
        for _ in range(3):
            reset_test_schema(engine, Base.metadata, database_url=database_url)
            with engine.connect() as connection:
                tables = set(inspect(connection).get_table_names())
                required_tables = {
                    "intelligence_supplier_portfolio_contexts",
                    "intelligence_supplier_portfolio_assessment_versions",
                    "intelligence_supplier_portfolio_input_snapshots",
                }
                assert required_tables.issubset(tables)
                for table in required_tables:
                    row_count = connection.execute(
                        text(f'SELECT count(*) FROM "{table}"')
                    ).scalar_one()
                    assert row_count == 0
                dependency = connection.execute(
                    text(
                        """
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'fk_supplier_portfolio_current_assessment'
                          AND conrelid = 'intelligence_supplier_portfolio_contexts'::regclass
                          AND confrelid =
                              'intelligence_supplier_portfolio_assessment_versions'::regclass
                        """
                    )
                ).scalar_one_or_none()
                assert dependency == 1
                marker = connection.execute(
                    text("SELECT project_identifier FROM test_database_marker WHERE marker_id = 1")
                ).scalar_one()
                assert marker == "vayujit-os-disposable-test-database-v1"
    finally:
        engine.dispose()
