# CHAMELEON In-Process Benchmark Record

**Run date:** 2026-08-15  
**Command:**

```bash
go test -run '^$' -bench BenchmarkTenNodeTopologyRevision -benchmem -count 3
```

## Harness

- 5 Raft voters and 5 non-voting observers
- Leader elected before timing
- One topology-reference quorum commit per iteration
- In-memory Go process only

## Output

```text
BenchmarkTenNodeTopologyRevision-4  220443  7791 ns/op  7334 B/op  4 allocs/op
BenchmarkTenNodeTopologyRevision-4  285988  5681 ns/op  7098 B/op  4 allocs/op
BenchmarkTenNodeTopologyRevision-4  282637  4814 ns/op  7180 B/op  4 allocs/op
```

## Interpretation

These are developer-machine in-process measurements, not CHAMELEON product
latency or throughput. They exclude network transport, TLS, persistence,
container scheduling, AWS topology, packet loss, and failure injection during
the timed section. No operational performance claim is authorized from this
record.
