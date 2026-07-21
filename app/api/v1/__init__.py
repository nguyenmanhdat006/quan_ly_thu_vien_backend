from fastapi import APIRouter

from app.api.v1 import auth, authors, books, borrows, categories, me, reports, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(categories.router)
api_router.include_router(authors.router)
api_router.include_router(books.router)
api_router.include_router(borrows.router)
api_router.include_router(reports.router)
api_router.include_router(me.router)
