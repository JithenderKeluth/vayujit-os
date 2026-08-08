# VAYUJIT OS Windows installation runbook

## Prerequisites

- Windows 10/11 x64.
- PostgreSQL 17 reachable at `127.0.0.1:5432` with a database and user matching the configured
  `VAYUJIT_DATABASE_URL`.
- Python 3.12 available as `py -3.12` or `python`.
- pg_dump available on PATH for the mandatory pre-upgrade backup.

Run `npm.cmd run release:prerequisites` from the repository before packaging or use the equivalent checks on an installed machine.

The installer does not bundle PostgreSQL, Redis, Python, test databases, `.env` files, or
connector credentials.

## Install and first run

1. Verify the SHA-256 sidecar before running `VAYUJIT-OS-0.1.0-rc.1-Setup.exe`.
2. Run the installer as the current Windows user. It creates Start Menu and desktop shortcuts.
3. From the installed `resources\scripts` directory, run:

   ```powershell
   .\install-packaged-api.ps1 -ApiRoot ..\api
   .\start-packaged-api.ps1 -ApiRoot ..\api
   ```

4. Launch VAYUJIT OS. The renderer is loaded from `app://vayujit`; no Angular development server
   is used. Complete owner setup on the first launch. Later launches show login.

## Data locations

`%LOCALAPPDATA%\VAYUJIT OS` is preserved across upgrades and contains:

- `config\credential-encryption.key` — random, stable AES-GCM key material protected for the
  current Windows user.
- `logs\` — API and launcher logs.
- `backups\` — verified pre-upgrade backups.
- `media\` — local media files.
- `runtime\api-venv\` — the per-user API runtime.
- `tmp\` — disposable runtime files.

The installer directory contains only application files and immutable API/migration resources. The release scripts are `npm.cmd run package:windows`, `npm.cmd run package:checksum`, `npm.cmd run package:verify`, and `npm.cmd run release:verify`.

## Upgrade

1. Close VAYUJIT OS and stop the API launcher.
2. The packaged launcher runs `backup-packaged-api.ps1` before `alembic upgrade head`; it writes and checksums a custom-format dump under `%LOCALAPPDATA%\VAYUJIT OS\backups` and stops if `pg_dump` or the backup fails. Do not continue if backup verification fails.
3. Run the newer per-user installer over the existing installation.
4. Start the packaged API launcher. It runs `alembic upgrade head` before Uvicorn and stops on a
   migration error. It never downgrades the database.
5. Launch the app and verify owner login, brands, products, campaigns, execution history, media,
   and connector configuration.

## Uninstall and recovery

Uninstall removes binaries and shortcuts but preserves `%LOCALAPPDATA%\VAYUJIT OS`, PostgreSQL
data, backups, media, and encryption material. To remove all data, stop the services, export or
verify backups, uninstall, and explicitly delete that directory and the PostgreSQL database.
