from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.user import TokenResponse, UserLogin, RefreshTokenRequest
from app.services.auth import AuthService
from app.services.user import UserService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """ユーザーログイン"""
    auth_service = AuthService(db)
    
    try:
        tokens, user = await auth_service.login(credentials)
        
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """トークンリフレッシュ"""
    auth_service = AuthService(db)
    user_service = UserService(db)
    
    try:
        new_tokens = await auth_service.refresh_token(refresh_request.refresh_token)
        
        # Get user info for response
        payload = auth_service.verify_token(new_tokens.access_token)
        user = await user_service.get_user(payload["user_id"])
        
        return TokenResponse(
            access_token=new_tokens.access_token,
            refresh_token=new_tokens.refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post("/logout")
async def logout(
    access_token: str,
    refresh_token: str = None,
    db: AsyncSession = Depends(get_db)
):
    """ユーザーログアウト"""
    auth_service = AuthService(db)
    
    success = await auth_service.logout(access_token, refresh_token)
    
    if success:
        return {"message": "Successfully logged out"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )