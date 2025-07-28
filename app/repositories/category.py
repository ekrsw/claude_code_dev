from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import InfoCategory
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[InfoCategory]):
    """Category repository"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(InfoCategory, db)