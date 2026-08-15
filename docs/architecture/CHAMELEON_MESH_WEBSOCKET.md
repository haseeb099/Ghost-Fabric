# CHAMELEON Mesh WebSocket Subscription — GF-34

**Status:** Design only — implementation gated  
**Depends on:** `docs/architecture/CHAMELEON_TRANSPORT_REVIEW.md` approvals  
**Non-goals:** Live topology push before transport/security review; browser SQLite replicas; unauthenticated mesh control

## Why deferred

The console already streams **scenario events** on `/ws/events`. That channel is explicitly **not** a CHAMELEON topology subscription. Opening a mesh WebSocket before the transport review would create a second control plane and an unauthenticated membership surface.

## Proposed future contract (not implemented)

| Item | Proposal |
|---|---|
| Endpoint | `/mesh/subscribe` (versioned under `/api/v1` once auth design lands) |
| Encoding | Compact JSON diffs first; Protobuf optional after schema freeze |
| Auth | Same operator/viewer credentials as REST; no anonymous subscribe |
| Payload | Topology snapshot + health grade diffs only |
| Forbidden fields | Recovery options, PHOENIX actions, executable commands |
| Heartbeat | Application ping/pong; clients reconnect with last `commit_index` |
| Client cache | IndexedDB optional; never a source of authority |

## Acceptance when unblocked

1. Transport review checklist signed (architecture + security).
2. Messages validate against an approved schema (no extra/recovery-shaped keys).
3. Tests cover reconnect, auth failure, and diff-only updates.
4. Latency numbers remain developer measurements, not product SLAs.

## Current substitute

- REST: `GET /mesh/topology`, `POST /mesh/failover` (operator, audited)
- In-process Go mesh core under `services/chameleon-control-plane/`
- Evidence bridge: `contracts/chameleon-topology-commit.schema.json`
