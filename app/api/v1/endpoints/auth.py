from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import TokenResponse, UserLogin, RefreshTokenRequest
from app.services.auth import AuthService
from app.services.user import UserService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """ユーザーログイン"""
    auth_service = AuthService(db)
    
    # Extract client information
    user_agent = request.headers.get("User-Agent", "Unknown")
    ip_address = request.client.host if request.client else "Unknown"
    
    # Check for forwarded headers
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        ip_address = real_ip.strip()
    
    try:
        tokens, user = await auth_service.login(
            credentials, 
            user_agent=user_agent,
            ip_address=ip_address
        )
        
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
    session_id: str = None,
    db: AsyncSession = Depends(get_db)
):
    """ユーザーログアウト"""
    auth_service = AuthService(db)
    
    success = await auth_service.logout(access_token, refresh_token, session_id)
    
    if success:
        return {"message": "Successfully logged out"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get("/sessions")
async def get_user_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """現在のユーザーのセッション一覧取得"""
    auth_service = AuthService(db)
    
    try:
        sessions = await auth_service.get_user_sessions(current_user.id)
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get sessions"
        )


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """特定のセッションを無効化"""
    auth_service = AuthService(db)
    
    success = await auth_service.revoke_user_session(current_user.id, session_id)
    
    if success:
        return {"message": "Session revoked successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already revoked"
        )


@router.post("/logout-all")
async def logout_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """全セッションからログアウト"""
    auth_service = AuthService(db)
    
    success = await auth_service.logout_all_sessions(current_user.id)
    
    if success:
        return {"message": "All sessions logged out successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout all sessions"
        )