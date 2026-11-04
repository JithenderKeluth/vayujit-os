from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from vayujit_api.core.config import Settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.external_models import ExternalProviderState
from vayujit_api.intelligence.external_service import _check_quota

NOW = datetime(2026, 10, 24, 16, 30, 15, tzinfo=UTC)


def quota_context(
    *,
    previous: datetime = NOW,
    counts: tuple[int, int, int] = (10, 10, 10),
    usage: tuple[int, int, int] = (0, 0, 0),
) -> tuple[MagicMock, User, ExternalProviderState, Settings]:
    owner = User(id=uuid.uuid4())
    state = ExternalProviderState(
        owner_id=owner.id,
        provider="brave",
        status="RATE_LIMITED",
        requests_minute=counts[0],
        requests_hour=counts[1],
        requests_day=counts[2],
        updated_at=previous,
        disabled=False,
        last_failure="search_rate_limited",
    )
    db = MagicMock(spec=Session)
    db.scalar.return_value = state
    db.execute.return_value.one.return_value = usage
    settings = Settings(
        intelligence_search_requests_per_minute=10,
        intelligence_search_requests_per_hour=100,
        intelligence_search_daily_cap=500,
    )
    return db, owner, state, settings


def test_historical_exhausted_counter_reconstructs_usage_before_admitting() -> None:
    db, owner, state, settings = quota_context(previous=NOW - timedelta(days=24))

    result = _check_quota(cast(Session, db), owner, "brave", settings, now=NOW)

    assert result is state
    assert (state.requests_minute, state.requests_hour, state.requests_day) == (1, 1, 1)
    assert state.updated_at == NOW
    assert state.status == "READY" and state.last_failure is None
    db.execute.assert_called_once()
    db.commit.assert_not_called()


def test_minute_rollover_preserves_hour_and_day_reservations() -> None:
    db, owner, state, settings = quota_context(
        previous=NOW - timedelta(minutes=1), counts=(10, 24, 65), usage=(0, 12, 40)
    )

    _check_quota(cast(Session, db), owner, "brave", settings, now=NOW)

    assert (state.requests_minute, state.requests_hour, state.requests_day) == (1, 25, 66)


def test_legacy_timestamp_cannot_discard_recent_durable_usage() -> None:
    db, owner, state, settings = quota_context(
        previous=NOW - timedelta(days=24), usage=(10, 30, 60)
    )

    with pytest.raises(HTTPException) as failure:
        _check_quota(cast(Session, db), owner, "brave", settings, now=NOW)

    assert failure.value.status_code == 429
    assert failure.value.headers == {"Retry-After": "45"}
    assert (state.requests_minute, state.requests_hour, state.requests_day) == (10, 30, 60)
    assert state.status == "RATE_LIMITED" and state.updated_at == NOW
    db.commit.assert_called_once()


def test_active_window_still_rejects_without_rebuilding_its_reservations() -> None:
    db, owner, state, settings = quota_context()

    with pytest.raises(HTTPException) as failure:
        _check_quota(cast(Session, db), owner, "brave", settings, now=NOW)

    assert failure.value.status_code == 429
    assert state.requests_minute == 10
    db.execute.assert_not_called()


def test_retry_after_respects_longest_exhausted_window() -> None:
    db, owner, state, settings = quota_context(counts=(10, 100, 100))

    with pytest.raises(HTTPException) as failure:
        _check_quota(cast(Session, db), owner, "brave", settings, now=NOW)

    assert failure.value.headers == {"Retry-After": "1785"}


def test_hour_rollover_does_not_clear_daily_cap() -> None:
    db, owner, state, settings = quota_context(
        previous=NOW - timedelta(hours=1), counts=(10, 100, 500)
    )

    with pytest.raises(HTTPException) as failure:
        _check_quota(cast(Session, db), owner, "brave", settings, now=NOW)

    assert failure.value.status_code == 429
    assert (state.requests_minute, state.requests_hour, state.requests_day) == (0, 0, 500)
    assert failure.value.headers == {"Retry-After": "26985"}


def test_utc_day_rollover_reconstructs_each_window_independently() -> None:
    db, owner, state, settings = quota_context(
        previous=NOW - timedelta(days=1), counts=(10, 100, 500), usage=(2, 7, 11)
    )

    _check_quota(cast(Session, db), owner, "brave", settings, now=NOW)

    assert (state.requests_minute, state.requests_hour, state.requests_day) == (3, 8, 12)


def test_continuous_traffic_does_not_prevent_next_minute_rollover() -> None:
    db, owner, state, settings = quota_context(counts=(9, 24, 65))
    later = NOW + timedelta(seconds=50)

    _check_quota(cast(Session, db), owner, "brave", settings, now=NOW)
    assert state.requests_minute == 10
    _check_quota(cast(Session, db), owner, "brave", settings, now=later)

    assert (state.requests_minute, state.requests_hour, state.requests_day) == (1, 26, 67)
    assert state.updated_at == later


def test_backward_clock_does_not_reopen_exhausted_windows() -> None:
    future = NOW + timedelta(hours=1)
    db, owner, state, settings = quota_context(previous=future)

    with pytest.raises(HTTPException) as failure:
        _check_quota(cast(Session, db), owner, "brave", settings, now=NOW)

    assert failure.value.status_code == 429 and state.updated_at == future
    db.execute.assert_not_called()


def test_disabled_provider_remains_blocked_after_expiry() -> None:
    db, owner, state, settings = quota_context(previous=NOW - timedelta(days=24))
    state.disabled = True

    with pytest.raises(HTTPException) as failure:
        _check_quota(cast(Session, db), owner, "brave", settings, now=NOW)

    assert failure.value.status_code == 409 and state.requests_minute == 10
    db.execute.assert_not_called()
    db.commit.assert_not_called()


def test_naive_legacy_timestamp_is_treated_as_utc() -> None:
    db, owner, state, settings = quota_context(
        previous=(NOW - timedelta(days=24)).replace(tzinfo=None)
    )

    _check_quota(cast(Session, db), owner, "brave", settings, now=NOW)

    assert state.requests_minute == 1 and state.updated_at == NOW
