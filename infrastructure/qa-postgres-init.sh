#!/bin/sh
set -eu
# No password interpolation into shell arguments or output. Only this new QA
# instance's bootstrap user can read the mounted credentials through pg_read_file.
psql -v ON_ERROR_STOP=1 --username postgres --dbname postgres <<'SQL'
DO $qa$
BEGIN
  EXECUTE format('CREATE ROLE vayujit_qa_admin LOGIN CREATEDB NOSUPERUSER NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L', btrim(pg_read_file('/run/secrets/qa_password')));
END
$qa$;
REVOKE CREATE ON DATABASE postgres FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA vayujit_qa_guard AUTHORIZATION postgres;
CREATE TABLE vayujit_qa_guard.instance_identity (
  instance_id text PRIMARY KEY,
  qa_role text NOT NULL CHECK (qa_role = 'vayujit_qa_admin'),
  scope text NOT NULL CHECK (scope = 'disposable-only')
);
INSERT INTO vayujit_qa_guard.instance_identity
VALUES (btrim(pg_read_file('/run/secrets/instance_id')), 'vayujit_qa_admin', 'disposable-only');
REVOKE ALL ON SCHEMA vayujit_qa_guard FROM PUBLIC;
REVOKE ALL ON vayujit_qa_guard.instance_identity FROM PUBLIC;
GRANT CONNECT ON DATABASE postgres TO vayujit_qa_admin;
GRANT USAGE ON SCHEMA vayujit_qa_guard TO vayujit_qa_admin;
GRANT SELECT ON vayujit_qa_guard.instance_identity TO vayujit_qa_admin;
SQL
