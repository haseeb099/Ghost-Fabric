# Ghost Fabric — EDGE C2 Continuum

Ghost Fabric is a fictional, simulation-first **contested-communications console**: it rehearses how a frontline unit keeps command and control coherent when its coordination relay is jammed or destroyed. It shows deterministic coordinator handoff, partition awareness, labeled link-degradation review, declared course-of-action comparison, human-approved reversible restore, and an append-only hash-chained event stream with optional PostgreSQL durability.

It protects the **friendly** network only. It is not an operational military system: the repository uses fictional assets and synthetic data, performs **no** threat tracking, geolocation, targeting, weapons assignment, or individual profiling, and requires explicit human approval for every simulated recovery action.

## Current vertical slice

- CHAMELEON graph routing with coordinator-loss injection, deterministic handoff, shortest paths, and degraded-partition detection
- PROPHET labeled synthetic telemetry with baseline noise, a 47-minute pattern onset, virtual-time countdown, preserved missing data, and a reviewed false-positive case
- MIRROR approved YAML catalog with human-selected tabletop branches and `mirror.*` audit traces
- PHOENIX stepped recovery workflow: approve → simulate execution → verify → restored|rollback
- CITIZEN community sensor grid: 5,000 synthetic consenting phones as anonymous district aggregates, multi-district corroboration guardrails, 30% sensor-attrition survival, SMS → FM → offline-mesh advisory fallback, and operator-approved simulated civilian advisories
- Guided cinematic demo phases projected from durable scenario state
- Production foundation: typed settings, `/api/v1` contracts, OpenAPI artifact, bearer viewer/operator auth, Compose + PostgreSQL audit store
- Real OpenStreetMap geography with clearly labeled fictional exercise overlays
- First-run operator guide explaining the four layers and the five-step golden path
- Live public Open-Meteo weather context with an offline-safe unavailable state
- Audited 1× / 2× / 4× simulation speeds and tabletop branch selections
- Versioned `broken-signal-v1` golden scenario with a fixed seed, two operator branch points, canonical actions, and an asserted end state
- Versioned event envelopes, correlation IDs, chained event hashes, and request-level idempotency
- Fixture fallback when the backend is unavailable

## Active exercise data

The default **CIVIL CONTINUITY** exercise uses generated civil communications,
utility-queue, and emergency-mesh telemetry informed by abstracted patterns in
public reporting from the Russia–Ukraine war. It is not a reconstruction of an
actual incident: node names, coordinates, values, timing, and outcomes are
fictional and deliberately generalized. The repository contains no real asset
locations, current tactical observations, targeting data, or operational
forecasts.

## Frontline problem framing

Electronic warfare and precision attrition take out command and control before
anything else. A unit then loses three things at once: **who is still
reachable**, **who coordinates the mesh**, and **whether a restored link can be
trusted**. Peacetime monitoring tools assume uptime; they do not model hostile
degradation, partitioned units, or approval-bound recovery under stress.

Ghost Fabric rehearses that exact sequence and produces a signed decision record
for after-action review. See [docs/FRONTLINE_C2_PITCH.md](docs/FRONTLINE_C2_PITCH.md)
for the submission narrative, demo script, and claim boundaries.

## Citizen sensor grid boundary

The CITIZEN layer rehearses how a city could reach civilians when normal
channels fail. It models consenting phones only as anonymous district counts and
deliberately **does not** estimate a trajectory, locate any source, produce
coordinates, or support interception or targeting of anything. A public advisory
requires at least three independent corroborating districts, 55% corroboration,
and an explicit operator approval; the approved advisory is recorded in the audit
stream as `simulation-only` and is never transmitted. The 4-minute lead time is a
labeled fixture value, not a measured or promised warning time.

## Run locally

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Interactive docs: `/docs`. Versioned routes: `/api/v1/*`. Legacy aliases: `/api/*`.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

### Docker Compose (durable audit)

```powershell
copy .env.example .env
docker compose up --build
```

- Console: `http://127.0.0.1:8080`
- API: `http://127.0.0.1:8000`
- Demo tokens: `operator-token` / `viewer-token`

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

### Reference documentation

- [API reference](docs/API_REFERENCE.md) — versioned endpoints, authentication, and curl/Python/Go examples
- [Architecture guide](docs/ARCHITECTURE.md) — components, data flow, and safety boundaries
- [Operations manual](docs/OPERATIONS_MANUAL.md) — validation, backup, recovery, and scaling limits
- [Load testing](docs/LOAD_TESTING.md) — developer-only synthetic load harness (not capacity claims)

### AWS pilot foundation (GF-29)

Three independent regional footprints (ECS/Fargate + RDS + Secrets Manager). Manual apply only:

- [docs/AWS_PILOT_DEPLOYMENT.md](docs/AWS_PILOT_DEPLOYMENT.md)
- Terraform root: `infra/aws/`

Not multi-region consensus/failover — that remains later CHAMELEON work.

### CHAMELEON consensus design (GF-32)

The proposed control-plane protocol is Raft for crash/omission faults only;
it coordinates replicated topology state and cannot approve recovery actions.
Principal Architect approval is pending before implementation:

- [docs/architecture/CHAMELEON_CONSENSUS_DECISION.md](docs/architecture/CHAMELEON_CONSENSUS_DECISION.md)

## Verify

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python scripts\check_openapi.py

cd ..\frontend
npm run build
```

GitHub Actions runs backend tests, OpenAPI drift check, frontend build, Compose Postgres smoke, Terraform fmt/validate, and Playwright smoke tests.

### Performance review

```powershell
cd backend
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python scripts\measure_perf.py
```

This writes `backend/app/fixtures/perf-review-latest.json` with p50/p95 event-to-UI and reset latency.

### Demo and degraded mode

- Timed demo script: `docs/DEMO_RUNBOOK.md`
- Rehearsal log (3 timed takes + reviewer): `docs/DEMO_REHEARSAL_LOG.md`
- Machine rehearsal results: `backend/app/fixtures/demo-rehearsal-results.json` (`scripts/run_demo_rehearsals.py`)
- Operator recovery (backend down, reconnect, AI-offline, backup recording): `docs/OPERATOR_RUNBOOK.md`
- Evidence checksums for a backup recording:

```powershell
cd backend
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python scripts\checksum_backup_evidence.py
```

## Go-to-market (Weeks 1–2)

- Positioning + personas: [docs/gtm/POSITIONING.md](docs/gtm/POSITIONING.md)
- Vertical 1-pagers: [docs/gtm/](docs/gtm/)
- Three-slide pitch: [docs/gtm/PITCH_DECK_3_SLIDES.md](docs/gtm/PITCH_DECK_3_SLIDES.md)
- Hiring pack (architect, backend, ML, frontend): [docs/gtm/HIRING.md](docs/gtm/HIRING.md)

## Safety boundary

- Synthetic or approved training data only
- Real public geography and weather may provide environmental context; no real operational coordinates, actors, asset feeds, or current-conflict data
- No target selection, weapon assignment, autonomous action, or operational deception
- AI output is schema-constrained, non-authoritative, and replaceable by deterministic fixtures
- Authenticated operator identity is recorded in durable audit events when auth tokens are configured
- Outbound GTM materials must not invent measured accuracy, warning-time, or certification claims
