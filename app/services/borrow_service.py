import random
import uuid
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import Book
from app.models.borrow import BorrowRecord, BorrowRecordItem
from app.models.user import User
from app.schemas.borrow import BorrowCreate, FinePreviewItem, FinePreviewOut


async def _generate_code(db: AsyncSession, today: date) -> str:
    prefix = f"BR-{today.strftime('%Y%m%d')}"
    for _ in range(10):
        suffix = f"{random.randint(0, 9999):04d}"
        code = f"{prefix}-{suffix}"
        exists = (
            await db.execute(select(func.count()).select_from(BorrowRecord).where(BorrowRecord.code == code))
        ).scalar_one()
        if exists == 0:
            return code
    raise HTTPException(status_code=500, detail="Không sinh được mã phiếu mượn, vui lòng thử lại")


async def create_borrow(db: AsyncSession, librarian_id: uuid.UUID, payload: BorrowCreate) -> BorrowRecord:
    reader = await db.get(User, payload.reader_id)
    if reader is None or reader.role != "reader" or not reader.is_active:
        raise HTTPException(status_code=400, detail="Độc giả không hợp lệ hoặc đã bị khóa")

    today = date.today()
    if payload.due_date < today:
        raise HTTPException(status_code=400, detail="Hạn trả không được ở trong quá khứ")

    # Gộp số lượng nếu client gửi trùng book_id
    merged: dict[uuid.UUID, int] = {}
    for item in payload.items:
        merged[item.book_id] = merged.get(item.book_id, 0) + item.quantity

    shortages: list[str] = []
    books: dict[uuid.UUID, Book] = {}
    for book_id, qty in merged.items():
        # SELECT ... FOR UPDATE để khóa dòng, chống race condition khi 2 thủ thư
        # cùng lập phiếu mượn cùng lúc.
        result = await db.execute(select(Book).where(Book.id == book_id).with_for_update())
        book = result.scalar_one_or_none()
        if book is None:
            shortages.append(f"Không tìm thấy sách (id={book_id})")
            continue
        if book.quantity_available < qty:
            shortages.append(f"'{book.title}' chỉ còn {book.quantity_available} cuốn, yêu cầu {qty}")
            continue
        books[book_id] = book

    if shortages:
        raise HTTPException(status_code=400, detail="; ".join(shortages))

    code = await _generate_code(db, today)
    record = BorrowRecord(
        code=code,
        reader_id=payload.reader_id,
        librarian_id=librarian_id,
        borrow_date=today,
        due_date=payload.due_date,
        status="borrowing",
        note=payload.note,
    )
    db.add(record)
    await db.flush()

    for book_id, qty in merged.items():
        books[book_id].quantity_available -= qty
        db.add(
            BorrowRecordItem(
                borrow_record_id=record.id,
                book_id=book_id,
                quantity=qty,
                status="borrowing",
            )
        )

    await db.commit()
    await db.refresh(record)
    return record


