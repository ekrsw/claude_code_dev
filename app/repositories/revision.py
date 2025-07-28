from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.revision import Revision, RevisionEditHistory, RevisionInstruction
from app.models.user import User
from app.models.article import Article
from app.models.category import InfoCategory
from app.repositories.base import BaseRepository
from app.constants.enums import RevisionStatus


class RevisionRepository(BaseRepository[Revision]):
    """Revision repository"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Revision, db)
    
    async def get_with_relations(self, revision_id: UUID) -> Optional[Revision]:
        """Get revision with all relations loaded"""
        result = await self.db.execute(
            select(Revision)
            .options(
                selectinload(Revision.proposer),
                selectinload(Revision.approver),
                selectinload(Revision.target_article),
                selectinload(Revision.before_category),
                selectinload(Revision.after_category),
                selectinload(Revision.edit_histories).selectinload(RevisionEditHistory.editor),
                selectinload(Revision.instructions).selectinload(RevisionInstruction.instructor)
                # TODO: Add approval_histories when ApprovalHistory model is implemented in Task 2.11
            )
            .where(Revision.id == revision_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_article(self, article_id: str) -> List[Revision]:
        """Get all revisions for a specific article"""
        result = await self.db.execute(
            select(Revision)
            .options(
                selectinload(Revision.proposer),
                selectinload(Revision.approver)
            )
            .where(Revision.target_article_id == article_id)
            .order_by(Revision.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_by_proposer(self, proposer_id: UUID) -> List[Revision]:
        """Get all revisions by a specific proposer"""
        result = await self.db.execute(
            select(Revision)
            .options(
                selectinload(Revision.target_article),
                selectinload(Revision.approver)
            )
            .where(Revision.proposer_id == proposer_id)
            .order_by(Revision.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_by_status(self, status: RevisionStatus) -> List[Revision]:
        """Get all revisions with a specific status"""
        result = await self.db.execute(
            select(Revision)
            .options(
                selectinload(Revision.proposer),
                selectinload(Revision.target_article),
                selectinload(Revision.approver)
            )
            .where(Revision.status == status)
            .order_by(Revision.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_pending_revisions(self, approver_id: Optional[UUID] = None) -> List[Revision]:
        """Get revisions pending review/approval"""
        query = select(Revision).options(
            selectinload(Revision.proposer),
            selectinload(Revision.target_article)
        ).where(
            Revision.status.in_([
                RevisionStatus.UNDER_REVIEW,
                RevisionStatus.REVISION_REQUESTED
            ])
        )
        
        if approver_id:
            # Filter by specific approver if needed
            pass  # TODO: Implement approver-specific filtering based on permissions
        
        query = query.order_by(Revision.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def check_active_revision_exists(self, article_id: str, exclude_id: Optional[UUID] = None) -> bool:
        """Check if an active revision exists for an article"""
        query = select(Revision).where(
            and_(
                Revision.target_article_id == article_id,
                Revision.status.in_([
                    RevisionStatus.DRAFT,
                    RevisionStatus.UNDER_REVIEW,
                    RevisionStatus.REVISION_REQUESTED
                ])
            )
        )
        
        if exclude_id:
            query = query.where(Revision.id != exclude_id)
        
        result = await self.db.execute(query.limit(1))
        return result.scalar_one_or_none() is not None
    
    async def increment_version(self, revision_id: UUID) -> int:
        """Increment revision version for optimistic locking"""
        revision = await self.get(revision_id)
        if revision:
            revision.version += 1
            await self.db.flush()
            return revision.version
        return 0


class RevisionEditHistoryRepository(BaseRepository[RevisionEditHistory]):
    """Revision edit history repository"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(RevisionEditHistory, db)
    
    async def get_by_revision(self, revision_id: UUID) -> List[RevisionEditHistory]:
        """Get all edit histories for a revision"""
        result = await self.db.execute(
            select(RevisionEditHistory)
            .options(selectinload(RevisionEditHistory.editor))
            .where(RevisionEditHistory.revision_id == revision_id)
            .order_by(RevisionEditHistory.edited_at.desc())
        )
        return list(result.scalars().all())


class RevisionInstructionRepository(BaseRepository[RevisionInstruction]):
    """Revision instruction repository"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(RevisionInstruction, db)
    
    async def get_by_revision(self, revision_id: UUID) -> List[RevisionInstruction]:
        """Get all instructions for a revision"""
        result = await self.db.execute(
            select(RevisionInstruction)
            .options(selectinload(RevisionInstruction.instructor))
            .where(RevisionInstruction.revision_id == revision_id)
            .order_by(RevisionInstruction.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_unresolved(self, revision_id: UUID) -> List[RevisionInstruction]:
        """Get unresolved instructions for a revision"""
        result = await self.db.execute(
            select(RevisionInstruction)
            .options(selectinload(RevisionInstruction.instructor))
            .where(
                and_(
                    RevisionInstruction.revision_id == revision_id,
                    RevisionInstruction.resolved_at.is_(None)
                )
            )
            .order_by(RevisionInstruction.priority.desc(), RevisionInstruction.created_at)
        )
        return list(result.scalars().all())