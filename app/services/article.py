from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.article import ArticleRepository
from app.models.article import Article
from app.schemas.article import ArticleBase


class ArticleService:
    """Article service for managing existing knowledge articles"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.article_repo = ArticleRepository(db)
    
    async def get_article_by_id(self, article_id: int) -> Optional[Article]:
        """Get article by ID"""
        return await self.article_repo.get_by_id(article_id)
    
    async def get_articles_by_category(self, category_id: int) -> List[Article]:
        """Get articles by category"""
        return await self.article_repo.get_by_category(category_id)
    
    async def search_articles(self, query: str) -> List[Article]:
        """Search articles by title or content"""
        return await self.article_repo.search(query)
    
    async def get_all_articles(self, skip: int = 0, limit: int = 100) -> List[Article]:
        """Get all articles with pagination"""
        return await self.article_repo.get_all(skip=skip, limit=limit)