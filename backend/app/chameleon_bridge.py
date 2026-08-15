"""Canonical, transport-free ingress for CHAMELEON commit evidence.

External Go↔Python transport is intentionally not implemented here. A reviewed
future process boundary must validate a signed/authorized message, deserialize
it into ``ChameleonTopologyCommit``, and use this module to append the one
canonical FastAPI event through ``AuditStore``.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.auth import Principal


class ChameleonBridgeError(ValueError):
    """Rejected CHAMELEON evidence must not enter the canonical audit chain."""


class ChameleonTopologyCommit(BaseModel):
    """Non-executable evidence for a quorum-committed topology revision."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=1, ge=1)
    cluster_id: str = Field(min_length=1, max_length=128)
    raft_term: int = Field(ge=1)
    raft_index: int = Field(ge=1)
    correlation_id: str = Field(min_length=1)
    payload_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    audit_event_ref: str = Field(pattern=r"^evt_[A-Za-z0-9_]+$")


class ChameleonEventWriter(Protocol):
    correlation_id: str

    def set_actor_context(self, principal: Principal) -> None: ...

    def record_chameleon_topology_commit(
        self, evidence: ChameleonTopologyCommit
    ) -> dict[str, object]: ...


def ingest_committed_topology(
    state: ChameleonEventWriter,
    *,
    principal: Principal,
    evidence: ChameleonTopologyCommit,
) -> dict[str, object]:
    """Append a server-hashed canonical event for committed topology evidence.

    This accepts evidence only for the active scenario correlation ID and only
    from an authenticated operator context. It cannot invoke PHOENIX recovery.
    """

    if principal.role != "operator":
        raise ChameleonBridgeError("operator role required for CHAMELEON topology evidence")
    if evidence.correlation_id != state.correlation_id:
        raise ChameleonBridgeError("CHAMELEON evidence correlation ID does not match active scenario")

    state.set_actor_context(principal)
    return state.record_chameleon_topology_commit(evidence)
