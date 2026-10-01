# Performance audit

The route tree is lazy-loaded and provider search has explicit request budgets. Database and network bounds exist in the fetcher and test guard.

No evidence justifies speculative optimization. Measure first at milestone closure: API latency for goal→research, provider/fetch latency and quota, query counts/N+1 on evidence projections, payload size/pagination for long intelligence pages, worker throughput, connection-pool use, and Angular bundle/load timings. Treat large evidence projections and repeated refreshes as the first measurement targets.
