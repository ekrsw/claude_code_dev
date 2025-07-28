from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user, get_current_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate, UserResponse, UserUpdate, UserProfileUpdate, 
    UserRoleUpdate, UserPasswordChange, PaginatedResponse
)
from app.schemas.common import PaginationParams
from app.services.user import UserService

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """ユーザー登録"""
    user_service = UserService(db)
    
    try:
        user = await user_service.create_user(user_data)
        return user
    except Exception as e:
        if "already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """現在のユーザー情報取得"""
    return current_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ユーザー情報取得"""
    user_service = UserService(db)
    
    # Users can only view themselves unless they are admin
    if user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )
    
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ユーザー情報更新"""
    user_service = UserService(db)
    
    try:
        user = await user_service.update_user(user_id, user_data, current_user)
        return user
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/{user_id}/profile", response_model=UserResponse)
async def update_user_profile(
    user_id: UUID,
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ユーザープロファイル更新"""
    user_service = UserService(db)
    
    try:
        user = await user_service.update_profile(user_id, profile_data, current_user)
        return user
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: UUID,
    role_data: UserRoleUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """ユーザーロール更新（管理者のみ）"""
    user_service = UserService(db)
    
    try:
        user = await user_service.update_role(user_id, role_data, current_user)
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{user_id}/change-password")
async def change_password(
    user_id: UUID,
    password_data: UserPasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """パスワード変更"""
    user_service = UserService(db)
    
    try:
        success = await user_service.change_password(
            user_id,
            password_data.current_password,
            password_data.new_password,
            current_user
        )
        
        if success:
            return {"message": "Password changed successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password change failed"
            )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=PaginatedResponse[UserResponse])
async def list_users(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """ユーザー一覧取得（管理者のみ）"""
    user_service = UserService(db)
    
    users, total = await user_service.get_users(
        skip=pagination.offset,
        limit=pagination.size
    )
    
    return PaginatedResponse.create(
        items=users,
        total=total,
        page=pagination.page,
        size=pagination.size
    )