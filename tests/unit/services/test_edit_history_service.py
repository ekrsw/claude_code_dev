"""
編集履歴サービスの単体テスト
"""
import pytest
from uuid import uuid4
from datetime import datetime

from app.services.edit_history import EditHistoryService
from app.models.revision import RevisionEditHistory
from app.constants.enums import Role


@pytest.mark.asyncio
class TestEditHistoryService:
    """EditHistoryServiceのテストクラス"""
    
    async def test_record_edit_success(self, db_session, test_user, test_revision):
        """編集履歴記録が成功することを確認"""
        edit_history_service = EditHistoryService(db_session)
        
        changes = {
            "title": {
                "before": "元のタイトル",
                "after": "修正後タイトル"
            },
            "answer": {
                "before": "元の回答",
                "after": "修正後回答"
            }
        }
        
        edit_history = await edit_history_service.record_edit(
            revision_id=test_revision.id,
            editor_id=test_user.id,
            editor_role=test_user.role,
            changes=changes,
            comment="テスト用の編集履歴です。",
            version_before=1,
            version_after=2
        )
        
        assert edit_history is not None
        assert edit_history.revision_id == test_revision.id
        assert edit_history.editor_id == test_user.id
        assert edit_history.editor_role == test_user.role
        assert edit_history.changes == changes
        assert edit_history.comment == "テスト用の編集履歴です。"
        assert edit_history.version_before == 1
        assert edit_history.version_after == 2
    
    async def test_record_edit_without_comment(self, db_session, test_user, test_revision):
        """コメントなしの編集履歴記録が成功することを確認"""
        edit_history_service = EditHistoryService(db_session)
        
        changes = {
            "answer": {
                "before": "元の回答",
                "after": "修正後回答"
            }
        }
        
        edit_history = await edit_history_service.record_edit(
            revision_id=test_revision.id,
            editor_id=test_user.id,
            editor_role=test_user.role,
            changes=changes
        )
        
        assert edit_history is not None
        assert edit_history.comment is None
        assert edit_history.changes == changes
    
    async def test_get_edit_history_success(self, db_session, test_user, test_approver, test_revision):
        """編集履歴取得が成功することを確認"""
        edit_history_service = EditHistoryService(db_session)
        
        # 複数の編集履歴を作成
        changes1 = {
            "title": {
                "before": "元のタイトル",
                "after": "修正タイトル1"
            }
        }
        
        changes2 = {
            "title": {
                "before": "修正タイトル1",
                "after": "修正タイトル2"
            },
            "answer": {
                "before": "元の回答",
                "after": "修正後回答"
            }
        }
        
        await edit_history_service.record_edit(
            revision_id=test_revision.id,
            editor_id=test_user.id,
            editor_role=test_user.role,
            changes=changes1,
            comment="最初の編集",
            version_before=1,
            version_after=2
        )
        
        await edit_history_service.record_edit(
            revision_id=test_revision.id,
            editor_id=test_approver.id,
            editor_role=test_approver.role,
            changes=changes2,
            comment="二回目の編集",
            version_before=2,
            version_after=3
        )
        
        # 編集履歴を取得
        history_list = await edit_history_service.get_edit_history(test_revision.id)
        
        assert len(history_list) >= 2
        
        # 履歴リストの内容をチェック（順序は問わない）
        editor_ids = [h["editor_id"] for h in history_list]
        comments = [h["comment"] for h in history_list]
        
        assert test_user.id in editor_ids
        assert test_approver.id in editor_ids
        assert "最初の編集" in comments
        assert "二回目の編集" in comments
        
        # いずれかの履歴の詳細をチェック
        first_history = history_list[0]
        assert first_history["revision_id"] == test_revision.id
        assert first_history["editor_id"] in [test_user.id, test_approver.id]
        assert "editor_name" in first_history
        assert "edited_at" in first_history
        assert first_history["version_before"] >= 1
        assert first_history["version_after"] >= 2
    
    async def test_get_edit_history_empty(self, db_session, test_revision):
        """編集履歴がない場合の取得が成功することを確認"""
        edit_history_service = EditHistoryService(db_session)
        
        # 存在しない修正案IDの編集履歴を取得
        non_existent_revision_id = uuid4()
        history_list = await edit_history_service.get_edit_history(non_existent_revision_id)
        
        assert history_list == []
    
    def test_calculate_field_changes_with_differences(self):
        """フィールド変更計算が正しく動作することを確認"""
        edit_history_service = EditHistoryService(None)  # DBセッション不要
        
        before_data = {
            "title": "元のタイトル",
            "answer": "元の回答",
            "keywords": "元のキーワード",
            "importance": False,
            "target": "社内向け"
        }
        
        after_data = {
            "title": "修正後タイトル",
            "answer": "元の回答",  # 変更なし
            "keywords": "修正後キーワード",
            "importance": True,
            "target": "社内向け",  # 変更なし
            "additional_comment": "新しいコメント"  # 新規追加
        }
        
        changes = edit_history_service.calculate_field_changes(before_data, after_data)
        
        expected_changes = {
            "title": {
                "before": "元のタイトル",
                "after": "修正後タイトル"
            },
            "keywords": {
                "before": "元のキーワード",
                "after": "修正後キーワード"
            },
            "importance": {
                "before": False,
                "after": True
            },
            "additional_comment": {
                "before": None,
                "after": "新しいコメント"
            }
        }
        
        assert changes == expected_changes
        
        # 変更がないフィールドは含まれていないことを確認
        assert "answer" not in changes
        assert "target" not in changes
    
    def test_calculate_field_changes_no_differences(self):
        """変更がない場合のフィールド変更計算が正しく動作することを確認"""
        edit_history_service = EditHistoryService(None)  # DBセッション不要
        
        data = {
            "title": "同じタイトル",
            "answer": "同じ回答",
            "keywords": "同じキーワード"
        }
        
        changes = edit_history_service.calculate_field_changes(data, data)
        
        assert changes == {}
    
    def test_calculate_field_changes_with_none_values(self):
        """None値を含むフィールド変更計算が正しく動作することを確認"""
        edit_history_service = EditHistoryService(None)  # DBセッション不要
        
        before_data = {
            "title": None,
            "answer": "元の回答",
            "keywords": None
        }
        
        after_data = {
            "title": "新しいタイトル",
            "answer": None,
            "keywords": None
        }
        
        changes = edit_history_service.calculate_field_changes(before_data, after_data)
        
        expected_changes = {
            "title": {
                "before": None,
                "after": "新しいタイトル"
            },
            "answer": {
                "before": "元の回答",
                "after": None
            }
        }
        
        assert changes == expected_changes
        assert "keywords" not in changes  # None -> None なので変更なし
    
    async def test_get_version_diff_success(self, db_session, test_user, test_revision):
        """バージョン間差分取得が成功することを確認"""
        edit_history_service = EditHistoryService(db_session)
        
        # 複数の編集履歴を作成
        changes1 = {
            "title": {
                "before": "元のタイトル",
                "after": "修正タイトル1"
            },
            "answer": {
                "before": "元の回答",
                "after": "修正回答1"
            }
        }
        
        changes2 = {
            "title": {
                "before": "修正タイトル1",
                "after": "修正タイトル2"
            }
        }
        
        changes3 = {
            "answer": {
                "before": "修正回答1",
                "after": "修正回答2"
            },
            "keywords": {
                "before": "元のキーワード",
                "after": "修正キーワード"
            }
        }
        
        await edit_history_service.record_edit(
            revision_id=test_revision.id,
            editor_id=test_user.id,
            editor_role=test_user.role,
            changes=changes1,
            version_before=1,
            version_after=2
        )
        
        await edit_history_service.record_edit(
            revision_id=test_revision.id,
            editor_id=test_user.id,
            editor_role=test_user.role,
            changes=changes2,
            version_before=2,
            version_after=3
        )
        
        await edit_history_service.record_edit(
            revision_id=test_revision.id,
            editor_id=test_user.id,
            editor_role=test_user.role,
            changes=changes3,
            version_before=3,
            version_after=4
        )
        
        # バージョン1から4までの差分を取得
        version_diff = await edit_history_service.get_version_diff(
            revision_id=test_revision.id,
            from_version=1,
            to_version=4
        )
        
        assert version_diff["revision_id"] == str(test_revision.id)
        assert version_diff["from_version"] == 1
        assert version_diff["to_version"] == 4
        assert version_diff["total_edits"] >= 2
        
        # 変更内容があることを確認
        changes = version_diff["changes"]
        assert len(changes) > 0
        
        # 何らかのフィールドに変更があることを確認
        has_title_changes = "title" in changes
        has_answer_changes = "answer" in changes
        has_keywords_changes = "keywords" in changes
        
        assert has_title_changes or has_answer_changes or has_keywords_changes
        
        # titleの変更がある場合の確認
        if has_title_changes:
            assert "initial_value" in changes["title"]
            assert "final_value" in changes["title"]
            assert "change_history" in changes["title"]
    
    async def test_get_version_diff_no_changes(self, db_session, test_revision):
        """変更がないバージョン間の差分取得が成功することを確認"""
        edit_history_service = EditHistoryService(db_session)
        
        # 存在しないバージョン間の差分を取得
        version_diff = await edit_history_service.get_version_diff(
            revision_id=test_revision.id,
            from_version=5,
            to_version=6
        )
        
        assert version_diff["revision_id"] == str(test_revision.id)
        assert version_diff["from_version"] == 5
        assert version_diff["to_version"] == 6
        assert version_diff["total_edits"] == 0
        assert version_diff["changes"] == {}
    
    async def test_get_version_diff_single_version(self, db_session, test_user, test_revision):
        """単一バージョンの差分取得が成功することを確認"""
        edit_history_service = EditHistoryService(db_session)
        
        changes = {
            "title": {
                "before": "元のタイトル",
                "after": "修正後タイトル"
            }
        }
        
        await edit_history_service.record_edit(
            revision_id=test_revision.id,
            editor_id=test_user.id,
            editor_role=test_user.role,
            changes=changes,
            version_before=1,
            version_after=2
        )
        
        # 同一バージョン間の差分を取得
        version_diff = await edit_history_service.get_version_diff(
            revision_id=test_revision.id,
            from_version=1,
            to_version=2
        )
        
        assert version_diff["total_edits"] >= 1
        assert "title" in version_diff["changes"]
        assert version_diff["changes"]["title"]["initial_value"] == "元のタイトル"
        assert version_diff["changes"]["title"]["final_value"] == "修正後タイトル"