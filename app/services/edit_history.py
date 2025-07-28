from typing import Dict, List, Any, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.constants.enums import Role
from app.models.revision import RevisionEditHistory
from app.repositories.revision import RevisionEditHistoryRepository
from app.repositories.user import UserRepository
from app.core.exceptions import NotFoundError

logger = structlog.get_logger()


class EditHistoryService:
    """編集履歴管理サービス"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.edit_history_repo = RevisionEditHistoryRepository(db)
        self.user_repo = UserRepository(db)
    
    async def record_edit(
        self,
        revision_id: UUID,
        editor_id: UUID,
        editor_role: Role,
        changes: Dict[str, Any],
        comment: Optional[str] = None,
        version_before: int = 1,
        version_after: int = 2
    ) -> RevisionEditHistory:
        """編集履歴を記録"""
        
        edit_history = RevisionEditHistory(
            revision_id=revision_id,
            editor_id=editor_id,
            editor_role=editor_role,
            changes=changes,
            comment=comment,
            version_before=version_before,
            version_after=version_after
        )
        
        created_history = await self.edit_history_repo.create(edit_history)
        await self.db.flush()
        
        logger.info(
            "Edit history recorded",
            revision_id=str(revision_id),
            editor_id=str(editor_id),
            changes_count=len(changes),
            version_before=version_before,
            version_after=version_after
        )
        
        return created_history
    
    async def get_edit_history(
        self,
        revision_id: UUID
    ) -> List[Dict[str, Any]]:
        """修正案の編集履歴を取得"""
        histories = await self.edit_history_repo.get_by_revision(revision_id)
        
        result = []
        for history in histories:
            # エディター情報を取得
            editor = history.editor if hasattr(history, 'editor') else await self.user_repo.get(history.editor_id)
            
            history_data = {
                "id": history.id,
                "revision_id": history.revision_id,
                "editor_id": history.editor_id,
                "editor_name": editor.full_name if editor else "Unknown",
                "editor_role": history.editor_role.value,
                "edited_at": history.edited_at,
                "changes": history.changes,
                "comment": history.comment,
                "version_before": history.version_before,
                "version_after": history.version_after
            }
            result.append(history_data)
        
        return result
    
    def calculate_field_changes(
        self,
        before_data: Dict[str, Any],
        after_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        修正前後のデータから変更フィールドを計算
        """
        changes = {}
        
        # 比較対象フィールド
        fields_to_compare = [
            'title', 'info_category', 'keywords', 'importance',
            'target', 'question', 'answer', 'additional_comment',
            'publish_start', 'publish_end'
        ]
        
        for field in fields_to_compare:
            before_value = before_data.get(field)
            after_value = after_data.get(field)
            
            # 値が変更されている場合のみ記録
            if before_value != after_value:
                changes[field] = {
                    'before': before_value,
                    'after': after_value
                }
        
        return changes
    
    async def get_version_diff(
        self,
        revision_id: UUID,
        from_version: int,
        to_version: int
    ) -> Dict[str, Any]:
        """指定バージョン間の差分を取得"""
        histories = await self.edit_history_repo.get_by_revision(revision_id)
        
        # 指定バージョン間の履歴をフィルタ
        relevant_histories = [
            h for h in histories 
            if h.version_before >= from_version and h.version_after <= to_version
        ]
        
        # 変更内容を統合
        combined_changes = {}
        for history in relevant_histories:
            for field, change in history.changes.items():
                if field not in combined_changes:
                    combined_changes[field] = {
                        'initial_value': change['before'],
                        'final_value': change['after'],
                        'change_history': []
                    }
                else:
                    combined_changes[field]['final_value'] = change['after']
                
                combined_changes[field]['change_history'].append({
                    'version': history.version_after,
                    'editor_id': str(history.editor_id),
                    'changed_at': history.edited_at.isoformat() if history.edited_at else None,
                    'from': change['before'],
                    'to': change['after']
                })
        
        return {
            'revision_id': str(revision_id),
            'from_version': from_version,
            'to_version': to_version,
            'changes': combined_changes,
            'total_edits': len(relevant_histories)
        }