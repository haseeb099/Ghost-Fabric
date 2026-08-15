"""Simulation-only PHOENIX notification outbox.

The outbox records delivery intent for a future reviewed PagerDuty/Slack
adapter. It intentionally performs no network I/O and never carries recovery
commands.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhoenixNotification:
    sequence: int
    correlation_id: str
    workflow_id: str
    event_type: str
    actor: str
    status: str = "queued"
    channel: str = "simulation-outbox"


class PhoenixNotificationOutbox:
    def __init__(self) -> None:
        self._notifications: list[PhoenixNotification] = []

    def queue(
        self,
        *,
        correlation_id: str,
        workflow_id: str,
        event_type: str,
        actor: str,
    ) -> PhoenixNotification:
        notification = PhoenixNotification(
            sequence=len(self._notifications) + 1,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            event_type=event_type,
            actor=actor,
        )
        self._notifications.append(notification)
        return notification

    def snapshot(self) -> list[dict[str, object]]:
        return [notification.__dict__.copy() for notification in self._notifications]

    def restore(self, items: list[dict[str, object]]) -> None:
        self._notifications = [
            PhoenixNotification(
                sequence=int(item["sequence"]),
                correlation_id=str(item["correlation_id"]),
                workflow_id=str(item["workflow_id"]),
                event_type=str(item["event_type"]),
                actor=str(item["actor"]),
                status=str(item.get("status", "queued")),
                channel=str(item.get("channel", "simulation-outbox")),
            )
            for item in items
        ]
