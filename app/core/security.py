from __future__ import annotations

import base64
import json
import os
import secrets
from dataclasses import dataclass
from typing import Any, Literal
from urllib import parse, request

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core.error_codes import CommonErrorCodes, error_response
from app.core.trace import current_trace_id


AuthMode = Literal["static", "gateway_header", "oidc_jwt", "oauth2_introspection"]


@dataclass(frozen=True, slots=True)
class AuthResult:
    identity: dict[str, Any]
    permissions: dict[str, Any]
    auth_system: str


def auth_mode() -> AuthMode:
    mode = os.getenv("OPEN_PLATFORM_AUTH_MODE", "static").strip().lower()
    if mode in {"static", "gateway_header", "oidc_jwt", "oauth2_introspection"}:
        return mode
    return "static"


def extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    cleaned_token = token.strip()
    return cleaned_token if cleaned_token else None


def configured_tokens() -> set[str]:
    tokens: set[str] = set()
    single_token = os.getenv("OPEN_PLATFORM_TOKEN", "").strip()
    if single_token:
        tokens.add(single_token)

    token_list = os.getenv("OPEN_PLATFORM_TOKENS", "")
    if token_list:
        tokens.update(item.strip() for item in token_list.split(",") if item.strip())
    return tokens


def is_token_valid(authorization: str | None) -> bool:
    request_token = extract_bearer_token(authorization)
    if request_token is None:
        return False

    valid_tokens = configured_tokens()
    if not valid_tokens:
        # 无环境变量 token 时，检查管理面 SQLite 中是否有活跃 token。
        db_tokens = _active_db_token_hashes()
        if not db_tokens:
            if not _db_has_any_token_record():
                # 完全未配置 token：仅强制 Bearer token 存在。
                return True
            # 配置过 token 但全部撤销/过期：拒绝。
            return False
        return _db_token_in_set(request_token, db_tokens)

    if any(secrets.compare_digest(request_token, valid) for valid in valid_tokens):
        return True
    # 环境变量未命中时，回退检查管理面 SQLite token。
    return _db_token_in_set(request_token, _active_db_token_hashes())


def _active_db_token_hashes() -> set[str]:
    """惰性读取管理面 SQLite 活跃 token 哈希集合；模块不可用/异常时返回空集。"""
    try:
        from app.core.admin.token_store import active_token_set

        return active_token_set()
    except Exception:
        return set()


def _db_has_any_token_record() -> bool:
    """管理面 SQLite 是否存在任何 token 记录（含已撤销/过期）。"""
    try:
        from app.core.admin.token_store import has_any_token_record

        return has_any_token_record()
    except Exception:
        return False


def _db_token_in_set(plain_token: str, token_hashes: set[str]) -> bool:
    """明文 token 是否命中 DB 活跃集合；命中时更新 last_used_at。"""
    if not token_hashes:
        return False
    try:
        from app.core.admin.token_store import is_token_in_db

        return is_token_in_db(plain_token)
    except Exception:
        return False


def authenticate_request(request: Request) -> AuthResult | None:
    mode = auth_mode()
    if mode == "static":
        if not is_token_valid(request.headers.get("Authorization")):
            return None
        identity, permissions = _context_from_headers(request)
        return AuthResult(identity=identity, permissions=permissions, auth_system=_resolve_auth_system(request))

    if mode == "gateway_header":
        identity, permissions = _context_from_headers(request)
        user_header = os.getenv("OPEN_PLATFORM_AUTH_HEADER_USER_ID", "X-User-Id")
        if not identity.get("user_id") and request.headers.get(user_header):
            identity["user_id"] = request.headers.get(user_header)
        if not identity.get("user_id"):
            return None

        require_bearer = _truthy(os.getenv("OPEN_PLATFORM_GATEWAY_REQUIRE_BEARER", "false"))
        if require_bearer and not extract_bearer_token(request.headers.get("Authorization")):
            return None
        return AuthResult(identity=identity, permissions=permissions, auth_system=_resolve_auth_system(request))

    if mode == "oidc_jwt":
        token = extract_bearer_token(request.headers.get("Authorization"))
        if token is None:
            return None
        claims = _decode_oidc_claims(token)
        if claims is None:
            return None
        identity, permissions = _context_from_claims(claims)
        return AuthResult(identity=identity, permissions=permissions, auth_system=_resolve_auth_system(request, claims))

    if mode == "oauth2_introspection":
        token = extract_bearer_token(request.headers.get("Authorization"))
        if token is None:
            return None
        claims = _introspect_token(token)
        if claims is None:
            return None
        identity, permissions = _context_from_claims(claims)
        return AuthResult(identity=identity, permissions=permissions, auth_system=_resolve_auth_system(request, claims))

    return None


def build_unauthorized_response(trace_id: str | None = None) -> JSONResponse:
    resolved_trace_id = trace_id or current_trace_id()
    unauthorized_response = JSONResponse(
        status_code=200,
        content=jsonable_encoder(
            {
                **error_response(
                    CommonErrorCodes.UNAUTHORIZED,
                    {"reason": "Authorization token is required or invalid"},
                ),
                "traceId": resolved_trace_id,
            }
        ),
    )
    unauthorized_response.headers.setdefault("X-Request-Id", resolved_trace_id)
    unauthorized_response.headers.setdefault("X-Trace-Id", resolved_trace_id)
    return unauthorized_response


