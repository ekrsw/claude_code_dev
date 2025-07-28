from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.constants.enums import RevisionStatus, Priority


class RevisionModifications(BaseModel):
    """修正内容のモデル"""
    title: Optional[str] = None
    info_category: Optional[str] = None
    keywords: Optional[List[str]] = None
    importance: Optional[bool] = None
    target: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None
    additional_comment: Optional[str] = None
    publish_start: Optional[datetime] = None
    publish_end: Optional[datetime] = None
    
    @field_validator('info_category')
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) != 2:
            raise ValueError('情報カテゴリコードは2文字である必要があります')
        return v


class RevisionCreate(BaseModel):
    """Revision creation schema"""
    target_article_id: str = Field(..., description="Target article ID")
    reason: str = Field(..., min_length=10, description="Reason for revision")
    modifications: RevisionModifications = Field(..., description="Modification details")
    
    @field_validator('modifications')
    @classmethod
    def validate_modifications(cls, v: RevisionModifications) -> RevisionModifications:
        # 少なくとも1つのフィールドが修正されている必要がある
        if not any(value is not None for value in v.model_dump().values()):
            raise ValueError('少なくとも1つのフィールドを修正してください')
        return v
    

class RevisionUpdate(BaseModel):
    """Revision update schema"""
    reason: Optional[str] = Field(None, min_length=10, description="Reason for revision")
    modifications: Optional[RevisionModifications] = Field(None, description="Modification details")


class RevisionResponse(BaseModel):
    """Revision response schema"""
    id: UUID = Field(..., description="Revision ID")
    target_article_id: str = Field(..., description="Target article ID")
    proposer_id: UUID = Field(..., description="Proposer ID")
    status: RevisionStatus = Field(..., description="Revision status")
    reason: str = Field(..., description="Reason for revision")
    version: int = Field(..., description="Version number")
    
    # 修正前後のフィールド
    before_title: Optional[str] = None
    after_title: Optional[str] = None
    before_info_category: Optional[str] = None
    after_info_category: Optional[str] = None
    before_keywords: Optional[str] = None
    after_keywords: Optional[str] = None
    before_importance: Optional[bool] = None
    after_importance: Optional[bool] = None
    before_publish_start: Optional[datetime] = None
    after_publish_start: Optional[datetime] = None
    before_publish_end: Optional[datetime] = None
    after_publish_end: Optional[datetime] = None
    before_target: Optional[str] = None
    after_target: Optional[str] = None
    before_question: Optional[str] = None
    after_question: Optional[str] = None
    before_answer: Optional[str] = None
    after_answer: Optional[str] = None
    before_additional_comment: Optional[str] = None
    after_additional_comment: Optional[str] = None
    
    # 承認情報
    approver_id: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    approval_comment: Optional[str] = None
    
    # レビュー期間
    review_start_date: Optional[datetime] = None
    review_deadline_date: Optional[datetime] = None
    
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    # 追加情報
    proposer_name: Optional[str] = None
    approver_name: Optional[str] = None
    article_title: Optional[str] = None
    modified_fields: List[str] = Field(default_factory=list, description="List of modified fields")
    
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
    target_article_id: Optional[str] = Field(None, description="Target article filter")
    created_after: Optional[datetime] = Field(None, description="Created after filter")
    created_before: Optional[datetime] = Field(None, description="Created before filter")


class RevisionDiff(BaseModel):
    """Revision diff response"""
    field: str = Field(..., description="Field name")
    before: Any = Field(..., description="Value before modification")
    after: Any = Field(..., description="Value after modification")
    is_modified: bool = Field(..., description="Whether the field is modified")


class RevisionDetailDiff(BaseModel):
    """Detailed revision diff response"""
    revision_id: UUID = Field(..., description="Revision ID")
    modified_fields: List[str] = Field(..., description="List of modified fields")
    diffs: List[RevisionDiff] = Field(..., description="Detailed diffs")


# 修正指示関連スキーマ
class ModificationInstructionCreate(BaseModel):
    """修正指示作成スキーマ"""
    instruction_text: str = Field(..., min_length=10, description="Instruction text")
    required_fields: Optional[List[str]] = Field(None, description="Fields requiring modification")
    priority: Priority = Field(Priority.NORMAL, description="Priority level")
    due_date: Optional[datetime] = Field(None, description="Due date")


class ModificationInstructionResponse(BaseModel):
    """修正指示レスポンススキーマ"""
    id: UUID = Field(..., description="Instruction ID")
    revision_id: UUID = Field(..., description="Revision ID")
    instructor_id: UUID = Field(..., description="Instructor ID")
    instruction_text: str = Field(..., description="Instruction text")
    required_fields: Optional[List[str]] = Field(None, description="Fields requiring modification")
    priority: Priority = Field(..., description="Priority level")
    due_date: Optional[datetime] = Field(None, description="Due date")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    resolution_comment: Optional[str] = Field(None, description="Resolution comment")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    # 追加情報
    instructor_name: Optional[str] = None
    
    class Config:
        from_attributes = True