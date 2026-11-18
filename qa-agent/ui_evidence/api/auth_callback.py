from __future__ import annotations

import base64
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from fastapi import (
    APIRouter,
    Cookie,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from pydantic import BaseModel

from ui_evidence.api.portal_access import (
    QA_PORTAL_ACCESS_ROLES,
    authorize_portal_access,
    parse_email_allowlist,
)
from ui_evidence.config import settings

logger = logging.getLogger("am-ui-test-agent.auth")

router = APIRouter(tags=["Authentication"])


def _authorize_qa_user(email: str | None, token_roles: list[str]) -> list[str]:
    try:
        return authorize_portal_access(
            email=email,
            token_roles=token_roles,
            required_roles=QA_PORTAL_ACCESS_ROLES,
            email_allowlist=parse_email_allowlist(settings.QA_PORTAL_ALLOWED_EMAILS),
            session_roles_on_allowlist=["access-qa-portal", "qa_operator"],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


class CallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None
    code_verifier: Optional[str] = None
    redirect_uri: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None


class CallbackResponse(BaseModel):
    success: bool
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    state: Optional[str] = None
    user: dict[str, Any]


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode JWT payload without verifying signature (signature verified by Keycloak)."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            # Opaque direct tokens are not JWTs — caller must use stored user session.
            return {}
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded)
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        logger.warning("Failed to decode JWT payload: %s", exc)
        return {}


def _exchange_code_with_keycloak(
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict[str, Any]:
    token_endpoint = f"{settings.KEYCLOAK_URL.rstrip('/')}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
    if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", code_verifier):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PKCE verifier",
        )

    form_data = {
        "grant_type": "authorization_code",
        "client_id": settings.KEYCLOAK_QA_CLIENT_ID,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }

    encoded_data = urllib.parse.urlencode(form_data).encode("utf-8")
    req = urllib.request.Request(
        token_endpoint,
        data=encoded_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (AM-QA-Portal/1.0)",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        logger.error("Keycloak token exchange error (%s): %s", exc.code, err_body)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Keycloak code exchange failed: {err_body}",
        ) from exc
    except Exception as exc:
        logger.error("Network error during Keycloak token exchange: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to communicate with Keycloak: {exc}",
        ) from exc


@router.get("/config")
async def get_auth_config() -> dict[str, Any]:
    """Provides public OIDC configuration for the QA Portal UI."""
    redirect_uri = settings.KEYCLOAK_QA_REDIRECT_URI
    login_url = (
        f"{settings.CENTRAL_LOGIN_URL.rstrip('/')}"
        f"?client_id={urllib.parse.quote(settings.KEYCLOAK_QA_CLIENT_ID)}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&response_type=code"
        f"&scope={urllib.parse.quote('openid profile email')}"
    )
    return {
        "client_id": settings.KEYCLOAK_QA_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "issuer": settings.KEYCLOAK_ISSUER,
        "login_url": login_url,
        "central_login_url": settings.CENTRAL_LOGIN_URL,
    }


class CentralSessionRequest(BaseModel):
    access_token: Optional[str] = None
    token: Optional[str] = None
    state: Optional[str] = None


@router.post("/central-session", response_model=CallbackResponse)
async def central_session(
    request: CentralSessionRequest,
    response: Response,
) -> CallbackResponse:
    """Open a QA portal session from an AM Central (Modern UI) access token."""
    import time

    access_token = (request.access_token or request.token or "").strip()
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing AM access token",
        )

    safe_state = "/"
    if (
        request.state
        and request.state.startswith("/")
        and not request.state.startswith("//")
    ):
        safe_state = request.state

    claims = _decode_jwt_payload(access_token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid AM access token",
        )

    trusted = {
        settings.KEYCLOAK_ISSUER,
        settings.KEYCLOAK_CENTRAL_ISSUER,
        "https://auth.asrax.in/realms/am-dev-realm",
        "https://auth.asrax.in/realms/am-qa-agents-dev",
    }
    if claims.get("iss") not in trusted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Untrusted token issuer",
        )

    exp = claims.get("exp")
    if isinstance(exp, (int, float)) and exp < time.time():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AM access token expired",
        )

    roles = _authorize_qa_user(
        claims.get("email"),
        list(claims.get("realm_access", {}).get("roles", []) or []),
    )
    user_info = {
        "sub": claims.get("sub"),
        "username": claims.get("preferred_username")
        or claims.get("email")
        or "qa_user",
        "email": claims.get("email"),
        "name": claims.get("name"),
        "roles": roles,
    }
    expires_in = (
        max(0, int(exp - time.time())) if isinstance(exp, (int, float)) else 3600
    )
    response.set_cookie(
        key="qa_session",
        value=access_token,
        httponly=True,
        secure=settings.KEYCLOAK_QA_REDIRECT_URI.startswith("https://"),
        samesite="lax",
        path="/",
        max_age=expires_in,
    )
    return CallbackResponse(
        success=True,
        access_token=access_token,
        token_type="Bearer",
        expires_in=expires_in,
        state=safe_state,
        user=user_info,
    )