async def get_record_or_404(db: AsyncSession, record_id: uuid.UUID) -> BorrowRecord:
    record = await db.get(BorrowRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu mượn")
    return record


async def get_items(db: AsyncSession, record_id: uuid.UUID) -> list[BorrowRecordItem]:
    result = await db.execute(select(BorrowRecordItem).where(BorrowRecordItem.borrow_record_id == record_id))
    return list(result.scalars().all())


def compute_fine(due_date: date, returned_at: date, quantity: int) -> Decimal:
    days_overdue = max(0, (returned_at - due_date).days)
    return Decimal(days_overdue) * Decimal(settings.FINE_PER_DAY) * Decimal(quantity)


async def preview_fine(db: AsyncSession, record_id: uuid.UUID) -> FinePreviewOut:
    record = await get_record_or_404(db, record_id)
    items = await get_items(db, record_id)
    today = date.today()

    preview_items: list[FinePreviewItem] = []
    total = Decimal(0)
    for item in items:
        if item.status != "borrowing":
            continue
        days_overdue = max(0, (today - record.due_date).days)
        fine = Decimal(days_overdue) * Decimal(settings.FINE_PER_DAY) * Decimal(item.quantity)
        preview_items.append(
            FinePreviewItem(item_id=item.id, book_id=item.book_id, days_overdue=days_overdue, fine_amount=fine)
        )
        total += fine

    return FinePreviewOut(items=preview_items, total_fine=total)


async def return_items(db: AsyncSession, record_id: uuid.UUID, item_ids: list[uuid.UUID]) -> BorrowRecord:
    record = await get_record_or_404(db, record_id)
    today = date.today()

    result = await db.execute(
        select(BorrowRecordItem).where(BorrowRecordItem.borrow_record_id == record_id).with_for_update()
    )
    items_by_id = {i.id: i for i in result.scalars().all()}

    missing = [str(iid) for iid in item_ids if iid not in items_by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy chi tiết phiếu mượn: {', '.join(missing)}")

    already_returned = [str(iid) for iid in item_ids if items_by_id[iid].status != "borrowing"]
    if already_returned:
        raise HTTPException(status_code=400, detail="Một số sách đã được trả trước đó")

    for item_id in item_ids:
        item = items_by_id[item_id]
        book_result = await db.execute(select(Book).where(Book.id == item.book_id).with_for_update())
        book = book_result.scalar_one()
        book.quantity_available += item.quantity

        item.returned_at = today
        item.status = "returned"
        item.fine_amount = compute_fine(record.due_date, today, item.quantity)

    all_items = await get_items(db, record_id)
    if all(i.status != "borrowing" for i in all_items):
        record.status = "returned"
    elif any(i.status == "returned" for i in all_items):
        record.status = "partially_returned"

    await db.commit()
    await db.refresh(record)
    return record


async def list_borrows(
    db: AsyncSession,
    *,
    status_filter: str | None,
    reader_id: uuid.UUID | None,
    search: str | None,
    page: int,
    size: int,
) -> tuple[list[BorrowRecord], int]:
    stmt = select(BorrowRecord)
    count_stmt = select(func.count()).select_from(BorrowRecord)

    if status_filter == "overdue":
        stmt = stmt.where(BorrowRecord.status != "returned", BorrowRecord.due_date < date.today())
        count_stmt = count_stmt.where(BorrowRecord.status != "returned", BorrowRecord.due_date < date.today())
    elif status_filter:
        stmt = stmt.where(BorrowRecord.status == status_filter)
        count_stmt = count_stmt.where(BorrowRecord.status == status_filter)

    if reader_id:
        stmt = stmt.where(BorrowRecord.reader_id == reader_id)
        count_stmt = count_stmt.where(BorrowRecord.reader_id == reader_id)

    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(BorrowRecord.code.ilike(pattern))
        count_stmt = count_stmt.where(BorrowRecord.code.ilike(pattern))

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(BorrowRecord.created_at.desc()).offset((page - 1) * size).limit(size)
    items = (await db.execute(stmt)).scalars().all()
    return list(items), total


def is_overdue(record: BorrowRecord) -> bool:
    return record.status != "returned" and record.due_date < date.today()


async def serialize_record(db: AsyncSession, record: BorrowRecord) -> dict:
    """Gộp header + items + độc giả + sách + cờ quá hạn (tính động) thành dict
    khớp schema BorrowRecordOut."""
    from app.services.book_service import _serialize_book

    reader = await db.get(User, record.reader_id)
    items = await get_items(db, record.id)
    item_dicts = []
    for item in items:
        book = await db.get(Book, item.book_id)
        item_dicts.append(
            {
                "id": item.id,
                "book_id": item.book_id,
                "book": await _serialize_book(db, book) if book else None,
                "quantity": item.quantity,
                "returned_at": item.returned_at,
                "status": item.status,
                "fine_amount": item.fine_amount,
            }
        )

    return {
        "id": record.id,
        "code": record.code,
        "reader_id": record.reader_id,
        "reader": reader,
        "librarian_id": record.librarian_id,
        "borrow_date": record.borrow_date,
        "due_date": record.due_date,
        "status": record.status,
        "note": record.note,
        "is_overdue": is_overdue(record),
        "items": item_dicts,
        "created_at": record.created_at,
    }