def _context_from_headers(request: Request) -> tuple[dict[str, Any], dict[str, Any]]:
    user_header = os.getenv("OPEN_PLATFORM_AUTH_HEADER_USER_ID", "X-User-Id")
    tenant_header = os.getenv("OPEN_PLATFORM_AUTH_HEADER_TENANT_ID", "X-Tenant-Id")
    roles_header = os.getenv("OPEN_PLATFORM_AUTH_HEADER_ROLES", "X-User-Roles")
    scopes_header = os.getenv("OPEN_PLATFORM_AUTH_HEADER_SCOPES", "X-User-Scopes")
    perms_header = os.getenv("OPEN_PLATFORM_AUTH_HEADER_PERMISSIONS", "X-User-Permissions")
    deny_header = os.getenv("OPEN_PLATFORM_AUTH_HEADER_DENY_PERMISSIONS", "X-User-Deny-Permissions")

    identity = {
        "user_id": request.headers.get(user_header) or "",
        "tenant_id": request.headers.get(tenant_header) or "",
        "roles": _split_csv(request.headers.get(roles_header, "")),
        "scopes": _split_csv(request.headers.get(scopes_header, "")),
    }
    permissions = {
        "roles": identity["roles"],
        "permissions": _split_csv(request.headers.get(perms_header, "")),
        "deny_permissions": _split_csv(request.headers.get(deny_header, "")),
    }
    return identity, permissions


def _context_from_claims(claims: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    user_id_key = os.getenv("OPEN_PLATFORM_AUTH_CLAIM_USER_ID", "sub")
    tenant_key = os.getenv("OPEN_PLATFORM_AUTH_CLAIM_TENANT_ID", "tenant_id")
    roles_key = os.getenv("OPEN_PLATFORM_AUTH_CLAIM_ROLES", "roles")
    scopes_key = os.getenv("OPEN_PLATFORM_AUTH_CLAIM_SCOPES", "scope")
    perms_key = os.getenv("OPEN_PLATFORM_AUTH_CLAIM_PERMISSIONS", "permissions")
    deny_perms_key = os.getenv("OPEN_PLATFORM_AUTH_CLAIM_DENY_PERMISSIONS", "deny_permissions")

    identity = {
        "user_id": str(claims.get(user_id_key, "") or ""),
        "tenant_id": str(claims.get(tenant_key, "") or ""),
        "roles": _as_list(claims.get(roles_key)),
        "scopes": _as_scope_list(claims.get(scopes_key)),
    }
    permissions = {
        "roles": identity["roles"],
        "permissions": _as_list(claims.get(perms_key)),
        "deny_permissions": _as_list(claims.get(deny_perms_key)),
    }
    return identity, permissions


def _decode_oidc_claims(token: str) -> dict[str, Any] | None:
    issuer = os.getenv("OPEN_PLATFORM_OIDC_ISSUER", "").strip()
    audience = os.getenv("OPEN_PLATFORM_OIDC_AUDIENCE", "").strip()
    jwks_url = os.getenv("OPEN_PLATFORM_OIDC_JWKS_URL", "").strip()
    algorithms = _split_csv(os.getenv("OPEN_PLATFORM_OIDC_ALGORITHMS", "RS256")) or ["RS256"]

    if not jwks_url:
        return None

    try:
        import jwt
        from jwt import PyJWKClient

        jwk_client = PyJWKClient(jwks_url)
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        verify_options = {
            "verify_signature": True,
            "verify_aud": bool(audience),
            "verify_iss": bool(issuer),
        }
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=algorithms,
            audience=audience or None,
            issuer=issuer or None,
            options=verify_options,
        )
        return dict(claims)
    except Exception:
        return None


def _introspect_token(token: str) -> dict[str, Any] | None:
    introspection_url = os.getenv("OPEN_PLATFORM_OAUTH2_INTROSPECTION_URL", "").strip()
    client_id = os.getenv("OPEN_PLATFORM_OAUTH2_CLIENT_ID", "").strip()
    client_secret = os.getenv("OPEN_PLATFORM_OAUTH2_CLIENT_SECRET", "").strip()
    timeout_seconds = float(os.getenv("OPEN_PLATFORM_OAUTH2_TIMEOUT_SECONDS", "3"))

    if not introspection_url:
        return None

    body = parse.urlencode({"token": token}).encode("utf-8")
    req = request.Request(introspection_url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if client_id and client_secret:
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {basic}")

    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if not payload.get("active"):
                return None
            return dict(payload)
    except Exception:
        return None


def _resolve_auth_system(request: Request, claims: dict[str, Any] | None = None) -> str:
    from_header = request.headers.get("X-Auth-System")
    if from_header:
        return from_header
    if claims:
        claim_key = os.getenv("OPEN_PLATFORM_AUTH_CLAIM_SYSTEM", "auth_system")
        claim_value = claims.get(claim_key)
        if claim_value:
            return str(claim_value)
    return os.getenv("OPEN_PLATFORM_AUTH_SYSTEM", "default")


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _split_csv(value)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _as_scope_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(" ") if item.strip()]
    return _as_list(value)


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
