from datetime import date

from pydantic import BaseModel


class SummaryReport(BaseModel):
    total_books: int
    total_book_copies: int
    total_borrowing: int
    total_overdue: int
    total_readers: int


class TopBookReport(BaseModel):
    book_id: str
    title: str
    total_borrows: int


class OverdueReaderReport(BaseModel):
    record_code: str
    reader_id: str
    reader_name: str
    due_date: date
    days_overdue: int
