import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
async def list_categories(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[CategoryOut]:
    items = await category_service.list_categories(db)
    return [CategoryOut.model_validate(i) for i in items]


@router.post("", response_model=CategoryOut, status_code=201)
async def create_category(
    payload: CategoryCreate,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> CategoryOut:
    item = await category_service.create_category(db, payload)
    return CategoryOut.model_validate(item)


@router.patch("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> CategoryOut:
    item = await category_service.update_category(db, category_id, payload)
    return CategoryOut.model_validate(item)


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: uuid.UUID,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await category_service.delete_category(db, category_id)
