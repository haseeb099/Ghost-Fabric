# CHAMELEON Chaos Fixture Results

Developer-machine, in-process fixture evidence only. Not an operational chaos
report and not a recovery-time or Byzantine-tolerance claim.

| Scenario | Correlation ID | Virtual time (ms) | Committed | Rejected | Notes |
|---|---|---:|---:|---:|---|
| three-voter-leader-crash-recovery | `run_chaos_3v` | 3300 | 2 | 0 | Leader crash + catch-up |
| five-voter-minority-partition | `run_chaos_5v` | 2050 | 2 | 1 | Live `Isolate` (not Crash); heal restores |
| live minority isolate | `run_partition_live` | n/a | 2 | 0 | Majority commits while minority stays alive |
| observer-outage | `run_chaos_obs` | 1500 | 1 | 0 | Quorum unchanged |
| invalid-message-rejection | `run_chaos_invalid` | 1500 | 1 | 2 | Validation boundary only |
| audit rejection under partition | `run_chaos_audit` | n/a | 0 | 1 | Canonical requested→rejected chain |

Commands:

```bash
go test ./... -run 'Chaos|ValidateTopology' -count=1
```

Safety notice retained on every `ChaosResult`:

> Fixture-only crash/omission chaos; not Byzantine-tolerant and not a recovery-time claim.
