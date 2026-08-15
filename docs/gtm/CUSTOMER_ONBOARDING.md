# Customer Onboarding Playbook — GF-57

**Audience:** Simulation pilot kickoff (not production cutover)  
**Data policy:** Synthetic or explicitly approved training fixtures only

## Week 1 — Access and health

1. Confirm MSA/DPA covers **simulation pilot** language (no operational authority).
2. Provision viewer + operator credentials (`AUTH_MODE=required` in shared envs).
3. Deploy Compose stack or AWS pilot region per `docs/DEPLOYMENT.md` / `docs/AWS_PILOT_DEPLOYMENT.md`.
4. Validate `/api/health`, `/api/v1/audit/export`, and console `API LIVE`.
5. Walk the safety ribbon and prohibited-use boundary with the customer sponsor.

## Week 2 — Integrations (simulation adapters)

1. Point Prometheus at `/metrics` using `infra/monitoring/prometheus.yml`.
2. Import `infra/monitoring/dashboards/ghost-fabric-red.json` into a local Grafana (developer-only).
3. Record notification **intent** only via the PHOENIX simulation outbox — do not connect PagerDuty/Slack until security approves adapters.
4. Confirm degraded-mode: stop API → console stays on fixture snapshot.

## Week 3 — Scenario rehearsal

1. Run the 120s script in `docs/DEMO_RUNBOOK.md` three times; log in `docs/DEMO_REHEARSAL_LOG.md`.
2. Operator training: approve → execute → verify → rollback on a reset scenario.
3. MIRROR: select declared branches only; no free-form generation.
4. Export audit and verify correlation IDs match the spoken narrative.

## Week 4 — Thresholds and go/no-go

1. Review PROPHET watch/warning thresholds as **fixture labels**, not production detectors.
2. Confirm no pre-approved automation auto-executes (operator confirm still required).
3. Go/no-go: proceed to longer pilot **only** if safety phrasing, audit export, and human approval are intact.

## Pilot entry gate (GF-58)

The pilot remains blocked until a named human owner records each item below. Repository artifacts prepare the process but cannot satisfy commercial, legal, or customer-environment acceptance criteria.

- [ ] MSA and DPA signed for a simulation-only pilot
- [ ] Customer sponsor, operator owner, security owner, and rollback authority named
- [ ] Deployment region and on-prem/cloud path approved
- [ ] Synthetic or explicitly approved data inventory signed off
- [ ] Prometheus adapter scope approved; no live PagerDuty/Slack connection without security review
- [ ] Two-week validation start/end dates agreed
- [ ] Success measures labeled as pilot observations, not production SLA or model-accuracy claims
- [ ] Go/no-go meeting owner and evidence location recorded

### Evidence packet

At kickoff, create a customer-controlled evidence folder containing the signed agreements, deployment approval, data approval, health-check output, audit export, rehearsal log, incident/rollback notes, and final go/no-go decision. Do not commit customer documents, credentials, or operational telemetry to this repository.

## Training materials

| Asset | Length | Path |
|---|---|---|
| Quick-start script | ~5 min spoken | `docs/DEMO_RUNBOOK.md` |
| Operator recovery | deep dive | `docs/OPERATOR_RUNBOOK.md` |
| Architecture boundaries | deep dive | `docs/ARCHITECTURE.md` |
| Module value props | optional | `docs/gtm/value-prop-*.md` |

## FAQ (pilot)

**Can Ghost Fabric auto-heal our network?**  
No. PHOENIX records simulated recovery after explicit operator approval.

**Is PROPHET a production anomaly detector?**  
No. It scores labeled synthetic evidence for review.

**Where is the compliance certificate?**  
See `docs/compliance/FEDRAMP_NERC_READINESS.md` — not certified.
