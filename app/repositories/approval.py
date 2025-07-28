"""
Repository for ApprovalHistory model
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.approval import ApprovalHistory
from app.repositories.base import BaseRepository


class ApprovalHistoryRepository(BaseRepository[ApprovalHistory]):
    """Repository for managing approval history data"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(ApprovalHistory, db)
    
    async def get_by_revision_id(
        self,
        revision_id: UUID,
        limit: Optional[int] = None
    ) -> List[ApprovalHistory]:
        """
        Get approval history for a specific revision
        
        Args:
            revision_id: ID of the revision
            limit: Optional limit on number of records
            
        Returns:
            List of approval history records
        """
        query = select(ApprovalHistory).where(
            ApprovalHistory.revision_id == revision_id
        ).options(
            selectinload(ApprovalHistory.actor),
            selectinload(ApprovalHistory.revision)
        ).order_by(ApprovalHistory.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_by_actor_id(
        self,
        actor_id: UUID,
        limit: Optional[int] = None
    ) -> List[ApprovalHistory]:
        """
        Get approval history for a specific actor (user)
        
        Args:
            actor_id: ID of the actor
            limit: Optional limit on number of records
            
        Returns:
            List of approval history records
        """
        query = select(ApprovalHistory).where(
            ApprovalHistory.actor_id == actor_id
        ).options(
            selectinload(ApprovalHistory.actor),
            selectinload(ApprovalHistory.revision)
        ).order_by(ApprovalHistory.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_latest_for_revision(
        self,
        revision_id: UUID
    ) -> Optional[ApprovalHistory]:
        """
        Get the latest approval history record for a revision
        
        Args:
            revision_id: ID of the revision
            
        Returns:
            Latest approval history record or None
        """
        query = select(ApprovalHistory).where(
            ApprovalHistory.revision_id == revision_id
        ).options(
            selectinload(ApprovalHistory.actor),
            selectinload(ApprovalHistory.revision)
        ).order_by(ApprovalHistory.created_at.desc()).limit(1)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def count_by_revision_id(self, revision_id: UUID) -> int:
        """
        Count approval history records for a revision
        
        Args:
            revision_id: ID of the revision
            
        Returns:
            Number of approval history records
        """
        query = select(ApprovalHistory.id).where(
            ApprovalHistory.revision_id == revision_id
        )
        
        result = await self.db.execute(query)
        return len(result.scalars().all())