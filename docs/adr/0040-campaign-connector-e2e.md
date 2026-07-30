# ADR 0040: Campaign connector E2E

Campaign connector acceptance must run only against guarded PostgreSQL and the repository fake
WordPress and Shopify servers. Existing connector tests remain regression evidence but do not count
as the coherent Campaign-specific acceptance scenario.
