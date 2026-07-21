import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BorrowRecord(Base):
    __tablename__ = "borrow_records"
    __table_args__ = (
        CheckConstraint("due_date >= borrow_date", name="ck_borrow_records_due_date"),
        CheckConstraint(
            "status IN ('borrowing','partially_returned','returned')",
            name="ck_borrow_records_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    reader_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    librarian_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    borrow_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True, default="borrowing")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BorrowRecordItem(Base):
    __tablename__ = "borrow_record_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_borrow_record_items_quantity"),
        CheckConstraint("fine_amount >= 0", name="ck_borrow_record_items_fine_amount"),
        CheckConstraint(
            "status IN ('borrowing','returned','lost')", name="ck_borrow_record_items_status"
        ),
        UniqueConstraint("borrow_record_id", "book_id", name="uq_borrow_record_items_record_book"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    borrow_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("borrow_records.id", ondelete="CASCADE"), nullable=False
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    returned_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="borrowing")
    fine_amount: Mapped[Decimal] = mapped_column(Numeric(12, 0), nullable=False, default=0)
