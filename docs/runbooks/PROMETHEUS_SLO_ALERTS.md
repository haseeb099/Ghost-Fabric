# Prometheus SLO alert runbook (GF-50)

**Scope:** Local Prometheus pilot for Ghost Fabric simulation services.  
**Non-goals:** Outbound PagerDuty/Slack delivery, production SLO claims, autonomous recovery.

Proposed pilot objectives (not measured guarantees):

| Objective | Proposed threshold |
|---|---|
| Availability | 99.99% |
| Failover / control-plane op latency | <500ms p99 |
| Inference / PROPHET route latency | <100ms p99 |

Alert rules live in `infra/monitoring/rules/slo-alerts.yml`. Each alert
annotation includes a `runbook_url` pointing here. Delivery to Slack or
PagerDuty remains approval-gated.

## GhostFabricAPIHighErrorRate

1. Confirm `/api/v1/health` and `/metrics`.
2. Inspect JSON access logs by `X-Request-ID` / `X-Correlation-ID`.
3. Check audit-store health and recent 5xx routes.
4. Prefer fail-closed behavior; do not invent a second audit sink.

## GhostFabricAPIRequestLatencyP99

1. Identify hot routes from `ghost_fabric_http_request_duration_seconds`.
2. Check Postgres/audit latency if persistence is enabled.
3. Compare against the proposed 500ms pilot objective only; do not publish
   operational latency claims from local developer runs.

## GhostFabricAuditStoreUnhealthy

1. Inspect `persistence` on `/api/v1/health`.
2. Verify database connectivity and restore settings.
3. Pause consequential simulation approvals until audit writes succeed.

## GhostFabricChameleonFailoverLatencyPilot

1. Review CHAMELEON in-process collector output for operation duration.
2. Confirm the alert reflects control-plane process timing, not authorized
   recovery or mesh transport claims.
3. Keep durable evidence on `AuditEventSink` / FastAPI bridge only.

## GhostFabricInferenceLatencyPilot

1. Confirm the affected routes are fixture-backed `/prophet/*` paths.
2. Treat the proposed 100ms objective as a pilot target for the explanation
   read model, never as model accuracy or warning-time evidence.

## External notification gate

Do not enable Alertmanager, PagerDuty, or Slack until security and operations
approve credentials, payload contracts, retries, and failure behavior.
