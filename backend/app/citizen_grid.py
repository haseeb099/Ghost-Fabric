"""Simulation-only citizen sensor grid for civilian early-warning rehearsal.

The grid models consenting smartphone sensors as anonymous district aggregates.
It never stores individual devices, locations, trajectories, launch origins, or
any targeting information. Confidence is corroboration evidence for a human
warning decision, not a forecast of a real event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


PROHIBITED_TERMS = (
    "target",
    "targeting",
    "trajectory",
    "launcher",
    "impact point",
    "coordinate",
    "weapon",
    "intercept",
    "strike",
)

GridState = Literal["listening", "corroborating", "confirmed"]
ChannelId = Literal["sms", "radio", "mesh"]

# Fixed synthetic districts; names are invented and carry no real geography.
DISTRICTS: tuple[tuple[str, str, int], ...] = (
    ("d1", "Riverside", 640),
    ("d2", "Old Market", 520),
    ("d3", "North Yards", 480),
    ("d4", "Foundry", 455),
    ("d5", "Garden Rows", 430),
    ("d6", "Rail Quarter", 410),
    ("d7", "Lakeside", 395),
    ("d8", "University", 380),
    ("d9", "Harbour Flats", 350),
    ("d10", "Hill Terrace", 335),
    ("d11", "West Gate", 315),
    ("d12", "Meadow End", 290),
)

CHANNEL_LADDER: tuple[tuple[ChannelId, str, int], ...] = (
    ("sms", "Cell broadcast / SMS", 96),
    ("radio", "Community FM relay", 71),
    ("mesh", "Offline mesh + siren relay", 48),
)

# Corroboration floor: a single district can never raise a public warning.
MIN_CONFIRMING_DISTRICTS = 3
CONFIRM_CONFIDENCE = 55
SYNTHETIC_LEAD_SECONDS = 240


def _validate_text(*values: str) -> None:
    combined = " ".join(values).lower()
    for term in PROHIBITED_TERMS:
        if term in combined:
            raise ValueError(f"prohibited citizen-grid term: {term}")


@dataclass
class District:
    id: str
    name: str
    sensors_total: int
    sensors_online: int
    reporting: bool = False


@dataclass
class Channel:
    id: ChannelId
    label: str
    reach_percent: int
    status: Literal["available", "degraded", "jammed"] = "available"


@dataclass
class CitizenGrid:
    """Deterministic aggregate sensor grid; no per-device data is retained."""

    districts: list[District] = field(default_factory=list)
    channels: list[Channel] = field(default_factory=list)
    detections: int = 0
    warning_dispatched: bool = False
    dispatch_channel: ChannelId | None = None

    def __post_init__(self) -> None:
        if not self.districts:
            self.districts = [
                District(id=item[0], name=item[1], sensors_total=item[2], sensors_online=item[2])
                for item in DISTRICTS
            ]
        if not self.channels:
            self.channels = [
                Channel(id=item[0], label=item[1], reach_percent=item[2]) for item in CHANNEL_LADDER
            ]
        _validate_text(*[district.name for district in self.districts])

    @property
    def sensors_total(self) -> int:
        return sum(district.sensors_total for district in self.districts)

    @property
    def sensors_online(self) -> int:
        return sum(district.sensors_online for district in self.districts)

    @property
    def reporting_districts(self) -> list[District]:
        return [district for district in self.districts if district.reporting and district.sensors_online]

    @property
    def confidence(self) -> int:
        online = self.sensors_online
        if not online:
            return 0
        reporting = sum(district.sensors_online for district in self.reporting_districts)
        return min(94, round(100 * reporting / online))

    @property
    def grid_state(self) -> GridState:
        confirming = len(self.reporting_districts)
        if confirming >= MIN_CONFIRMING_DISTRICTS and self.confidence >= CONFIRM_CONFIDENCE:
            return "confirmed"
        if confirming >= 2:
            return "corroborating"
        return "listening"

    @property
    def active_channel(self) -> Channel | None:
        return next((channel for channel in self.channels if channel.status != "jammed"), None)

    def register_detection(self) -> dict[str, Any]:
        """Advance corroboration by activating the next district in fixed order."""
        candidate = next(
            (district for district in self.districts if not district.reporting and district.sensors_online),
            None,
        )
        if candidate is not None:
            candidate.reporting = True
            self.detections += 1
        return {
            "district": candidate.name if candidate else None,
            "confirming_districts": len(self.reporting_districts),
            "confidence": self.confidence,
            "state": self.grid_state,
        }

    def apply_attrition(self, percent: int) -> dict[str, Any]:
        """Take a share of synthetic sensors offline to show graceful degradation."""
        before = self.sensors_online
        for district in self.districts:
            district.sensors_online = round(district.sensors_total * (100 - percent) / 100)
            if district.sensors_online == 0:
                district.reporting = False
        return {
            "removed_sensors": before - self.sensors_online,
            "sensors_online": self.sensors_online,
            "confidence": self.confidence,
            "state": self.grid_state,
        }

    def jam_active_channel(self) -> dict[str, Any]:
        """Mark the current channel jammed and fall back down the ladder."""
        channel = self.active_channel
        if channel is None:
            return {"jammed_channel": None, "fallback_channel": None}
        channel.status = "jammed"
        fallback = self.active_channel
        return {
            "jammed_channel": channel.id,
            "fallback_channel": fallback.id if fallback else None,
        }

    def dispatch_warning(self, channel_id: ChannelId) -> dict[str, Any]:
        """Record a human-approved simulated advisory; nothing is actually sent."""
        self.warning_dispatched = True
        self.dispatch_channel = channel_id
        channel = next(channel for channel in self.channels if channel.id == channel_id)
        return {
            "channel": channel.id,
            "channel_label": channel.label,
            "advisory_districts": [district.name for district in self.reporting_districts],
            "estimated_reach_percent": channel.reach_percent,
            "synthetic_lead_seconds": SYNTHETIC_LEAD_SECONDS,
            "effect": "simulation-only",
        }

    def projection(self) -> dict[str, Any]:
        active = self.active_channel
        confirming = len(self.reporting_districts)
        return {
            "schema_version": 1,
            "label": "citizen-sensor-simulation",
            "sensors_total": self.sensors_total,
            "sensors_online": self.sensors_online,
            "grid_survival_percent": round(100 * self.sensors_online / self.sensors_total),
            "confirming_districts": confirming,
            "min_confirming_districts": MIN_CONFIRMING_DISTRICTS,
            "confidence": self.confidence,
            "state": self.grid_state,
            "ready_for_warning": self.grid_state == "confirmed" and active is not None,
            "warning_dispatched": self.warning_dispatched,
            "dispatch_channel": self.dispatch_channel,
            "synthetic_lead_seconds": SYNTHETIC_LEAD_SECONDS,
            "advisory_districts": [district.name for district in self.reporting_districts],
            "districts": [
                {
                    "id": district.id,
                    "name": district.name,
                    "sensors_online": district.sensors_online,
                    "reporting": district.reporting,
                }
                for district in self.districts
            ],
            "channels": [
                {
                    "id": channel.id,
                    "label": channel.label,
                    "reach_percent": channel.reach_percent,
                    "status": channel.status,
                    "active": bool(active and channel.id == active.id),
                }
                for channel in self.channels
            ],
            "privacy": "Anonymous district aggregates only; no device identity, precise location, or audio is retained.",
            "notice": (
                "Synthetic corroboration evidence for a human advisory decision. "
                "No trajectory estimation, no location of any source, and no targeting."
            ),
            "guardrail": (
                f"At least {MIN_CONFIRMING_DISTRICTS} independent districts and "
                f"{CONFIRM_CONFIDENCE}% corroboration are required before an operator may advise."
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "detections": self.detections,
            "warning_dispatched": self.warning_dispatched,
            "dispatch_channel": self.dispatch_channel,
            "districts": [
                {
                    "id": district.id,
                    "name": district.name,
                    "sensors_total": district.sensors_total,
                    "sensors_online": district.sensors_online,
                    "reporting": district.reporting,
                }
                for district in self.districts
            ],
            "channels": [
                {
                    "id": channel.id,
                    "label": channel.label,
                    "reach_percent": channel.reach_percent,
                    "status": channel.status,
                }
                for channel in self.channels
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CitizenGrid":
        grid = cls(
            districts=[
                District(
                    id=str(item["id"]),
                    name=str(item["name"]),
                    sensors_total=int(item["sensors_total"]),
                    sensors_online=int(item["sensors_online"]),
                    reporting=bool(item["reporting"]),
                )
                for item in payload.get("districts", [])
            ],
            channels=[
                Channel(
                    id=item["id"],
                    label=str(item["label"]),
                    reach_percent=int(item["reach_percent"]),
                    status=item.get("status", "available"),
                )
                for item in payload.get("channels", [])
            ],
        )
        grid.detections = int(payload.get("detections", 0))
        grid.warning_dispatched = bool(payload.get("warning_dispatched", False))
        grid.dispatch_channel = payload.get("dispatch_channel")
        return grid
