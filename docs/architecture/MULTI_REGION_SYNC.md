# Multi-Region Topology Sync — GF-47

**Status:** Deferred design  
**Current posture:** Three **independent** AWS pilot footprints (`infra/aws`)  
**Non-goals:** Automatic cross-region leader election, silent conflict merge, production RPO claims

## Decision for this phase

Keep regions independent. Cross-region replication requires a separate architecture and security approval after CHAMELEON transport review and Principal Architect sign-off.

## Why independent footprints

1. Raft in-process mesh is not yet process-boundary safe.
2. Independent pilots avoid split-brain while consensus transport is gated.
3. Compliance and data-residency reviews are simpler per region.

## Future options (unevaluated)

| Approach | Notes |
|---|---|
| Logical replication of audit/event store | Preserves append-only trail; does not sync Raft membership |
| Async topology gossip | Needs causality / vector clocks; high review cost |
| Active-passive region failover | Operator-driven cutover before automatic promotion |

## Acceptance when unblocked

- Explicit conflict policy (not last-write-wins by default)
- Chaos evidence for region loss without dual leaders
- Documented RPO/RTO as measured goals, never marketing SLAs until verified

## Related

- `docs/AWS_PILOT_DEPLOYMENT.md`
- `docs/architecture/CHAMELEON_CONSENSUS_DECISION.md`
- `.cursor/rules/aws-pilot-infra.mdc`
