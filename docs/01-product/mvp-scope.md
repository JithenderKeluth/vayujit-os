# VAYUJIT OS — Initial MVP Scope

**Status:** Approved scope baseline  
**Delivery approach:** One local, end-to-end vertical slice

## Objective

Prove that one owner can turn local product data into validated, approved content and publish it through a deterministic mock connector, with a complete and recoverable audit trail.

## Included

- Windows desktop application using Electron, Angular, FastAPI, and PostgreSQL.
- One local owner account and authenticated local session.
- Create and view brands and products; attach local product assets.
- One versioned product-content workflow.
- Deterministic mock AI generation of a structured product description and social draft.
- Provider-neutral AI interface and an Ollama-compatible adapter after the mock path works.
- Schema validation, human approval or rejection, mock publishing, execution history, and audit events.
- Local settings, encrypted connector/provider secrets, basic backup and restore.

## Excluded

- Multiple users, roles, SaaS hosting, mobile clients, Redis, general workflow designer, schedules, marketplace synchronization, real external publishing, analytics dashboards, autonomous publishing, advanced media generation, inventory, suppliers, orders, and production auto-update.
- Production marketplace and publishing APIs remain postponed until the slice passes.

## Primary Journey

The owner launches and signs in, creates a brand and product, starts the product-content workflow, reviews validated output from the mock AI provider, approves or rejects it, sends approved content through the mock publishing connector, and views the complete execution history.

## Acceptance Criteria

1. The application launches locally and an initialized owner can sign in.
2. The owner can create and retrieve a brand and a product belonging to it.
3. Starting the workflow creates durable execution and step records.
4. The mock AI result is deterministic and conforms to the documented schema.
5. Invalid output fails validation and cannot reach approval.
6. Valid output pauses in `waiting_for_approval`.
7. Rejection ends the execution as `rejected` without publishing.
8. Approval invokes the mock publisher exactly once and stores its result.
9. A restart does not lose execution state; safe retry does not duplicate publishing.
10. History and audit views show actor, timestamps, transitions, errors, approval, and publishing result.
11. Core behavior has automated unit, integration, and end-to-end tests.

## Assumptions and Constraints

- One owner and one local machine; core business data remains local.
- Windows is the initial supported OS. Internet is optional for the mock path.
- Angular communicates with FastAPI over loopback HTTP.
- PostgreSQL is installed or bundled by a documented local process.
- Redis is not used unless a later ADR demonstrates a requirement.
- All high-impact actions, including publishing, require explicit approval.

## Success and Exit Criteria

The slice is successful when all acceptance criteria pass on a clean supported Windows environment, backup and restore are demonstrated, no high-severity security defects remain, and setup/troubleshooting documentation lets another developer run the system. Sprint 1 exits with a demoable slice, passing CI, and traceability from requirements to tests.

## Principal Risks

- Desktop/backend lifecycle complexity: prove startup and shutdown early.
- Local PostgreSQL friction: test clean-machine setup before feature expansion.
- Premature platform abstraction: implement only interfaces needed by this slice.
- AI unpredictability: use the deterministic mock as the acceptance baseline.
- Duplicate side effects: require idempotency keys and persisted transitions.
- Credential or asset exposure: encrypt secrets, validate paths, and redact logs/backups.
