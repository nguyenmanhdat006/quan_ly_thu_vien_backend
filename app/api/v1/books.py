import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.book import BookCreate, BookOut, BookUpdate
from app.schemas.common import Page
from app.services import book_service

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=Page[BookOut])
async def list_books(
    search: str | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    author_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Page[BookOut]:
    items, total = await book_service.list_books(
        db, search=search, category_id=category_id, author_id=author_id, page=page, size=size
    )
    return Page(items=[BookOut.model_validate(i) for i in items], total=total, page=page, size=size)


@router.post("", response_model=BookOut, status_code=201)
async def create_book(
    payload: BookCreate,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> BookOut:
    item = await book_service.create_book(db, payload)
    return BookOut.model_validate(item)


@router.get("/{book_id}", response_model=BookOut)
async def get_book(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BookOut:
    item = await book_service.get_book_out_or_404(db, book_id)
    return BookOut.model_validate(item)


@router.patch("/{book_id}", response_model=BookOut)
async def update_book(
    book_id: uuid.UUID,
    payload: BookUpdate,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> BookOut:
    item = await book_service.update_book(db, book_id, payload)
    return BookOut.model_validate(item)


@router.delete("/{book_id}", status_code=204)
async def delete_book(
    book_id: uuid.UUID,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await book_service.delete_book(db, book_id)
