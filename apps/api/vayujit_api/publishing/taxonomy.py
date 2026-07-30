import time
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.publishing.connector import ConnectorFailure
from vayujit_api.publishing.schemas import (
    WordPressAuthor,
    WordPressTaxonomyPage,
    WordPressTerm,
)
from vayujit_api.publishing.wordpress import connector_for, owned_configuration


@dataclass
class CacheValue:
    expires_at: float
    items: list[WordPressTerm] | list[WordPressAuthor]


_cache: dict[tuple[uuid.UUID, str, str, int, int], CacheValue] = {}


def invalidate(owner_id: uuid.UUID) -> None:
    for key in [key for key in _cache if key[0] == owner_id]:
        _cache.pop(key, None)


def discover(
    db: Session,
    owner: User,
    kind: str,
    *,
    search: str,
    page: int,
    page_size: int,
    refresh: bool,
) -> WordPressTaxonomyPage:
    key = (owner.id, kind, search.casefold(), page, page_size)
    stamp = time.monotonic()
    cached = _cache.get(key)
    if cached and cached.expires_at > stamp and not refresh:
        return WordPressTaxonomyPage(
            items=cached.items,
            page=page,
            page_size=page_size,
            has_more=len(cached.items) == page_size,
            cached=True,
        )
    configuration = owned_configuration(db, owner.id)
    if not configuration or not configuration.enabled:
        from fastapi import HTTPException

        raise HTTPException(409, "WordPress connector is disabled.")
    endpoint = {"categories": "/categories", "tags": "/tags", "authors": "/users"}[kind]
    try:
        result = connector_for(configuration).request(
            "GET",
            endpoint,
            params={"search": search, "page": page, "per_page": page_size},
        )
        if not isinstance(result, list):
            raise ConnectorFailure(
                "wordpress_invalid_taxonomy",
                "WordPress taxonomy response was invalid.",
                retryable=False,
            )
        if kind == "authors":
            items: list[WordPressAuthor] | list[WordPressTerm] = [
                WordPressAuthor(
                    id=int(item["id"]),
                    name=str(item["name"])[:160],
                    username=(
                        str(item["slug"])[:160] if isinstance(item.get("slug"), str) else None
                    ),
                )
                for item in result
                if isinstance(item, dict)
                and isinstance(item.get("id"), int)
                and isinstance(item.get("name"), str)
            ]
        else:
            items = [
                WordPressTerm(
                    id=int(item["id"]),
                    name=str(item["name"])[:160],
                    slug=str(item.get("slug") or "")[:160],
                    parent_id=(
                        int(item["parent"]) if isinstance(item.get("parent"), int) else None
                    ),
                )
                for item in result
                if isinstance(item, dict)
                and isinstance(item.get("id"), int)
                and isinstance(item.get("name"), str)
            ]
        _cache[key] = CacheValue(stamp + get_settings().wordpress_taxonomy_cache_seconds, items)
        record_event(
            db,
            actor_id=owner.id,
            action="publishing.taxonomy_refreshed",
            entity_type="wordpress_connector_configuration",
            entity_id=configuration.id,
            metadata={"kind": kind, "result_count": len(items)},
        )
        db.commit()
        return WordPressTaxonomyPage(
            items=items,
            page=page,
            page_size=page_size,
            has_more=len(items) == page_size,
            cached=False,
        )
    except ConnectorFailure as error:
        if cached:
            return WordPressTaxonomyPage(
                items=cached.items,
                page=page,
                page_size=page_size,
                has_more=len(cached.items) == page_size,
                cached=True,
                stale=True,
            )
        record_event(
            db,
            actor_id=owner.id,
            action="publishing.taxonomy_lookup_failed",
            entity_type="wordpress_connector_configuration",
            entity_id=configuration.id,
            metadata={"kind": kind, "code": error.code, "retryable": error.retryable},
        )
        db.commit()
        raise
