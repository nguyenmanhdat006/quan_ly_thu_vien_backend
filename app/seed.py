#!/usr/bin/env python3
"""
Seed script tạo dữ liệu mẫu cho dự án Quản lý thư viện.

Chạy: cd backend && python -m app.seed
hoặc: cd backend && python app/seed.py

Idempotent — chạy lại không tạo trùng lặp (kiểm tra tồn tại trước).
"""

import asyncio
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.keycloak import keycloak_client, KeycloakError
from app.db.session import AsyncSessionLocal
from app.models import (
    User,
    Category,
    Author,
    Book,
    BookAuthor,
    BorrowRecord,
    BorrowRecordItem,
)

# Seed data constants
SEED_USERS = [
    {
        "username": "admin",
        "email": "admin@library.vn",
        "password": "Admin@123",
        "full_name": "Admin",
        "role": "admin",
    },
    {
        "username": "librarian1",
        "email": "librarian1@library.vn",
        "password": "Librarian@123",
        "full_name": "Thủ thư Một",
        "role": "librarian",
    },
    {
        "username": "reader1",
        "email": "reader1@library.vn",
        "password": "Reader@123",
        "full_name": "Độc giả Một",
        "role": "reader",
    },
    {
        "username": "reader2",
        "email": "reader2@library.vn",
        "password": "Reader@123",
        "full_name": "Độc giả Hai",
        "role": "reader",
    },
]

SEED_CATEGORIES = [
    {"name": "Văn học", "description": "Sách văn học, tiểu thuyết"},
    {"name": "Lịch sử", "description": "Sách lịch sử, tiểu sử"},
    {"name": "Khoa học", "description": "Sách khoa học, công nghệ"},
    {"name": "Kinh tế", "description": "Sách kinh tế, quản lý"},
    {"name": "Tâm lý học", "description": "Sách tâm lý, phát triển bản thân"},
    {"name": "Kỹ năng sống", "description": "Sách hướng dẫn kỹ năng"},
    {"name": "Trẻ em", "description": "Sách cho trẻ em"},
    {"name": "Tham khảo", "description": "Sách tham khảo, từ điển"},
]

SEED_AUTHORS = [
    {"name": "Nguyễn Du", "bio": "Nhà thơ cổ điển Việt Nam"},
    {"name": "Trần Hưng Đạo", "bio": "Danh tướng chiến lược Việt Nam"},
    {"name": "Hà Nội", "bio": "Nhà văn hiện đại"},
    {"name": "Borges", "bio": "Nhà văn Argentina"},
    {"name": "Tolstoy", "bio": "Nhà văn Nga"},
    {"name": "Austen", "bio": "Nhà văn Anh"},
    {"name": "Stephen Hawking", "bio": "Nhà vật lý lý thuyết"},
    {"name": "Carl Sagan", "bio": "Nhà thiên văn học"},
    {"name": "Yuval Noah Harari", "bio": "Historian, tác giả Sapiens"},
    {"name": "Dale Carnegie", "bio": "Tác giả How to Win Friends"},
]

SEED_BOOKS = [
    {
        "title": "Truyện Kiều",
        "isbn": "978-1-001-00001-1",
        "category_name": "Văn học",
        "author_names": ["Nguyễn Du"],
        "publisher": "NXB Văn học",
        "publish_year": 1820,
        "description": "Tác phẩm kinh điển của nền văn học Việt Nam",
        "quantity_total": 5,
    },
    {
        "title": "Thĩnh Kiếp Ký",
        "isbn": "978-1-001-00002-2",
        "category_name": "Lịch sử",
        "author_names": ["Trần Hưng Đạo"],
        "publisher": "NXB Sử học",
        "publish_year": 1285,
        "description": "Chiến lược quân sự của danh tướng Trần Hưng Đạo",
        "quantity_total": 3,
    },
    {
        "title": "Sapiens: Từ quá khứ đến tương lai",
        "isbn": "978-1-001-00003-3",
        "category_name": "Lịch sử",
        "author_names": ["Yuval Noah Harari"],
        "publisher": "NXB Trí tuệ",
        "publish_year": 2014,
        "description": "Hành trình tiến hóa của loài người",
        "quantity_total": 7,
    },
    {
        "title": "Cosmos",
        "isbn": "978-1-001-00004-4",
        "category_name": "Khoa học",
        "author_names": ["Carl Sagan"],
        "publisher": "NXB Khoa học",
        "publish_year": 1980,
        "description": "Cuộc hành trình khám phá vũ trụ",
        "quantity_total": 4,
    },
    {
        "title": "A Brief History of Time",
        "isbn": "978-1-001-00005-5",
        "category_name": "Khoa học",
        "author_names": ["Stephen Hawking"],
        "publisher": "Bantam Books",
        "publish_year": 1988,
        "description": "Lịch sử ngắn gọn thời gian",
        "quantity_total": 6,
    },
    {
        "title": "How to Win Friends and Influence People",
        "isbn": "978-1-001-00006-6",
        "category_name": "Kỹ năng sống",
        "author_names": ["Dale Carnegie"],
        "publisher": "Simon & Schuster",
        "publish_year": 1936,
        "description": "Hướng dẫn xây dựng kỹ năng giao tiếp",
        "quantity_total": 8,
    },
    {
        "title": "War and Peace",
        "isbn": "978-1-001-00007-7",
        "category_name": "Văn học",
        "author_names": ["Tolstoy"],
        "publisher": "Oxford University Press",
        "publish_year": 1869,
        "description": "Tiểu thuyết kinh điển về chiến tranh và hòa bình",
        "quantity_total": 2,
    },
    {
        "title": "Pride and Prejudice",
        "isbn": "978-1-001-00008-8",
        "category_name": "Văn học",
        "author_names": ["Austen"],
        "publisher": "Penguin Classics",
        "publish_year": 1813,
        "description": "Tiểu thuyết tình yêu kinh điển",
        "quantity_total": 5,
    },
    {
        "title": "Ficciones",
        "isbn": "978-1-001-00009-9",
        "category_name": "Văn học",
        "author_names": ["Borges"],
        "publisher": "Grove Press",
        "publish_year": 1944,
        "description": "Tuyển tập truyện ngắn của Borges",
        "quantity_total": 3,
    },
    {
        "title": "Emotional Intelligence",
        "isbn": "978-1-001-00010-0",
        "category_name": "Tâm lý học",
        "author_names": ["Daniel Goleman"],
        "publisher": "Bantam Books",
        "publish_year": 1995,
        "description": "Thông minh cảm xúc trong cuộc sống",
        "quantity_total": 4,
    },
]


