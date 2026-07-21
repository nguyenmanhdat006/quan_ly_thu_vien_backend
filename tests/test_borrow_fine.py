"""Unit test cho phần tính phí phạt (thuần logic, không cần DB) — mục 12.6
CLAUDE.md yêu cầu unit test borrow_service: tồn kho, lock, phạt, trả một phần.
Các phần liên quan DB (tồn kho, lock, trả một phần) được kiểm thử end-to-end
qua Docker (xem README) vì phụ thuộc PostgreSQL thật (FOR UPDATE, CHECK
constraint). Ở đây kiểm tra công thức tính phạt độc lập."""
from datetime import date, timedelta
from decimal import Decimal

from app.core.config import settings
from app.services.borrow_service import compute_fine


def test_compute_fine_no_delay():
    due = date(2026, 1, 1)
    returned = date(2026, 1, 1)
    assert compute_fine(due, returned, quantity=1) == Decimal(0)


def test_compute_fine_returned_early_is_zero():
    due = date(2026, 1, 10)
    returned = date(2026, 1, 5)
    assert compute_fine(due, returned, quantity=2) == Decimal(0)


def test_compute_fine_overdue():
    due = date(2026, 1, 1)
    returned = due + timedelta(days=3)
    expected = Decimal(3) * Decimal(settings.FINE_PER_DAY) * Decimal(2)
    assert compute_fine(due, returned, quantity=2) == expected


def test_compute_fine_single_day_single_book():
    due = date(2026, 1, 1)
    returned = due + timedelta(days=1)
    assert compute_fine(due, returned, quantity=1) == Decimal(settings.FINE_PER_DAY)
