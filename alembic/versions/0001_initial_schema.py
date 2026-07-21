"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("keycloak_user_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('admin','librarian','reader')", name="ck_users_role"),
    )

    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
    )

    op.create_table(
        "authors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
    )

    op.create_table(
        "books",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("isbn", sa.String(20), nullable=True, unique=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("publisher", sa.String(255), nullable=True),
        sa.Column("publish_year", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity_total", sa.Integer(), nullable=False),
        sa.Column("quantity_available", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("quantity_total >= 0", name="ck_books_quantity_total"),
        sa.CheckConstraint("quantity_available >= 0 AND quantity_available <= quantity_total", name="ck_books_quantity_available"),
    )
    op.create_index("ix_books_title", "books", ["title"])
    op.create_index("ix_books_category_id", "books", ["category_id"])

    op.create_table(
        "book_authors",
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "borrow_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("reader_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("librarian_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("borrow_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="borrowing"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("due_date >= borrow_date", name="ck_borrow_records_due_date"),
        sa.CheckConstraint("status IN ('borrowing','partially_returned','returned')", name="ck_borrow_records_status"),
    )
    op.create_index("ix_borrow_records_reader_id", "borrow_records", ["reader_id"])
    op.create_index("ix_borrow_records_status", "borrow_records", ["status"])

    op.create_table(
        "borrow_record_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("borrow_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("borrow_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("returned_at", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="borrowing"),
        sa.Column("fine_amount", sa.Numeric(12, 0), nullable=False, server_default="0"),
        sa.CheckConstraint("quantity > 0", name="ck_borrow_record_items_quantity"),
        sa.CheckConstraint("fine_amount >= 0", name="ck_borrow_record_items_fine_amount"),
        sa.CheckConstraint("status IN ('borrowing','returned','lost')", name="ck_borrow_record_items_status"),
        sa.UniqueConstraint("borrow_record_id", "book_id", name="uq_borrow_record_items_record_book"),
    )
    op.create_index("ix_borrow_record_items_book_id", "borrow_record_items", ["book_id"])


def downgrade() -> None:
    op.drop_table("borrow_record_items")
    op.drop_table("borrow_records")
    op.drop_table("book_authors")
    op.drop_table("books")
    op.drop_table("authors")
    op.drop_table("categories")
    op.drop_table("users")
