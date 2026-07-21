from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.report import OverdueReaderReport, SummaryReport, TopBookReport
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary", response_model=SummaryReport)
async def summary(
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> SummaryReport:
    return await report_service.get_summary(db)


@router.get("/top-books", response_model=list[TopBookReport])
async def top_books(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> list[TopBookReport]:
    return await report_service.get_top_books(db, limit=limit)


@router.get("/overdue-readers", response_model=list[OverdueReaderReport])
async def overdue_readers(
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> list[OverdueReaderReport]:
    return await report_service.get_overdue_readers(db)
