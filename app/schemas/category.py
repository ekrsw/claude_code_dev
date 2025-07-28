from datetime import datetime
from pydantic import BaseModel, Field


class InfoCategoryBase(BaseModel):
    """Base info category schema"""
    code: str = Field(..., description="Category code")
    display_name: str = Field(..., description="Display name")
    display_order: int = Field(..., description="Display order")
    is_active: bool = Field(default=True, description="Active status")


class InfoCategoryResponse(InfoCategoryBase):
    """Info category response schema"""
    id: int = Field(..., description="Category ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True