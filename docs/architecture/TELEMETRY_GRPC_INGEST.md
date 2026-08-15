# Synthetic Telemetry Ingest Contract — GF-44

**Status:** Schema design only — no live gRPC server  
**Scope:** Versioned synthetic metric batches for future high-throughput ingest  
**Non-goals:** 10k events/sec product claims, production Kafka bridge, operational sensor feeds

## Decision

Ship a **protobuf schema for synthetic samples** so a future `IngestService` can be reviewed without inventing a live server in this phase. REST `/api/v1` remains the only supported ingest/read path.

## Schema location

`contracts/telemetry/synthetic_metrics.proto`

## Proposed service (not implemented)

```protobuf
service IngestService {
  rpc PublishMetrics (stream MetricBatch) returns (IngestAck);
}
```

## Safety rules

- Batches must carry `fixture_label` or `synthetic=true`.
- Reject payloads that include targeting, person identifiers, or recovery commands.
- Backpressure and Prometheushistograms are future work; do not claim throughput.

## Current substitute

- Fixture telemetry: `backend/app/fixtures/prophet-telemetry-v1.json`
- REST scores/explain/telemetry routes
- Developer load harness: `docs/LOAD_TESTING.md` (not capacity evidence)
