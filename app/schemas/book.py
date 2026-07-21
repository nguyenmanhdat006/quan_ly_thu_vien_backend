import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.author import AuthorOut
from app.schemas.category import CategoryOut


class BookBase(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    isbn: str | None = None
    category_id: uuid.UUID
    publisher: str | None = None
    publish_year: int | None = None
    description: str | None = None
    quantity_total: int = Field(ge=0)


class BookCreate(BookBase):
    author_ids: list[uuid.UUID] = Field(default_factory=list)


class BookUpdate(BaseModel):
    title: str | None = None
    isbn: str | None = None
    category_id: uuid.UUID | None = None
    publisher: str | None = None
    publish_year: int | None = None
    description: str | None = None
    quantity_total: int | None = Field(default=None, ge=0)
    author_ids: list[uuid.UUID] | None = None


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    isbn: str | None
    category_id: uuid.UUID
    category: CategoryOut | None = None
    publisher: str | None
    publish_year: int | None
    description: str | None
    quantity_total: int
    quantity_available: int
    authors: list[AuthorOut] = Field(default_factory=list)
    created_at: datetime
