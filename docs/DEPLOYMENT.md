# Ghost Fabric deployment guide

This document covers the production-foundation stack: FastAPI API, Vite/nginx console, and PostgreSQL durable audit.

## Safety boundary

- Synthetic or approved training data only
- Human approval required for simulated recovery
- No targeting, weapons assignment, autonomous action, or operational deception

## Local development (in-memory audit)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

```powershell
cd frontend
npm install
npm run dev
```

Defaults:
- Audit backend: `memory`
- Auth mode: `optional` (no bearer tokens required)
- API docs: `http://127.0.0.1:8000/docs`
- Versioned API: `/api/v1/*`
- Legacy aliases: `/api/*`

Copy `.env.example` to `.env` and adjust as needed.

## Docker Compose (PostgreSQL audit)

```powershell
docker compose up --build -d
```

Services:
- `db` — Postgres 16 on `localhost:5432`
- `api` — FastAPI on `localhost:8000` with `AUDIT_BACKEND=postgres`
- `prometheus` — local scrape of `api:8000/metrics` on `localhost:9090` (no Alertmanager)
- `web` — nginx console on `localhost:8080` proxying `/api` and `/ws`

Compose runs with `ENVIRONMENT=production` safeguards: `AUTH_MODE=required`,
`DEFAULT_ROLE=viewer`, and demo bearer tokens (local fixtures only):
- Viewer: `viewer-token`
- Operator: `operator-token`

See [SECURITY_FOUNDATION_REVIEW.md](SECURITY_FOUNDATION_REVIEW.md) for the
control matrix, secret rotation path, and TLS/mTLS gates.

Optional developer load harness (loopback, labeled observations only):

```powershell
cd backend
python -m scripts.run_load_harness --confirm-local-simulation --base-url http://127.0.0.1:8000
```

See [LOAD_TESTING.md](LOAD_TESTING.md). Do not treat results as production capacity evidence.

Example mutation:

```powershell
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/api/v1/scenario/reset -Headers @{ Authorization = "Bearer operator-token"; "X-Command-ID" = [guid]::NewGuid().ToString() }
```

## Migrations

Schema creation is applied automatically on API startup when `AUDIT_BACKEND=postgres` via SQLAlchemy `create_all` for:
- `scenario_runs`
- `audit_events` (unique `correlation_id + sequence`)
- `command_idempotency`

## Backup and recovery

1. Export append-only audit: `GET /api/v1/audit/export`
2. Postgres logical backup:

```powershell
docker compose exec db pg_dump -U ghost ghost_fabric > ghost_fabric_backup.sql
```

3. Restore:

```powershell
Get-Content ghost_fabric_backup.sql | docker compose exec -T db psql -U ghost ghost_fabric
```

4. Restart API with `RESTORE_ACTIVE_RUN=true` to reload the active run snapshot when present.

## Auth model

| Role | Capabilities |
|------|--------------|
| `viewer` | `query`, `export_audit` (scenario reads, observability, analysis, audit export) |
| `operator` | All viewer actions plus `mutate_scenario`, `mesh_failover`, `approve_recovery`, `rollback_recovery` |

Actor identity recorded in audit events comes from the authenticated principal, not free-text request bodies.
Authenticated allow/deny decisions also emit canonical `auth.decision` events (no raw credentials).

Supported API credentials (exactly one channel per request):

- configured bearer tokens (`AUTH_TOKENS`);
- HS256 JWTs with required `sub`, `role`, and `exp` claims
  (`AUTH_JWT_SECRET` ≥ 32 bytes, supplied from a secret manager); and
- configured `X-API-Key` credentials (`AUTH_API_KEYS`).

`ENVIRONMENT=production` rejects optional auth, operator-as-default, missing
credential sources, and short JWT secrets at settings load.

REST requests are limited to `RATE_LIMIT_PER_SECOND` (default `1000`) per
hashed credential identity. The pilot limiter is process-local; a
multi-instance deployment must replace it with an approved shared limiter.
Errors use `{ "code": "...", "detail": "..." }`. `/api/v1/*` is canonical,
while `/api/*` remains the compatibility surface.

## Verification

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q

cd ..\frontend
npm run build
npm run test:e2e

cd ..
python backend/scripts/export_openapi.py
```

## AWS pilot (three-region foundation)

Local Compose remains the default developer path. For the bounded AWS pilot scaffold (GF-29):

- Guide: [AWS_PILOT_DEPLOYMENT.md](AWS_PILOT_DEPLOYMENT.md)
- Terraform: `infra/aws/`
- Regions: `us-east-1`, `eu-west-1`, `ap-southeast-1`
- `terraform apply` is **manual** — CI only runs `fmt` / `validate`

This does **not** implement cross-region mesh failover. Each region is an independent pilot footprint with its own RDS audit store.