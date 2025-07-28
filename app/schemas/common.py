from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(default=1, ge=1, description="Page number")
    size: int = Field(default=20, ge=1, le=100, description="Page size")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database query"""
        return (self.page - 1) * self.size


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper"""
    items: List[T] = Field(description="List of items")
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    size: int = Field(description="Page size")
    pages: int = Field(description="Total number of pages")
    
    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        size: int
    ) -> "PaginatedResponse[T]":
        """Create paginated response"""
        pages = (total + size - 1) // size  # Ceiling division
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages
        )


class ErrorResponse(BaseModel):
    """Error response model"""
    error: "ErrorDetail"


class ErrorDetail(BaseModel):
    """Error detail model"""
    code: str = Field(description="Error code")
    message: str = Field(description="Error message")
    details: Optional[List[str]] = Field(default=None, description="Additional error details")


class SuccessResponse(BaseModel):
    """Success response model"""
    message: str = Field(description="Success message")
    data: Optional[dict] = Field(default=None, description="Additional data")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(description="Health status")
    version: str = Field(description="API version")
    timestamp: str = Field(description="Current timestamp")