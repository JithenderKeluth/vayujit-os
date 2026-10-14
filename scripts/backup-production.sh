#!/usr/bin/env bash
set -euo pipefail

# Encrypted backup wrapper. It intentionally fails closed when age and a
# secret-managed recipient are not available. It does not contact a remote
# destination; operators must configure the approved off-host target.
: "${VAYUJIT_DATABASE_URL:?VAYUJIT_DATABASE_URL is required}"
: "${VAYUJIT_BACKUP_AGE_RECIPIENT:?VAYUJIT_BACKUP_AGE_RECIPIENT is required}"
command -v pg_dump >/dev/null || { echo "pg_dump is required" >&2; exit 2; }
command -v age >/dev/null || { echo "age is required for encrypted backups" >&2; exit 2; }

destination="${VAYUJIT_BACKUP_DIRECTORY:?VAYUJIT_BACKUP_DIRECTORY is required}"
mkdir -p "${destination}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="${destination}/vayujit-${stamp}.dump.age"
pg_dump --format=custom --no-owner --no-privileges "${VAYUJIT_DATABASE_URL}" \
  | age --encrypt --recipient "${VAYUJIT_BACKUP_AGE_RECIPIENT}" --output "${output}"
test -s "${output}"
sha256sum "${output}" > "${output}.sha256"
echo "Encrypted backup created: ${output}"
