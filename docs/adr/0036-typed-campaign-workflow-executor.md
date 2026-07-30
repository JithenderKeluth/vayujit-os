# ADR 0036: Typed Campaign Workflow executor

Campaign Workflow actions use a Pydantic discriminated union and a closed executor. Unknown action
keys and extra fields are rejected before execution. Results distinguish durable scheduling from
remote publication and retain caller correlation identifiers.
