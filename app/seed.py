"""Seed dữ liệu mẫu (idempotent — chạy lại không tạo trùng).
Chạy: python -m app.seed
"""
import asyncio
import random
from datetime import date, timedelta

from sqlalchemy import select

from app.core.keycloak import KeycloakError, keycloak_client
from app.db.session import AsyncSessionLocal
from app.models.author import Author
from app.models.book import Book, BookAuthor
from app.models.borrow import BorrowRecord, BorrowRecordItem
from app.models.category import Category
from app.models.user import User

DEMO_USERS = [
    {
        "username": "admin",
        "email": "admin@library.local",
        "full_name": "Quản Trị Viên",
        "password": "Admin@123",
        "role": "admin",
    },
    {
        "username": "librarian1",
        "email": "librarian1@library.local",
        "full_name": "Nguyễn Thủ Thư",
        "password": "Librarian@123",
        "role": "librarian",
    },
    {
        "username": "reader1",
        "email": "reader1@library.local",
        "full_name": "Trần Văn Đọc",
        "password": "Reader@123",
        "role": "reader",
    },
    {
        "username": "reader2",
        "email": "reader2@library.local",
        "full_name": "Lê Thị Sách",
        "password": "Reader@123",
        "role": "reader",
    },
]

CATEGORIES = [
    ("Văn học", "Tiểu thuyết, truyện ngắn, thơ ca"),
    ("Khoa học", "Sách khoa học tự nhiên"),
    ("Công nghệ thông tin", "Lập trình, khoa học máy tính"),
    ("Lịch sử", "Sách lịch sử Việt Nam và thế giới"),
    ("Kinh tế", "Sách kinh tế, quản trị kinh doanh"),
    ("Tâm lý học", "Sách tâm lý, kỹ năng sống"),
    ("Thiếu nhi", "Sách dành cho thiếu nhi"),
    ("Ngoại ngữ", "Sách học ngoại ngữ"),
]

AUTHORS = [
    "Nguyễn Nhật Ánh", "Tô Hoài", "Ngô Tất Tố", "Nam Cao", "Vũ Trọng Phụng",
    "Robert C. Martin", "Andrew Hunt", "Yuval Noah Harari", "Dale Carnegie",
    "Adam Smith",
]

BOOKS = [
    ("Kính vạn hoa", "Văn học", "Nguyễn Nhật Ánh"),
    ("Dế mèn phiêu lưu ký", "Thiếu nhi", "Tô Hoài"),
    ("Tắt đèn", "Văn học", "Ngô Tất Tố"),
    ("Chí Phèo", "Văn học", "Nam Cao"),
    ("Số đỏ", "Văn học", "Vũ Trọng Phụng"),
    ("Clean Code", "Công nghệ thông tin", "Robert C. Martin"),
    ("Clean Architecture", "Công nghệ thông tin", "Robert C. Martin"),
    ("The Pragmatic Programmer", "Công nghệ thông tin", "Andrew Hunt"),
    ("Sapiens: Lược Sử Loài Người", "Lịch sử", "Yuval Noah Harari"),
    ("Homo Deus", "Khoa học", "Yuval Noah Harari"),
    ("Đắc Nhân Tâm", "Tâm lý học", "Dale Carnegie"),
    ("Quẳng Gánh Lo Đi Và Vui Sống", "Tâm lý học", "Dale Carnegie"),
    ("Của Cải Của Các Dân Tộc", "Kinh tế", "Adam Smith"),
    ("Lịch Sử Việt Nam", "Lịch sử", "Tô Hoài"),
    ("Học Tiếng Anh Giao Tiếp", "Ngoại ngữ", "Dale Carnegie"),
    ("Truyện Cổ Tích Việt Nam", "Thiếu nhi", "Tô Hoài"),
    ("Kinh Tế Học Vi Mô", "Kinh tế", "Adam Smith"),
    ("Design Patterns", "Công nghệ thông tin", "Robert C. Martin"),
    ("Vũ Trụ Trong Vỏ Hạt Dẻ", "Khoa học", "Yuval Noah Harari"),
    ("Sống Đơn Giản Cho Mình Thanh Thản", "Tâm lý học", "Dale Carnegie"),
]


