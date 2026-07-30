# Contributing

## Prerequisites

- Node.js 22.22.3 or newer supported by Angular 22
- npm 10 or newer
- Python 3.12
- Docker Desktop with Compose

On Windows, install Python 3.12 with:

```powershell
winget install --exact --id Python.Python.3.12
```

Open a new terminal afterward and verify `py -3.12 --version`.

## Setup and checks

1. Copy `.env.example` to `.env`.
2. Run `npm run install:all`.
3. Run `npm run db:up`.
4. Run `npm run db:migrate`.
5. Run `npm run dev`.

Before proposing changes, run `npm run lint`, `npm test`, `npm run build`,
`npm run format:check`, and `git diff --check`.

Keep domain modules behind public interfaces. Do not introduce Redis or production
connectors without an accepted ADR. Never commit secrets or generated artifacts.
