# WordPress taxonomy mapping

Categories and tags use searchable multi-selection; authors use searchable single-selection.
Backend calls are paginated and bounded to 100 results. Results are cached for 15 minutes by owner,
kind, query, and page. Configuration changes invalidate the cache. Explicit refresh bypasses it;
an expired cached response may be returned as stale when WordPress temporarily fails.

Only IDs discovered from WordPress are stored in production destination configuration. Author
visibility depends on the WordPress application-password user permissions.
