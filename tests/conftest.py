"""
グローバルなテストフィクスチャと設定
"""
import asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base_model import BaseModel
from app.main import app
from app.models.user import User
from app.models.article import Article
from app.models.revision import Revision
from app.core.security import get_password_hash
from app.constants.enums import Role, RevisionStatus


# テスト用データベースURL
if "sqlite" in settings.DATABASE_URL:
    # SQLiteの場合、テスト用のファイル名を作成
    TEST_DATABASE_URL = settings.DATABASE_URL.replace(".db", "_test.db")
else:
    # PostgreSQLの場合
    TEST_DATABASE_URL = settings.DATABASE_URL.replace(
        "knowledge_revision", "knowledge_revision_test"
    )


# イベントループの設定
@pytest.fixture(scope="session")
def event_loop():
    """セッション全体で使用するイベントループ"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# データベース関連のフィクスチャ
@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """テスト用データベースエンジン"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """テスト用データベースセッション"""
    async_session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            # テスト終了時にロールバック（まだアクティブな場合のみ）
            if session.in_transaction():
                await session.rollback()
            await session.close()


# テストデータのフィクスチャ
@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """テスト用一般ユーザー"""
    user_id = uuid4()
    user = User(
        id=user_id,
        username=f"testuser_{str(user_id)[:8]}",
        email=f"test_{str(user_id)[:8]}@example.com",
        hashed_password=get_password_hash("testpass123"),
        full_name="Test User",
        role=Role.GENERAL,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin(db_session: AsyncSession) -> User:
    """テスト用管理者ユーザー"""
    admin_id = uuid4()
    admin = User(
        id=admin_id,
        username=f"admin_{str(admin_id)[:8]}",
        email=f"admin_{str(admin_id)[:8]}@example.com",
        hashed_password=get_password_hash("adminpass123"),
        full_name="Admin User",
        role=Role.ADMIN,
        is_active=True
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest_asyncio.fixture
async def test_supervisor(db_session: AsyncSession) -> User:
    """テスト用スーパーバイザー"""
    supervisor_id = uuid4()
    supervisor = User(
        id=supervisor_id,
        username=f"supervisor_{str(supervisor_id)[:8]}",
        email=f"supervisor_{str(supervisor_id)[:8]}@example.com",
        hashed_password=get_password_hash("supervisorpass123"),
        full_name="Supervisor User",
        role=Role.SUPERVISOR,
        is_active=True
    )
    db_session.add(supervisor)
    await db_session.commit()
    await db_session.refresh(supervisor)
    return supervisor


@pytest_asyncio.fixture
async def test_approver(db_session: AsyncSession) -> User:
    """テスト用承認者"""
    approver_id = uuid4()
    approver = User(
        id=approver_id,
        username=f"approver_{str(approver_id)[:8]}",
        email=f"approver_{str(approver_id)[:8]}@example.com",
        hashed_password=get_password_hash("approverpass123"),
        full_name="Approver User",
        role=Role.APPROVER,
        is_active=True
    )
    db_session.add(approver)
    await db_session.commit()
    await db_session.refresh(approver)
    return approver


@pytest_asyncio.fixture
async def test_article(db_session: AsyncSession) -> Article:
    """テスト用記事"""
    article_uuid = uuid4()
    article = Article(
        id=article_uuid,
        article_id=f"TEST-{str(article_uuid)[:8]}",
        title="テスト記事",
        info_category_code="01",
        keywords="テスト,サンプル",
        importance=False,
        target="社内向け",
        question="テストに関する質問",
        answer="テストに関する回答",
        is_active=True
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article


@pytest_asyncio.fixture
async def test_revision(
    db_session: AsyncSession,
    test_user: User,
    test_article: Article
) -> Revision:
    """テスト用修正案"""
    revision = Revision(
        id=uuid4(),
        target_article_id=test_article.article_id,  # Use article_id string, not UUID
        proposer_id=test_user.id,
        status=RevisionStatus.DRAFT,
        reason="テスト用の修正案です。内容を改善するために作成しました。",
        # Set some before/after values for testing
        before_title=test_article.title,
        after_title="修正されたタイトル",
        before_answer=test_article.answer,
        after_answer="修正された回答内容",
        version=1
    )
    db_session.add(revision)
    await db_session.commit()
    await db_session.refresh(revision)
    return revision


# HTTPクライアントのフィクスチャ
@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """テスト用HTTPクライアント"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# 認証ヘッダーのヘルパー関数
def auth_headers(token: str) -> dict:
    """認証ヘッダーを生成"""
    return {"Authorization": f"Bearer {token}"}