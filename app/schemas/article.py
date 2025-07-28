from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ArticleBase(BaseModel):
    """Base article schema"""
    article_id: str = Field(..., description="Article ID")
    title: str = Field(..., description="Article title")
    info_category_code: Optional[str] = Field(None, description="Category code")
    keywords: Optional[str] = Field(None, description="Keywords")
    importance: bool = Field(default=False, description="Importance flag")
    target: Optional[str] = Field(None, description="Target audience")


class ArticleResponse(ArticleBase):
    """Article response schema"""
    id: UUID = Field(..., description="Internal ID")
    article_number: Optional[str] = Field(None, description="Article number")
    question: Optional[str] = Field(None, description="Question")
    answer: Optional[str] = Field(None, description="Answer")
    additional_comment: Optional[str] = Field(None, description="Additional comment")
    publish_start: Optional[datetime] = Field(None, description="Publish start date")
    publish_end: Optional[datetime] = Field(None, description="Publish end date")
    approval_group: Optional[str] = Field(None, description="Approval group")
    is_active: bool = Field(..., description="Active status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class ArticleListResponse(BaseModel):
    """Article list item response"""
    id: UUID = Field(..., description="Internal ID")
    article_id: str = Field(..., description="Article ID")
    title: str = Field(..., description="Article title")
    info_category_code: Optional[str] = Field(None, description="Category code")
    importance: bool = Field(..., description="Importance flag")
    target: Optional[str] = Field(None, description="Target audience")
    is_active: bool = Field(..., description="Active status")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True


class ArticleFilter(BaseModel):
    """Article filter parameters"""
    search: Optional[str] = Field(None, description="Search term")
    category: Optional[str] = Field(None, description="Category filter")
    importance: Optional[bool] = Field(None, description="Importance filter")
    target: Optional[str] = Field(None, description="Target filter")
    is_active: Optional[bool] = Field(default=True, description="Active status filter")