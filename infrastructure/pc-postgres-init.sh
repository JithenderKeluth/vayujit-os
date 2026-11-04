#!/bin/sh
set -eu

: "${VAYUJIT_DATABASE_NAME:?VAYUJIT_DATABASE_NAME is required}"
: "${VAYUJIT_DATABASE_USER:?VAYUJIT_DATABASE_USER is required}"
: "${VAYUJIT_DATABASE_PASSWORD:?VAYUJIT_DATABASE_PASSWORD is required}"

psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=ON_ERROR_STOP=1 \
  --set=app_database="$VAYUJIT_DATABASE_NAME" \
  --set=app_user="$VAYUJIT_DATABASE_USER" \
  --set=app_password="$VAYUJIT_DATABASE_PASSWORD" <<'SQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password';
CREATE DATABASE :"app_database" OWNER :"app_user";
SQL