async def seed_users(session) -> dict[str, User]:
    result: dict[str, User] = {}
    for data in DEMO_USERS:
        existing = (
            await session.execute(select(User).where(User.username == data["username"]))
        ).scalar_one_or_none()
        if existing:
            result[data["username"]] = existing
            continue

        try:
            keycloak_user_id = await keycloak_client.create_user(
                username=data["username"],
                email=data["email"],
                full_name=data["full_name"],
                password=data["password"],
                role=data["role"],
            )
        except KeycloakError as exc:
            print(f"[seed] Bỏ qua tạo user '{data['username']}' trên Keycloak: {exc.detail}")
            continue

        user = User(
            keycloak_user_id=keycloak_user_id,
            username=data["username"],
            email=data["email"],
            full_name=data["full_name"],
            role=data["role"],
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        result[data["username"]] = user
        print(f"[seed] Đã tạo user '{data['username']}'")
    return result


async def seed_categories(session) -> dict[str, Category]:
    result: dict[str, Category] = {}
    for name, description in CATEGORIES:
        existing = (await session.execute(select(Category).where(Category.name == name))).scalar_one_or_none()
        if existing:
            result[name] = existing
            continue
        category = Category(name=name, description=description)
        session.add(category)
        await session.commit()
        await session.refresh(category)
        result[name] = category
    return result


async def seed_authors(session) -> dict[str, Author]:
    result: dict[str, Author] = {}
    for name in AUTHORS:
        existing = (await session.execute(select(Author).where(Author.name == name))).scalar_one_or_none()
        if existing:
            result[name] = existing
            continue
        author = Author(name=name)
        session.add(author)
        await session.commit()
        await session.refresh(author)
        result[name] = author
    return result


async def seed_books(session, categories: dict[str, Category], authors: dict[str, Author]) -> list[Book]:
    result: list[Book] = []
    for title, category_name, author_name in BOOKS:
        existing = (await session.execute(select(Book).where(Book.title == title))).scalar_one_or_none()
        if existing:
            result.append(existing)
            continue
        qty = random.randint(1, 10)
        book = Book(
            title=title,
            category_id=categories[category_name].id,
            quantity_total=qty,
            quantity_available=qty,
        )
        session.add(book)
        await session.flush()
        session.add(BookAuthor(book_id=book.id, author_id=authors[author_name].id))
        await session.commit()
        await session.refresh(book)
        result.append(book)
    return result


async def seed_borrows(session, users: dict[str, User], books: list[Book]) -> None:
    existing = (await session.execute(select(BorrowRecord))).scalars().first()
    if existing:
        return
    if "reader1" not in users or "librarian1" not in users or len(books) < 3:
        print("[seed] Bỏ qua tạo phiếu mượn mẫu (thiếu user/sách)")
        return

    reader1 = users["reader1"]
    librarian1 = users["librarian1"]
    today = date.today()

    # Phiếu 1: đang mượn, chưa đến hạn
    record1 = BorrowRecord(
        code="BR-DEMO-0001",
        reader_id=reader1.id,
        librarian_id=librarian1.id,
        borrow_date=today - timedelta(days=3),
        due_date=today + timedelta(days=11),
        status="borrowing",
    )
    session.add(record1)
    await session.flush()
    book1 = books[0]
    book1.quantity_available = max(0, book1.quantity_available - 1)
    session.add(BorrowRecordItem(borrow_record_id=record1.id, book_id=book1.id, quantity=1, status="borrowing"))

    # Phiếu 2: quá hạn để demo phí phạt
    record2 = BorrowRecord(
        code="BR-DEMO-0002",
        reader_id=reader1.id,
        librarian_id=librarian1.id,
        borrow_date=today - timedelta(days=20),
        due_date=today - timedelta(days=6),
        status="borrowing",
    )
    session.add(record2)
    await session.flush()
    book2 = books[1]
    book2.quantity_available = max(0, book2.quantity_available - 1)
    session.add(BorrowRecordItem(borrow_record_id=record2.id, book_id=book2.id, quantity=1, status="borrowing"))

    await session.commit()
    print("[seed] Đã tạo 2 phiếu mượn mẫu (1 đang mượn, 1 quá hạn)")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        users = await seed_users(session)
        categories = await seed_categories(session)
        authors = await seed_authors(session)
        books = await seed_books(session, categories, authors)
        await seed_borrows(session, users, books)
    print("[seed] Hoàn tất seed dữ liệu.")


if __name__ == "__main__":
    asyncio.run(main())
