from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ScenarioRunRow(Base):
    __tablename__ = "scenario_runs"

    correlation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fixture_id: Mapped[str] = mapped_column(String(128), nullable=False)
    fixture_version: Mapped[str] = mapped_column(String(32), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    latest_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("correlation_id", "sequence", name="uq_audit_run_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(80), nullable=True)
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class CommandIdempotencyRow(Base):
    __tablename__ = "command_idempotency"

    command_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


def create_db_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def run_migrations(engine: Engine) -> None:
    Base.metadata.create_all(engine)


class PostgresAuditStore:
    """PostgreSQL-backed append-only audit and idempotency store."""

    backend = "postgres"

    def __init__(self, database_url: str) -> None:
        self.engine = create_db_engine(database_url)
        run_migrations(self.engine)
        self._session_factory = create_session_factory(self.engine)

    def start_run(
        self,
        *,
        correlation_id: str,
        fixture_id: str,
        fixture_version: str,
        seed: int,
        snapshot: dict[str, Any],
    ) -> None:
        with self._session_factory() as session:
            session.execute(update(ScenarioRunRow).values(active=False))
            session.merge(
                ScenarioRunRow(
                    correlation_id=correlation_id,
                    fixture_id=fixture_id,
                    fixture_version=fixture_version,
                    seed=seed,
                    active=True,
                    latest_snapshot=deepcopy(snapshot),
                    updated_at=datetime.now(UTC),
                )
            )
            session.commit()

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
        with self._session_factory() as session:
            existing = session.scalar(
                select(AuditEventRow).where(
                    AuditEventRow.correlation_id == correlation_id,
                    AuditEventRow.sequence == sequence,
                )
            )
            if existing is not None:
                raise ValueError(f"Duplicate sequence {sequence} for run {correlation_id}")
            session.add(
                AuditEventRow(
                    correlation_id=correlation_id,
                    sequence=sequence,
                    event_id=str(event["event_id"]),
                    event_type=str(event["type"]),
                    event_hash=str(event["event_hash"]),
                    previous_hash=previous_hash,
                    actor=actor,
                    role=role,
                    payload=deepcopy(event),
                )
            )
            run = session.get(ScenarioRunRow, correlation_id)
            if run is None:
                run = ScenarioRunRow(
                    correlation_id=correlation_id,
                    fixture_id=str(snapshot.get("scenario", {}).get("id", "unknown")),
                    fixture_version=str(snapshot.get("scenario", {}).get("fixture_version", "0")),
                    seed=int(snapshot.get("scenario", {}).get("seed", 0)),
                    active=True,
                    latest_snapshot=deepcopy(snapshot),
                )
                session.add(run)
            else:
                run.active = True
                run.latest_snapshot = deepcopy(snapshot)
                run.updated_at = datetime.now(UTC)
            session.execute(
                update(ScenarioRunRow)
                .where(ScenarioRunRow.correlation_id != correlation_id)
                .values(active=False)
            )
            session.commit()

    def list_events(self, correlation_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(AuditEventRow)
                .where(AuditEventRow.correlation_id == correlation_id)
                .order_by(AuditEventRow.sequence.asc())
            ).all()
            return [deepcopy(row.payload) for row in rows]

    def get_active_run(self) -> dict[str, Any] | None:
        with self._session_factory() as session:
            run = session.scalar(select(ScenarioRunRow).where(ScenarioRunRow.active.is_(True)))
            if run is None:
                return None
            events = self.list_events(run.correlation_id)
            return {
                "correlation_id": run.correlation_id,
                "fixture_id": run.fixture_id,
                "fixture_version": run.fixture_version,
                "seed": run.seed,
                "active": run.active,
                "snapshot": deepcopy(run.latest_snapshot),
                "events": events,
            }

    def save_command(
        self,
        *,
        command_id: str,
        correlation_id: str,
        result: dict[str, Any],
    ) -> None:
        with self._session_factory() as session:
            session.merge(
                CommandIdempotencyRow(
                    command_id=command_id,
                    correlation_id=correlation_id,
                    result=deepcopy(result),
                )
            )
            session.commit()

    def get_command(self, command_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.get(CommandIdempotencyRow, command_id)
            return deepcopy(row.result) if row else None

    def health(self) -> dict[str, Any]:
        try:
            with self._session_factory() as session:
                run_count = session.scalar(select(ScenarioRunRow.correlation_id)) is not None
                active = session.scalar(select(ScenarioRunRow).where(ScenarioRunRow.active.is_(True)))
                return {
                    "backend": self.backend,
                    "status": "healthy",
                    "has_runs": bool(run_count),
                    "active_correlation_id": active.correlation_id if active else None,
                }
        except Exception as exc:  # noqa: BLE001 - surface store health failures
            return {
                "backend": self.backend,
                "status": "degraded",
                "error": str(exc),
            }


def dump_schema_sql() -> str:
    """Helper used by docs/tests to describe the durable schema."""
    return json.dumps(
        {
            "tables": [
                "scenario_runs",
                "audit_events",
                "command_idempotency",
            ],
            "constraints": [
                "uq_audit_run_sequence",
                "command_idempotency.command_id PK",
            ],
        }
    )
