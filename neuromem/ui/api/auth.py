"""Service-mode API-key auth middleware + ``/api/users`` routes.

Wiring (in :func:`neuromem.ui.server.create_app`):

* If ``cfg.mode == 'service'``, ``UserManager.configure(SqlUserStore(...))``
  is called once at boot, the middleware is added, and the users router
  is included.
* Otherwise nothing here is mounted — single-user mode keeps its
  fixed user_id from the env var, no auth.

The middleware exempts the wizard endpoints (``/api/config*``,
``/api/health``) so a fresh service-mode boot can still reach the UI to
configure / mint the first key. Once setup is complete, operators
should set ``setup_complete: true`` and protect ``/api/config`` with an
external reverse proxy if they want to lock down config edits.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from neuromem.user import User, UserManager

# Endpoints reachable without an API key. Keep this list tight.
_AUTH_EXEMPT_PREFIXES = (
    "/api/health",
    "/api/config",  # wizard / settings — protect via reverse proxy if needed
    "/docs",
    "/openapi.json",
    "/redoc",
)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Validate ``X-API-Key`` header and attach the user to ``request.state``.

    Static SPA assets (anything not starting with ``/api/``) pass
    through — the SPA itself fetches with the API key from localStorage.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        if any(path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES):
            return await call_next(request)

        # POST /api/users is "soft-exempt" — the route handler decides
        # bootstrap vs auth, but we still parse a key if one is present
        # so authenticated callers (minting users 2..N) attach correctly.
        api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
        is_soft_exempt = path == "/api/users" and request.method == "POST"

        if api_key:
            user = UserManager.get_by_api_key(api_key)
            if user is None and not is_soft_exempt:
                return JSONResponse({"detail": "invalid API key"}, status_code=401)
            if user is not None:
                request.state.user = user
        elif not is_soft_exempt:
            return JSONResponse({"detail": "X-API-Key header required"}, status_code=401)

        return await call_next(request)


def _require_user(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


class CreateUserBody(BaseModel):
    external_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


class UserOut(BaseModel):
    id: str
    external_id: Optional[str]
    metadata: Dict[str, Any]
    created_at: str


def _user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        external_id=u.external_id,
        metadata=u.metadata,
        created_at=u.created_at.isoformat(),
    )


def build_users_router(*, allow_unauthenticated_first_user: bool = True) -> APIRouter:
    """Routes for managing users in service mode.

    ``allow_unauthenticated_first_user``: if ``True`` and the user table
    is empty, ``POST /api/users`` accepts an unauthenticated request.
    This is the bootstrap path for minting the first admin key — once
    one user exists, all subsequent calls require an API key.
    """
    router = APIRouter(prefix="/api/users", tags=["users"])

    @router.post("")
    def create_user(body: CreateUserBody, request: Request) -> Dict[str, Any]:
        existing = UserManager.list_all()
        is_first = len(existing) == 0
        if not (is_first and allow_unauthenticated_first_user):
            _require_user(request)
        user, plain_key = UserManager.create_with_api_key(
            external_id=body.external_id,
            metadata=body.metadata,
        )
        return {
            "user": _user_out(user).model_dump(),
            "api_key": plain_key,
            "warning": "Store this key now — it cannot be retrieved later.",
        }

    @router.get("/me")
    def me(request: Request) -> UserOut:
        return _user_out(_require_user(request))

    @router.get("")
    def list_users(request: Request) -> List[UserOut]:
        _require_user(request)
        return [_user_out(u) for u in UserManager.list_all()]

    @router.delete("/{user_id}")
    def delete_user(user_id: str, request: Request) -> Dict[str, Any]:
        _require_user(request)
        ok = UserManager.delete(user_id)
        if not ok:
            raise HTTPException(status_code=404, detail="user not found")
        return {"ok": True, "id": user_id}

    return router


def configure_user_backend_for_service_mode(database_url: str) -> None:
    """Swap UserManager to SqlUserStore. Idempotent."""
    from neuromem.user_store import SqlUserStore

    UserManager.configure(SqlUserStore(database_url))


__all__ = [
    "APIKeyAuthMiddleware",
    "build_users_router",
    "configure_user_backend_for_service_mode",
]
