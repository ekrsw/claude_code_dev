from sqlalchemy.ext.asyncio import AsyncSession

from app.models.revision import Revision
from app.repositories.base import BaseRepository


class RevisionRepository(BaseRepository[Revision]):
    """Revision repository"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Revision, db)