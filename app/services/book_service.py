import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, BookAuthor
from app.models.borrow import BorrowRecordItem
from app.schemas.book import BookCreate, BookUpdate


async def list_books(
    db: AsyncSession,
    *,
    search: str | None,
    category_id: uuid.UUID | None,
    author_id: uuid.UUID | None,
    page: int,
    size: int,
) -> tuple[list[dict], int]:
    stmt = select(Book)
    count_stmt = select(func.count(func.distinct(Book.id))).select_from(Book)

    if author_id:
        stmt = stmt.join(BookAuthor, BookAuthor.book_id == Book.id).where(BookAuthor.author_id == author_id)
        count_stmt = count_stmt.join(BookAuthor, BookAuthor.book_id == Book.id).where(
            BookAuthor.author_id == author_id
        )
    if category_id:
        stmt = stmt.where(Book.category_id == category_id)
        count_stmt = count_stmt.where(Book.category_id == category_id)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Book.title.ilike(pattern))
        count_stmt = count_stmt.where(Book.title.ilike(pattern))

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Book.title).offset((page - 1) * size).limit(size).distinct()
    books = (await db.execute(stmt)).scalars().unique().all()
    return [await _serialize_book(db, b) for b in books], total


async def _serialize_book(db: AsyncSession, book: Book) -> dict:
    from app.models.author import Author
    from app.models.category import Category

    category = await db.get(Category, book.category_id)
    author_rows = await db.execute(
        select(Author).join(BookAuthor, BookAuthor.author_id == Author.id).where(BookAuthor.book_id == book.id)
    )
    authors = author_rows.scalars().all()
    return {
        "id": book.id,
        "title": book.title,
        "isbn": book.isbn,
        "category_id": book.category_id,
        "category": category,
        "publisher": book.publisher,
        "publish_year": book.publish_year,
        "description": book.description,
        "quantity_total": book.quantity_total,
        "quantity_available": book.quantity_available,
        "authors": list(authors),
        "created_at": book.created_at,
    }


async def get_book_or_404(db: AsyncSession, book_id: uuid.UUID) -> Book:
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")
    return book


async def get_book_out_or_404(db: AsyncSession, book_id: uuid.UUID) -> dict:
    book = await get_book_or_404(db, book_id)
    return await _serialize_book(db, book)


async def create_book(db: AsyncSession, payload: BookCreate) -> dict:
    book = Book(
        title=payload.title,
        isbn=payload.isbn,
        category_id=payload.category_id,
        publisher=payload.publisher,
        publish_year=payload.publish_year,
        description=payload.description,
        quantity_total=payload.quantity_total,
        quantity_available=payload.quantity_total,
    )
    db.add(book)
    try:
        await db.flush()
        for author_id in payload.author_ids:
            db.add(BookAuthor(book_id=book.id, author_id=author_id))
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="ISBN đã tồn tại hoặc dữ liệu không hợp lệ") from exc
    await db.refresh(book)
    return await _serialize_book(db, book)


async def update_book(db: AsyncSession, book_id: uuid.UUID, payload: BookUpdate) -> dict:
    book = await get_book_or_404(db, book_id)

    if payload.quantity_total is not None:
        borrowed = book.quantity_total - book.quantity_available
        if payload.quantity_total < borrowed:
            raise HTTPException(
                status_code=400,
                detail=f"Không thể giảm tổng số lượng xuống dưới số đang được mượn ({borrowed})",
            )
        delta = payload.quantity_total - book.quantity_total
        book.quantity_total = payload.quantity_total
        book.quantity_available = book.quantity_available + delta

    if payload.title is not None:
        book.title = payload.title
    if payload.isbn is not None:
        book.isbn = payload.isbn
    if payload.category_id is not None:
        book.category_id = payload.category_id
    if payload.publisher is not None:
        book.publisher = payload.publisher
    if payload.publish_year is not None:
        book.publish_year = payload.publish_year
    if payload.description is not None:
        book.description = payload.description

    if payload.author_ids is not None:
        await db.execute(BookAuthor.__table__.delete().where(BookAuthor.book_id == book.id))
        for author_id in payload.author_ids:
            db.add(BookAuthor(book_id=book.id, author_id=author_id))

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="ISBN đã tồn tại hoặc dữ liệu không hợp lệ") from exc
    await db.refresh(book)
    return await _serialize_book(db, book)


async def delete_book(db: AsyncSession, book_id: uuid.UUID) -> None:
    book = await get_book_or_404(db, book_id)
    borrowing_count = (
        await db.execute(
            select(func.count())
            .select_from(BorrowRecordItem)
            .where(BorrowRecordItem.book_id == book_id, BorrowRecordItem.status == "borrowing")
        )
    ).scalar_one()
    if borrowing_count > 0:
        raise HTTPException(status_code=400, detail="Không thể xóa sách đang được mượn")

    try:
        await db.delete(book)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Không thể xóa sách đã có lịch sử mượn") from exc
