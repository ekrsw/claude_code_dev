from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import structlog

from app.repositories.revision import (
    RevisionRepository,
    RevisionEditHistoryRepository,
    RevisionInstructionRepository
)
from app.repositories.article import ArticleRepository
from app.repositories.user import UserRepository
from app.models.revision import Revision, RevisionEditHistory
from app.schemas.revision import (
    RevisionCreate, RevisionUpdate, RevisionResponse,
    RevisionFilter, RevisionDiff, RevisionDetailDiff
)
from app.constants.enums import RevisionStatus, Role
from app.core.exceptions import (
    InvalidStateError, NotFoundError, AuthorizationError, ConflictError
)
from app.utils.cache import cache_manager

logger = structlog.get_logger()


class RevisionService:
    """Revision management service"""
    
    def __init__(self, db: AsyncSession, notification_service=None):
        self.db = db
        self.revision_repo = RevisionRepository(db)
        self.edit_history_repo = RevisionEditHistoryRepository(db)
        self.instruction_repo = RevisionInstructionRepository(db)
        self.article_repo = ArticleRepository(db)
        self.user_repo = UserRepository(db)
        self.notification_service = notification_service
    
    async def create_revision(
        self,
        revision_data: RevisionCreate,
        user_id: UUID
    ) -> RevisionResponse:
        """Create a new revision"""
        # Check if article exists
        article = await self.article_repo.get_by_article_id(revision_data.target_article_id)
        if not article:
            raise NotFoundError(f"Article {revision_data.target_article_id} not found")
        
        # Check for active revisions on the same article
        active_exists = await self.revision_repo.check_active_revision_exists(
            revision_data.target_article_id
        )
        if active_exists:
            raise ConflictError(
                f"An active revision already exists for article {revision_data.target_article_id}"
            )
        
        # Create revision entity
        revision = Revision(
            target_article_id=revision_data.target_article_id,
            proposer_id=user_id,
            reason=revision_data.reason,
            status=RevisionStatus.DRAFT
        )
        
        # Set before values from current article
        revision.before_title = article.title
        revision.before_info_category = article.info_category_code
        revision.before_keywords = article.keywords
        revision.before_importance = article.importance
        revision.before_target = article.target
        revision.before_question = article.question
        revision.before_answer = article.answer
        revision.before_additional_comment = article.additional_comment
        revision.before_publish_start = article.publish_start
        revision.before_publish_end = article.publish_end
        
        # Set after values from modifications
        modifications = revision_data.modifications
        if modifications.title is not None:
            revision.after_title = modifications.title
        if modifications.info_category is not None:
            revision.after_info_category = modifications.info_category
        if modifications.keywords is not None:
            revision.after_keywords = ','.join(modifications.keywords) if modifications.keywords else None
        if modifications.importance is not None:
            revision.after_importance = modifications.importance
        if modifications.target is not None:
            revision.after_target = modifications.target
        if modifications.question is not None:
            revision.after_question = modifications.question
        if modifications.answer is not None:
            revision.after_answer = modifications.answer
        if modifications.additional_comment is not None:
            revision.after_additional_comment = modifications.additional_comment
        if modifications.publish_start is not None:
            revision.after_publish_start = modifications.publish_start
        if modifications.publish_end is not None:
            revision.after_publish_end = modifications.publish_end
        
        # Save to database
        try:
            # Convert revision model to dict for repository create method
            revision_data_dict = {
                'target_article_id': revision.target_article_id,
                'proposer_id': revision.proposer_id,
                'reason': revision.reason,
                'status': revision.status,
                'before_title': revision.before_title,
                'after_title': revision.after_title,
                'before_info_category': revision.before_info_category,
                'after_info_category': revision.after_info_category,
                'before_keywords': revision.before_keywords,
                'after_keywords': revision.after_keywords,
                'before_importance': revision.before_importance,
                'after_importance': revision.after_importance,
                'before_target': revision.before_target,
                'after_target': revision.after_target,
                'before_question': revision.before_question,
                'after_question': revision.after_question,
                'before_answer': revision.before_answer,
                'after_answer': revision.after_answer,
                'before_additional_comment': revision.before_additional_comment,
                'after_additional_comment': revision.after_additional_comment,
                'before_publish_start': revision.before_publish_start,
                'after_publish_start': revision.after_publish_start,
                'before_publish_end': revision.before_publish_end,
                'after_publish_end': revision.after_publish_end,
                'version': revision.version if hasattr(revision, 'version') else 1
            }
            revision = await self.revision_repo.create(**revision_data_dict)
            await self.db.commit()
            
            # Invalidate cache
            await cache_manager.delete(f"article:{revision_data.target_article_id}")
            
            logger.info(
                "Revision created",
                revision_id=str(revision.id),
                article_id=revision_data.target_article_id,
                user_id=str(user_id)
            )
            
            return await self._build_revision_response(revision)
            
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("Revision creation failed", error=str(e))
            raise InvalidStateError("Failed to create revision")
    
    async def get_revision(self, revision_id: UUID) -> RevisionResponse:
        """Get revision by ID"""
        revision = await self.revision_repo.get_with_relations(revision_id)
        if not revision:
            raise NotFoundError(f"Revision {revision_id} not found")
        
        return await self._build_revision_response(revision)
    
    async def update_revision(
        self,
        revision_id: UUID,
        update_data: RevisionUpdate,
        user_id: UUID,
        user_role: Role
    ) -> RevisionResponse:
        """Update an existing revision"""
        revision = await self.revision_repo.get(revision_id)
        if not revision:
            raise NotFoundError(f"Revision {revision_id} not found")
        
        # Check permissions
        if not self._can_edit_revision(revision, user_id, user_role):
            raise AuthorizationError("You don't have permission to edit this revision")
        
        # Record current state for history
        current_version = revision.version
        changes = {}
        
        # Update reason if provided
        if update_data.reason:
            changes['reason'] = {'before': revision.reason, 'after': update_data.reason}
            revision.reason = update_data.reason
        
        # Update modifications if provided
        if update_data.modifications:
            modifications = update_data.modifications
            
            if modifications.title is not None:
                changes['title'] = {'before': revision.after_title, 'after': modifications.title}
                revision.after_title = modifications.title
                
            if modifications.info_category is not None:
                changes['info_category'] = {
                    'before': revision.after_info_category,
                    'after': modifications.info_category
                }
                revision.after_info_category = modifications.info_category
                
            if modifications.answer is not None:
                changes['answer'] = {'before': revision.after_answer, 'after': modifications.answer}
                revision.after_answer = modifications.answer
                
            if modifications.keywords is not None:
                keywords_str = ','.join(modifications.keywords) if modifications.keywords else None
                changes['keywords'] = {'before': revision.after_keywords, 'after': keywords_str}
                revision.after_keywords = keywords_str
                
            if modifications.question is not None:
                changes['question'] = {'before': revision.after_question, 'after': modifications.question}
                revision.after_question = modifications.question
                
            if modifications.additional_comment is not None:
                changes['additional_comment'] = {
                    'before': revision.after_additional_comment,
                    'after': modifications.additional_comment
                }
                revision.after_additional_comment = modifications.additional_comment
        
        # Increment version
        revision.version += 1
        
        try:
            await self.db.flush()
            
            # Record edit history
            if changes:
                await self.edit_history_repo.create(
                    revision_id=revision_id,
                    editor_id=user_id,
                    editor_role=user_role.value,
                    changes=changes,
                    version_before=current_version,
                    version_after=revision.version
                )
            
            await self.db.commit()
            
            logger.info(
                "Revision updated",
                revision_id=str(revision_id),
                editor_id=str(user_id),
                changes=len(changes)
            )
            
            return await self._build_revision_response(revision)
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Revision update failed", error=str(e))
            raise InvalidStateError("Failed to update revision")
    
    async def delete_revision(
        self,
        revision_id: UUID,
        user_id: UUID,
        user_role: Role
    ) -> bool:
        """Delete a revision (only for draft status)"""
        revision = await self.revision_repo.get(revision_id)
        if not revision:
            raise NotFoundError(f"Revision {revision_id} not found")
        
        # Only draft revisions can be deleted
        if revision.status != RevisionStatus.DRAFT:
            raise InvalidStateError("Only draft revisions can be deleted")
        
        # Check permissions
        if revision.proposer_id != user_id and user_role != Role.ADMIN:
            raise AuthorizationError("You don't have permission to delete this revision")
        
        await self.revision_repo.delete(revision_id)
        await self.db.commit()
        
        logger.info(
            "Revision deleted",
            revision_id=str(revision_id),
            user_id=str(user_id)
        )
        
        return True
    
    async def list_revisions(
        self,
        filters: RevisionFilter,
        skip: int = 0,
        limit: int = 20
    ) -> List[RevisionResponse]:
        """List revisions with filters"""
        # Build query based on filters
        revisions = []
        
        if filters.status:
            revisions = await self.revision_repo.get_by_status(filters.status)
        elif filters.proposer_id:
            revisions = await self.revision_repo.get_by_proposer(filters.proposer_id)
        elif filters.target_article_id:
            revisions = await self.revision_repo.get_by_article(filters.target_article_id)
        else:
            # Get all with pagination
            revisions = await self.revision_repo.get_all(skip=skip, limit=limit)
        
        # Apply additional filters if needed
        if filters.created_after:
            revisions = [r for r in revisions if r.created_at >= filters.created_after]
        if filters.created_before:
            revisions = [r for r in revisions if r.created_at <= filters.created_before]
        
        # Apply pagination
        revisions = revisions[skip:skip + limit]
        
        return [await self._build_revision_response(r) for r in revisions]
    
    async def get_revisions_by_article(self, article_id: str) -> List[RevisionResponse]:
        """Get revisions by article ID"""
        revisions = await self.revision_repo.get_by_article(article_id)
        return [await self._build_revision_response(r) for r in revisions]
    
    async def get_revisions_by_proposer(self, proposer_id: UUID) -> List[RevisionResponse]:
        """Get revisions by proposer ID"""
        revisions = await self.revision_repo.get_by_proposer(proposer_id)
        return [await self._build_revision_response(r) for r in revisions]
    
    async def calculate_diff(self, revision_id: UUID) -> RevisionDetailDiff:
        """Calculate detailed diff for a revision"""
        revision = await self.revision_repo.get(revision_id)
        if not revision:
            raise NotFoundError(f"Revision {revision_id} not found")
        
        fields = [
            'title', 'info_category', 'keywords', 'importance',
            'target', 'question', 'answer', 'additional_comment',
            'publish_start', 'publish_end'
        ]
        
        diffs = []
        modified_fields = []
        
        for field in fields:
            before_value = getattr(revision, f'before_{field}', None)
            after_value = getattr(revision, f'after_{field}', None)
            
            is_modified = after_value is not None and before_value != after_value
            
            if is_modified:
                modified_fields.append(field)
            
            diffs.append(RevisionDiff(
                field=field,
                before=before_value,
                after=after_value if after_value is not None else before_value,
                is_modified=is_modified
            ))
        
        return RevisionDetailDiff(
            revision_id=revision_id,
            modified_fields=modified_fields,
            diffs=diffs
        )
    
    def _can_edit_revision(
        self,
        revision: Revision,
        user_id: UUID,
        user_role: Role
    ) -> bool:
        """Check if user can edit revision"""
        # Admin can always edit
        if user_role == Role.ADMIN:
            return True
        
        # Check based on status
        if revision.status == RevisionStatus.DRAFT:
            return revision.proposer_id == user_id
        elif revision.status in [RevisionStatus.UNDER_REVIEW, RevisionStatus.REVISION_REQUESTED]:
            return user_role in [Role.APPROVER, Role.SUPERVISOR] or revision.proposer_id == user_id
        else:
            return False
    
    async def _build_revision_response(self, revision: Revision) -> RevisionResponse:
        """Build revision response with additional info"""
        # Get related data - always fetch explicitly in async context
        proposer = await self.user_repo.get(revision.proposer_id)
        approver = await self.user_repo.get(revision.approver_id) if revision.approver_id else None
        article = await self.article_repo.get_by_article_id(revision.target_article_id)
        
        # Get current datetime for fallback
        current_time = datetime.utcnow()
        
        # Build response with explicit field mapping, avoiding lazy loading
        response_data = {
            'id': revision.id,
            'target_article_id': revision.target_article_id,
            'proposer_id': revision.proposer_id,
            'approver_id': revision.approver_id,
            'status': revision.status,
            'reason': revision.reason,
            'before_title': revision.before_title,
            'after_title': revision.after_title,
            'before_info_category': revision.before_info_category,
            'after_info_category': revision.after_info_category,
            'before_keywords': revision.before_keywords,
            'after_keywords': revision.after_keywords,
            'before_importance': revision.before_importance,
            'after_importance': revision.after_importance,
            'before_target': revision.before_target,
            'after_target': revision.after_target,
            'before_question': revision.before_question,
            'after_question': revision.after_question,
            'before_answer': revision.before_answer,
            'after_answer': revision.after_answer,
            'before_additional_comment': revision.before_additional_comment,
            'after_additional_comment': revision.after_additional_comment,
            'before_publish_start': revision.before_publish_start,
            'after_publish_start': revision.after_publish_start,
            'before_publish_end': revision.before_publish_end,
            'after_publish_end': revision.after_publish_end,
            'version': revision.version if hasattr(revision, 'version') and revision.version else 1,
            'created_at': current_time,
            'updated_at': current_time,
            'proposer_name': proposer.full_name if proposer else None,
            'approver_name': approver.full_name if approver else None,
            'article_title': article.title if article else None,
            'modified_fields': revision.get_modified_fields() if hasattr(revision, 'get_modified_fields') else []
        }
        
        return RevisionResponse(**response_data)
    
    async def submit_for_review(
        self,
        revision_id: UUID,
        user_id: UUID,
        user_role: Role
    ) -> RevisionResponse:
        """Submit revision for review"""
        revision = await self.revision_repo.get(revision_id)
        if not revision:
            raise NotFoundError(f"Revision {revision_id} not found")
        
        # Check if revision can be submitted
        if revision.status != RevisionStatus.DRAFT:
            raise InvalidStateError("Only draft revisions can be submitted for review")
        
        # Check permissions (only proposer can submit)
        if revision.proposer_id != user_id and user_role != Role.ADMIN:
            raise AuthorizationError("Only the proposer can submit revision for review")
        
        # Update status
        revision.status = RevisionStatus.UNDER_REVIEW
        revision.submitted_at = datetime.utcnow()
        
        try:
            await self.db.flush()
            await self.db.commit()
            
            # Send notifications to approvers
            if self.notification_service:
                try:
                    # Get all approvers (users who can approve revisions)
                    approvers = await self.user_repo.get_approvers()
                    
                    if approvers:
                        await self.notification_service.notify_revision_submitted(
                            revision, approvers
                        )
                except Exception as e:
                    # Log error but don't fail the submission process
                    logger.error(f"Failed to send submission notifications: {e}")
            
            logger.info(
                "Revision submitted for review",
                revision_id=str(revision_id),
                user_id=str(user_id)
            )
            
            return await self._build_revision_response(revision)
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Revision submission failed", error=str(e))
            raise InvalidStateError("Failed to submit revision for review")