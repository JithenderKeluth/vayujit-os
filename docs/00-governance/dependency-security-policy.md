# Dependency Security Policy

Supported runtimes are Node 22 or 24, npm 11, and Python 3.12. `package-lock.json` is required.
Production high or critical advisories fail `security:audit:prod`; development findings require
exploitability review and a documented exception. Major or forced fixes require a separate tested
change. License output is engineering visibility, not legal approval.

## 2026-07-29 review

| Package | Relationship/version | Exploitability and fix | Action |
|---|---|---|---|
| `@angular/cli` | Direct dev, 22.0.8 | Inherits the MCP/Hono advisory; npm proposes an incompatible CLI 21 downgrade | Temporary tooling exception |
| `@modelcontextprotocol/sdk` | Transitive dev, 1.29.0 | Not invoked by VAYUJIT; 1.30 is fixed but CLI pins its nested version | Recheck with next CLI |
| `@hono/node-server` | Transitive dev, 1.19.17 | GHSA-frvp-7c67-39w9; VAYUJIT exposes no Hono static server; 2.0.5 is fixed | Non-runtime exception |
| `angular-eslint` | Direct dev, 22.0.0 | Reported through the CLI chain; downgrade would misalign Angular 22 | Retain aligned tooling |
| `@angular-eslint/builder` | Transitive dev, 22.0.0 | Build/lint only; inherits parent finding | Parent exception |
| `@angular-eslint/schematics` | Transitive dev, 22.0.0 | Schematics are not exposed; inherits parent finding | Parent exception |

There are no production high or critical npm findings. Remove the exception when Angular CLI
consumes MCP SDK 1.30 or later.
