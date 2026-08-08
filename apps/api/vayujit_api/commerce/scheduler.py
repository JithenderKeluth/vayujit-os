"""Durable scheduler payload contracts for future commerce workers."""

from typing import Literal

CommerceJobType = Literal[
    "commerce.submit_listing",
    "commerce.update_listing",
    "commerce.inventory_sync",
    "commerce.order_sync",
    "commerce.settlement_sync",
]

COMMERCE_JOB_TYPES: tuple[CommerceJobType, ...] = (
    "commerce.submit_listing",
    "commerce.update_listing",
    "commerce.inventory_sync",
    "commerce.order_sync",
    "commerce.settlement_sync",
)


def job_payload(job_type: CommerceJobType, *, account_id: str, resource_id: str) -> dict[str, str]:
    return {"job_type": job_type, "account_id": account_id, "resource_id": resource_id}
