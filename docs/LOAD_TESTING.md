# Ghost Fabric load testing (GF-52)

Developer-only synthetic load harness for local or Compose API traffic.

**Label:** `developer-fixture-only` / `developer-baseline-only`  
**Non-goals:** production capacity proof, 10k events/sec for one hour, real leader kill, mesh-transport failover latency, inference P99 claims, memory guarantees.

## Prerequisites

- API reachable on loopback (recommended: `docker compose up`)
- Demo tokens when Compose auth is enabled (`viewer-token`, `operator-token`)
- Explicit `--confirm-local-simulation`

## Run

```powershell
cd backend
python -m scripts.run_load_harness `
  --confirm-local-simulation `
  --base-url http://127.0.0.1:8000 `
  --read-requests 40 `
  --mutation-advances 20 `
  --concurrency 4 `
  --max-rate-per-second 50
```

Optional single simulated mesh failover observation (not a process kill):

```powershell
python -m scripts.run_load_harness `
  --confirm-local-simulation `
  --include-mesh-failover-observation
```

Artifacts (gitignored):

- `backend/app/fixtures/load-harness/load-harness-latest.json`
- `backend/app/fixtures/load-harness/load-harness-latest.csv`
- `backend/app/fixtures/load-harness/load-harness-latest.svg`

Committed schema example: `backend/app/fixtures/load-harness-result.schema.json`.

## Workload phases

1. **Read** — fixed mix of viewer GETs: `/health`, `/mesh/topology`, `/prophet/scores`, `/observability`
2. **Mutation** — one `scenario/reset`, then fixed concurrent `scenario/advance` with deterministic `X-Command-ID`s
3. **Optional** — one `POST /mesh/failover` observation only

PHOENIX approve/rollback routes are intentionally excluded.

## Interpreting results

- Report observations only (`p50` / `p95` / `p99`, throughput, error rate).
- Do not publish Notion acceptance thresholds (10k/sec, `<500ms`, `<100ms`, `<2GB`) from these runs.
- The API’s process-local rate limiter may cap results; that is not multi-instance capacity evidence.

## Correlate with Prometheus

When Compose Prometheus is running (`localhost:9090`):

```promql
sum(rate(ghost_fabric_http_requests_total[1m]))
sum(rate(ghost_fabric_http_request_errors_total[1m]))
histogram_quantile(0.95, sum by (le) (rate(ghost_fabric_http_request_duration_seconds_bucket[1m])))
```

Harness JSON/SVG and Prometheus RED metrics are complementary developer views, not SLO certification.

## Explicit exclusions

- No Gremlin / process kill / packet injection
- No one-hour sustained 10k events/sec default
- No CHAMELEON transport or Byzantine load claims
- No PHOENIX recovery under load
- Full harness invocation stays out of default CI; unit tests cover config and aggregation only
