import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.author import Author
from app.schemas.author import AuthorCreate, AuthorUpdate


async def list_authors(db: AsyncSession) -> list[Author]:
    result = await db.execute(select(Author).order_by(Author.name))
    return list(result.scalars().all())


async def get_author_or_404(db: AsyncSession, author_id: uuid.UUID) -> Author:
    author = await db.get(Author, author_id)
    if author is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác giả")
    return author


async def create_author(db: AsyncSession, payload: AuthorCreate) -> Author:
    author = Author(name=payload.name, bio=payload.bio)
    db.add(author)
    await db.commit()
    await db.refresh(author)
    return author


async def update_author(db: AsyncSession, author_id: uuid.UUID, payload: AuthorUpdate) -> Author:
    author = await get_author_or_404(db, author_id)
    if payload.name is not None:
        author.name = payload.name
    if payload.bio is not None:
        author.bio = payload.bio
    await db.commit()
    await db.refresh(author)
    return author


async def delete_author(db: AsyncSession, author_id: uuid.UUID) -> None:
    author = await get_author_or_404(db, author_id)
    await db.delete(author)
    await db.commit()
