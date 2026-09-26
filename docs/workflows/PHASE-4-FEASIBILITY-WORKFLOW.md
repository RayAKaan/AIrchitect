# Phase 4 persisted feasibility workflow

## Definition 1.0.0
1. `INTERPRET_BRIEF`
2. `VALIDATE_WORLD_MODEL`
3. `GENERATE_DESIGN`
4. `ROUTE_ALTERNATIVE`
5. `RUN_ENGINEERING`
6. `ASSEMBLE_EVIDENCE`
7. `HUMAN_REVIEW_GATE`

Each step has explicit state, attempts/max attempts, timestamps, failure class/code/message, input/output hash, result, provider, and optional artifact reference. Workflow runs have an idempotency key, definition version, current step, hashes, timestamps, and terminal failure details.

## State and recovery
The bounded states are CREATED, RUNNING, WAITING_HUMAN_REVIEW, COMPLETED, CHANGES_REQUESTED, BLOCKED, FAILED, and CANCELLED. Existing lease/heartbeat and PostgreSQL `SKIP LOCKED` worker facilities remain available. Retryable failed runs may be resumed while attempts remain. Cancellation updates pending/running work. No step executes after the review gate without a human action.

## Idempotency
Organization plus idempotency key identifies a run. Deterministic engines retain their own hash-based reuse. Repeated starts return the existing run.

## Failure classes
Validation and policy conflicts are non-retryable. Unexpected provider/infrastructure failures are retryable within the bounded attempt count. Partial successful steps are committed and resume skips them.
