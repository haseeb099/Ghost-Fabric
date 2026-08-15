from __future__ import annotations

from copy import deepcopy
from typing import Any


class MemoryAuditStore:
    """Process-local audit store used by tests and fixture mode."""

    backend = "memory"

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}
        self._events: dict[str, list[dict[str, Any]]] = {}
        self._commands: dict[str, dict[str, Any]] = {}
        self._active_correlation_id: str | None = None

    def start_run(
        self,
        *,
        correlation_id: str,
        fixture_id: str,
        fixture_version: str,
        seed: int,
        snapshot: dict[str, Any],
    ) -> None:
        self._active_correlation_id = correlation_id
        self._runs[correlation_id] = {
            "correlation_id": correlation_id,
            "fixture_id": fixture_id,
            "fixture_version": fixture_version,
            "seed": seed,
            "active": True,
            "snapshot": deepcopy(snapshot),
        }
        self._events[correlation_id] = []
        for run in self._runs.values():
            if run["correlation_id"] != correlation_id:
                run["active"] = False

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
    ) -> None:
        bucket = self._events.setdefault(correlation_id, [])
        if any(item["sequence"] == sequence for item in bucket):
            raise ValueError(f"Duplicate sequence {sequence} for run {correlation_id}")
        record = {
            **deepcopy(event),
            "previous_hash": previous_hash,
            "actor": actor,
            "role": role,
        }
        bucket.append(record)
        run = self._runs.setdefault(
            correlation_id,
            {
                "correlation_id": correlation_id,
                "fixture_id": snapshot.get("scenario", {}).get("id"),
                "fixture_version": snapshot.get("scenario", {}).get("fixture_version"),
                "seed": snapshot.get("scenario", {}).get("seed"),
                "active": True,
            },
        )
        run["snapshot"] = deepcopy(snapshot)
        run["active"] = True
        self._active_correlation_id = correlation_id

    def list_events(self, correlation_id: str) -> list[dict[str, Any]]:
        return deepcopy(self._events.get(correlation_id, []))

    def get_active_run(self) -> dict[str, Any] | None:
        if not self._active_correlation_id:
            return None
        run = self._runs.get(self._active_correlation_id)
        if not run:
            return None
        return {
            **deepcopy(run),
            "events": self.list_events(self._active_correlation_id),
        }

    def save_command(
        self,
        *,
        command_id: str,
        correlation_id: str,
        result: dict[str, Any],
    ) -> None:
        self._commands[command_id] = {
            "command_id": command_id,
            "correlation_id": correlation_id,
            "result": deepcopy(result),
        }

    def get_command(self, command_id: str) -> dict[str, Any] | None:
        item = self._commands.get(command_id)
        return deepcopy(item["result"]) if item else None

    def health(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "status": "healthy",
            "run_count": len(self._runs),
            "active_correlation_id": self._active_correlation_id,
        }
