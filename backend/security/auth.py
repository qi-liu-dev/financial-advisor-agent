from __future__ import annotations

import base64
import binascii
import json
import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from backend.config import Settings, get_settings


_bearer = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True, slots=True)
class Principal:
    principal_id: str
    display_name: str | None
    roles: frozenset[str]
    auth_source: str

    def has_role(self, *roles: str) -> bool:
        return "admin" in self.roles or bool(self.roles.intersection(roles))


def get_current_principal(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Security(_bearer),
    api_key: str | None = Security(_api_key_header),
) -> Principal:
    settings: Settings = getattr(request.app.state, "settings", get_settings())

    if settings.auth_mode == "disabled":
        return Principal(
            principal_id=settings.dev_principal_id,
            display_name="Local development principal",
            roles=frozenset(settings.dev_principal_roles),
            auth_source="disabled",
        )

    if settings.auth_mode == "api_key":
        supplied = api_key
        if supplied is None and bearer and bearer.scheme.lower() == "bearer":
            supplied = bearer.credentials
        if not supplied:
            raise _authentication_error("Missing API credential.")
        principal = _principal_from_api_key(supplied, settings)
        if principal is None:
            raise _authentication_error("Invalid API credential.")
        return principal

    if settings.auth_mode == "azure_easy_auth":
        principal = _principal_from_azure_headers(request)
        if principal is None:
            raise _authentication_error("Azure authenticated principal is missing.")
        return principal

    raise _authentication_error("Unsupported authentication mode.")


def require_admin(principal: Principal = Security(get_current_principal)) -> Principal:
    if not principal.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "forbidden",
                "message": "Administrator access is required.",
            },
        )
    return principal


def require_advisor(principal: Principal = Security(get_current_principal)) -> Principal:
    if not principal.has_role("advisor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "forbidden",
                "message": "Advisor access is required.",
            },
        )
    return principal


def ensure_advisor_access(principal: Principal, advisor_id: str) -> None:
    if principal.has_role("admin") or principal.principal_id == advisor_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "forbidden",
            "message": "You cannot access another advisor's data.",
        },
    )


def ensure_owner_access(principal: Principal, owner_id: str) -> None:
    if principal.has_role("admin") or principal.principal_id == owner_id:
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found", "message": "Resource not found."},
    )


def _principal_from_api_key(key: str, settings: Settings) -> Principal | None:
    try:
        registry = json.loads(settings.api_keys_json or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("API_KEYS_JSON is not valid JSON.") from exc
    if not isinstance(registry, dict):
        raise RuntimeError("API_KEYS_JSON must be a JSON object keyed by API key.")

    matched: Any | None = None
    for configured_key, definition in registry.items():
        if isinstance(configured_key, str) and secrets.compare_digest(key, configured_key):
            matched = definition
            break
    if matched is None:
        return None

    if isinstance(matched, str):
        return Principal(
            principal_id=matched,
            display_name=None,
            roles=frozenset({"advisor"}),
            auth_source="api_key",
        )
    if not isinstance(matched, dict):
        raise RuntimeError("Each API_KEYS_JSON value must be a string or object.")

    principal_id = str(matched.get("principal_id", "")).strip()
    if not principal_id:
        raise RuntimeError("Each API key entry requires principal_id.")
    roles_value = matched.get("roles", ["advisor"])
    if not isinstance(roles_value, list):
        raise RuntimeError("API key roles must be a JSON array.")
    roles = frozenset(str(role).strip().lower() for role in roles_value if str(role).strip())
    return Principal(
        principal_id=principal_id,
        display_name=_optional_string(matched.get("display_name")),
        roles=roles or frozenset({"advisor"}),
        auth_source="api_key",
    )


def _principal_from_azure_headers(request: Request) -> Principal | None:
    encoded = request.headers.get("x-ms-client-principal")
    principal_id = request.headers.get("x-ms-client-principal-id")
    display_name = request.headers.get("x-ms-client-principal-name")
    roles: set[str] = set()

    if encoded:
        try:
            padding = "=" * (-len(encoded) % 4)
            payload = json.loads(base64.b64decode(encoded + padding).decode("utf-8"))
        except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
            raise _authentication_error("Malformed Azure client principal header.")

        principal_id = principal_id or _optional_string(
            payload.get("userId") or payload.get("user_id")
        )
        display_name = display_name or _optional_string(
            payload.get("userDetails") or payload.get("name")
        )
        for role in payload.get("userRoles", []) or []:
            if isinstance(role, str) and role.strip():
                roles.add(role.strip().lower())
        for claim in payload.get("claims", []) or []:
            if not isinstance(claim, dict):
                continue
            claim_type = str(claim.get("typ") or claim.get("type") or "").lower()
            claim_value = _optional_string(claim.get("val") or claim.get("value"))
            if not claim_value:
                continue
            if claim_type.endswith("/name") or claim_type in {"name", "preferred_username"}:
                display_name = display_name or claim_value
            if claim_type.endswith("/nameidentifier") or claim_type in {
                "oid",
                "sub",
                "nameidentifier",
            }:
                principal_id = principal_id or claim_value
            if claim_type.endswith("/role") or claim_type in {"role", "roles"}:
                roles.add(claim_value.lower())

    if not principal_id:
        return None
    return Principal(
        principal_id=principal_id,
        display_name=display_name,
        roles=frozenset(roles or {"advisor"}),
        auth_source="azure_easy_auth",
    )


def _authentication_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
        detail={"code": "unauthorized", "message": message},
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
