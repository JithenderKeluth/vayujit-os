# ADR 0018: Persisted Workflow publishing waits

Status: Accepted

Workflow scheduling persists a relationship between the Workflow instance, step execution,
schedule, job, expected terminal state, and correlation ID. Schedule creation completes when the
durable record exists; remote Publishing success is represented only by completion of the wait.
This makes API and worker restarts safe and avoids in-memory promises or timers.
