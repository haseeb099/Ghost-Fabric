from __future__ import annotations

from typing import Any, Protocol


class AuditStore(Protocol):
    """Append-only audit and command idempotency persistence."""

    backend: str

    def start_run(
        self,
        *,
        correlation_id: str,
        fixture_id: str,
        fixture_version: str,
        seed: int,
        snapshot: dict[str, Any],
    ) -> None: ...

    def append_event(
        self,
        *,
        correlation_id: str,
        sequence: int,
        event: dict[str, Any],
        previous_hash: str,
        actor: str | None,
        role: str | None,
        snapshot: dict[str, Any],
    ) -> None: ...

    def list_events(self, correlation_id: str) -> list[dict[str, Any]]: ...

    def get_active_run(self) -> dict[str, Any] | None: ...

    def save_command(
        self,
        *,
        command_id: str,
        correlation_id: str,
        result: dict[str, Any],
    ) -> None: ...

    def get_command(self, command_id: str) -> dict[str, Any] | None: ...

    def health(self) -> dict[str, Any]: ...
