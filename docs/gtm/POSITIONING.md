# Ghost Fabric — Go-To-Market Positioning (GF-24)

**Status:** Positioning brief ready for outreach  
**Safety:** Simulation-first product; human approval required; no operational targeting claims.  
**Claims policy:** Numeric market figures below are industry framing for discovery conversations, not measured Ghost Fabric outcomes. Pilot metrics must be labeled fixture or customer-measured.

## Positioning statement

**Ghost Fabric** is a production-minded **resilience OS for mission-critical distributed networks**: mesh continuity, explainable pre-event anomaly review, bounded tabletop branches, and human-approved workflow recovery with an append-only audit trail.

## First three enterprise pilot segments

| # | Segment | Example buyer titles | Primary pain | Entry wedge |
|---|---------|----------------------|--------------|-------------|
| 1 | **Regional / IOU energy utility** | VP Grid Operations, Director of OT Reliability, CISO (OT) | Long MTTR after control/comms node loss; weak auditability of recovery decisions | Tabletop + approved recovery rehearsal with durable audit export |
| 2 | **National / regional telecom carrier** | Head of Network Resilience, SRE Director, NOC Transformation Lead | Failover latency and opaque handoffs across regional PoPs | Mesh handoff visibility + operator-gated recovery with replay |
| 3 | **Exchange / market infrastructure or Tier-1 financial platform** | Head of Site Reliability, Operational Resilience Lead, Compliance Technology | Downtime + proof of control for auditors | Deterministic replay, correlation IDs, approval-bound audit chain |

### Suggested first outreach targets (placeholders — replace with live accounts)

1. **Energy:** One large IOU or TSO/DSO in your home market; one Nordic/UK utility innovation team; one US ISO/RTO reliability program contact.  
2. **Telecom:** One Tier-1 carrier network resilience team; one regional fiber/mobile operator NOC; one wholesale interconnect operator.  
3. **Finance / market infra:** One exchange/clearing technology ops lead; one payment-rail SRE org; one regulated bank operational-resilience program.

> Owner action remaining: schedule 30-minute discovery calls and capture notes against the persona worksheets below.

## Buyer personas (discovery)

### Persona A — Grid operations leader (Energy)

- **Jobs:** Keep situational awareness up when relay/comms nodes fail; shorten restoration without unsafe automation.  
- **Fears:** Black-box AI decisions; regulatory findings; false alarms that erode trust.  
- **Success:** Auditable rehearsal of node loss → handoff → human-approved restore; evidence pack for after-action review.

### Persona B — Carrier resilience / NOC lead (Telecom)

- **Jobs:** Prove failover paths; reduce mean time to understand topology after a PoP event.  
- **Fears:** Tool sprawl; WebSocket/event loss; operators missing the approval step.  
- **Success:** Live topology + shared timeline; role-gated mutations; reconnect/resume; exportable audit.

### Persona C — Operational resilience / compliance tech (Finance)

- **Jobs:** Demonstrate control effectiveness and decision provenance.  
- **Fears:** Unlabeled synthetic accuracy claims; incomplete audit chains.  
- **Success:** Hash-chained events, actor/role on approvals, restart-safe export, fixture-labeled analytics.

## Value props by vertical (1-pagers)

See:

- [docs/gtm/value-prop-energy.md](value-prop-energy.md)
- [docs/gtm/value-prop-telecom.md](value-prop-telecom.md)
- [docs/gtm/value-prop-finance.md](value-prop-finance.md)

## Discovery call agenda (30 min)

1. Current failover / recovery workflow (5)  
2. Where human approval is mandatory today (5)  
3. What “good” audit evidence looks like for them (5)  
4. Show Ghost Fabric golden path (fail → branch → approve → export) (10)  
5. Pilot shape, data boundaries, next step (5)

## Exit criteria checklist

- [x] Identify 3 target prospect segments (utilities, telecom, finance/market infra)  
- [x] Document buyer personas and pain points  
- [x] Create 1-pager value prop per vertical  
- [ ] Schedule 30-min discovery calls (owner / GTM)  
- [ ] Capture call notes and revise personas  
