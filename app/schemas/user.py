from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator

from app.constants.enums import Role
from app.schemas.common import PaginatedResponse


class UserBase(BaseModel):
    """Base user schema"""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="Email address")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name")


class UserCreate(UserBase):
    """User creation schema"""
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    
    @validator("username")
    def validate_username(cls, v):
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, hyphens, and underscores")
        return v.lower()


class UserUpdate(BaseModel):
    """User update schema"""
    email: Optional[EmailStr] = Field(None, description="Email address")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name")
    is_active: Optional[bool] = Field(None, description="Account status")


class UserProfileUpdate(BaseModel):
    """User profile update schema"""
    full_name: Optional[str] = Field(None, max_length=255, description="Full name")
    sweet_name: Optional[str] = Field(None, max_length=100, description="Sweet system name")
    ctstage_name: Optional[str] = Field(None, max_length=100, description="Ctstage system name")


class UserRoleUpdate(BaseModel):
    """User role update schema (admin only)"""
    role: Role = Field(..., description="User role")
    is_sv: bool = Field(default=False, description="Supervisor flag")


class UserPasswordChange(BaseModel):
    """Password change schema"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")


class UserLogin(BaseModel):
    """User login schema"""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class UserResponse(UserBase):
    """User response schema"""
    id: UUID = Field(..., description="User ID")
    role: Role = Field(..., description="User role")
    is_sv: bool = Field(..., description="Supervisor flag")
    is_active: bool = Field(..., description="Account status")
    sweet_name: Optional[str] = Field(None, description="Sweet system name")
    ctstage_name: Optional[str] = Field(None, description="Ctstage system name")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """User list item response"""
    id: UUID = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: EmailStr = Field(..., description="Email address")
    full_name: Optional[str] = Field(None, description="Full name")
    role: Role = Field(..., description="User role")
    is_sv: bool = Field(..., description="Supervisor flag")
    is_active: bool = Field(..., description="Account status")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """Token schema"""
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    token_type: str = Field(default="bearer", description="Token type")


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: UserResponse = Field(..., description="User information")


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""
    refresh_token: str = Field(..., description="Refresh token")


class LogoutRequest(BaseModel):
    """Logout request schema"""
    access_token: str = Field(..., description="Access token to blacklist")
    refresh_token: Optional[str] = Field(None, description="Refresh token to blacklist")