async def seed_users(session: AsyncSession) -> dict[str, uuid.UUID]:
    """Tạo user mẫu trên Keycloak và DB. Trả về mapping username -> user_id."""
    user_map = {}

    for user_data in SEED_USERS:
        username = user_data["username"]
        
        # Kiểm tra user đã tồn tại trong DB
        result = await session.execute(
            select(User).where(User.username == username)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"  User '{username}' đã tồn tại, bỏ qua")
            user_map[username] = existing_user.id
            continue

        # Tạo user trên Keycloak + DB
        try:
            keycloak_user_id = await keycloak_client.create_user(
                username=username,
                email=user_data["email"],
                full_name=user_data["full_name"],
                password=user_data["password"],
                role=user_data["role"],
            )
            
            # Insert vào DB
            user = User(
                id=uuid.uuid4(),
                keycloak_user_id=keycloak_user_id,
                username=username,
                email=user_data["email"],
                full_name=user_data["full_name"],
                role=user_data["role"],
                is_active=True,
            )
            session.add(user)
            user_map[username] = user.id
            print(f"  ✓ User '{username}' ({user_data['role']}) tạo thành công")
        
        except KeycloakError as e:
            if e.status_code == 409:
                print(f"  User '{username}' đã tồn tại trên Keycloak, skip")
                # Tạo record DB mà không tạo Keycloak
                user = User(
                    id=uuid.uuid4(),
                    keycloak_user_id=uuid.uuid4(),  # Dummy ID, sẽ fix manual
                    username=username,
                    email=user_data["email"],
                    full_name=user_data["full_name"],
                    role=user_data["role"],
                    is_active=True,
                )
                session.add(user)
                user_map[username] = user.id
            else:
                print(f"  ✗ Lỗi tạo user '{username}': {e.detail}")
                raise

    await session.commit()
    return user_map


async def seed_categories(session: AsyncSession) -> dict[str, uuid.UUID]:
    """Tạo thể loại mẫu."""
    category_map = {}

    for cat_data in SEED_CATEGORIES:
        result = await session.execute(
            select(Category).where(Category.name == cat_data["name"])
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"  Category '{cat_data['name']}' đã tồn tại")
            category_map[cat_data["name"]] = existing.id
            continue

        cat = Category(
            id=uuid.uuid4(),
            name=cat_data["name"],
            description=cat_data.get("description"),
        )
        session.add(cat)
        category_map[cat_data["name"]] = cat.id
        print(f"  ✓ Category '{cat_data['name']}' tạo thành công")

    await session.commit()
    return category_map


async def seed_authors(session: AsyncSession) -> dict[str, uuid.UUID]:
    """Tạo tác giả mẫu."""
    author_map = {}

    for author_data in SEED_AUTHORS:
        result = await session.execute(
            select(Author).where(Author.name == author_data["name"])
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"  Author '{author_data['name']}' đã tồn tại")
            author_map[author_data["name"]] = existing.id
            continue

        author = Author(
            id=uuid.uuid4(),
            name=author_data["name"],
            bio=author_data.get("bio"),
        )
        session.add(author)
        author_map[author_data["name"]] = author.id
        print(f"  ✓ Author '{author_data['name']}' tạo thành công")

    await session.commit()
    return author_map


