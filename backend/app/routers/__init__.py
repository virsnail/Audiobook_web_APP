from app.routers.auth import router as auth_router
from app.routers.books import router as books_router
from app.routers.activity import router as activity_router

__all__ = [
    "auth_router",
    "books_router",
]
