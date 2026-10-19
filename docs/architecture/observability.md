# Observability

**Status:** S0.5 foundation.

AIrchitect uses structured, correlated telemetry so a user-visible failure can be traced from the browser request through the API and into project/revision/command/generation work.

## Correlation identifiers

| Identifier | Meaning | Authority |
|---|---|---|
| `request_id` | One HTTP request/response correlation id | API middleware |
| `project_id` | Project whose canonical/derived state is being accessed | Project domain |
| `revision_id` | Canonical project revision involved in the operation | Versioned domain model |
| `command_id` | Canonical mutation command correlation id | Command bus (S3) |
| `generation_id` | Long-running generation/regeneration correlation id | Workflow/regeneration runtime |
| `actor_id` | Authenticated user responsible for an operation | Identity/auth layer |

The API accepts validated correlation headers (`X-Request-Id`, `X-Project-Id`, `X-Revision-Id`, `X-Command-Id`, `X-Generation-Id`) and returns the identifiers it knows. The request id is always generated when a caller does not supply a valid one.

## Structured logs

API logs are JSON records containing timestamp, level, logger, message and available correlation identifiers. Event-specific data is placed under `data` rather than interpolated into the message.

Logs must not contain passwords, access tokens, API keys, raw authorization headers, or other secrets. Domain identifiers are acceptable because they are operational correlation metadata.

## Frontend telemetry

The frontend records the latest API request id in session storage and includes it with client-side error telemetry. The application error boundary reports route, message, stack and component stack. The current S0.5 implementation intentionally logs telemetry locally rather than introducing an external observability vendor before the provider/data-license review is complete.

## Task lifecycle

Workflow/regeneration tasks must use the same correlation identifiers when they are introduced or extended. Task events should preserve project, revision, command and generation lineage rather than creating an unrelated logging identity.

## Future production integration

S0.5 establishes the internal contract. Production deployment may forward these structured records to an approved log/trace provider after its software license, data processing terms, retention, geographic residency and commercial-use constraints are registered in the S0.3 compliance registry.
