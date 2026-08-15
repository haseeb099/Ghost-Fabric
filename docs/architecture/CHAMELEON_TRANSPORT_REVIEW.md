# CHAMELEON Process Transport Review — GF-33 Gate

**Status:** Pending Principal Architect and security approval  
**Scope:** A future local Go control-plane → FastAPI audit bridge only  
**Excluded:** Browser subscriptions, peer-to-peer mesh transport, AWS
cross-region traffic, PHOENIX recovery, and external action execution

## Fixed input contract

The only candidate message is
`contracts/chameleon-topology-commit.schema.json`. It carries evidence of a
quorum-committed topology revision:

- cluster ID, Raft term/index, and active correlation ID;
- SHA-256 payload reference; and
- prior canonical requested-event reference.

It must never carry raw recovery commands, route instructions, credentials, or
an approval assertion. FastAPI's `backend/app/chameleon_bridge.py` validates
the evidence and creates the server-hashed canonical event.

## Decisions reviewers must approve

1. **Transport:** local Unix socket/named pipe, loopback TLS, or another
   reviewed mechanism. Do not enable TCP or WebSockets by default.
2. **Node identity:** workload identity and mutual authentication design,
   rotation, revocation, and test fixtures. Existing user bearer tokens are
   not a node-authentication protocol.
3. **Replay protection:** persist and reject duplicate `(cluster_id,
   raft_term, raft_index)` evidence; define restart behavior.
4. **Authorization:** map authenticated node identity to the permitted cluster
   and preserve the human operator actor already present in audit evidence.
5. **Availability behavior:** define fail-closed behavior when the audit
   bridge is unavailable. No silent local log fallback is allowed.
6. **Observability:** redact secrets, record correlation IDs, and alert on
   malformed, duplicate, or unauthorized evidence.

## Required acceptance tests after approval

- Valid mutually authenticated evidence becomes one canonical `AuditStore`
  event with a server-generated hash.
- Wrong identity, cluster, correlation ID, payload hash, or replay is rejected
  without mutating canonical audit state.
- Audit-store failure is visible and does not create a shadow event log.
- Recovery-shaped data is rejected at schema validation.
- Restart/replay behavior is deterministic and audited.

## Explicit non-approval

This packet records a proposed boundary; it is not an approval to implement
any external transport, publish WebSocket events, or claim failover latency.
