import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keycloak import KeycloakError, keycloak_client
from app.models.user import User
from app.schemas.user import UserUpdate


async def list_users(
    db: AsyncSession, *, role: str | None, search: str | None, page: int, size: int
) -> tuple[list[User], int]:
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    if role:
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)
    if search:
        pattern = f"%{search}%"
        cond = (User.full_name.ilike(pattern)) | (User.username.ilike(pattern)) | (User.email.ilike(pattern))
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size)
    items = (await db.execute(stmt)).scalars().all()
    return list(items), total


async def get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    return user


async def create_user(
    db: AsyncSession,
    *,
    username: str,
    email: str,
    full_name: str,
    password: str,
    role: str,
    phone: str | None = None,
    address: str | None = None,
) -> User:
    try:
        keycloak_user_id = await keycloak_client.create_user(
            username=username,
            email=email,
            full_name=full_name,
            password=password,
            role=role,
        )
    except KeycloakError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    user = User(
        keycloak_user_id=keycloak_user_id,
        username=username,
        email=email,
        full_name=full_name,
        phone=phone,
        address=address,
        role=role,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        await keycloak_client.delete_user(keycloak_user_id)
        raise HTTPException(status_code=409, detail="Tên đăng nhập hoặc email đã tồn tại") from exc
    except Exception:
        await db.rollback()
        await keycloak_client.delete_user(keycloak_user_id)
        raise

    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user_id: uuid.UUID, payload: UserUpdate) -> User:
    user = await get_user_or_404(db, user_id)
    old_role = user.role

    if payload.email is not None:
        user.email = payload.email
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.address is not None:
        user.address = payload.address
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email đã được sử dụng") from exc

    try:
        if payload.email is not None or payload.full_name is not None:
            await keycloak_client.update_profile(
                user.keycloak_user_id, email=payload.email, full_name=payload.full_name
            )
        if payload.role is not None and payload.role != old_role:
            await keycloak_client.update_realm_role(user.keycloak_user_id, old_role, payload.role)
        if payload.is_active is not None:
            await keycloak_client.set_enabled(user.keycloak_user_id, payload.is_active)
    except KeycloakError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    await db.refresh(user)
    return user


async def soft_delete_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    user = await get_user_or_404(db, user_id)
    user.is_active = False
    await db.commit()
    try:
        await keycloak_client.set_enabled(user.keycloak_user_id, False)
    except KeycloakError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


async def reset_password(db: AsyncSession, user_id: uuid.UUID, new_password: str) -> None:
    user = await get_user_or_404(db, user_id)
    try:
        await keycloak_client.reset_password(user.keycloak_user_id, new_password)
    except KeycloakError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
