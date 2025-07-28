from typing import Dict, List, Optional, Set
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.constants.enums import RevisionStatus, Role
from app.models.revision import Revision
from app.core.exceptions import InvalidStateError, AuthorizationError
from app.repositories.revision import RevisionRepository

logger = structlog.get_logger()


class WorkflowService:
    """修正案ワークフロー管理サービス"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.revision_repo = RevisionRepository(db)
        
        # 状態遷移マップ: 現在の状態 -> 可能な遷移先の状態
        self.state_transitions: Dict[RevisionStatus, Set[RevisionStatus]] = {
            RevisionStatus.DRAFT: {
                RevisionStatus.UNDER_REVIEW,  # 提出
                RevisionStatus.WITHDRAWN      # 取り下げ
            },
            RevisionStatus.UNDER_REVIEW: {
                RevisionStatus.APPROVED,           # 承認
                RevisionStatus.REJECTED,           # 却下
                RevisionStatus.REVISION_REQUESTED  # 修正指示
            },
            RevisionStatus.REVISION_REQUESTED: {
                RevisionStatus.UNDER_REVIEW       # 再提出
            },
            # 終了状態からの遷移は基本的になし
            RevisionStatus.APPROVED: set(),
            RevisionStatus.REJECTED: set(),
            RevisionStatus.WITHDRAWN: set()
        }
    
    def validate_state_transition(
        self,
        current_status: RevisionStatus,
        new_status: RevisionStatus
    ) -> bool:
        """状態遷移の妥当性をチェック"""
        allowed_transitions = self.state_transitions.get(current_status, set())
        return new_status in allowed_transitions
    
    def get_allowed_transitions(
        self,
        current_status: RevisionStatus
    ) -> List[RevisionStatus]:
        """現在の状態から可能な遷移先の状態一覧を取得"""
        return list(self.state_transitions.get(current_status, set()))
    
    async def can_transition_to_status(
        self,
        revision_id: UUID,
        new_status: RevisionStatus,
        user_id: UUID,
        user_role: Role
    ) -> tuple[bool, Optional[str]]:
        """
        特定のユーザーが修正案の状態を変更できるかチェック
        Returns: (可否, 不可の場合の理由)
        """
        revision = await self.revision_repo.get(revision_id)
        if not revision:
            return False, "修正案が見つかりません"
        
        # 状態遷移の妥当性チェック
        if not self.validate_state_transition(revision.status, new_status):
            return False, f"{revision.status.value}から{new_status.value}への遷移は無効です"
        
        # 権限チェック
        return self._check_transition_permission(
            revision, new_status, user_id, user_role
        )
    
    def _check_transition_permission(
        self,
        revision: Revision,
        new_status: RevisionStatus,
        user_id: UUID,
        user_role: Role
    ) -> tuple[bool, Optional[str]]:
        """状態遷移に対する権限をチェック"""
        
        # 管理者は全ての遷移が可能
        if user_role == Role.ADMIN:
            return True, None
        
        current_status = revision.status
        
        # Draft -> UnderReview (提出): 提案者のみ
        if current_status == RevisionStatus.DRAFT and new_status == RevisionStatus.UNDER_REVIEW:
            if revision.proposer_id == user_id:
                return True, None
            return False, "修正案の提出は提案者のみ可能です"
        
        # Draft -> Withdrawn (取り下げ): 提案者のみ
        if current_status == RevisionStatus.DRAFT and new_status == RevisionStatus.WITHDRAWN:
            if revision.proposer_id == user_id:
                return True, None
            return False, "修正案の取り下げは提案者のみ可能です"
        
        # UnderReview -> Approved/Rejected/RevisionRequested: 承認者・SV
        if current_status == RevisionStatus.UNDER_REVIEW:
            if user_role in [Role.APPROVER, Role.SUPERVISOR]:
                return True, None
            return False, "承認・却下・修正指示は承認者のみ可能です"
        
        # RevisionRequested -> UnderReview (再提出): 提案者のみ
        if current_status == RevisionStatus.REVISION_REQUESTED and new_status == RevisionStatus.UNDER_REVIEW:
            if revision.proposer_id == user_id:
                return True, None
            return False, "修正案の再提出は提案者のみ可能です"
        
        return False, "この操作の権限がありません"
    
    async def transition_status(
        self,
        revision_id: UUID,
        new_status: RevisionStatus,
        user_id: UUID,
        user_role: Role,
        comment: Optional[str] = None
    ) -> Revision:
        """
        修正案の状態を遷移させる
        """
        # 権限チェック
        can_transition, reason = await self.can_transition_to_status(
            revision_id, new_status, user_id, user_role
        )
        
        if not can_transition:
            raise AuthorizationError(reason or "状態遷移の権限がありません")
        
        # 修正案取得
        revision = await self.revision_repo.get(revision_id)
        if not revision:
            raise InvalidStateError("修正案が見つかりません")
        
        # 状態遷移前のログ
        logger.info(
            "Revision status transition",
            revision_id=str(revision_id),
            from_status=revision.status.value,
            to_status=new_status.value,
            user_id=str(user_id),
            user_role=user_role.value
        )
        
        # 状態変更
        old_status = revision.status
        revision.status = new_status
        revision.updated_at = datetime.utcnow()
        
        # 特定の状態遷移時の追加処理
        if new_status == RevisionStatus.APPROVED:
            revision.approver_id = user_id
            revision.approved_at = datetime.utcnow()
            revision.approval_comment = comment
        
        # データベース更新
        await self.db.flush()
        
        logger.info(
            "Revision status transitioned successfully",
            revision_id=str(revision_id),
            old_status=old_status.value,
            new_status=new_status.value
        )
        
        return revision
    
    def is_terminal_status(self, status: RevisionStatus) -> bool:
        """終了状態（それ以上遷移しない状態）かどうかを判定"""
        return status in {
            RevisionStatus.APPROVED,
            RevisionStatus.REJECTED,
            RevisionStatus.WITHDRAWN
        }
    
    def get_status_display_name(self, status: RevisionStatus) -> str:
        """状態の日本語表示名を取得"""
        status_names = {
            RevisionStatus.DRAFT: "下書き",
            RevisionStatus.UNDER_REVIEW: "レビュー中",
            RevisionStatus.REVISION_REQUESTED: "修正依頼中",
            RevisionStatus.APPROVED: "承認済み",
            RevisionStatus.REJECTED: "却下",
            RevisionStatus.WITHDRAWN: "取り下げ"
        }
        return status_names.get(status, status.value)