# ADR-048: Bounded Shopify media polling

Status: Accepted

Use an injectable polling policy capped by duration and attempts, persist every observation, and
stop on ready, failed, timeout, unknown beyond policy, or local cancellation. This prevents
indefinite requests and makes timing deterministic in tests.
