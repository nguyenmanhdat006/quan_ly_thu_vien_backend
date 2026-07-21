import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate


async def list_categories(db: AsyncSession) -> list[Category]:
    result = await db.execute(select(Category).order_by(Category.name))
    return list(result.scalars().all())


async def get_category_or_404(db: AsyncSession, category_id: uuid.UUID) -> Category:
    category = await db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thể loại")
    return category


async def create_category(db: AsyncSession, payload: CategoryCreate) -> Category:
    category = Category(name=payload.name, description=payload.description)
    db.add(category)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Tên thể loại đã tồn tại") from exc
    await db.refresh(category)
    return category


async def update_category(db: AsyncSession, category_id: uuid.UUID, payload: CategoryUpdate) -> Category:
    category = await get_category_or_404(db, category_id)
    if payload.name is not None:
        category.name = payload.name
    if payload.description is not None:
        category.description = payload.description
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Tên thể loại đã tồn tại") from exc
    await db.refresh(category)
    return category


async def delete_category(db: AsyncSession, category_id: uuid.UUID) -> None:
    category = await get_category_or_404(db, category_id)
    try:
        await db.delete(category)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Không thể xóa thể loại đang có sách") from exc
