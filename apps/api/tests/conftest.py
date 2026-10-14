"""Shared deterministic PostgreSQL fixture for the milestone integration tests."""

from __future__ import annotations

import os
import sys

# Integration tests must never inherit a developer/.env runtime mode. Set
# these before importing the application so cached settings cannot select a
# live provider for a test run.
os.environ["VAYUJIT_ENV"] = "test"
os.environ["VAYUJIT_ENVIRONMENT"] = "test"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_RESEARCH_ENABLED"] = "false"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_PROVIDER_MODE"] = "LOCAL_FIXTURE"
# The shared fixture uses LOCAL_FIXTURE, so the external endpoint may exercise
# its deterministic ledger without opening a live provider or network path.
# Individual safety tests override the setting explicitly when validating the
# kill switch.
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_KILL_SWITCH"] = "false"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_REQUIRE_SOURCE_APPROVAL"] = "false"
# Migration-created foreign keys are intentionally not all represented in the
# ORM metadata (the portfolio current-assessment pointer is one example).
# Use the dependency-safe disposable reset path for every integration fixture;
# it truncates mapped tables with PostgreSQL's validated FK-aware CASCADE while
# preserving the migrated schema and the test marker.
os.environ.setdefault("VAYUJIT_FAST_TEST_RESET", "1")
from collections.abc import Generator
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.main import create_app


@pytest.fixture
def pr56_client() -> Generator[TestClient, None, None]:
    database_url = os.environ.get("VAYUJIT_TEST_DATABASE_URL")
    assert database_url, "VAYUJIT_TEST_DATABASE_URL is required for integration tests"
    engine = create_engine(database_url, poolclass=NullPool)
    reset_test_schema(engine, Base.metadata, database_url=database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    # A few legacy integration modules expose their session factory as a
    # module-level compatibility handle.  The shared fixture is intentionally
    # the canonical disposable database fixture, so keep that handle in sync
    # when those modules are collected as plugins alongside this fixture.
    legacy_integration = cast(Any, sys.modules.get("test_ai_integration"))
    if legacy_integration is not None:
        legacy_integration.factory = factory

    def test_session() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app) as value:
            yield value
    finally:
        reset_test_schema(engine, Base.metadata, database_url=database_url)
        engine.dispose()


@pytest.fixture
def client(pr56_client: TestClient) -> TestClient:
    """Compatibility alias for milestone modules that request ``client``.

    Some PR-7/8 modules load ``test_pr5b_landed_cost`` as a local plugin. When
    pytest collects that plugin module alongside its source test module, the
    plugin fixture is not visible to sibling modules. Reusing the shared
    disposable fixture keeps aggregate collection deterministic without
    changing any application code.
    """

    return pr56_client
