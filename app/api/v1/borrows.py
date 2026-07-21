import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.borrow import BorrowCreate, BorrowRecordOut, FinePreviewOut, ReturnRequest
from app.schemas.common import Page
from app.services import borrow_service

router = APIRouter(prefix="/borrows", tags=["borrows"])


@router.post("", response_model=BorrowRecordOut, status_code=201)
async def create_borrow(
    payload: BorrowCreate,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> BorrowRecordOut:
    record = await borrow_service.create_borrow(db, current_user.id, payload)
    return BorrowRecordOut.model_validate(await borrow_service.serialize_record(db, record))


@router.get("", response_model=Page[BorrowRecordOut])
async def list_borrows(
    status: str | None = Query(default=None),
    reader_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> Page[BorrowRecordOut]:
    items, total = await borrow_service.list_borrows(
        db, status_filter=status, reader_id=reader_id, search=search, page=page, size=size
    )
    serialized = [await borrow_service.serialize_record(db, r) for r in items]
    return Page(items=[BorrowRecordOut.model_validate(s) for s in serialized], total=total, page=page, size=size)


@router.get("/{record_id}", response_model=BorrowRecordOut)
async def get_borrow(
    record_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BorrowRecordOut:
    record = await borrow_service.get_record_or_404(db, record_id)
    if current_user.role == "reader" and record.reader_id != current_user.id:
        raise HTTPException(status_code=403, detail="Không có quyền xem phiếu mượn này")
    return BorrowRecordOut.model_validate(await borrow_service.serialize_record(db, record))


@router.get("/{record_id}/fine-preview", response_model=FinePreviewOut)
async def fine_preview(
    record_id: uuid.UUID,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> FinePreviewOut:
    return await borrow_service.preview_fine(db, record_id)


@router.post("/{record_id}/return", response_model=BorrowRecordOut)
async def return_borrow(
    record_id: uuid.UUID,
    payload: ReturnRequest,
    current_user: User = Depends(require_roles("admin", "librarian")),
    db: AsyncSession = Depends(get_db),
) -> BorrowRecordOut:
    record = await borrow_service.return_items(db, record_id, payload.item_ids)
    return BorrowRecordOut.model_validate(await borrow_service.serialize_record(db, record))


