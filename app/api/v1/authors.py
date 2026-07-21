import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.author import AuthorCreate, AuthorOut, AuthorUpdate
from app.services import author_service

router = APIRouter(prefix="/authors", tags=["authors"])


@router.get("", response_model=list[AuthorOut])
async def list_authors(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[AuthorOut]:
    items = await author_service.list_authors(db)
    return [AuthorOut.model_validate(i) for i in items]


@router.post("", response_model=AuthorOut, status_code=201)
async def create_author(
    payload: AuthorCreate,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> AuthorOut:
    item = await author_service.create_author(db, payload)
    return AuthorOut.model_validate(item)


@router.patch("/{author_id}", response_model=AuthorOut)
async def update_author(
    author_id: uuid.UUID,
    payload: AuthorUpdate,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> AuthorOut:
    item = await author_service.update_author(db, author_id, payload)
    return AuthorOut.model_validate(item)


@router.delete("/{author_id}", status_code=204)
async def delete_author(
    author_id: uuid.UUID,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await author_service.delete_author(db, author_id)
