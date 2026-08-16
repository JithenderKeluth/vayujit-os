ACTIVITY_ACTIONS: dict[str, tuple[str | None, str | None]] = {
    "mock_publish": ("mock_publisher_v1", "publish"),
    "video_campaign": ("campaign_video", "publish"),
    "wordpress_create_draft": ("wordpress", "create_draft"),
    "wordpress_publish": ("wordpress", "publish"),
    "wordpress_update": ("wordpress", "update"),
    "wordpress_move_to_draft": ("wordpress", "move_to_draft"),
    "shopify_create_draft": ("shopify", "create_draft"),
    "shopify_update_product": ("shopify", "update_product"),
    "shopify_activate_product": ("shopify", "activate_product"),
    "shopify_archive_product": ("shopify", "archive_product"),
    "shopify_reconcile": ("shopify", "reconcile"),
    "review_checkpoint": (None, None),
    "approval_checkpoint": (None, None),
}

LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"planning", "cancelled"},
    "planning": {"ready", "cancelled"},
    "ready": {"scheduled", "paused", "cancelled"},
    "scheduled": {"running", "paused", "cancelled"},
    "running": {"paused", "partially_completed", "completed", "failed", "cancelled"},
    "paused": {"ready", "scheduled", "running", "cancelled"},
    "partially_completed": {"running", "completed", "failed", "cancelled"},
    "completed": {"archived"},
    "failed": {"paused", "running", "cancelled", "archived"},
    "cancelled": {"archived"},
    "archived": set(),
}

TERMINAL_ACTIVITY_STATES = {
    "succeeded",
    "completed_with_warning",
    "failed",
    "dead_letter",
    "cancelled",
    "archived",
}

JOB_ACTIVITY_STATES = {
    "pending": "queued",
    "scheduled": "scheduled",
    "claimed": "queued",
    "running": "running",
    "retry_wait": "retrying",
    "succeeded": "succeeded",
    "failed": "failed",
    "dead_letter": "dead_letter",
    "cancel_requested": "cancel_requested",
    "cancelled": "cancelled",
    "paused": "paused",
    "expired": "reconciliation_required",
}
