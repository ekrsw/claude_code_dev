from typing import Optional, Tuple
from uuid import UUID

from app.constants.enums import RevisionStatus, Role
from app.models.revision import Revision
from app.models.user import User


class RevisionPermissionService:
    """修正案の権限管理サービス"""
    
    @staticmethod
    def can_view_revision(
        user: User,
        revision: Revision
    ) -> Tuple[bool, Optional[str]]:
        """
        修正案の閲覧権限をチェック
        Returns: (閲覧可否, 不可の場合の理由)
        """
        # 管理者は常に閲覧可能
        if user.role == Role.ADMIN:
            return True, None
            
        # 提案者は常に自分の修正案を閲覧可能
        if user.id == revision.proposer_id:
            return True, None
            
        # 承認者・SVは承認関連の状態の修正案を閲覧可能
        if user.role in [Role.APPROVER, Role.SUPERVISOR]:
            if revision.status in [
                RevisionStatus.UNDER_REVIEW,
                RevisionStatus.REVISION_REQUESTED,
                RevisionStatus.APPROVED,
                RevisionStatus.REJECTED
            ]:
                return True, None
        
        # 承認済みの修正案は一般ユーザーも閲覧可能（記事の対象者設定による）
        if revision.status == RevisionStatus.APPROVED:
            return True, None
            
        return False, "この修正案を閲覧する権限がありません"
    
    @staticmethod
    def can_edit_revision(
        user: User,
        revision: Revision
    ) -> Tuple[bool, Optional[str]]:
        """
        修正案の編集権限をチェック
        Returns: (編集可否, 不可の場合の理由)
        """
        # 管理者は常に編集可能
        if user.role == Role.ADMIN:
            return True, None
            
        # 状態別の権限チェック
        if revision.status == RevisionStatus.DRAFT:
            # 下書きは提案者のみ編集可能
            if user.id == revision.proposer_id:
                return True, None
            return False, "下書きは提案者のみ編集可能です"
            
        elif revision.status == RevisionStatus.UNDER_REVIEW:
            # レビュー中は承認者とSVが編集可能
            if user.role in [Role.APPROVER, Role.SUPERVISOR]:
                return True, None
            return False, "レビュー中の修正案は承認者のみ編集可能です"
            
        elif revision.status == RevisionStatus.REVISION_REQUESTED:
            # 修正依頼中は提案者と承認者が編集可能
            if user.id == revision.proposer_id:
                return True, None
            if user.role in [Role.APPROVER, Role.SUPERVISOR]:
                return True, None
            return False, "修正依頼中の修正案は提案者または承認者のみ編集可能です"
            
        else:
            # その他の状態（承認済み、却下、取り下げ）は編集不可
            return False, f"{revision.status.value}の修正案は編集できません"
    
    @staticmethod
    def can_delete_revision(
        user: User,
        revision: Revision
    ) -> Tuple[bool, Optional[str]]:
        """
        修正案の削除権限をチェック
        Returns: (削除可否, 不可の場合の理由)
        """
        # 管理者は常に削除可能
        if user.role == Role.ADMIN:
            return True, None
            
        # 下書き状態の修正案のみ削除可能
        if revision.status != RevisionStatus.DRAFT:
            return False, "下書き状態の修正案のみ削除できます"
            
        # 提案者のみ削除可能
        if user.id == revision.proposer_id:
            return True, None
            
        return False, "修正案の削除は提案者のみ可能です"
    
    @staticmethod
    def can_approve_revision(
        user: User,
        revision: Revision
    ) -> Tuple[bool, Optional[str]]:
        """
        修正案の承認権限をチェック
        Returns: (承認可否, 不可の場合の理由)
        """
        # 管理者、承認者、SVのみ承認可能
        if user.role not in [Role.ADMIN, Role.APPROVER, Role.SUPERVISOR]:
            return False, "承認権限がありません"
            
        # レビュー中または修正依頼中の修正案のみ承認可能
        if revision.status not in [RevisionStatus.UNDER_REVIEW, RevisionStatus.REVISION_REQUESTED]:
            return False, f"{revision.status.value}の修正案は承認できません"
            
        return True, None
    
    @staticmethod
    def can_reject_revision(
        user: User,
        revision: Revision
    ) -> Tuple[bool, Optional[str]]:
        """
        修正案の却下権限をチェック
        Returns: (却下可否, 不可の場合の理由)
        """
        # 管理者、承認者、SVのみ却下可能
        if user.role not in [Role.ADMIN, Role.APPROVER, Role.SUPERVISOR]:
            return False, "却下権限がありません"
            
        # レビュー中または修正依頼中の修正案のみ却下可能
        if revision.status not in [RevisionStatus.UNDER_REVIEW, RevisionStatus.REVISION_REQUESTED]:
            return False, f"{revision.status.value}の修正案は却下できません"
            
        return True, None
    
    @staticmethod
    def can_request_modification(
        user: User,
        revision: Revision
    ) -> Tuple[bool, Optional[str]]:
        """
        修正指示権限をチェック
        Returns: (修正指示可否, 不可の場合の理由)
        """
        # 管理者、承認者、SVのみ修正指示可能
        if user.role not in [Role.ADMIN, Role.APPROVER, Role.SUPERVISOR]:
            return False, "修正指示権限がありません"
            
        # レビュー中の修正案のみ修正指示可能
        if revision.status != RevisionStatus.UNDER_REVIEW:
            return False, f"{revision.status.value}の修正案には修正指示できません"
            
        return True, None
    
    @staticmethod
    def can_submit_revision(
        user: User,
        revision: Revision
    ) -> Tuple[bool, Optional[str]]:
        """
        修正案提出権限をチェック
        Returns: (提出可否, 不可の場合の理由)
        """
        # 提案者のみ提出可能（管理者も含む）
        if user.role == Role.ADMIN or user.id == revision.proposer_id:
            # 下書きまたは修正依頼中の修正案のみ提出可能
            if revision.status in [RevisionStatus.DRAFT, RevisionStatus.REVISION_REQUESTED]:
                return True, None
            return False, f"{revision.status.value}の修正案は提出できません"
            
        return False, "修正案の提出は提案者のみ可能です"
    
    @staticmethod
    def can_withdraw_revision(
        user: User,
        revision: Revision
    ) -> Tuple[bool, Optional[str]]:
        """
        修正案取り下げ権限をチェック
        Returns: (取り下げ可否, 不可の場合の理由)
        """
        # 管理者または提案者のみ取り下げ可能
        if user.role == Role.ADMIN or user.id == revision.proposer_id:
            # 下書き状態の修正案のみ取り下げ可能
            if revision.status == RevisionStatus.DRAFT:
                return True, None
            return False, "下書き状態の修正案のみ取り下げできます"
            
        return False, "修正案の取り下げは提案者のみ可能です"
    
    @staticmethod
    def get_available_actions(
        user: User,
        revision: Revision
    ) -> list[str]:
        """
        ユーザーが実行可能なアクション一覧を取得
        """
        actions = []
        
        # 閲覧
        can_view, _ = RevisionPermissionService.can_view_revision(user, revision)
        if can_view:
            actions.append("view")
        
        # 編集
        can_edit, _ = RevisionPermissionService.can_edit_revision(user, revision)
        if can_edit:
            actions.append("edit")
        
        # 削除
        can_delete, _ = RevisionPermissionService.can_delete_revision(user, revision)
        if can_delete:
            actions.append("delete")
        
        # 提出
        can_submit, _ = RevisionPermissionService.can_submit_revision(user, revision)
        if can_submit:
            actions.append("submit")
        
        # 取り下げ
        can_withdraw, _ = RevisionPermissionService.can_withdraw_revision(user, revision)
        if can_withdraw:
            actions.append("withdraw")
        
        # 承認
        can_approve, _ = RevisionPermissionService.can_approve_revision(user, revision)
        if can_approve:
            actions.append("approve")
        
        # 却下
        can_reject, _ = RevisionPermissionService.can_reject_revision(user, revision)
        if can_reject:
            actions.append("reject")
        
        # 修正指示
        can_request_mod, _ = RevisionPermissionService.can_request_modification(user, revision)
        if can_request_mod:
            actions.append("request_modification")
        
        return actions