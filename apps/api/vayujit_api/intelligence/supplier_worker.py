from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select

from vayujit_api.core.database import SessionFactory
from vayujit_api.identity.models import User
from vayujit_api.intelligence.supplier_models import SupplierSearch
from vayujit_api.intelligence.supplier_service import execute_search

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def run_supplier_searches_once(limit: int = 10, crash_stage: str | None = None) -> int:
    """Run a bounded deterministic batch with durable claims and lease recovery.

    ``crash_stage`` is a disposable-test hook. ``before_provider`` leaves a claimed
    search resumable; ``after_provider`` leaves provider checkpoint metadata before
    the normal finalization path continues.
    """
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    if crash_stage not in {None, "before_provider", "after_provider"}:
        raise ValueError("unsupported crash stage")
    completed = 0
    with SessionFactory() as db:
        now = _now()
        searches = list(
            db.scalars(
                select(SupplierSearch)
                .where(
                    or_(
                        SupplierSearch.status == "pending",
                        (SupplierSearch.status == "running")
                        & (SupplierSearch.lease_expires_at.is_not(None))
                        & (SupplierSearch.lease_expires_at < now),
                    )
                )
                .order_by(SupplierSearch.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for search in searches:
            owner = db.get(User, search.owner_id)
            if owner is None:
                search.status = "failed"
                search.failure_classification = "invalid_supplier"
                db.commit()
                continue
            search.lease_token = uuid.uuid4().hex
            search.lease_expires_at = _now() + timedelta(minutes=5)
            search.status = "running"
            db.commit()
            if crash_stage == "before_provider":
                continue
            try:
                execute_search(db, owner, search)
                search.checkpoint_state = {
                    **(search.checkpoint_state or {}),
                    "provider_persisted": True,
                }
                db.commit()
                if crash_stage == "after_provider":
                    # Checkpoint is durable; replay cannot repeat provider execution.
                    continue
                completed += 1
            except Exception:
                db.rollback()
                failed = db.get(SupplierSearch, search.id)
                if failed is not None:
                    failed.status = "failed"
                    failed.failure_classification = "scoring_failed"
                    failed.lease_token = None
                    failed.lease_expires_at = None
                    db.commit()
                logger.exception("Supplier search failed", extra={"search_id": str(search.id)})
    return completed


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    print(run_supplier_searches_once())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
