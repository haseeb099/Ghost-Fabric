from __future__ import annotations

from typing import Annotated, Literal

import jwt
from fastapi import Depends, Header, HTTPException, Request, status

from app.rbac import Action, action_allowed
from app.settings import Settings, get_settings

Role = Literal["viewer", "operator"]
MIN_JWT_SECRET_BYTES = 32


class Principal:
    def __init__(self, subject: str, role: Role, authenticated: bool) -> None:
        self.subject = subject
        self.role = role
        self.authenticated = authenticated


def resolve_principal(
    authorization: str | None,
    settings: Settings,
    api_key: str | None = None,
) -> Principal:
    """Resolve identity from exactly one credential channel."""
    has_api_key = bool(api_key and api_key.strip())
    has_authorization = bool(authorization and authorization.strip())
    if has_api_key and has_authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provide either X-API-Key or Authorization, not both",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if has_api_key:
        identity = settings.parsed_api_keys().get(api_key.strip())
        if identity is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        role, subject = identity
        return Principal(subject=subject, role=role, authenticated=True)  # type: ignore[arg-type]

    tokens = settings.parsed_auth_tokens()
    if has_authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization must use Bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        identity = tokens.get(token.strip())
        if identity is not None:
            role, subject = identity
            return Principal(subject=subject, role=role, authenticated=True)  # type: ignore[arg-type]
        if not settings.auth_jwt_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if len(settings.auth_jwt_secret.encode("utf-8")) < MIN_JWT_SECRET_BYTES:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT authentication is misconfigured",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            claims = jwt.decode(
                token.strip(),
                settings.auth_jwt_secret,
                algorithms=[settings.auth_jwt_algorithm],
                options={"require": ["exp", "sub", "role"]},
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        role = claims.get("role")
        subject = claims.get("sub")
        if role not in {"viewer", "operator"} or not isinstance(subject, str) or not subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid JWT identity claims",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return Principal(subject=subject, role=role, authenticated=True)

    if settings.auth_mode == "required":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Principal(
        subject=settings.default_actor,
        role=settings.default_role,
        authenticated=False,
    )


def get_principal(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    settings: Settings = Depends(get_settings),
) -> Principal:
    return resolve_principal(authorization, settings, x_api_key)


def _record_auth_decision(
    request: Request | None,
    *,
    decision: Literal["allow", "deny"],
    action: str,
    reason: str,
    principal: Principal,
) -> None:
    """Persist allow/deny evidence on the canonical audit chain only."""
    if request is not None and getattr(request.state, "auth_decision_recorded", False):
        return
    try:
        from app.main import state

        state.record_auth_decision(
            decision=decision,
            action=action,
            reason=reason,
            subject=principal.subject,
            role=principal.role,
            authenticated=principal.authenticated,
        )
        if request is not None:
            request.state.auth_decision_recorded = True
    except Exception:
        # Auth decisions must not break the request path if audit append fails.
        pass


def require_action(action: Action):
    """Dependency factory enforcing the explicit action allow-list."""

    def _dependency(
        request: Request,
        principal: Principal = Depends(get_principal),
    ) -> Principal:
        if not action_allowed(action, principal.role):  # type: ignore[arg-type]
            reason = f"Role '{principal.role}' is not permitted for action '{action}'"
            _record_auth_decision(
                request,
                decision="deny",
                action=action,
                reason=reason,
                principal=principal,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=reason,
            )
        # Authenticated allow decisions only — avoids flooding optional demo runs.
        if principal.authenticated:
            _record_auth_decision(
                request,
                decision="allow",
                action=action,
                reason=f"Role '{principal.role}' permitted for action '{action}'",
                principal=principal,
            )
        return principal

    return _dependency


def require_operator(principal: Principal = Depends(require_action("mutate_scenario"))) -> Principal:
    return principal


def require_viewer(principal: Principal = Depends(require_action("query"))) -> Principal:
    return principal
