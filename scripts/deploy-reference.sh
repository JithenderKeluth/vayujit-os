#!/usr/bin/env bash
set -euo pipefail

# Safe VPS reference wrapper. It validates by default; `apply` is an explicit
# operator action and must only be used after HUMAN infrastructure approval.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT}/infrastructure/docker-compose.production.yml"
ENV_FILE="${ROOT}/infrastructure/.env.production"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}; copy the template into a secret-managed location." >&2
  exit 2
fi
if [[ "$(stat -c '%a' "${ENV_FILE}" 2>/dev/null || stat -f '%Lp' "${ENV_FILE}")" != "600" ]]; then
  echo "${ENV_FILE} must be mode 600." >&2
  exit 2
fi

case "${1:-validate}" in
  validate)
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" config >/dev/null
    echo "PASS: reference deployment configuration is valid."
    ;;
  apply)
    : "${VAYUJIT_HUMAN_DEPLOY_APPROVED:?Set VAYUJIT_HUMAN_DEPLOY_APPROVED=YES after explicit approval}"
    [[ "${VAYUJIT_HUMAN_DEPLOY_APPROVED}" == "YES" ]] || { echo "Deployment approval must be YES." >&2; exit 3; }
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build
    ;;
  *)
    echo "Usage: $0 validate|apply" >&2
    exit 2
    ;;
esac
