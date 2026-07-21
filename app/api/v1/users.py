import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import Page
from app.schemas.user import ResetPasswordRequest, UserCreate, UserOut, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserOut])
async def list_users(
    role: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> Page[UserOut]:
    if current_user.role == "librarian":
        role = "reader"

    items, total = await user_service.list_users(db, role=role, search=search, page=page, size=size)
    return Page(items=[UserOut.model_validate(u) for u in items], total=total, page=page, size=size)


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    if current_user.role == "librarian" and payload.role != "reader":
        raise HTTPException(status_code=403, detail="Thủ thư chỉ được tạo tài khoản độc giả")

    user = await user_service.create_user(
        db,
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        password=payload.password,
        role=payload.role,
        phone=payload.phone,
        address=payload.address,
    )
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await user_service.get_user_or_404(db, user_id)
    if current_user.role == "librarian" and user.role != "reader":
        raise HTTPException(status_code=403, detail="Không có quyền xem tài khoản này")
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    # Librarian chỉ được quản lý (sửa hồ sơ, khóa/mở khóa) tài khoản độc giả,
    # và không được đổi vai trò — chỉ Admin mới có quyền đổi role (mục 3.5, 5.2).
    if current_user.role == "librarian":
        if payload.role is not None:
            raise HTTPException(status_code=403, detail="Chỉ Admin mới có quyền đổi vai trò")
        target = await user_service.get_user_or_404(db, user_id)
        if target.role != "reader":
            raise HTTPException(status_code=403, detail="Thủ thư chỉ được quản lý tài khoản độc giả")

    user = await user_service.update_user(db, user_id, payload)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await user_service.soft_delete_user(db, user_id)


@router.post("/{user_id}/reset-password", status_code=204)
async def reset_password(
    user_id: uuid.UUID,
    payload: ResetPasswordRequest,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await user_service.reset_password(db, user_id, payload.new_password)
