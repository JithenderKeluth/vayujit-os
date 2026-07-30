# Remote drift and reconciliation

Reconciliation compares title, status, slug, excerpt, modified time, categories, tags, author, and
featured media. It reports in-sync, changed-remotely, missing-remotely, unknown, or failure state
with field-level values.

Remote changes are never overwritten automatically. Operators may keep remote changes, explicitly
update from an approved Artifact, create a new draft, move the remote post to draft, or open the
post and destination settings. Remote deletion is not supported.
