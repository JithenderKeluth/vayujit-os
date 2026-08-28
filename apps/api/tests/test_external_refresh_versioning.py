# ruff: noqa: E501
from datetime import UTC, datetime, timedelta

from vayujit_api.intelligence.external_evidence import derive_freshness


def test_refresh_version_safety_fields_are_deterministic():
    t1 = derive_freshness(
        datetime(2026, 1, 1, tzinfo=UTC), now=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)
    )
    t2 = derive_freshness(
        t1.retrieved_at + timedelta(days=2), now=t1.retrieved_at + timedelta(days=2, seconds=1)
    )
    assert t1.retrieved_at != t2.retrieved_at and t1.fresh_until != t2.fresh_until
