# Phase 2 — Identity and Project Core

## Delivered scope
- Scrypt password hashing and signed short-lived access tokens backed by revocable server-side sessions.
- Registration, login, current-user lookup, logout, logout-all, session listing and per-session revocation.
- Browser HttpOnly/SameSite cookies, CSRF double-submit validation, rotating refresh tokens, and no refresh-token exposure in browser JSON responses.
- Organization membership and invitations: single-use expiring invitation tokens stored only as digests, email-bound acceptance, role management, member removal, revocation, and audit events.
- Project create/list/read/update with tenant membership enforcement, strong ETags, required If-Match preconditions, atomic version increments, stale-write rejection, and audit metadata.
- Email verification and password recovery using short-lived single-use random tokens; only token digests are persisted. Password reset revokes all active sessions.
- SMTP delivery with TLS/STARTTLS support and generic forgot-password responses to prevent account enumeration.
- PostgreSQL/PostGIS integration tests for schema availability, cross-tenant project isolation, and concurrent writes against one ETag.

## API surface
- POST /api/v1/auth/register, /auth/login, /auth/refresh, /auth/logout, /auth/logout-all, /auth/sessions, /auth/sessions/{id}
- POST /api/v1/auth/verify-email, /auth/resend-verification, /auth/forgot-password, /auth/reset-password
- GET /api/v1/auth/me
- GET /api/v1/organizations, organization invitation/member routes
- POST /api/v1/projects, GET /api/v1/projects, GET /api/v1/projects/{id}, PATCH /api/v1/projects/{id}

## Security properties
- Passwords use scrypt; verification/reset/refresh/invitation tokens are random and only digests are stored.
- Verification tokens expire after 24 hours; reset tokens expire after 30 minutes. Tokens are single-use, and issuing a new token invalidates prior outstanding tokens of the same purpose.
- Login is blocked until email verification when SMTP-backed verification is enabled. Existing accounts are marked verified by the migration to avoid locking out current users.
- Password reset rotates the password hash and revokes every active session.
- Production startup requires a non-default authentication secret, PostgreSQL credentials, SMTP host/sender, CAD production configuration, and HTTPS deployment at the edge.
- Cookie-authenticated unsafe methods require CSRF validation; bearer API clients remain supported.
- Project updates require If-Match; stale writes return 412 and missing preconditions return 428.

## Verification
- API tests cover session lifecycle, refresh rotation/replay, CSRF, invitations and role boundaries, email verification/replay, password reset/replay/session revocation, ETag preconditions, and tenant authorization.
- CI runs PostgreSQL/PostGIS-marked integration tests against a real PostGIS service, plus the full SQLite application suite, frontend tests/build, browser acceptance, Docker builds/Compose smoke, and release preflight.
- The phase is complete only when all required CI jobs pass, all Phase 2 PRs are merged to main, and the tracker is marked Delivered.
