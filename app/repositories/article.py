from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.article import Article
from app.repositories.base import BaseRepository


class ArticleRepository(BaseRepository[Article]):
    """Article repository for database operations"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Article, db)
    
    async def get_by_category(self, category_id: int) -> List[Article]:
        """Get articles by category"""
        result = await self.db.execute(
            select(Article).where(Article.category_id == category_id)
        )
        return list(result.scalars().all())
    
    async def search(self, query: str) -> List[Article]:
        """Search articles by title or content"""
        result = await self.db.execute(
            select(Article).where(
                or_(
                    Article.title.ilike(f"%{query}%"),
                    Article.answer.ilike(f"%{query}%")
                )
            )
        )
        return list(result.scalars().all())
    
    async def get_by_article_id(self, article_id: str) -> Optional[Article]:
        """Get article by article_id"""
        result = await self.db.execute(
            select(Article).where(Article.article_id == article_id)
        )
        return result.scalar_one_or_none()