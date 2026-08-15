# GF-63 Security Foundation Review

Scoped review of Ghost Fabric authentication, authorization, secrets handling,
encryption boundaries, and audit evidence. This document is **not** a
penetration-test report and does **not** claim production TLS 1.3, AES-256
verification, mTLS service mesh, or live secret-manager deployment as complete.

## Control matrix

| Control | Status | Notes |
|---------|--------|-------|
| Bearer token auth (`AUTH_TOKENS`) | **Implemented** | Demo/local and Secrets Manager–backed maps |
| HS256 JWT (`sub` / `role` / `exp`) | **Implemented** | Secret must be ≥32 bytes when configured |
| API key auth (`X-API-Key`) | **Implemented** | Mutually exclusive with `Authorization` |
| Production auth-mode safeguards | **Implemented** | `ENVIRONMENT=production` ⇒ `AUTH_MODE=required`, credential source present, `DEFAULT_ROLE=viewer` |
| Fine-grained action RBAC | **Implemented** | `query`, `export_audit`, `mutate_scenario`, `mesh_failover`, `approve_recovery`, `rollback_recovery` |
| Auth allow/deny audit events | **Implemented** | Canonical `auth.decision` events; no raw credentials |
| Append-only audit hash chain | **Implemented** | Existing `AuditStore` / `event_hash` chain |
| Compose demo credentials | **Configuration-required** | Local fixtures only; rotate before any shared environment |
| AWS Secrets Manager wiring | **Configuration-required** | Terraform injects `DATABASE_URL` + `AUTH_TOKENS`; add/rotate `AUTH_JWT_SECRET` / `AUTH_API_KEYS` when those channels are enabled |
| RDS storage encryption flag | **Configuration-required** | `storage_encrypted = true` in Terraform; KMS key confirmation is gated |
| ALB HTTPS / TLS 1.3 | **Architecture-gated** | Pilot ALB is HTTP :80 today; ACM + HTTPS listener required before production exposure |
| WebSocket authentication | **Architecture-gated** | `/ws/events` streams are unauthenticated today; gate or disable before external pilot exposure |
| Public `/metrics` scrape | **Configuration-required** | Intentional RED surface; restrict by network / scrape auth for shared pilots |
| Shared rate-limit store | **Architecture-gated** | Process-local limiter is pilot-only; multi-task ECS needs an approved shared store |
| At-rest AES-256 verification | **External-assessment-required** | Confirm KMS CMK, RDS encryption evidence, and volume encryption with ops |
| Service-to-service mTLS | **Architecture-gated** | CHAMELEON remains transport-free; see transport review gate |
| External penetration test | **External-assessment-required** | Hire external firm; out of scope for this application review |

## Application posture (implemented)

- `backend/app/auth.py` — single credential channel, JWT claim checks, action dependencies
- `backend/app/rbac.py` — explicit action allow-list
- `backend/app/settings.py` — production and JWT-secret validators
- Canonical `auth.decision` events via `ScenarioState.record_auth_decision`
- Focused tests in `backend/tests/test_security_foundation.py`

## Secret rotation runbook (production path)

1. Generate new bearer / API-key maps and JWT signing secret (≥32 bytes) in
   AWS Secrets Manager (or approved manager). Do not put production secrets in
   git, Compose files, or chat.
2. Update the regional secret versions referenced by ECS task definitions
   (`AUTH_TOKENS`, `DATABASE_URL`, and JWT secret when enabled).
3. Roll ECS services one region at a time; verify `/api/v1/health` and a
   viewer-authenticated read before cutting operator traffic.
4. Revoke prior secret versions after the roll completes; keep a break-glass
   operator credential in the manager only.
5. Confirm `auth.decision` deny events appear for revoked credentials and that
   audit exports contain **no** raw tokens, keys, or JWT compact strings.

Local Compose tokens (`viewer-token` / `operator-token`) are **fixtures** for
the demonstration stack only.

## TLS / mTLS prerequisites (gated)

### Edge TLS (pilot → production)

- Provision ACM certificates per region.
- Add HTTPS :443 listener; redirect or disable plaintext :80 for internet exposure.
- Prefer TLS 1.3 only at the load balancer / CDN policy after security sign-off.
- Re-validate CORS origins against the HTTPS console origin.

### Data-at-rest

- Keep RDS `storage_encrypted = true`.
- Confirm customer-managed KMS keys (or account default CMK evidence) during
  external assessment; do not claim AES-256 verification from Terraform alone.

### CHAMELEON mTLS

- Ineligible until `docs/architecture/CHAMELEON_TRANSPORT_REVIEW.md` approvals
  complete.
- Future node identity must be mutual authentication distinct from console
  bearer tokens.
- Do not enable unreviewed TCP/WebSocket transport from this review.

## Explicit non-claims

This review does **not** assert:

- completed external penetration testing;
- enforced TLS 1.3 on all transports;
- verified AES-256 at-rest cryptography in a live account;
- deployed mTLS between CHAMELEON and the API; or
- that Secrets Manager is populated/rotated in every region.

## Related docs

- [DEPLOYMENT.md](DEPLOYMENT.md)
- [AWS_PILOT_DEPLOYMENT.md](AWS_PILOT_DEPLOYMENT.md)
- [architecture/CHAMELEON_TRANSPORT_REVIEW.md](architecture/CHAMELEON_TRANSPORT_REVIEW.md)
