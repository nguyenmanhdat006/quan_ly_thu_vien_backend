from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.borrow import BorrowRecord, BorrowRecordItem
from app.models.user import User
from app.schemas.report import OverdueReaderReport, SummaryReport, TopBookReport


async def get_summary(db: AsyncSession) -> SummaryReport:
    total_books = (await db.execute(select(func.count()).select_from(Book))).scalar_one()
    total_copies = (await db.execute(select(func.coalesce(func.sum(Book.quantity_total), 0)))).scalar_one()
    total_borrowing = (
        await db.execute(
            select(func.count()).select_from(BorrowRecordItem).where(BorrowRecordItem.status == "borrowing")
        )
    ).scalar_one()
    total_overdue = (
        await db.execute(
            select(func.count())
            .select_from(BorrowRecord)
            .where(BorrowRecord.status != "returned", BorrowRecord.due_date < date.today())
        )
    ).scalar_one()
    total_readers = (
        await db.execute(select(func.count()).select_from(User).where(User.role == "reader"))
    ).scalar_one()

    return SummaryReport(
        total_books=total_books,
        total_book_copies=int(total_copies),
        total_borrowing=total_borrowing,
        total_overdue=total_overdue,
        total_readers=total_readers,
    )


async def get_top_books(db: AsyncSession, limit: int = 10) -> list[TopBookReport]:
    stmt = (
        select(Book.id, Book.title, func.sum(BorrowRecordItem.quantity).label("total_borrows"))
        .join(BorrowRecordItem, BorrowRecordItem.book_id == Book.id)
        .group_by(Book.id, Book.title)
        .order_by(func.sum(BorrowRecordItem.quantity).desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [TopBookReport(book_id=str(r.id), title=r.title, total_borrows=int(r.total_borrows)) for r in rows]


async def get_overdue_readers(db: AsyncSession) -> list[OverdueReaderReport]:
    stmt = (
        select(BorrowRecord.code, User.id, User.full_name, BorrowRecord.due_date)
        .join(User, User.id == BorrowRecord.reader_id)
        .where(BorrowRecord.status != "returned", BorrowRecord.due_date < date.today())
        .order_by(BorrowRecord.due_date)
    )
    rows = (await db.execute(stmt)).all()
    today = date.today()
    return [
        OverdueReaderReport(
            record_code=r.code,
            reader_id=str(r.id),
            reader_name=r.full_name,
            due_date=r.due_date,
            days_overdue=(today - r.due_date).days,
        )
        for r in rows
    ]
