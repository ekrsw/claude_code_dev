"""
Basic validation tests for revision functionality
"""
import pytest
from uuid import uuid4

from app.constants.enums import RevisionStatus, Role
from app.schemas.revision import RevisionCreate, RevisionModifications


class TestRevisionBasics:
    """Basic tests for revision functionality"""
    
    def test_revision_create_schema_validation(self):
        """Test revision creation schema validation"""
        # Valid data
        valid_data = RevisionCreate(
            target_article_id="ARTICLE001",
            reason="Need to update for accuracy",
            modifications=RevisionModifications(
                title="Updated Title",
                answer="Updated Answer"
            )
        )
        
        assert valid_data.target_article_id == "ARTICLE001"
        assert len(valid_data.reason) >= 10
        assert valid_data.modifications.title == "Updated Title"
    
    def test_revision_create_schema_validation_short_reason(self):
        """Test validation fails for short reason"""
        with pytest.raises(ValueError):
            RevisionCreate(
                target_article_id="ARTICLE001",
                reason="Short",  # Too short
                modifications=RevisionModifications(title="Test")
            )
    
    def test_revision_create_schema_validation_no_modifications(self):
        """Test validation fails when no modifications are provided"""
        with pytest.raises(ValueError):
            RevisionCreate(
                target_article_id="ARTICLE001",
                reason="Need to update for accuracy",
                modifications=RevisionModifications()  # No modifications
            )
    
    def test_revision_modifications_category_validation(self):
        """Test info_category validation"""
        # Valid 2-character code
        valid_mods = RevisionModifications(
            info_category="01",
            title="Test"
        )
        assert valid_mods.info_category == "01"
        
        # Invalid code length
        with pytest.raises(ValueError):
            RevisionModifications(
                info_category="001",  # Too long
                title="Test"
            )
    
    def test_revision_status_enum(self):
        """Test revision status enumeration"""
        assert RevisionStatus.DRAFT == "draft"
        assert RevisionStatus.UNDER_REVIEW == "under_review"
        assert RevisionStatus.APPROVED == "approved"
        assert RevisionStatus.REJECTED == "rejected"
    
    def test_role_enum(self):
        """Test role enumeration"""
        assert Role.GENERAL == "general"
        assert Role.SUPERVISOR == "supervisor"
        assert Role.APPROVER == "approver"
        assert Role.ADMIN == "admin"


if __name__ == "__main__":
    pytest.main([__file__])