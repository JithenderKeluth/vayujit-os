# ADR 0033: Distinct Calendar projections

Month, week, and agenda use separate typed projections. Month returns bounded daily summaries, week
returns operational slots and workload/overlap data, and agenda returns paginated detailed events.
All originate from the same owner-scoped stable event query.
