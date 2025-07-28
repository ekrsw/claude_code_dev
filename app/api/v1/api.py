from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, articles, revisions, categories

api_router = APIRouter()

# Include routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(articles.router, prefix="/articles", tags=["articles"])
api_router.include_router(revisions.router, prefix="/revisions", tags=["revisions"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])