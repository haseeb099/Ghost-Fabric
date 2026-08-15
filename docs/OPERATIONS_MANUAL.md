# Ghost Fabric Operations Manual

## Scope

This manual covers the current simulation platform. It does not authorize
production network control, autonomous recovery, or operational claims.

## Start and validate

```powershell
copy .env.example .env
docker compose up --build -d
```

Confirm API health and the versioned contract:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
Invoke-RestMethod http://localhost:8000/api/v1/mesh/topology `
  -Headers @{ Authorization = "Bearer viewer-token" }
```

Expected: healthy persistence, a correlation ID, and fixture-backed topology.

Responses also echo `X-Request-ID` (accepted or generated) and the active
scenario `X-Correlation-ID`. JSON process logs go to stdout and are compatible
with CloudWatch/Datadog/Splunk collectors; they are not a second audit store.

Local Prometheus (Compose service `prometheus` on port `9090`) scrapes
`http://api:8000/metrics`. Import the RED dashboard from
`infra/monitoring/dashboards/ghost-fabric-red.json` if desired. Alert rules
are evaluated locally only; Alertmanager/PagerDuty/Slack are not enabled.

## Authentication operations

Store `AUTH_JWT_SECRET`, `AUTH_TOKENS`, and `AUTH_API_KEYS` in the deployment
secret manager. Never commit their values. JWTs must use HS256 and carry:

```json
{ "sub": "operator-subject", "role": "operator", "exp": 1735689600 }
```

Use a shared rate-limit store before scaling beyond one API process; the
current fixed-window limiter is process-local.

## Audit backup and restore

1. Export the canonical audit:

   ```powershell
   Invoke-RestMethod http://localhost:8000/api/v1/audit/export `
     -Headers @{ Authorization = "Bearer viewer-token" } |
     ConvertTo-Json -Depth 20 | Set-Content audit-export.json
   ```

2. Backup PostgreSQL:

   ```powershell
   docker compose exec db pg_dump -U ghost ghost_fabric > ghost_fabric_backup.sql
   ```

3. Restore only into an approved environment:

   ```powershell
   Get-Content ghost_fabric_backup.sql |
     docker compose exec -T db psql -U ghost ghost_fabric
   ```

4. Restart the API with `RESTORE_ACTIVE_RUN=true`, then inspect `/health` and
   `/audit/export` before permitting further simulation mutations.

## Incident handling

| Symptom | Operator response |
|---|---|
| API unavailable | Use the console fixture fallback; restart API; do not claim live authority. |
| Audit persistence unhealthy | Stop simulation mutations, preserve evidence, restore audit store, then verify chain/export. |
| Rate limit response | Wait one second; retry the same mutation with the original `X-Command-ID`. |
| Invalid/expired credential | Rotate through the approved secret channel; never paste it into an audit payload. |
| No PHOENIX option | Treat as a safe manual-review outcome; do not bypass approval. |

## Scaling and support boundary

Scale only after the following reviews:

- use a shared rate-limit store for multiple API replicas;
- replace configured local credentials with approved secret-manager delivery;
- complete CHAMELEON node-identity and transport review;
- validate monitoring and backup procedures in the target environment.

The current AWS pilot regions are independent. Do not present them as a
cross-region failover system.

## Routine verification

```powershell
cd backend
python -m pytest -q

cd ..
python backend/scripts/check_openapi.py

cd frontend
npm run build
```

Optional developer load observations (loopback only; not a capacity claim):

```powershell
cd backend
python -m scripts.run_load_harness --confirm-local-simulation
```

See [LOAD_TESTING.md](LOAD_TESTING.md). For demo-specific recovery steps, see [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md).
