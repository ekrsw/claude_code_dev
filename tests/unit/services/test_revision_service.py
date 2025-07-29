"""
修正案サービスの単体テスト
"""
import pytest
from uuid import uuid4
from datetime import datetime

from app.services.revision import RevisionService
from app.services.notification import NotificationService
from app.models.revision import Revision
from app.schemas.revision import RevisionCreate, RevisionUpdate, RevisionFilter
from app.constants.enums import Role, RevisionStatus
from app.core.exceptions import NotFoundError, AuthorizationError, InvalidStateError


@pytest.mark.asyncio
class TestRevisionService:
    """RevisionServiceのテストクラス"""
    
    async def test_create_revision_success(self, db_session, test_user, test_article):
        """修正案作成が成功することを確認"""
        notification_service = NotificationService(db_session)
        revision_service = RevisionService(db_session, notification_service)
        
        from app.schemas.revision import RevisionModifications
        
        modifications = RevisionModifications(
            title="修正されたタイトル",
            answer="修正された回答内容",
            additional_comment="テスト用の修正"
        )
        
        revision_data = RevisionCreate(
            target_article_id=test_article.article_id,
            reason="テスト用の修正案を作成します。内容を改善するためです。",
            modifications=modifications
        )
        
        revision = await revision_service.create_revision(
            revision_data,
            test_user.id
        )
        
        assert revision is not None
        assert revision.target_article_id == test_article.article_id
        assert revision.proposer_id == test_user.id
        assert revision.status == RevisionStatus.DRAFT
        assert revision.reason == "テスト用の修正案を作成します。内容を改善するためです。"
        # 修正内容の確認
        assert revision.after_title == "修正されたタイトル"
        assert revision.after_answer == "修正された回答内容"
    
    async def test_get_revision_success(self, db_session, test_revision):
        """修正案取得が成功することを確認"""
        notification_service = NotificationService(db_session)
        revision_service = RevisionService(db_session, notification_service)
        
        revision = await revision_service.get_revision(test_revision.id)
        
        assert revision is not None
        assert revision.id == test_revision.id
        assert revision.after_title == test_revision.after_title
    
    async def test_get_revision_not_found(self, db_session):
        """存在しない修正案の取得が失敗することを確認"""
        notification_service = NotificationService(db_session)
        revision_service = RevisionService(db_session, notification_service)
        
        with pytest.raises(NotFoundError):
            await revision_service.get_revision(uuid4())
    
    async def test_update_revision_by_proposer(self, db_session, test_revision, test_user):
        """提案者による修正案更新が成功することを確認"""
        notification_service = NotificationService(db_session)
        revision_service = RevisionService(db_session, notification_service)
        
        from app.schemas.revision import RevisionModifications
        
        update_data = RevisionUpdate(
            reason="テスト用の修正理由を更新します",
            modifications=RevisionModifications(
                title="更新されたタイトル",
                answer="更新された内容"
            )
        )
        
        updated = await revision_service.update_revision(
            test_revision.id,
            update_data,
            test_user.id,
            test_user.role
        )
        
        assert updated is not None
        assert updated.after_title == "更新されたタイトル"
        assert updated.after_answer == "更新された内容"
        assert updated.version == 2  # バージョンが増加
    
    async def test_update_revision_unauthorized(self, db_session, test_revision):
        """権限のないユーザーによる修正案更新が失敗することを確認"""
        notification_service = NotificationService(db_session)
        revision_service = RevisionService(db_session, notification_service)
        
        other_user_id = uuid4()
        update_data = RevisionUpdate(title="不正な更新")
        
        with pytest.raises(AuthorizationError):
            await revision_service.update_revision(
                test_revision.id,
                update_data,
                other_user_id,
                Role.GENERAL
            )
    
    async def test_submit_for_review(self, db_session, test_revision, test_user):
        """レビュー提出が成功することを確認"""
        notification_service = NotificationService(db_session)
        revision_service = RevisionService(db_session, notification_service)
        
        submitted = await revision_service.submit_for_review(
            test_revision.id,
            test_user.id,
            test_user.role
        )
        
        assert submitted is not None
        assert submitted.status == RevisionStatus.UNDER_REVIEW
    
    async def test_submit_for_review_invalid_state(self, db_session, test_user, test_article):
        """無効な状態からのレビュー提出が失敗することを確認"""
        notification_service = NotificationService(db_session)
        revision_service = RevisionService(db_session, notification_service)
        
        # 承認済みの修正案を作成
        approved_revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.APPROVED,
            reason="承認済みの修正案です。テスト用です。",
            after_title="承認済み",
            after_answer="承認済み内容"
        )
        db_session.add(approved_revision)
        await db_session.commit()
        
        with pytest.raises(InvalidStateError):
            await revision_service.submit_for_review(
                approved_revision.id,
                test_user.id,
                test_user.role
            )
    
    async def test_list_revisions_with_filter(self, db_session, test_user, test_article):
        """フィルター付き修正案一覧取得が成功することを確認"""
        notification_service = NotificationService(db_session)
        revision_service = RevisionService(db_session, notification_service)
        
        # 複数の修正案を作成
        for i in range(3):
            revision = Revision(
                id=uuid4(),
                target_article_id=test_article.article_id,
                proposer_id=test_user.id,
                status=RevisionStatus.DRAFT if i < 2 else RevisionStatus.UNDER_REVIEW,
                reason=f"修正案{i}のための理由です。テスト用です。",
                after_title=f"修正案{i}",
                after_answer=f"内容{i}"
            )
            db_session.add(revision)
        await db_session.commit()
        
        # ステータスでフィルター
        filter_params = RevisionFilter(status=RevisionStatus.DRAFT)
        revisions = await revision_service.list_revisions(filter_params, skip=0, limit=10)
        
        assert len(revisions) >= 2  # 少なくとも2つのDRAFT状態の修正案
        assert all(r.status == RevisionStatus.DRAFT for r in revisions)
    
    async def test_get_revision_detail_diff(self, db_session, test_revision, test_article):
        """修正案の差分詳細取得が成功することを確認"""
        notification_service = NotificationService(db_session)
        revision_service = RevisionService(db_session, notification_service)
        
        # 修正案に差分データを設定
        test_revision.before_title = test_article.title
        test_revision.after_title = "新しいタイトル"
        test_revision.before_content = "元の内容"
        test_revision.after_content = "新しい内容"
        await db_session.commit()
        
        diff = await revision_service.calculate_diff(test_revision.id)
        
        assert diff is not None
        assert diff.revision_id == test_revision.id
        assert "title" in diff.modified_fields
        assert len(diff.diffs) > 0
        
        # Check title diff specifically
        title_diff = next((d for d in diff.diffs if d.field == "title"), None)
        assert title_diff is not None
        assert title_diff.before == test_article.title
        assert title_diff.after == "新しいタイトル"
        assert title_diff.is_modified is True
    
    async def test_delete_revision_by_proposer(self, db_session, test_revision, test_user):
        """提案者による修正案削除が成功することを確認"""
        notification_service = NotificationService(db_session)
        revision_service = RevisionService(db_session, notification_service)
        
        success = await revision_service.delete_revision(
            test_revision.id,
            test_user.id,
            test_user.role
        )
        
        assert success is True
        
        # 削除されたことを確認
        with pytest.raises(NotFoundError):
            await revision_service.get_revision(test_revision.id)
    
    async def test_delete_revision_unauthorized(self, db_session, test_revision):
        """権限のないユーザーによる修正案削除が失敗することを確認"""
        notification_service = NotificationService(db_session)
        revision_service = RevisionService(db_session, notification_service)
        
        other_user_id = uuid4()
        
        with pytest.raises(AuthorizationError):
            await revision_service.delete_revision(
                test_revision.id,
                other_user_id,
                Role.GENERAL
            )
    
    async def test_get_revisions_by_article(self, db_session, test_article, test_user):
        """記事別修正案取得が成功することを確認"""
        notification_service = NotificationService(db_session)
        revision_service = RevisionService(db_session, notification_service)
        
        # 同じ記事に対する複数の修正案を作成
        for i in range(2):
            revision = Revision(
                id=uuid4(),
                target_article_id=test_article.article_id,
                proposer_id=test_user.id,
                status=RevisionStatus.DRAFT,
                reason=f"記事修正案{i}のための理由です。テスト用です。",
                after_title=f"記事修正案{i}",
                after_answer=f"内容{i}"
            )
            db_session.add(revision)
        await db_session.commit()
        
        revisions = await revision_service.get_revisions_by_article(test_article.article_id)
        
        assert len(revisions) >= 2
        assert all(r.target_article_id == test_article.article_id for r in revisions)
    
    async def test_get_revisions_by_proposer(self, db_session, test_user, test_article):
        """提案者別修正案取得が成功することを確認"""
        notification_service = NotificationService(db_session)
        revision_service = RevisionService(db_session, notification_service)
        
        # 同じユーザーによる複数の修正案を作成
        for i in range(2):
            revision = Revision(
                id=uuid4(),
                target_article_id=test_article.article_id,
                proposer_id=test_user.id,
                status=RevisionStatus.DRAFT,
                reason=f"ユーザー修正案{i}のための理由です。テスト用です。",
                after_title=f"ユーザー修正案{i}",
                after_answer=f"内容{i}"
            )
            db_session.add(revision)
        await db_session.commit()
        
        revisions = await revision_service.get_revisions_by_proposer(test_user.id)
        
        assert len(revisions) >= 2
        assert all(r.proposer_id == test_user.id for r in revisions)