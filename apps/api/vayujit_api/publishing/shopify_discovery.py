import time
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.publishing.schemas import ShopifyDiscoveryPage, ShopifyRemoteItem
from vayujit_api.publishing.shopify import connector_for, owned_configuration


@dataclass
class CacheValue:
    expires_at: float
    page: ShopifyDiscoveryPage


_cache: dict[tuple[uuid.UUID, str, str, str | None, int], CacheValue] = {}


def invalidate(owner_id: uuid.UUID) -> None:
    for key in [key for key in _cache if key[0] == owner_id]:
        _cache.pop(key, None)


def discover(
    db: Session,
    owner: User,
    kind: Literal["collections", "publications"],
    *,
    search: str,
    cursor: str | None,
    page_size: int,
    refresh: bool,
) -> ShopifyDiscoveryPage:
    configuration = owned_configuration(db, owner.id)
    if not configuration or not configuration.enabled:
        raise ValueError("Configure, validate, and enable Shopify before discovery.")
    key = (owner.id, kind, search.casefold(), cursor, page_size)
    stamp = time.monotonic()
    cached = _cache.get(key)
    if cached and not refresh and cached.expires_at > stamp:
        return cached.page.model_copy(update={"cached": True})
    try:
        data = connector_for(configuration).discover(
            kind, first=page_size, after=cursor, search=search
        )
        connection = data.get(kind)
        if not isinstance(connection, dict):
            raise ValueError("Shopify discovery response was invalid.")
        nodes = connection.get("nodes")
        page_info = connection.get("pageInfo")
        if not isinstance(nodes, list) or not isinstance(page_info, dict):
            raise ValueError("Shopify discovery response was invalid.")
        items: list[ShopifyRemoteItem] = []
        for node in nodes:
            if not isinstance(node, dict) or not isinstance(node.get("id"), str):
                raise ValueError("Shopify discovery response was invalid.")
            name = node.get("title") if kind == "collections" else node.get("name")
            if not isinstance(name, str):
                raise ValueError("Shopify discovery response was invalid.")
            handle = node.get("handle")
            items.append(
                ShopifyRemoteItem(
                    id=node["id"],
                    name=name[:255],
                    handle=handle[:255] if isinstance(handle, str) else None,
                )
            )
        result = ShopifyDiscoveryPage(
            items=items,
            has_more=page_info.get("hasNextPage") is True,
            end_cursor=(str(page_info["endCursor"])[:500] if page_info.get("endCursor") else None),
            cached=False,
        )
        _cache[key] = CacheValue(stamp + get_settings().shopify_discovery_cache_seconds, result)
        record_event(
            db,
            actor_id=owner.id,
            action=f"publishing.shopify_{kind}_refreshed",
            entity_type="shopify_connector_configuration",
            entity_id=configuration.id,
            metadata={"connector": "shopify", "result_count": len(items)},
        )
        db.commit()
        return result
    except Exception:
        if cached:
            return cached.page.model_copy(update={"cached": True, "stale": True})
        raise
