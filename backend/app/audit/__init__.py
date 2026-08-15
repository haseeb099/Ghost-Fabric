from __future__ import annotations

from app.audit.base import AuditStore
from app.audit.memory import MemoryAuditStore
from app.audit.postgres import PostgresAuditStore
from app.settings import Settings


def build_audit_store(settings: Settings) -> AuditStore:
    if settings.audit_backend == "postgres":
        return PostgresAuditStore(settings.database_url)
    return MemoryAuditStore()