async def seed_books(
    session: AsyncSession,
    category_map: dict[str, uuid.UUID],
    author_map: dict[str, uuid.UUID],
) -> list[uuid.UUID]:
    """Tạo sách mẫu."""
    book_ids = []

    for book_data in SEED_BOOKS:
        result = await session.execute(
            select(Book).where(Book.title == book_data["title"])
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"  Book '{book_data['title']}' đã tồn tại")
            book_ids.append(existing.id)
            continue

        book = Book(
            id=uuid.uuid4(),
            title=book_data["title"],
            isbn=book_data.get("isbn"),
            category_id=category_map[book_data["category_name"]],
            publisher=book_data.get("publisher"),
            publish_year=book_data.get("publish_year"),
            description=book_data.get("description"),
            quantity_total=book_data["quantity_total"],
            quantity_available=book_data["quantity_total"],  # Ban đầu tất cả đều có sẵn
        )
        session.add(book)
        book_ids.append(book.id)
        
        # Thêm tác giả
        for author_name in book_data["author_names"]:
            if author_name in author_map:
                ba = BookAuthor(book_id=book.id, author_id=author_map[author_name])
                session.add(ba)
        
        print(f"  ✓ Book '{book_data['title']}' tạo thành công")

    await session.commit()
    return book_ids


async def seed_borrow_records(
    session: AsyncSession,
    user_map: dict[str, uuid.UUID],
    book_ids: list[uuid.UUID],
) -> None:
    """Tạo phiếu mượn mẫu (vài phiếu lịch sử để demo báo cáo)."""
    
    if len(book_ids) < 2 or "librarian1" not in user_map or "reader1" not in user_map:
        print("  Bỏ qua seed phiếu mượn (dữ liệu không đủ)")
        return

    librarian_id = user_map["librarian1"]
    reader_id = user_map["reader1"]
    
    # Phiếu 1: đang mượn (không quá hạn)
    today = datetime.now().date()
    due_date_1 = today + timedelta(days=14)
    
    record1 = BorrowRecord(
        id=uuid.uuid4(),
        code=f"BR-{today.strftime('%Y%m%d')}-0001",
        reader_id=reader_id,
        librarian_id=librarian_id,
        borrow_date=today,
        due_date=due_date_1,
        status="borrowing",
        note="Phiếu mượn mẫu 1",
    )
    session.add(record1)
    
    # Thêm 2 đầu sách vào phiếu 1
    item1 = BorrowRecordItem(
        id=uuid.uuid4(),
        borrow_record_id=record1.id,
        book_id=book_ids[0],
        quantity=1,
        returned_at=None,
        status="borrowing",
        fine_amount=0,
    )
    session.add(item1)
    
    # Cập nhật tồn kho
    book1 = await session.get(Book, book_ids[0])
    if book1:
        book1.quantity_available -= 1
    
    print(f"  ✓ Phiếu mượn mẫu 1 (đang mượn, không quá hạn) tạo thành công")
    
    # Phiếu 2: quá hạn (để demo tính phạt)
    due_date_2 = today - timedelta(days=3)  # 3 ngày trước
    
    record2 = BorrowRecord(
        id=uuid.uuid4(),
        code=f"BR-{today.strftime('%Y%m%d')}-0002",
        reader_id=reader_id,
        librarian_id=librarian_id,
        borrow_date=due_date_2 - timedelta(days=14),
        due_date=due_date_2,
        status="borrowing",
        note="Phiếu mượn mẫu 2 (quá hạn)",
    )
    session.add(record2)
    
    # Thêm 1 đầu sách vào phiếu 2
    item2 = BorrowRecordItem(
        id=uuid.uuid4(),
        borrow_record_id=record2.id,
        book_id=book_ids[1],
        quantity=1,
        returned_at=None,
        status="borrowing",
        fine_amount=0,  # Chưa trả nên phạt = 0, tính khi trả
    )
    session.add(item2)
    
    # Cập nhật tồn kho
    book2 = await session.get(Book, book_ids[1])
    if book2:
        book2.quantity_available -= 1
    
    print(f"  ✓ Phiếu mượn mẫu 2 (quá hạn {(today - due_date_2).days} ngày) tạo thành công")

    await session.commit()


async def main():
    """Main seed function."""
    print("\n" + "="*60)
    print("SEEDING DATABASE - QUẢN LÝ THƯ VIỆN")
    print("="*60)

    async with AsyncSessionLocal() as session:
        try:
            print("\n1. Tạo user...")
            user_map = await seed_users(session)
            
            print("\n2. Tạo thể loại...")
            category_map = await seed_categories(session)
            
            print("\n3. Tạo tác giả...")
            author_map = await seed_authors(session)
            
            print("\n4. Tạo sách...")
            book_ids = await seed_books(session, category_map, author_map)
            
            print("\n5. Tạo phiếu mượn mẫu...")
            await seed_borrow_records(session, user_map, book_ids)
            
            print("\n" + "="*60)
            print("✓ SEED THÀNH CÔNG!")
            print("="*60)
            print("\nTài khoản mẫu:")
            print("  Admin:     admin / Admin@123")
            print("  Librarian: librarian1 / Librarian@123")
            print("  Reader:    reader1 / Reader@123")
            print("             reader2 / Reader@123")
            print("\nTest ngay: POST /auth/login với username/password trên")
            print("="*60 + "\n")
        
        except Exception as e:
            print(f"\n✗ LỖI SEED: {type(e).__name__}: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())