import time
import uuid

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JOSEError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.keycloak import keycloak_client
from app.db.session import get_db
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)

_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL_SECONDS = 300


async def _get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    now = time.time()
    if _jwks_cache is not None and now - _jwks_fetched_at < _JWKS_TTL_SECONDS:
        return _jwks_cache

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(keycloak_client.jwks_uri)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Không lấy được khóa xác thực từ Keycloak")

    _jwks_cache = resp.json()
    _jwks_fetched_at = now
    return _jwks_cache


async def _decode_token(token: str) -> dict:
    jwks = await _get_jwks()
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JOSEError as exc:
        raise HTTPException(status_code=401, detail="Token không hợp lệ") from exc

    key = next((k for k in jwks.get("keys", []) if k.get("kid") == unverified_header.get("kid")), None)
    if key is None:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=[key.get("alg", "RS256")],
            options={"verify_aud": False},
            issuer=settings.keycloak_issuer_candidates,
        )
    except JOSEError as exc:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn") from exc

    if payload.get("azp") != settings.KEYCLOAK_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")

    return payload


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiếu thông tin xác thực",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = await _decode_token(credentials.credentials)
    sub = payload.get("sub")
    try:
        keycloak_user_id = uuid.UUID(sub)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Token không hợp lệ") from exc

    result = await db.execute(select(User).where(User.keycloak_user_id == keycloak_user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="Tài khoản không tồn tại trong hệ thống")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")

    return user


def require_roles(*roles: str):
    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Bạn không có quyền thực hiện thao tác này")
        return current_user

    return _checker
