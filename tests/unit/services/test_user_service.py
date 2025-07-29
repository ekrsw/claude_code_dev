"""
ユーザーサービスの単体テスト
"""
import pytest
from uuid import uuid4

from app.services.user import UserService
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserProfileUpdate, UserRoleUpdate
from app.constants.enums import Role
from app.core.exceptions import ConflictError, NotFoundError, AuthorizationError


@pytest.mark.asyncio
class TestUserService:
    """UserServiceのテストクラス"""
    
    async def test_create_user_success(self, db_session):
        """ユーザー作成が成功することを確認"""
        user_service = UserService(db_session)
        
        user_data = UserCreate(
            username="newuser",
            email="newuser@example.com",
            password="Password123!",
            full_name="New User",
            role=Role.GENERAL
        )
        
        user = await user_service.create_user(user_data)
        
        assert user is not None
        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.full_name == "New User"
        assert user.role == Role.GENERAL
        assert user.is_active is True
        assert user.hashed_password != "password123"  # パスワードがハッシュ化されている
    
    async def test_create_user_duplicate_username(self, db_session):
        """重複するユーザー名でユーザー作成が失敗することを確認"""
        user_service = UserService(db_session)
        
        # First create a user
        first_user_data = UserCreate(
            username="testuser",
            email="first@example.com",
            password="Password123!",
            full_name="First User"
        )
        await user_service.create_user(first_user_data)
        
        # Try to create another user with the same username
        duplicate_user_data = UserCreate(
            username="testuser",  # 既存のユーザー名
            email="another@example.com",
            password="Password123!",
            full_name="Another User"
        )
        
        with pytest.raises(ConflictError) as exc_info:
            await user_service.create_user(duplicate_user_data)
        
        assert "already exists" in str(exc_info.value)
    
    async def test_create_user_duplicate_email(self, db_session):
        """重複するメールアドレスでユーザー作成が失敗することを確認"""
        user_service = UserService(db_session)
        
        # First create a user
        first_user_data = UserCreate(
            username="firstuser",
            email="test@example.com",
            password="Password123!",
            full_name="First User"
        )
        await user_service.create_user(first_user_data)
        
        # Try to create another user with the same email
        duplicate_user_data = UserCreate(
            username="anotheruser",
            email="test@example.com",  # 既存のメールアドレス
            password="Password123!",
            full_name="Another User"
        )
        
        with pytest.raises(ConflictError) as exc_info:
            await user_service.create_user(duplicate_user_data)
        
        assert "already exists" in str(exc_info.value)
    
    async def test_get_user_success(self, db_session, test_user):
        """ユーザー取得が成功することを確認"""
        user_service = UserService(db_session)
        
        user = await user_service.get_user(test_user.id)
        
        assert user is not None
        assert user.id == test_user.id
        assert user.username == test_user.username
    
    async def test_get_user_not_found(self, db_session):
        """存在しないユーザーの取得が失敗することを確認"""
        user_service = UserService(db_session)
        
        user = await user_service.get_user(uuid4())
        
        assert user is None
    
    async def test_update_user_success(self, db_session, test_user):
        """ユーザー更新が成功することを確認"""
        user_service = UserService(db_session)
        
        update_data = UserUpdate(
            full_name="Updated Name",
            email="updated@example.com"
        )
        
        updated_user = await user_service.update_user(
            test_user.id,
            update_data,
            test_user  # 自分自身を更新
        )
        
        assert updated_user is not None
        assert updated_user.full_name == "Updated Name"
        assert updated_user.email == "updated@example.com"
    
    async def test_update_user_by_admin(self, db_session, test_user, test_admin):
        """管理者による他ユーザーの更新が成功することを確認"""
        user_service = UserService(db_session)
        
        update_data = UserUpdate(
            full_name="Admin Updated"
        )
        
        updated_user = await user_service.update_user(
            test_user.id,
            update_data,
            test_admin  # 管理者として更新
        )
        
        assert updated_user is not None
        assert updated_user.full_name == "Admin Updated"
    
    async def test_update_user_unauthorized(self, db_session, test_user):
        """権限のないユーザーによる更新が失敗することを確認"""
        user_service = UserService(db_session)
        
        # 別のユーザーを作成
        other_user = User(
            id=uuid4(),
            username="otheruser",
            email="other@example.com",
            hashed_password="dummy",
            role=Role.GENERAL
        )
        db_session.add(other_user)
        await db_session.commit()
        
        update_data = UserUpdate(full_name="Unauthorized Update")
        
        with pytest.raises(AuthorizationError):
            await user_service.update_user(
                test_user.id,
                update_data,
                other_user  # 権限のないユーザー
            )
    
    async def test_update_profile_success(self, db_session, test_user):
        """プロファイル更新が成功することを確認"""
        user_service = UserService(db_session)
        
        profile_data = UserProfileUpdate(
            full_name="Profile Updated",
            sweet_name="sweet_user",
            ctstage_name="ctstage_user"
        )
        
        updated_user = await user_service.update_profile(
            test_user.id,
            profile_data,
            test_user
        )
        
        assert updated_user is not None
        assert updated_user.full_name == "Profile Updated"
        assert updated_user.sweet_name == "sweet_user"
        assert updated_user.ctstage_name == "ctstage_user"
    
    async def test_update_role_by_admin(self, db_session, test_user, test_admin):
        """管理者によるロール更新が成功することを確認"""
        user_service = UserService(db_session)
        
        role_data = UserRoleUpdate(role=Role.SUPERVISOR)
        
        updated_user = await user_service.update_role(
            test_user.id,
            role_data,
            test_admin
        )
        
        assert updated_user is not None
        assert updated_user.role == Role.SUPERVISOR
    
    async def test_update_role_unauthorized(self, db_session, test_user, test_supervisor):
        """権限のないユーザーによるロール更新が失敗することを確認"""
        user_service = UserService(db_session)
        
        role_data = UserRoleUpdate(role=Role.ADMIN)
        
        with pytest.raises(AuthorizationError):
            await user_service.update_role(
                test_user.id,
                role_data,
                test_supervisor  # SVには権限がない
            )
    
    async def test_change_password_success(self, db_session, test_user):
        """パスワード変更が成功することを確認"""
        user_service = UserService(db_session)
        
        success = await user_service.change_password(
            test_user.id,
            "testpass123",  # 現在のパスワード
            "NewPassword123!",  # 新しいパスワード
            test_user
        )
        
        assert success is True
        
        # 新しいパスワードで認証できることを確認
        from app.services.auth import AuthService
        from app.schemas.user import UserLogin
        auth_service = AuthService(db_session)
        credentials = UserLogin(username=test_user.username, password="NewPassword123!")
        authenticated = await auth_service.authenticate_user(credentials)
        assert authenticated is not None
    
    async def test_change_password_wrong_current(self, db_session, test_user):
        """間違った現在のパスワードでパスワード変更が失敗することを確認"""
        user_service = UserService(db_session)
        
        with pytest.raises(AuthorizationError) as exc_info:
            await user_service.change_password(
                test_user.id,
                "WrongPassword123!",  # 間違ったパスワード
                "newpassword123",
                test_user
            )
        
        assert "Current password is incorrect" in str(exc_info.value)
    
    async def test_delete_user_by_admin(self, db_session, test_user, test_admin):
        """管理者によるユーザー削除が成功することを確認"""
        user_service = UserService(db_session)
        
        success = await user_service.delete_user(
            test_user.id,
            test_admin
        )
        
        assert success is True
        
        # ユーザーが削除されたことを確認
        deleted_user = await user_service.get_user(test_user.id)
        assert deleted_user is None
    
    async def test_delete_user_unauthorized(self, db_session, test_user, test_supervisor):
        """権限のないユーザーによる削除が失敗することを確認"""
        user_service = UserService(db_session)
        
        with pytest.raises(AuthorizationError):
            await user_service.delete_user(
                test_user.id,
                test_supervisor  # SVには削除権限がない
            )
    
    async def test_get_users_with_pagination(self, db_session, test_user, test_admin, test_supervisor):
        """ページネーション付きユーザー一覧取得が成功することを確認"""
        user_service = UserService(db_session)
        
        # 最初のページ
        users, total = await user_service.get_users(skip=0, limit=2)
        
        assert len(users) <= 2
        assert total >= 3  # 少なくとも3人のユーザーが存在
        
        # 2ページ目
        users_page2, _ = await user_service.get_users(skip=2, limit=2)
        
        assert len(users_page2) >= 1
        
        # ユーザーIDが重複していないことを確認
        user_ids_page1 = {u.id for u in users}
        user_ids_page2 = {u.id for u in users_page2}
        assert len(user_ids_page1 & user_ids_page2) == 0