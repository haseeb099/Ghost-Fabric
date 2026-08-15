# Hiring pack — Ghost Fabric (GF-25 to GF-28)

Post these descriptions on HN Who’s Hiring, AngelList/Wellfound, LinkedIn, and your network. All roles support a **simulation-first, human-controlled** resilience product. No work on autonomous targeting, real-world weapons assignment, or operational deception.

**Location:** Remote-friendly / hybrid *(customize)*  
**Engagement:** Full-time contractor or employee *(customize)*  
**Start target:** within 2 weeks of offer for Principal Architect; stagger backend hires

---

## GF-25 — Principal Architect (Consensus & Distributed Systems)

### Mission

Own the multi-node resilience architecture: consensus approach for CHAMELEON mesh, API boundaries, multi-region event durability strategy, and technical hiring bar.

### Must-have

- Shipped production distributed systems (consensus, membership, or strongly consistent stores)  
- Deep familiarity with Raft or PBFT-class protocols and failure modes  
- Comfortable in Go and/or Rust; can review Python/FastAPI and TypeScript surfaces  
- Writes crisp ADRs; mentors senior engineers  

### Nice-to-have

- OT / telecom / exchange operational environments  
- Threat modeling for control-plane software  
- Prior startup founding or staff+ architecture role  

### First 90 days

1. ADR: consensus choice + deployment topology for 20–50 node mesh goals  
2. Harden `/api/v1` contracts and audit durability assumptions  
3. Staff and unblock CHAMELEON + PHOENIX backend workstreams  

### How to apply

Send CV + one architecture write-up (link or PDF) describing a consensus or multi-region system you owned. Subject: `GF Principal Architect`.

---

## GF-26 — Senior Backend Engineer (CHAMELEON)

### Mission

Implement mesh failover, topology sync, and real-time event fan-out for CHAMELEON against agreed latency budgets.

### Must-have

- 5+ years backend; strong concurrency and networking fundamentals  
- Production experience with WebSockets or streaming APIs  
- Go, Rust, or Python expert; SQL + Postgres  
- Writes tests as part of the definition of done  

### First 90 days

Mesh core vertical slice on top of existing deterministic simulator; integration tests; OpenAPI updates.

### Apply

Subject: `GF Backend CHAMELEON` + link to a systems project.

---

## GF-26b — Senior Backend Engineer (PHOENIX)

### Mission

Own workflow state machine, approval APIs, and durable audit semantics for recovery paths.

### Must-have

- Workflow / state-machine systems in production  
- Postgres transactional design; idempotency patterns  
- AuthN/Z integration experience (OIDC/RBAC)  
- Clear written design reviews  

### First 90 days

Formalize PHOENIX states beyond demo ranker; approval signatures roadmap; audit export for compliance consumers.

### Apply

Subject: `GF Backend PHOENIX`.

---

## GF-27 — ML / Data Engineer (PROPHET)

### Mission

Move PROPHET from labeled fixture scoring toward a trainable anomaly pipeline with explainability and strict non-authoritative boundaries.

### Must-have

- Time-series anomaly detection in production or research deployed to prod  
- PyTorch or equivalent; feature pipelines; evaluation discipline  
- Refuses to over-claim model accuracy; documents uncertainty  

### Nice-to-have

- SHAP / similar explainability tooling  
- Kafka / feature-store experience  

### First 90 days

Model architecture ADR; offline evaluation harness on synthetic + approved datasets; fixture fallback remains mandatory.

### Apply

Subject: `GF ML PROPHET` + short note on a past false-positive failure you fixed.

---

## GF-28 — Frontend Engineer (Console & Dashboards)

### Mission

Evolve the React operator console: approval UX, topology/dashboard views, accessibility, and contract-safe API client.

### Must-have

- Strong React + TypeScript  
- Real-time UI (WebSocket or SSE)  
- Accessibility (keyboard, semantics) as a first-class requirement  
- Comfortable with design systems without over-carding operational UIs  

### First 90 days

Split remaining monolith panels; golden-path e2e; role-aware approval queue polish; performance on map-heavy views.

### Apply

Subject: `GF Frontend Console` + portfolio or repo.

---

## Interview loop (shared)

1. Screen (30) — mission fit + safety boundary alignment  
2. Technical deep dive (60) — systems / ML / UI as appropriate  
3. Design exercise (60) — failure mode + auditability  
4. Founder / values (30)  

### Decision scorecard

Each interviewer scores `1` (insufficient evidence), `2` (mixed), `3` (meets bar), or `4` (raises bar). Record concrete evidence, not intuition. A hire requires no safety-boundary score below `3` and an average of at least `3` across the role criteria.

| Role | Required criteria |
|---|---|
| Principal Architect | consensus failure modes; production ownership; architecture writing; security boundaries; mentorship |
| Backend | concurrency/networking or workflow durability; testing; idempotency; observability; safety boundaries |
| ML/Data | time-series evaluation; false-positive analysis; data governance; explainability; claim discipline |
| Frontend | React/TypeScript; real-time state; accessible interaction; failure UX; contract-safe API use |

### Exercises

- **Principal Architect:** review `CHAMELEON_CONSENSUS_DECISION.md`; identify unsafe assumptions, quorum/partition behavior, and the approvals required before external transport.
- **Backend:** design an idempotent topology-commit or PHOENIX transition handler with correlation IDs, retries, and rollback behavior.
- **ML/Data take-home:** using synthetic data only, propose an offline anomaly-evaluation harness. Include leakage controls, precision/recall reporting, false-positive review, and a promotion gate. Do not train on or request customer data.
- **Frontend design review:** critique the operator approve → execute → verify flow for keyboard access, stale state, degraded API behavior, and irreversible-action prevention.

Interviewers must not ask candidates to connect external systems, use production credentials, or process real customer data.

## Posting checklist

- [ ] Customize comp, location, and apply email  
- [ ] Post Principal Architect first  
- [ ] Post both backend roles within 48 hours  
- [ ] Post ML/Data and Frontend roles after assigning interview owners
- [ ] Copy the relevant scorecard and exercise into each candidate packet
- [ ] Track candidates in Notion Delivery Tasks comments  

## Ready-to-post blurb (HN / Wellfound)

Copy and customize the apply email before posting. Ghost Fabric cannot mark hiring Done until humans complete screening and offers.

```
Ghost Fabric (simulation-first resilience OS) is hiring:
- Principal Architect (Raft/distributed systems, Go/Rust)
- 2× Senior Backend (CHAMELEON mesh + PHOENIX workflow audit)
- ML/Data Engineer (PROPHET fixture→model path, time-series)
- Frontend Engineer (React console, approval UX, a11y)

Safety boundary: synthetic/approved training data only; human approval for recovery; no targeting or deception work.
JDs: docs/gtm/HIRING.md in the product repo (or request PDF).
```

**Remaining human gates:** post channels, screen candidates, sign offers, confirm start dates. 
