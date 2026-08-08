# ADR-053: Windows local-MVP packaging

Status: Accepted for `0.1.0-rc.1`  
Date: 2026-08-08

## Decision

The Windows release is a per-user NSIS installer containing the Electron shell, the compiled
Angular renderer, and the API source/migration bundle. The runtime topology remains:

```text
Electron shell (app://vayujit)
  -> local Angular renderer
  -> local FastAPI service on 127.0.0.1
  -> local PostgreSQL on 127.0.0.1
```

PostgreSQL is a documented prerequisite, not bundled by the installer. Python 3.12 is also a
prerequisite for the externally managed API runtime. `install-packaged-api.ps1` creates the
per-user API virtual environment; `start-packaged-api.ps1` initializes configuration, applies
Alembic migrations, and starts Uvicorn on localhost. Electron does not execute arbitrary shell
commands or silently create multiple API instances.

The installer is per-user and preserves `%LOCALAPPDATA%\VAYUJIT OS` across upgrades and
uninstallation. It creates Start Menu and desktop shortcuts, uses an asar archive, and does not
ship `.env` files, test databases, or connector credentials. Automatic internet updates are not
included.

## Consequences

- The first-run prerequisite check must report missing PostgreSQL, Python, API runtime, or
  migration readiness without exposing stack traces.
- Upgrade is manual: close the app, create and verify a backup, run the new installer, start the
  packaged API launcher, and allow migrations to complete before opening the UI.
- User data, encrypted credential keys, logs, media, backups, and the database remain outside the
  installation directory.
