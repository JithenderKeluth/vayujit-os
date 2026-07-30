# ADR 0035: Two-worker Campaign E2E harness

Campaign connector acceptance must reuse the guarded scheduler harness, fake WordPress and Shopify
servers, injected clock, lease recovery, and two independent workers. Production endpoints and
credentials are prohibited. This harness remains a completion item until the coherent scenario is
implemented.
