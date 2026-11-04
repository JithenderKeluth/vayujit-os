"""Explicitly installed offline WP7A test hooks; never imported by production.

Fault injection affects local research capabilities only. It never changes global
provider settings, killswitches, credentials, source approvals or worker execution.
"""

import hashlib
import json
import os
import traceback
import uuid
from datetime import timedelta
from functools import wraps
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session


def install(app, token, engine, output):
    from vayujit_api.audit.service import record_event
    from vayujit_api.commerce.models import (
        InventoryItem,
        InventoryMovement,
        MarketplaceAccount,
    )
    from vayujit_api.core.database import Base, get_session
    from vayujit_api.core.test_database import assert_safe_test_database
    from vayujit_api.identity.models import AuthSession, User
    from vayujit_api.identity.router import current_user
    from vayujit_api.identity.service import now
    from vayujit_api.intelligence import business_agent_service as agent
    from vayujit_api.intelligence.business_agent_models import (
        BusinessAgentRun,
        BusinessAgentStep,
    )
    from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
    from vayujit_api.video.models import (
        VideoCaptionTrack,
        VideoGeneration,
        VideoOutput,
        VideoStoryboard,
    )

    if os.environ.get("QA_BROWSER_PHASE") not in {
        "WP7A",
        "WP7A2",
        "WP7A3",
        "WP7A4",
        "WP7A5",
        "WP7A6",
        "WP7A7",
    }:
        raise ValueError("WP7A_EXPLICIT_FIXTURE_ONLY")
    with engine.connect() as c:
        assert_safe_test_database(c, database_url=str(engine.url), environment="test")
        if engine.url.database != f"vayujit_qa{token}_test":
            raise ValueError("WP7A_TOKEN_DENIED")
    faults = {}
    previous_handler = app.exception_handlers[Exception]
    errors = []

    async def safe_error(request, error):
        original = getattr(error, "orig", None)
        diagnostic = getattr(original, "diag", None)
        errors.append(
            {
                "path": request.url.path,
                "exception_type": type(error).__name__,
                "sqlstate": getattr(original, "sqlstate", None),
                "table": (
                    getattr(diagnostic, "table_name", None)
                    if getattr(diagnostic, "table_name", None) in Base.metadata.tables
                    else None
                ),
                "column": (
                    getattr(diagnostic, "column_name", None)
                    if getattr(diagnostic, "column_name", None)
                    in {
                        c.name for t in Base.metadata.tables.values() for c in t.columns
                    }
                    else None
                ),
                "frames": [
                    {
                        "file": (
                            frame.filename.replace("\\", "/").split("/vayujit_api/")[-1]
                            if "/vayujit_api/" in frame.filename.replace("\\", "/")
                            else os.path.basename(frame.filename)
                        ),
                        "line": frame.lineno,
                        "function": frame.name,
                    }
                    for frame in traceback.extract_tb(error.__traceback__)
                ],
                "raw_output_persisted": False,
            }
        )
        (output / "wp7a-safe-errors.json").write_text(
            json.dumps(errors, indent=2), encoding="utf-8"
        )
        return await previous_handler(request, error)

    app.add_exception_handler(Exception, safe_error)
    for name in (
        "execute_trend_capability",
        "execute_review_capability",
        "execute_competitor_capability",
        "execute_provider_neutral_search",
    ):
        original = getattr(agent, name)

        def wrapper(original):
            @wraps(original)
            def call(db, owner, *args, **kwargs):
                if faults.get(str(owner.id)) == "PROVIDER_UNAVAILABLE":
                    raise ConnectionError("QA offline provider unavailable")
                return original(db, owner, *args, **kwargs)

            return call

        setattr(agent, name, wrapper(original))

    @app.post("/__qa/wp7a/control", include_in_schema=False)
    def control(
        data: dict,
        request: Request,
        db: Annotated[Session, Depends(get_session)],
        owner: Annotated[User, Depends(current_user)],
        x_qa_token: str = Header(default=""),
    ):
        if x_qa_token != token:
            raise HTTPException(403, "WP7A fixture ownership required")
        scenario = data.get("scenario")
        if scenario in {"NONE", "PROVIDER_UNAVAILABLE"}:
            faults[str(owner.id)] = scenario
        elif scenario == "EXPIRE_SESSION":
            token_hash = hashlib.sha256(
                request.cookies.get("vayujit_session", "").encode()
            ).hexdigest()
            session = db.scalar(
                select(AuthSession).where(
                    AuthSession.user_id == owner.id,
                    AuthSession.token_hash == token_hash,
                )
            )
            if session is None:
                raise HTTPException(403, "WP7A exact session required")
            session.expires_at = now() - timedelta(seconds=1)
            db.commit()
        elif scenario in {"EXPIRED", "INVALID", "REVOKED"}:
            row = db.scalar(
                select(MarketplaceAccount).where(
                    MarketplaceAccount.id == uuid.UUID(data["account_id"]),
                    MarketplaceAccount.owner_id == owner.id,
                )
            )
            if (
                row is None
                or row.environment != "sandbox"
                or not row.seller_account_id.startswith("qa3-wp7a-")
            ):
                raise HTTPException(403, "WP7A synthetic account required")
            row.enabled = False
            row.validation_status = {
                "EXPIRED": "expired",
                "INVALID": "invalid",
                "REVOKED": "unknown",
            }[scenario]
            # An explicitly NON-CREDENTIAL fixture sentinel, never usable provider authorization.
            row.encrypted_credentials = (
                None
                if scenario == "REVOKED"
                else "WP7A_SYNTHETIC_NON_CREDENTIAL_SENTINEL"
            )
            row.credential_status = "missing" if scenario == "REVOKED" else "configured"
            row.configuration_json = {
                "qa_synthetic_fixture": True,
                "external_writes": False,
            }
            record_event(
                db,
                actor_id=owner.id,
                action="qa.wp7a.synthetic_fault",
                entity_type="marketplace_account",
                entity_id=row.id,
                metadata={"scenario": scenario, "synthetic": True},
            )
            db.commit()
        else:
            raise HTTPException(422, "WP7A scenario denied")
        return {"scenario": scenario, "synthetic": True, "external_writes": False}

    @app.get("/__qa/wp7a/state", include_in_schema=False)
    def state(
        db: Annotated[Session, Depends(get_session)],
        owner: Annotated[User, Depends(current_user)],
        x_qa_token: str = Header(default=""),
    ):
        if x_qa_token != token:
            raise HTTPException(403, "WP7A fixture ownership required")

        def owned(model):
            return db.scalars(select(model).where(model.owner_id == owner.id)).all()

        return {
            "token": token,
            "synthetic": True,
            "inventory": [
                {
                    "id": str(r.id),
                    "product_id": str(r.product_id),
                    "variant_id": str(r.variant_id) if r.variant_id else None,
                    "quantity": r.on_hand_quantity,
                    "version": r.version,
                }
                for r in owned(InventoryItem)
            ],
            "movements": [
                {
                    "id": str(r.id),
                    "item_id": str(r.inventory_item_id),
                    "delta": r.quantity,
                    "key": r.idempotency_key,
                }
                for r in owned(InventoryMovement)
            ],
            "runs": [
                {
                    "id": str(r.id),
                    "goal_id": str(r.goal_id),
                    "status": r.status,
                    "failure": r.failure.get("classification") or r.failure.get("code"),
                }
                for r in owned(BusinessAgentRun)
            ],
            "steps": [
                {
                    "id": str(r.id),
                    "status": r.status,
                    "attempts": r.attempt_count,
                    "capability": r.capability_id,
                }
                for r in owned(BusinessAgentStep)
            ],
            "candidates": [
                {
                    "id": str(r.id),
                    "state": r.evidence_state,
                    "tags": r.tags,
                    "origin": r.origin,
                }
                for r in owned(ProductOpportunity)
            ],
            "videos": [
                {
                    "id": str(r.id),
                    "product_id": str(r.product_id),
                    "status": r.status,
                    "provider": r.provider_key,
                    "version": r.storyboard_version,
                    "output": db.scalar(
                        select(VideoOutput.media_id).where(
                            VideoOutput.generation_id == r.id,
                            VideoOutput.owner_id == owner.id,
                        )
                    )
                    is not None,
                }
                for r in owned(VideoGeneration)
            ],
            "storyboards": [
                {
                    "id": str(r.id),
                    "version": r.version,
                    "row_version": r.row_version,
                    "state": r.state,
                }
                for r in owned(VideoStoryboard)
            ],
            "caption_count": db.query(VideoCaptionTrack)
            .join(
                VideoGeneration, VideoCaptionTrack.generation_id == VideoGeneration.id
            )
            .filter(VideoGeneration.owner_id == owner.id)
            .count(),
            "accounts": [
                {
                    "id": str(r.id),
                    "enabled": r.enabled,
                    "validation": r.validation_status,
                    "has_credential": bool(r.encrypted_credentials),
                }
                for r in owned(MarketplaceAccount)
            ],
        }
