import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.book import BookOut
from app.schemas.user import UserOut

ItemStatus = Literal["borrowing", "returned", "lost"]
RecordStatus = Literal["borrowing", "partially_returned", "returned"]


class BorrowItemCreate(BaseModel):
    book_id: uuid.UUID
    quantity: int = Field(default=1, gt=0)


class BorrowCreate(BaseModel):
    reader_id: uuid.UUID
    due_date: date
    note: str | None = None
    items: list[BorrowItemCreate] = Field(min_length=1)


class ReturnRequest(BaseModel):
    item_ids: list[uuid.UUID] = Field(min_length=1)


class BorrowRecordItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    book_id: uuid.UUID
    book: BookOut | None = None
    quantity: int
    returned_at: date | None
    status: ItemStatus
    fine_amount: Decimal


class BorrowRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    reader_id: uuid.UUID
    reader: UserOut | None = None
    librarian_id: uuid.UUID
    borrow_date: date
    due_date: date
    status: RecordStatus
    note: str | None
    is_overdue: bool = False
    items: list[BorrowRecordItemOut] = Field(default_factory=list)
    created_at: datetime


class FinePreviewItem(BaseModel):
    item_id: uuid.UUID
    book_id: uuid.UUID
    days_overdue: int
    fine_amount: Decimal


class FinePreviewOut(BaseModel):
    items: list[FinePreviewItem]
    total_fine: Decimal
