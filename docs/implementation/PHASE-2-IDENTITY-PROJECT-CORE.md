# Phase 2 — Identity and Project Core

## Implemented
- Password hashing with scrypt; signed, expiring bearer sessions using HMAC-SHA256.
- Registration creates a user, organization, owner membership, and audit event in one transaction.
- Login and current-user endpoints.
- Organization listing scoped to the authenticated member.
- Project create/list/read/update endpoints, organization membership enforcement, role checks, version increment on edits, and audit events.
- SQLAlchemy models for users, organizations, memberships, projects, and audit events.
- Minimal web UI for registration/sign-in and project creation/listing. Token is held in sessionStorage (not a production-grade cookie/session deployment).
- Local-only schema bootstrap; production schema changes are expected to use Alembic migrations.

## API
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/organizations`
- `POST /api/v1/projects`
- `GET /api/v1/projects?organization_id=...`
- `GET /api/v1/projects/{project_id}`
- `PATCH /api/v1/projects/{project_id}`

## Security and scope notes
- Password minimum is 12 characters at registration. Login failures use a generic response.
- Organization membership is checked server-side; cross-organization project reads return not-found.
- Production deployment still requires a strong `AUTH_SECRET`, HTTPS, rate limiting, secure cookie/session strategy, migration execution, and security review.
- Organization invitation/member-management UI, password reset, email verification, refresh/revocation, and comprehensive concurrency control are not implemented in this phase.
- Project updates currently use a version increment, but optimistic concurrency with `If-Match`/expected-version is still outstanding.

## Verification
Run from `apps/api`: `pytest`, `ruff check app tests`, and `mypy app` after installing project dependencies. Full PostgreSQL/PostGIS verification requires Docker or an external database.
