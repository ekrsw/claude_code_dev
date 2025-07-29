"""
Pydantic schemas for approval functionality
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.constants.enums import ApprovalAction


class ApprovalHistoryBase(BaseModel):
    """Base approval history schema"""
    revision_id: UUID
    actor_id: UUID
    action: ApprovalAction
    comment: Optional[str] = None


class ApprovalHistoryCreate(ApprovalHistoryBase):
    """Schema for creating approval history"""
    pass


class ApprovalHistoryResponse(ApprovalHistoryBase):
    """Schema for approval history response"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    # Actor information
    actor_name: Optional[str] = Field(None, description="Name of the actor")
    actor_username: Optional[str] = Field(None, description="Username of the actor")
    
    class Config:
        from_attributes = True


class ApprovalRequest(BaseModel):
    """Schema for approval request"""
    comment: Optional[str] = Field(None, description="Optional approval comment")


class RejectionRequest(BaseModel):
    """Schema for rejection request"""
    comment: str = Field(..., description="Required rejection comment", min_length=1)


class WithdrawalRequest(BaseModel):
    """Schema for withdrawal request"""
    comment: Optional[str] = Field(None, description="Optional withdrawal comment")


class ModificationRequest(BaseModel):
    """Schema for modification request"""
    instruction_text: str = Field(..., description="Instruction text for modification", min_length=1)
    required_fields: Optional[list[str]] = Field(None, description="List of fields that need modification")
    priority: str = Field("normal", description="Priority level", pattern="^(low|normal|high|urgent)$")


class ApprovalStatusCounts(BaseModel):
    """Schema for approval status counts"""
    under_review: int = Field(0, description="Number of revisions under review")
    revision_requested: int = Field(0, description="Number of revisions with modification requested")
    approved: int = Field(0, description="Number of approved revisions")
    rejected: int = Field(0, description="Number of rejected revisions")


class ApprovalSummary(BaseModel):
    """Schema for approval summary"""
    revision_id: UUID
    current_status: str
    approver_id: Optional[UUID] = None
    approver_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_comment: Optional[str] = None
    history_count: int = 0
    latest_action: Optional[ApprovalAction] = None
    latest_action_at: Optional[datetime] = None