@router.post("/callback", response_model=CallbackResponse)
async def auth_callback(
    request: CallbackRequest,
    response: Response,
) -> CallbackResponse:
    """Exchange authorization code from Keycloak for an access token."""
    configured_redirect = settings.KEYCLOAK_QA_REDIRECT_URI
    allowed_redirects = {
        configured_redirect,
        "http://localhost:8151/callback",
        "http://127.0.0.1:8151/callback",
        "https://am-dev.asrax.in/qa/ui/callback",
    }
    redirect_uri = (
        request.redirect_uri
        if request.redirect_uri and request.redirect_uri in allowed_redirects
        else configured_redirect
    )

    # Validate state parameter for safe redirection (prevent open redirect attacks)
    safe_state = "/"
    if (
        request.state
        and request.state.startswith("/")
        and not request.state.startswith("//")
    ):
        safe_state = request.state

    if not request.code_verifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing PKCE verifier",
        )
    token_data = _exchange_code_with_keycloak(
        request.code, redirect_uri, request.code_verifier
    )
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token response did not contain access_token",
        )

    claims = _decode_jwt_payload(access_token)
    roles = _authorize_qa_user(
        claims.get("email"),
        list(claims.get("realm_access", {}).get("roles", []) or []),
    )

    user_info = {
        "sub": claims.get("sub"),
        "username": claims.get("preferred_username")
        or claims.get("email")
        or "qa_user",
        "email": claims.get("email"),
        "name": claims.get("name"),
        "roles": roles,
    }

    # Set secure session cookie
    response.set_cookie(
        key="qa_session",
        value=access_token,
        httponly=True,
        secure=settings.KEYCLOAK_QA_REDIRECT_URI.startswith("https://"),
        samesite="lax",
        path="/",
        max_age=token_data.get("expires_in", 3600),
    )

    return CallbackResponse(
        success=True,
        access_token=access_token,
        token_type=token_data.get("token_type", "Bearer"),
        expires_in=token_data.get("expires_in", 3600),
        state=safe_state,
        user=user_info,
    )


@router.get("/callback")
async def auth_callback_get():
    """Reject legacy GET callbacks, which cannot provide a PKCE verifier."""
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Complete QA sign-in through the portal callback with PKCE.",
    )


@router.get("/me")
async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    qa_session: Optional[str] = Cookie(None),
    token: Optional[str] = Query(None, description="Direct access token fallback"),
) -> dict[str, Any]:
    """Retrieve currently authenticated user profile from token or cookie."""
    jwt_token = None
    if authorization and authorization.lower().startswith("bearer "):
        jwt_token = authorization.split(" ", 1)[1].strip()
    elif qa_session:
        jwt_token = qa_session
    elif request.cookies.get("qa_session"):
        jwt_token = request.cookies.get("qa_session")
    elif token:
        jwt_token = token

    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide 'qa_session' cookie, 'Authorization: Bearer <token>', or '?token=<token>' query parameter.",
        )

    claims = _decode_jwt_payload(jwt_token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
        )

    return {
        "authenticated": True,
        "sub": claims.get("sub"),
        "username": claims.get("preferred_username") or claims.get("email"),
        "email": claims.get("email"),
        "name": claims.get("name"),
        "roles": claims.get("realm_access", {}).get("roles", []),
    }
