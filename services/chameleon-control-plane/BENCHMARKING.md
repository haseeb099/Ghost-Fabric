# CHAMELEON Prototype Benchmarking

The Go control-plane benchmark is a repeatable **in-process correctness
baseline**, not a production performance claim.

## Run

```bash
cd services/chameleon-control-plane
go test -run '^$' -bench BenchmarkTenNodeTopologyRevision -benchmem -count 5
```

When Go is unavailable locally:

```bash
docker run --rm \
  -v "$PWD/services/chameleon-control-plane:/workspace" \
  -w /workspace golang:1.23-alpine \
  go test -run '^$' -bench BenchmarkTenNodeTopologyRevision -benchmem -count 5
```

## Harness shape

- 5 Raft voters, 5 non-voting observers
- In-memory topology references only
- Deterministic leader election before the timed section
- Quorum commit plus observer replication

## Excluded from measurement

- Network I/O, packet loss, latency, or partitions
- TLS, node identity, certificate rotation
- PostgreSQL/AuditStore persistence
- Container scheduling, CPU pressure, or disk I/O
- AWS regional topology and cross-region replication

Do not quote benchmark `ns/op`, operations per second, or latency as
CHAMELEON product performance. GF-33 needs a reviewed multi-process,
failure-injection, persistence-aware benchmark before any operational target
can be assessed.
