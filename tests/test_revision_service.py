"""
Basic tests for RevisionService functionality
"""
import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from datetime import datetime

from app.services.revision import RevisionService
from app.schemas.revision import RevisionCreate, RevisionModifications
from app.constants.enums import RevisionStatus, Role
from app.models.revision import Revision
from app.models.article import Article


class TestRevisionService:
    """Test cases for RevisionService"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_db = Mock()
        self.service = RevisionService(self.mock_db)
        
        # Mock repositories
        self.service.revision_repo = Mock()
        self.service.article_repo = Mock()
        self.service.user_repo = Mock()
        
        # Sample data
        self.article_id = "ARTICLE001"
        self.user_id = uuid4()
        self.revision_id = uuid4()
        
        self.sample_article = Article(
            article_id=self.article_id,
            title="Original Title",
            info_category_code="01",
            keywords="test,sample",
            importance=False,
            target="社内向け",
            question="Original Question?",
            answer="Original Answer",
            additional_comment="Original Comment"
        )
        
        self.sample_revision_data = RevisionCreate(
            target_article_id=self.article_id,
            reason="Need to update the content for accuracy",
            modifications=RevisionModifications(
                title="Updated Title",
                answer="Updated Answer"
            )
        )
    
    @pytest.mark.asyncio
    async def test_create_revision_success(self):
        """Test successful revision creation"""
        # Setup mocks
        self.service.article_repo.get_by_article_id = AsyncMock(return_value=self.sample_article)
        self.service.revision_repo.check_active_revision_exists = AsyncMock(return_value=False)
        self.service.revision_repo.create = AsyncMock()
        self.service.db.commit = AsyncMock()
        
        # Mock the revision creation
        created_revision = Revision(
            id=self.revision_id,
            target_article_id=self.article_id,
            proposer_id=self.user_id,
            status=RevisionStatus.DRAFT,
            reason=self.sample_revision_data.reason,
            before_title=self.sample_article.title,
            after_title=self.sample_revision_data.modifications.title
        )
        self.service.revision_repo.create.return_value = created_revision
        
        # Mock _build_revision_response
        self.service._build_revision_response = AsyncMock()
        
        # Execute
        await self.service.create_revision(self.sample_revision_data, self.user_id)
        
        # Verify
        self.service.article_repo.get_by_article_id.assert_called_once_with(self.article_id)
        self.service.revision_repo.check_active_revision_exists.assert_called_once_with(self.article_id)
        self.service.revision_repo.create.assert_called_once()
        self.service.db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_revision_article_not_found(self):
        """Test revision creation with non-existent article"""
        from app.core.exceptions import NotFoundError
        
        # Setup mocks
        self.service.article_repo.get_by_article_id = AsyncMock(return_value=None)
        
        # Execute and verify
        with pytest.raises(NotFoundError):
            await self.service.create_revision(self.sample_revision_data, self.user_id)
    
    @pytest.mark.asyncio
    async def test_create_revision_conflict_existing_active(self):
        """Test revision creation when active revision already exists"""
        from app.core.exceptions import ConflictError
        
        # Setup mocks
        self.service.article_repo.get_by_article_id = AsyncMock(return_value=self.sample_article)
        self.service.revision_repo.check_active_revision_exists = AsyncMock(return_value=True)
        
        # Execute and verify
        with pytest.raises(ConflictError):
            await self.service.create_revision(self.sample_revision_data, self.user_id)
    
    def test_can_edit_revision_admin(self):
        """Test that admin can always edit revisions"""
        revision = Revision(
            proposer_id=uuid4(),  # Different user
            status=RevisionStatus.APPROVED  # Any status
        )
        
        result = self.service._can_edit_revision(revision, self.user_id, Role.ADMIN)
        assert result is True
    
    def test_can_edit_revision_proposer_draft(self):
        """Test that proposer can edit draft revisions"""
        revision = Revision(
            proposer_id=self.user_id,
            status=RevisionStatus.DRAFT
        )
        
        result = self.service._can_edit_revision(revision, self.user_id, Role.GENERAL)
        assert result is True
    
    def test_can_edit_revision_proposer_approved_cannot(self):
        """Test that proposer cannot edit approved revisions"""
        revision = Revision(
            proposer_id=self.user_id,
            status=RevisionStatus.APPROVED
        )
        
        result = self.service._can_edit_revision(revision, self.user_id, Role.GENERAL)
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__])