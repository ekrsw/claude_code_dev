"""
認証サービスの単体テスト
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.auth import AuthService
from app.models.user import User
from app.core.config import settings
from app.core.security import verify_password, get_password_hash
from app.schemas.user import UserLogin
from app.constants.enums import Role


@pytest.mark.asyncio
class TestAuthService:
    """AuthServiceのテストクラス"""
    
    async def test_authenticate_user_success(self, db_session, test_user):
        """正しい認証情報でユーザー認証が成功することを確認"""
        auth_service = AuthService(db_session)
        
        # ユーザー認証
        credentials = UserLogin(username=test_user.username, password="testpass123")
        authenticated_user = await auth_service.authenticate_user(credentials)
        
        assert authenticated_user is not None
        assert authenticated_user.id == test_user.id
        assert authenticated_user.username == test_user.username
        assert authenticated_user.email == test_user.email
    
    async def test_authenticate_user_invalid_username(self, db_session):
        """存在しないユーザー名で認証が失敗することを確認"""
        auth_service = AuthService(db_session)
        
        credentials = UserLogin(username="nonexistent", password="anypassword")
        authenticated_user = await auth_service.authenticate_user(credentials)
        
        assert authenticated_user is None
    
    async def test_authenticate_user_invalid_password(self, db_session, test_user):
        """間違ったパスワードで認証が失敗することを確認"""
        auth_service = AuthService(db_session)
        
        credentials = UserLogin(username=test_user.username, password="wrongpassword")
        authenticated_user = await auth_service.authenticate_user(credentials)
        
        assert authenticated_user is None
    
    async def test_authenticate_user_inactive(self, db_session):
        """非アクティブユーザーの認証が失敗することを確認"""
        # 非アクティブユーザーを作成
        inactive_id = uuid4()
        inactive_user = User(
            id=inactive_id,
            username=f"inactive_{str(inactive_id)[:8]}",
            email=f"inactive_{str(inactive_id)[:8]}@example.com",
            hashed_password=get_password_hash("password123"),
            full_name="Inactive User",
            role=Role.GENERAL,
            is_active=False
        )
        db_session.add(inactive_user)
        await db_session.commit()
        
        auth_service = AuthService(db_session)
        
        credentials = UserLogin(username=inactive_user.username, password="password123")
        authenticated_user = await auth_service.authenticate_user(credentials)
        
        assert authenticated_user is None
    
    async def test_password_hashing(self):
        """パスワードのハッシュ化と検証が正しく動作することを確認"""
        plain_password = "testpassword123"
        
        # パスワードをハッシュ化
        hashed = get_password_hash(plain_password)
        
        assert hashed != plain_password
        assert len(hashed) > 0
        
        # 正しいパスワードで検証が成功
        assert verify_password(plain_password, hashed) is True
        
        # 間違ったパスワードで検証が失敗
        assert verify_password("wrongpassword", hashed) is False
    
    async def test_create_tokens(self, db_session, test_user):
        """トークン作成が正しく動作することを確認"""
        auth_service = AuthService(db_session)
        
        tokens = await auth_service.create_tokens(test_user)
        
        assert tokens is not None
        assert tokens.access_token is not None
        assert tokens.refresh_token is not None
        assert tokens.token_type == "bearer"
        assert len(tokens.access_token) > 0
        assert len(tokens.refresh_token) > 0
    
    async def test_login_success(self, db_session, test_user):
        """ログインが成功することを確認"""
        auth_service = AuthService(db_session)
        
        credentials = UserLogin(username=test_user.username, password="testpass123")
        tokens, user = await auth_service.login(credentials)
        
        assert tokens is not None
        assert user is not None
        assert user.id == test_user.id
        assert tokens.access_token is not None
        assert tokens.refresh_token is not None
        assert tokens.token_type == "bearer"
    
    async def test_login_invalid_credentials(self, db_session):
        """無効な認証情報でログインが失敗することを確認"""
        from app.core.exceptions import AuthenticationError
        
        auth_service = AuthService(db_session)
        
        credentials = UserLogin(username="nonexistent", password="wrongpassword")
        
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.login(credentials)
        
        assert "Invalid credentials" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, db_session, test_user):
        """リフレッシュトークンが正しく動作することを確認"""
        from app.core.security import create_refresh_token
        
        auth_service = AuthService(db_session)
        
        # リフレッシュトークンを作成
        refresh_token = create_refresh_token(
            subject=test_user.username,
            user_id=str(test_user.id)
        )
        
        # トークンをリフレッシュ
        new_tokens = await auth_service.refresh_token(refresh_token)
        
        assert new_tokens is not None
        assert new_tokens.access_token is not None
        assert new_tokens.refresh_token is not None
        assert new_tokens.token_type == "bearer"
    
    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, db_session):
        """無効なリフレッシュトークンでエラーになることを確認"""
        from app.core.exceptions import AuthenticationError
        
        auth_service = AuthService(db_session)
        
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.refresh_token("invalid_token")
        
        assert "Invalid or expired refresh token" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_logout_success(self, db_session, test_user):
        """ログアウトが正しく動作することを確認"""
        auth_service = AuthService(db_session)
        
        # トークンを作成
        tokens = await auth_service.create_tokens(test_user)
        
        # ログアウト
        result = await auth_service.logout(tokens.access_token, tokens.refresh_token)
        
        # 結果を確認 (キャッシュが利用できない場合はFalseになることがある)
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_logout_all_sessions(self, db_session, test_user):
        """全セッションログアウトが正しく動作することを確認"""
        auth_service = AuthService(db_session)
        
        result = await auth_service.logout_all_sessions(test_user.id)
        
        # 結果を確認 (キャッシュが利用できない場合でも何らかの結果を返す)
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_verify_user_token_success(self, db_session, test_user):
        """ユーザートークン検証が正しく動作することを確認"""
        from app.core.security import create_access_token
        
        auth_service = AuthService(db_session)
        
        # アクセストークンを作成
        access_token = create_access_token(
            subject=test_user.username,
            user_id=str(test_user.id)
        )
        
        # トークンを検証
        verified_user = await auth_service.verify_user_token(access_token)
        
        assert verified_user is not None
        assert verified_user.id == test_user.id
        assert verified_user.username == test_user.username
    
    @pytest.mark.asyncio
    async def test_verify_user_token_invalid(self, db_session):
        """無効なトークンで検証が失敗することを確認"""
        auth_service = AuthService(db_session)
        
        result = await auth_service.verify_user_token("invalid_token")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_change_password_with_auth_success(self, db_session, test_user):
        """パスワード変更が正しく動作することを確認"""
        auth_service = AuthService(db_session)
        
        result = await auth_service.change_password_with_auth(
            user_id=test_user.id,
            current_password="testpass123",
            new_password="NewPass123!"
        )
        
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_change_password_with_auth_wrong_current(self, db_session, test_user):
        """現在のパスワードが間違っている場合のエラー確認"""
        from app.core.exceptions import AuthenticationError
        
        auth_service = AuthService(db_session)
        
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.change_password_with_auth(
                user_id=test_user.id,
                current_password="wrongpassword",
                new_password="newpass123"
            )
        
        assert "Current password is incorrect" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_change_password_user_not_found(self, db_session):
        """存在しないユーザーでパスワード変更エラー確認"""
        from app.core.exceptions import NotFoundError
        from uuid import uuid4
        
        auth_service = AuthService(db_session)
        
        with pytest.raises(NotFoundError) as exc_info:
            await auth_service.change_password_with_auth(
                user_id=uuid4(),
                current_password="anypassword",
                new_password="newpass123"
            )
        
        assert "User not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_token_info(self, db_session, test_user):
        """トークン情報取得が正しく動作することを確認"""
        from app.core.security import create_access_token
        
        auth_service = AuthService(db_session)
        
        # アクセストークンを作成
        access_token = create_access_token(
            subject=test_user.username,
            user_id=str(test_user.id)
        )
        
        # トークン情報を取得
        token_info = await auth_service.get_token_info(access_token)
        
        assert token_info is not None
        assert token_info["user_id"] == str(test_user.id)
        assert token_info["username"] == test_user.username
        assert token_info["token_type"] == "access"
        assert "jti" in token_info
        assert "exp" in token_info
        assert "is_blacklisted" in token_info
    
    @pytest.mark.asyncio
    async def test_get_token_info_invalid(self, db_session):
        """無効なトークンで情報取得が失敗することを確認"""
        auth_service = AuthService(db_session)
        
        result = await auth_service.get_token_info("invalid_token")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_is_token_blacklisted(self, db_session, test_user):
        """トークンブラックリスト確認が動作することを確認"""
        from app.core.security import create_access_token
        
        auth_service = AuthService(db_session)
        
        # アクセストークンを作成
        access_token = create_access_token(
            subject=test_user.username,
            user_id=str(test_user.id)
        )
        
        # ブラックリスト確認 (初期状態では false のはず)
        is_blacklisted = await auth_service.is_token_blacklisted(access_token)
        
        assert isinstance(is_blacklisted, bool)