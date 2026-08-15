"""Fine-grained action policy for Ghost Fabric REST controls.

Roles remain viewer/operator. Actions name the consequential capability
without introducing a second authorization system.
"""

from __future__ import annotations

from typing import Literal

Role = Literal["viewer", "operator"]
Action = Literal[
    "query",
    "mutate_scenario",
    "mesh_failover",
    "approve_recovery",
    "rollback_recovery",
    "export_audit",
]

# Explicit allow-list: every guarded route must map to one of these actions.
ACTION_POLICY: dict[Action, frozenset[Role]] = {
    "query": frozenset({"viewer", "operator"}),
    "export_audit": frozenset({"viewer", "operator"}),
    "mutate_scenario": frozenset({"operator"}),
    "mesh_failover": frozenset({"operator"}),
    "approve_recovery": frozenset({"operator"}),
    "rollback_recovery": frozenset({"operator"}),
}


def action_allowed(action: Action, role: Role) -> bool:
    allowed = ACTION_POLICY.get(action)
    if allowed is None:
        return False
    return role in allowed
