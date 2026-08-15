# Ghost Fabric operator runbook

## Purpose

Recover from demo-day failures without changing claims or leaving the simulation-only boundary.

## Nominal start

```powershell
cd backend
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

cd ..\frontend
npm run dev
```

Confirm:

1. Browser opens `http://127.0.0.1:5173`
2. Status pill shows `API LIVE`
3. Safety ribbon remains visible
4. Correlation ID is present in the header

## Failure modes

### 1. Backend unreachable

Symptoms: `FIXTURE MODE`, disabled mutation buttons, local snapshot still visible.

Operator actions:

1. Keep presenting from the local fixture.
2. Say: “The console has a deterministic fixture fallback. This demo uses no live AI decision authority.”
3. Restart backend, then click `Reset scenario` after reconnect if live controls are needed again.

### 2. WebSocket disconnect / refresh

Symptoms: brief `CONNECTING`, then resume or fresh snapshot.

Operator actions:

1. Do not reload mid-sentence if avoidable.
2. If refreshed, wait for `API LIVE`, then reset if the sequence looks stale.
3. If reconnect resumes from `after_sequence`, continue; no duplicate events should appear.

### 3. Live AI unavailable

Symptoms: `/api/analysis/summary` returns `mode: fixture`.

Operator actions:

1. Continue. Analysis is review-only and fixture-backed by default.
2. Do not claim live model authority.

Verification:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/analysis/summary | ConvertTo-Json
```

Expected: `"mode": "fixture"`.

### 4. Map or weather unavailable

Symptoms: map loading delay or `WEATHER UNAVAILABLE`.

Operator actions:

1. Continue with fictional overlay narrative.
2. Emphasize public basemap/weather are environmental context only.

### 5. No valid recovery route

Symptoms: PHOENIX shows `NO VALID ROUTE — MANUAL REVIEW`.

Operator actions:

1. Treat as a successful safety outcome: the planner refused an incomplete path.
2. Reset and re-run the golden path if a restored-state climax is required.

## Golden path recovery

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/scenario/reset
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/scenario/speed -ContentType application/json -Body '{"multiplier":2}'
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/scenario/advance -ContentType application/json -Body '{"seconds":45}'
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/tabletop/select -ContentType application/json -Body '{"branch_id":"bridge","decision_point_id":"relay-loss"}'
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/network/fail/northstar
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/phoenix/approve -ContentType application/json -Body '{"option_id":"route-atlas"}'
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/phoenix/execute
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/phoenix/verify -ContentType application/json -Body '{"succeeded":true}'
```

## Backup recording

Use this only as a contingency if live demo infrastructure fails.

1. Record a local walkthrough following `docs/DEMO_RUNBOOK.md`.
2. Prefer screen capture of `http://127.0.0.1:5173` with audio muted or with the exact safety wording.
3. Store the file outside the repository (large binary).
4. Generate a SHA-256 checksum of fixture/source evidence used in the recording:

```powershell
cd backend
.\.venv\Scripts\python scripts\checksum_backup_evidence.py
```

5. Keep the checksum output with the recording so reviewers can confirm the same fixture versions.

## Claims that remain true in degraded mode

- Synthetic or approved training data only
- Human approval required for simulated recovery
- No operational targeting or autonomous action
- AI summaries, when shown, are schema-constrained and fixture-replaceable

## Fallback matrix (GF-54)

| Dependency unavailable | Expected behavior | Operator line |
|---|---|---|
| FastAPI backend | Console `FIXTURE MODE` via `fixtureSnapshot` | Deterministic local fixture; no live authority |
| Live model / analysis API | `ProviderNeutralAdapter` returns `mode: fixture` | Review-only fixture explanation |
| WebSocket | HTTP snapshot polling / reconnect resume | Continue; no duplicate events on resume |
| PostgreSQL audit (memory mode) | In-process audit store still appends for the run | Say durable Postgres is optional for local demo |
| Prometheus / Grafana | Console and audit remain authoritative | Metrics are pilot telemetry, not the audit trail |
| External notify (PagerDuty/Slack) | Simulation outbox only; no network I/O | Delivery adapters blocked pending security review |
