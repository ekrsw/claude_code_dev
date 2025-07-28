from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.constants.enums import RevisionStatus


class RevisionCreate(BaseModel):
    """Revision creation schema"""
    target_article_id: str = Field(..., description="Target article ID")
    reason: str = Field(..., description="Reason for revision")
    # Modification fields will be added later
    

class RevisionUpdate(BaseModel):
    """Revision update schema"""
    reason: Optional[str] = Field(None, description="Reason for revision")
    # Modification fields will be added later


class RevisionResponse(BaseModel):
    """Revision response schema"""
    id: UUID = Field(..., description="Revision ID")
    target_article_id: str = Field(..., description="Target article ID")
    proposer_id: UUID = Field(..., description="Proposer ID")
    status: RevisionStatus = Field(..., description="Revision status")
    reason: str = Field(..., description="Reason for revision")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class RevisionListResponse(BaseModel):
    """Revision list item response"""
    id: UUID = Field(..., description="Revision ID")
    target_article_id: str = Field(..., description="Target article ID")
    status: RevisionStatus = Field(..., description="Revision status")
    reason: str = Field(..., description="Reason for revision")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True


class RevisionFilter(BaseModel):
    """Revision filter parameters"""
    status: Optional[RevisionStatus] = Field(None, description="Status filter")
    proposer_id: Optional[UUID] = Field(None, description="Proposer filter")


class RevisionDiff(BaseModel):
    """Revision diff response"""
    revision_id: UUID = Field(..., description="Revision ID")
    modified_fields: List[str] = Field(..., description="List of modified fields")
    # Detailed diff will be added later