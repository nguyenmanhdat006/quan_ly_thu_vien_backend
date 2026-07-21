from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keycloak import KeycloakError, keycloak_client
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserOut, UserSelfUpdate, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("5/minute")
async def register(
    request: Request, payload: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    user = await user_service.create_user(
        db,
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        password=payload.password,
        role="reader",
        phone=payload.phone,
        address=payload.address,
    )

    try:
        token_data = await keycloak_client.login(payload.username, payload.password)
    except KeycloakError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return TokenResponse(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_in=token_data["expires_in"],
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        token_data = await keycloak_client.login(payload.username, payload.password)
    except KeycloakError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=403, detail="Tài khoản chưa được đăng ký trong hệ thống")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản bị khóa")

    return TokenResponse(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_in=token_data["expires_in"],
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        token_data = await keycloak_client.refresh_token(payload.refresh_token)
    except KeycloakError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    import uuid as _uuid

    from jose import jwt as _jwt

    unverified = _jwt.get_unverified_claims(token_data["access_token"])
    keycloak_user_id = _uuid.UUID(unverified["sub"])

    result = await db.execute(select(User).where(User.keycloak_user_id == keycloak_user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản không hợp lệ hoặc đã bị khóa")

    return TokenResponse(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_in=token_data["expires_in"],
        user=UserOut.model_validate(user),
    )


@router.post("/logout", status_code=204)
async def logout(payload: LogoutRequest, current_user: User = Depends(get_current_user)) -> None:
    await keycloak_client.logout(payload.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UserSelfUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await user_service.update_user(
        db,
        current_user.id,
        UserUpdate(full_name=payload.full_name, phone=payload.phone, address=payload.address),
    )
    return UserOut.model_validate(user)
