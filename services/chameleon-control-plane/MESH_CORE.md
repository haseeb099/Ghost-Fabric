# CHAMELEON Mesh Core Slice (GF-33)

In-process mesh behavior layered on the Raft prototype. Transport-free and
non-authoritative for recovery.

## Capabilities

| Capability | Module | Behavior |
|---|---|---|
| Health scoring | `health.go` | CPU / memory / latency signals → 0–100 score and grade |
| Route recalculation | `routing.go` | Shortest paths over alive edges after node loss |
| Graceful degradation | `degradation.go` | Feature shedding by criticality as pressure rises |
| Canonical audit adapter | `audit_adapter.go` | Requested → committed/rejected canonical-event sequence |
| Process metrics | `metrics.go` | Prometheus text for commits, rejections, duration, degradation |

## Safety

- Crash updates health to offline and recalculates routes when edges exist.
- Degradation never authorizes PHOENIX recovery or external action.
- The in-memory `AuditEventSink` is fixture/test-only; a future process
  boundary must write the FastAPI `AuditStore`, not a competing audit log.
- Latency/throughput acceptance targets in Notion remain **unproven**; any
  timed route recalculation log is fixture-labeled developer observation only.
- `MetricsCollector` is process telemetry only and never replaces
  `AuditEventSink`.

## Tests

```bash
cd services/chameleon-control-plane
go test ./...
```

Covered:

- healthy / degraded / critical / offline scoring
- minority-loss route exclusion and revision change
- shed_low → shed_medium → essential_only feature shedding
