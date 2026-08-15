# CHAMELEON Chaos Testing (GF-51)

Deterministic, fixture-only chaos harness for the in-process Raft control-plane
prototype. It validates crash and quorum-partition behavior under the approved
crash/omission fault model.

## Supported scenarios

| Scenario | Fault types | Expected outcome |
|---|---|---|
| Three-voter leader crash/recovery | `crash`, `recover`, `advance` | Replacement election; recovered node catches up |
| Five-voter minority partition | `partition`/`Isolate`, `heal`, `delay_marker` | Isolated nodes stay alive; minority-side writes rejected; heal restores catch-up |
| Live minority isolate | `Isolate`, `HealPartitions` | Majority still commits; isolated followers lag until heal |
| Observer outage | `crash`, `recover` | Quorum unchanged; observer catches up |
| Invalid message rejection | `reject_invalid_message` | Corrupt/recovery-shaped payloads rejected; committed state unchanged |

`partition` / `Isolate` is **not** `Crash`: nodes remain `Alive` but cannot
exchange votes or acknowledgements across the cut. Quorum is always measured
against the full voter configuration, preventing split-brain commits.

## Virtual-time contract

- Every `advance` / `delay_marker` step requires a positive `advance_ms`.
- Timing is virtual only; wall-clock recovery SLAs are not measured or claimed.
- Node IDs must be declared in the scenario voter/observer sets.
- Fault types are allowlisted. Unsupported types (including Byzantine
  equivocation agents) are rejected at scenario validation.

## Run

```bash
cd services/chameleon-control-plane
go test ./... -run Chaos -count=1
```

With Docker when Go is unavailable locally:

```bash
docker run --rm -v "$PWD:/src" -w /src golang:1.23-alpine go test ./... -run Chaos -count=1
```

## Explicit exclusions

- No Gremlin agent, process kill, packet drop, or live network delay injection
- No node identity, TLS, or multi-process transport
- No Byzantine fault tolerance (`f` liars / equivocating replicas)
- No PHOENIX recovery execution or external action authorization
- No `<1min recovery` or other operational latency claims

Corrupt/equivocating inputs are modeled only as **validation-boundary
rejection**. That proves unsafe messages do not commit; it does not prove
Byzantine-safe consensus.

See `CHAOS_RESULTS.md` for the deterministic fixture evidence summary.
