from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.borrow import BorrowRecordOut
from app.schemas.common import Page
from app.services import borrow_service

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/borrows", response_model=Page[BorrowRecordOut])
async def my_borrows(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("reader")),
    db: AsyncSession = Depends(get_db),
) -> Page[BorrowRecordOut]:
    items, total = await borrow_service.list_borrows(
        db, status_filter=status, reader_id=current_user.id, search=None, page=page, size=size
    )
    serialized = [await borrow_service.serialize_record(db, r) for r in items]
    return Page(items=[BorrowRecordOut.model_validate(s) for s in serialized], total=total, page=page, size=size)
