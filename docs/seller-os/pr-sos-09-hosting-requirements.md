# Hosting requirements and sizing

VAYUJIT OS is a modular FastAPI/Angular application for one seller per
installation. The supported reference is a Linux VPS with Docker Compose or an
equivalent process supervisor, private PostgreSQL, durable private object
storage, HTTPS reverse proxy, and encrypted off-host backups.

The smallest measured starting point must be established with the seller's real
catalog/media and worker schedule. The checked-in reference limits assume 2
vCPU/2 GiB for the API, 1 vCPU/1 GiB for the worker, 0.5 vCPU/256 MiB for web
and proxy, and PostgreSQL with at least 1 vCPU/1 GiB plus growth headroom.
These are not performance guarantees; monitor CPU, memory, connections, queue
latency, disk, backup duration, and error rate before launch.

Managed PostgreSQL is preferred for a first seller if private connectivity,
role restrictions, encryption, provider backups, and a witnessed restore are
available. Self-hosted PostgreSQL is acceptable only with an owned patching,
replication/backup, alerting, and restore runbook.
