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


## Phase 2 implementation update — revocable sessions
- Signed bearer tokens now carry a server-side session identifier and are accepted only while the persisted session is active and unexpired.
- Registration and login create durable session records transactionally with token issuance.
- Added logout, logout-all, session listing, and per-session revocation endpoints.
- Session rows are user-owned; cross-user revocation returns not-found.
- Legacy stateless tokens without persisted session records are intentionally rejected after deployment; users must sign in again.
- Remaining Phase 2 work: organization invitations/member management, password reset/email verification, secure browser cookie/CSRF flow, project optimistic concurrency, and expanded PostgreSQL tenant-isolation evidence.


## Phase 2 implementation update — organization invitations and membership
- Added single-use, seven-day organization invitations. Only a token digest is stored; the raw token is returned once to the authorized inviter for sharing.
- Invitation acceptance requires an authenticated account whose normalized email matches the invitation and whose inviter still has administrator authority.
- Added organization member listing, role changes, member removal, invitation listing/revocation, and audit events.
- Organization owners cannot be demoted or removed through member-management endpoints; administrator privilege boundaries are enforced server-side.
- Remaining Phase 2 work: secure browser cookie/CSRF flow, password reset/email verification and refresh, project optimistic concurrency, PostgreSQL tenant-isolation coverage, and invitation/member UI.


## Phase 2 implementation update — secure browser sessions and refresh rotation
- Browser authentication now uses HttpOnly, SameSite=Lax session and refresh cookies; Secure is enabled outside local/test environments.
- Cookie-authenticated unsafe requests require a matching CSRF cookie/header pair. Bearer-token API clients remain supported.
- Refresh tokens are random opaque values; only their SHA-256 digests are stored. Refresh rotates the token and extends the server-side session expiry.
- Browser bootstrap can renew a session without storing bearer tokens in sessionStorage. Logout and logout-all clear browser cookies.
- Remaining Phase 2 work: organization management/invitation UI, optimistic project concurrency, and real PostgreSQL tenant-isolation acceptance tests.
