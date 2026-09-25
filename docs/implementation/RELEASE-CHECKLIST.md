# Release checklist

A release owner must attach evidence for every gate before external/customer deployment.

- [ ] API lint + unit tests pass in CI
- [ ] Frontend dependency lockfile committed; clean install + production build pass
- [ ] PostgreSQL/PostGIS migrations run from empty database and upgrade path
- [ ] Tenant-isolation and authorization matrix tests pass
- [ ] Browser E2E: register/login → create project → generate geometry → estimate → validation → review → PDF/JSON
- [ ] Workflow concurrency, retries, leases, cancellation, and crash recovery tested
- [ ] Stale dependency invalidation is persisted and prevents current/approved export
- [ ] PDF/JSON source revision/hash verified against persisted artifacts
- [ ] Secrets, CORS, rate limits, token/session lifecycle, audit retention reviewed
- [ ] Container vulnerability scan, SBOM, license review, backup/restore, deployment rollback
- [ ] Saudi regulatory library reviewed by qualified authority; structural/cost assumptions reviewed by qualified professionals
- [ ] Product disclaimers, data retention, privacy, and customer support procedures approved

Do not release if any safety, authorization, stale-state, or provenance gate is unresolved.
