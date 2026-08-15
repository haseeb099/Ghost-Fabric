# Ghost Fabric API Reference

**Current contract:** [`contracts/openapi.json`](../contracts/openapi.json)  
**Interactive documentation:** `http://localhost:8000/docs`  
**Canonical base URL:** `http://localhost:8000/api/v1`  
**Compatibility base URL:** `http://localhost:8000/api`

Ghost Fabric APIs operate only on fictional, deterministic fixture state.
PROPHET responses are review-only. PHOENIX approval is a simulated,
operator-gated recovery decision; no endpoint executes an external action.

## Authentication and errors

Read endpoints require `viewer` or `operator`; mutations require `operator`.
Choose one credential:

- `Authorization: Bearer <configured-token>`
- `Authorization: Bearer <HS256 JWT>` with `sub`, `role`, and `exp` claims
- `X-API-Key: <configured-key>`

The pilot applies a per-credential, process-local rate limit (default
`1000` requests/second). Responses include `X-RateLimit-Limit` and
`X-RateLimit-Remaining`. Errors are:

```json
{ "code": "validation_error", "detail": "Request validation failed" }
```

Use `X-Command-ID` with every mutation for idempotent retry behavior.

Optional observability headers:

- `X-Request-ID`: accepted if provided, otherwise generated and echoed
- `X-Correlation-ID`: echoed as the active scenario/audit run ID

JSON access logs include timestamp, level, service, request_id,
correlation_id, action, status, duration, and a hashed user handle. They
never include raw credentials and are not a second audit store.

Prometheus scrapes public `/metrics` (also aliased under `/api/v1/metrics`)
for RED process telemetry. Metrics are not an audit export and do not
authorize recovery. Proposed SLO alert rules live under
`infra/monitoring/rules/` with runbook links in
`docs/runbooks/PROMETHEUS_SLO_ALERTS.md`. Outbound PagerDuty/Slack delivery
remains disabled pending approval.

## Core endpoints

| Method | Path | Role | Purpose |
|---|---|---|---|
| `GET` | `/health` | public | API and audit-store health |
| `GET` | `/metrics` | public | Prometheus RED process metrics |
| `GET` | `/observability` | viewer | Correlation ID, counters, recent JSON access-trace projection |
| `GET` | `/mesh/topology` | viewer | Fixture-backed mesh topology |
| `POST` | `/mesh/failover` | operator | Simulate node loss and handoff |
| `GET` | `/prophet/scores` | viewer | Labeled synthetic score |
| `GET` | `/prophet/explain` | viewer | Schema-validated review explanation |
| `GET` | `/mirror/catalog` | viewer | Approved fixture-only tabletop catalog |
| `GET` | `/mirror/scenarios/{scenario_id}` | viewer | Single MIRROR fixture projection |
| `POST` | `/tabletop/select` | operator | Record a declared human branch choice |
| `GET` | `/phoenix/workflows` | viewer | Simulated workflow/planner state |
| `POST` | `/phoenix/approve` | operator | Explicit approval only (`alert → approval → execution`) |
| `POST` | `/phoenix/execute` | operator | Record reversible simulated execution (`execution → verify`) |
| `POST` | `/phoenix/verify` | operator | Verify simulation (`verify → restored`) or forced rollback on failure |
| `POST` | `/phoenix/rollback` | operator | Roll back a restored simulated recovery |
| `GET` | `/citizen/grid` | viewer | Anonymous district-aggregate sensor projection |
| `POST` | `/citizen/detect` | operator | Add one corroborating synthetic district |
| `POST` | `/citizen/attrition` | operator | Take a share of synthetic sensors offline |
| `POST` | `/citizen/jam` | operator | Jam the active channel and fall back down the ladder |
| `POST` | `/citizen/warn` | operator | Record an approved simulated civilian advisory (409 below guardrail) |
| `GET` | `/audit/export` | viewer | Canonical event/audit export |
| `GET` | `/scenario/replay/{sequence}` | viewer | Read-only deterministic checkpoint |

Scenario snapshots include `scenario.demo_phase` (guided fictional pacing),
PROPHET virtual-time countdown metadata, catalog-backed MIRROR branches, and
the full PHOENIX transition history. Additional scenario controls remain under
`/scenario/*`.

## curl examples

```bash
export BASE_URL=http://localhost:8000/api/v1
export TOKEN=operator-token

curl "$BASE_URL/mesh/topology" \
  -H "Authorization: Bearer $TOKEN"

curl -X POST "$BASE_URL/mesh/failover" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Command-ID: mesh-failover-001" \
  -d '{"node_id":"northstar"}'

curl -X POST "$BASE_URL/phoenix/approve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Command-ID: phoenix-approve-001" \
  -d '{"option_id":"route-atlas"}'

curl -X POST "$BASE_URL/phoenix/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Command-ID: phoenix-execute-001"

curl -X POST "$BASE_URL/phoenix/verify" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Command-ID: phoenix-verify-001" \
  -d '{"succeeded":true}'

curl -X POST "$BASE_URL/phoenix/rollback" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Command-ID: phoenix-rollback-001" \
  -d '{"reason":"operator rehearsal rollback"}'
```

## Python example

```python
import uuid
import httpx

base_url = "http://localhost:8000/api/v1"
headers = {"X-API-Key": "operator-key"}

with httpx.Client(base_url=base_url, headers=headers) as client:
    topology = client.get("/mesh/topology").json()
    result = client.post(
        "/mesh/failover",
        json={"node_id": "northstar"},
        headers={"X-Command-ID": str(uuid.uuid4())},
    )
    result.raise_for_status()
    print(topology["correlation_id"], result.json()["network"]["coordinator"])
```

## Go example

```go
package main

import (
	"bytes"
	"net/http"
)

func main() {
	body := []byte(`{"option_id":"route-atlas"}`)
	req, _ := http.NewRequest(
		http.MethodPost,
		"http://localhost:8000/api/v1/phoenix/approve",
		bytes.NewReader(body),
	)
	req.Header.Set("X-API-Key", "operator-key")
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Command-ID", "phoenix-approve-001")
	_, _ = http.DefaultClient.Do(req)
}
```

## WebSocket event stream

`ws://localhost:8000/api/v1/ws/events` emits canonical scenario events and a
current snapshot. Use `correlation_id` and `after_sequence` to request a
replay window. It is a console synchronization stream, not a CHAMELEON
control-plane transport.
