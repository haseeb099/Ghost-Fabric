# FedRAMP / NERC / SOC 2 Readiness — GF-56

**Status:** Illustrative control mapping only  
**Certification:** **Not assessed. Not certified. Not audit-ready for customer contracts.**

This document maps *existing* Ghost Fabric simulation controls to common
compliance families so a future assessment has a starting inventory. It does
**not** constitute a System Security Plan, NERC CIP evidence package, or SOC 2
attestation.

## Scope of the current system

- Simulation-first resilience demonstrator with synthetic fixtures
- Human approval for consequential recovery transitions
- Append-only audit export with correlation IDs
- Pilot AWS footprints with manual Terraform apply

## Illustrative mapping (existing → family)

| Existing control | Artifact | Illustrative family |
|---|---|---|
| Bearer/JWT/API-key auth + RBAC actions | `docs/SECURITY_FOUNDATION_REVIEW.md`, `rbac.py` | Access control (AC) |
| Canonical `auth.decision` audit events | Audit store | Audit and accountability (AU) |
| Append-only export `/audit/export` | OpenAPI + audit store | AU / evidence retention (pilot) |
| Secrets via env / AWS Secrets module | Compose, `infra/aws/modules/secrets` | Identification & authentication / key mgmt (pilot) |
| TLS/mTLS gates documented, not verified | Security foundation review | System & communications protection (pending) |
| Simulation-only safety boundary | Cursor safety rules, charter | Program management / use restriction |
| Change evidence via CI + OpenAPI drift | `.github/workflows/quality.yml` | Configuration management (partial) |

## Explicit non-claims

- No FedRAMP Moderate authorization
- No NERC CIP asset inventory or CIP-007 evidence
- No SOC 2 Type II report or 6-month observation window
- No external penetration test completed (tracked as open GF-63 gate)
- No 7-year immutable legal hold implementation

## 12–18 month roadmap (planning only)

1. Complete TLS 1.3 / KMS at-rest verification in a deployed pilot.
2. Engage assessor for gap analysis against FedRAMP Moderate baseline.
3. Produce SSP stubs and control owners.
4. Run external pen-test; remediate findings.
5. Decide SOC 2 Type I → Type II path after pilot customer demand.

## Related

- `docs/SECURITY_FOUNDATION_REVIEW.md` (GF-63)
- `docs/AWS_PILOT_DEPLOYMENT.md`
- `/api/v1/audit/export`
