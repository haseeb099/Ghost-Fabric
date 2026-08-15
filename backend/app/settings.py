from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed runtime configuration for Ghost Fabric."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Ghost Fabric Simulation API"
    app_version: str = "0.2.0"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = "postgresql+psycopg://ghost:ghost@localhost:5432/ghost_fabric"
    audit_backend: Literal["memory", "postgres"] = "memory"
    restore_active_run: bool = True

    auth_mode: Literal["optional", "required"] = "optional"
    auth_tokens: str = Field(
        default="",
        description="Comma-separated token=role:subject entries, e.g. viewer-token=viewer:DEMO-VIEWER,operator-token=operator:DEMO-OPERATOR",
    )
    auth_api_keys: str = Field(
        default="",
        description="Comma-separated key=role:subject entries for X-API-Key authentication",
    )
    auth_jwt_secret: str = ""
    auth_jwt_algorithm: Literal["HS256"] = "HS256"
    rate_limit_per_second: int = Field(default=1000, ge=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = True
    default_actor: str = "DEMO-OPERATOR"
    default_role: Literal["viewer", "operator"] = "operator"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _strip_origins(cls, value: object) -> object:
        return value

    @model_validator(mode="after")
    def _enforce_production_security_posture(self) -> Self:
        if self.auth_jwt_secret and len(self.auth_jwt_secret.encode("utf-8")) < 32:
            raise ValueError("AUTH_JWT_SECRET must be at least 32 bytes when configured")
        if self.environment != "production":
            return self
        if self.auth_mode != "required":
            raise ValueError("AUTH_MODE must be 'required' when ENVIRONMENT=production")
        has_tokens = bool(self.parsed_auth_tokens())
        has_api_keys = bool(self.parsed_api_keys())
        has_jwt = bool(self.auth_jwt_secret)
        if not (has_tokens or has_api_keys or has_jwt):
            raise ValueError(
                "production requires at least one of AUTH_TOKENS, AUTH_API_KEYS, or AUTH_JWT_SECRET"
            )
        if self.default_role != "viewer":
            raise ValueError("DEFAULT_ROLE must be 'viewer' when ENVIRONMENT=production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def parsed_auth_tokens(self) -> dict[str, tuple[str, str]]:
        """Return token -> (role, subject)."""
        return self._parse_identities(self.auth_tokens)

    def parsed_api_keys(self) -> dict[str, tuple[str, str]]:
        """Return API key -> (role, subject)."""
        return self._parse_identities(self.auth_api_keys)

    def _parse_identities(self, value: str) -> dict[str, tuple[str, str]]:
        mapping: dict[str, tuple[str, str]] = {}
        if not value.strip():
            return mapping
        for item in value.split(","):
            token_part, _, role_subject = item.partition("=")
            role, _, subject = role_subject.partition(":")
            token = token_part.strip()
            role_name = role.strip()
            subject_name = subject.strip() or self.default_actor
            if token and role_name in {"viewer", "operator"}:
                mapping[token] = (role_name, subject_name)
        return mapping


@lru_cache
def get_settings() -> Settings:
    return Settings()
