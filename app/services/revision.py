from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.revision import RevisionRepository


class RevisionService:
    """Revision service (placeholder)"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.revision_repo = RevisionRepository(db)