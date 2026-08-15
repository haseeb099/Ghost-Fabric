# Monitoring pilot notes

Local Prometheus scrapes the FastAPI `/metrics` endpoint. CHAMELEON exposes
an in-process Prometheus text collector for control-plane tests and future
transport wiring; it is not scraped by Compose until an approved HTTP surface
exists.

Outbound Alertmanager / PagerDuty / Slack delivery is intentionally omitted.

## Local Grafana (developer-only)

1. Run Prometheus with `infra/monitoring/prometheus.yml` (Compose or standalone).
2. Start any local Grafana instance pointed at that Prometheus datasource.
3. Import `infra/monitoring/dashboards/ghost-fabric-red.json`.
4. Label the dashboard **developer-fixture-only** — not a customer SLO proof.

Proposed alert rules live in `infra/monitoring/rules/slo-alerts.yml` and are
documented in `docs/runbooks/PROMETHEUS_SLO_ALERTS.md`. Do not wire Alertmanager
without explicit approval.
