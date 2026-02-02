from app.routers.auth import router as auth_router
from app.routers.books import router as books_router

__all__ = [
    "auth_router",
    "books_router",
]
