from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user, get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.revision import (
    RevisionCreate, RevisionUpdate, RevisionResponse,
    RevisionFilter, RevisionDetailDiff
)
from app.schemas.common import PaginatedResponse, PaginationParams, SuccessResponse
from app.services.revision import RevisionService
from app.services.workflow import WorkflowService
from app.services.permission import RevisionPermissionService
from app.services.instruction import RevisionInstructionService
from app.services.edit_history import EditHistoryService
from app.services.approval import ApprovalService
from app.constants.enums import RevisionStatus
from app.schemas.revision import ModificationInstructionCreate, ModificationInstructionResponse
from app.schemas.approval import (
    ApprovalRequest, RejectionRequest, WithdrawalRequest, 
    ModificationRequest, ApprovalHistoryResponse, ApprovalStatusCounts
)
from app.core.exceptions import (
    InvalidStateError, NotFoundError, AuthorizationError, ConflictError
)

router = APIRouter()


@router.post("/", response_model=RevisionResponse, status_code=status.HTTP_201_CREATED)
async def create_revision(
    revision_data: RevisionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案作成"""
    service = RevisionService(db)
    
    try:
        revision = await service.create_revision(revision_data, current_user.id)
        return revision
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except InvalidStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{revision_id}", response_model=RevisionResponse)
async def get_revision(
    revision_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案詳細取得"""
    service = RevisionService(db)
    
    try:
        revision = await service.get_revision(revision_id)
        return revision
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/{revision_id}", response_model=RevisionResponse)
async def update_revision(
    revision_id: UUID,
    update_data: RevisionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案更新"""
    service = RevisionService(db)
    
    try:
        revision = await service.update_revision(
            revision_id, update_data, current_user.id, current_user.role
        )
        return revision
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except InvalidStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{revision_id}", response_model=SuccessResponse)
async def delete_revision(
    revision_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案削除（下書きのみ）"""
    service = RevisionService(db)
    
    try:
        await service.delete_revision(revision_id, current_user.id, current_user.role)
        return SuccessResponse(message="Revision deleted successfully")
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except InvalidStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=PaginatedResponse[RevisionResponse])
async def list_revisions(
    pagination: PaginationParams = Depends(),
    status_filter: str = Query(None, alias="status", description="Status filter"),
    proposer_id: UUID = Query(None, description="Proposer ID filter"),
    target_article_id: str = Query(None, description="Target article ID filter"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案一覧取得"""
    service = RevisionService(db)
    
    # Build filters
    filters = RevisionFilter()
    if status_filter:
        try:
            from app.constants.enums import RevisionStatus
            filters.status = RevisionStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )
    if proposer_id:
        filters.proposer_id = proposer_id
    if target_article_id:
        filters.target_article_id = target_article_id
    
    try:
        revisions = await service.list_revisions(
            filters, skip=pagination.offset, limit=pagination.size
        )
        
        # Get total count for pagination
        # For now, return the current page size as we don't have count method
        # TODO: Implement proper count method in service
        total = len(revisions) + pagination.offset if len(revisions) == pagination.size else pagination.offset + len(revisions)
        
        return PaginatedResponse.create(
            items=revisions,
            total=total,
            page=pagination.page,
            size=pagination.size
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list revisions: {str(e)}"
        )


@router.get("/{revision_id}/diff", response_model=RevisionDetailDiff)
async def get_revision_diff(
    revision_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案の詳細な差分取得"""
    service = RevisionService(db)
    
    try:
        diff = await service.calculate_diff(revision_id)
        return diff
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# ワークフロー関連エンドポイント

@router.post("/{revision_id}/submit", response_model=SuccessResponse)
async def submit_revision(
    revision_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案を提出（Draft → UnderReview）"""
    # Import here to avoid circular imports
    from app.services.notification import NotificationService
    
    notification_service = NotificationService(db)
    revision_service = RevisionService(db, notification_service)
    
    try:
        await revision_service.submit_for_review(
            revision_id=revision_id,
            user_id=current_user.id,
            user_role=current_user.role
        )
        
        return SuccessResponse(message="修正案を提出しました")
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except (NotFoundError, InvalidStateError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{revision_id}/approve", response_model=SuccessResponse)
async def approve_revision(
    revision_id: UUID,
    approval_data: ApprovalRequest = ApprovalRequest(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案を承認（UnderReview/RevisionRequested → Approved）"""
    # Import here to avoid circular imports
    from app.services.notification import NotificationService
    
    notification_service = NotificationService(db)
    approval_service = ApprovalService(db, notification_service)
    
    try:
        await approval_service.approve_revision(
            revision_id=revision_id,
            approver_id=current_user.id,
            approver_role=current_user.role,
            comment=approval_data.comment
        )
        await db.commit()
        
        return SuccessResponse(message="修正案を承認しました")
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except (NotFoundError, InvalidStateError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{revision_id}/reject", response_model=SuccessResponse)
async def reject_revision(
    revision_id: UUID,
    rejection_data: RejectionRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案を却下（UnderReview/RevisionRequested → Rejected）"""
    # Import here to avoid circular imports
    from app.services.notification import NotificationService
    
    notification_service = NotificationService(db)
    approval_service = ApprovalService(db, notification_service)
    
    try:
        await approval_service.reject_revision(
            revision_id=revision_id,
            rejector_id=current_user.id,
            rejector_role=current_user.role,
            comment=rejection_data.comment
        )
        await db.commit()
        
        return SuccessResponse(message="修正案を却下しました")
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except (NotFoundError, InvalidStateError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{revision_id}/withdraw", response_model=SuccessResponse)
async def withdraw_revision(
    revision_id: UUID,
    withdrawal_data: WithdrawalRequest = WithdrawalRequest(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案を取り下げ（Draft/UnderReview/RevisionRequested → Withdrawn）"""
    # Import here to avoid circular imports
    from app.services.notification import NotificationService
    
    notification_service = NotificationService(db)
    approval_service = ApprovalService(db, notification_service)
    
    try:
        await approval_service.withdraw_revision(
            revision_id=revision_id,
            withdrawer_id=current_user.id,
            withdrawer_role=current_user.role,
            comment=withdrawal_data.comment
        )
        await db.commit()
        
        return SuccessResponse(message="修正案を取り下げました")
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except (NotFoundError, InvalidStateError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{revision_id}/available-actions")
async def get_available_actions(
    revision_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ユーザーが実行可能なアクション一覧を取得"""
    revision_service = RevisionService(db)
    
    try:
        revision_response = await revision_service.get_revision(revision_id)
        # RevisionResponseからRevisionモデルを作成（簡易版）
        from app.models.revision import Revision
        revision = Revision(
            id=revision_response.id,
            proposer_id=revision_response.proposer_id,
            status=revision_response.status
        )
        
        actions = RevisionPermissionService.get_available_actions(current_user, revision)
        
        return {"available_actions": actions}
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/{revision_id}/request-modification", response_model=SuccessResponse)
async def request_modification(
    revision_id: UUID,
    instruction_data: ModificationInstructionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """修正指示を送信（UnderReview → RevisionRequested）"""
    workflow_service = WorkflowService(db)
    instruction_service = RevisionInstructionService(db)
    
    try:
        # 状態を修正依頼中に変更
        await workflow_service.transition_status(
            revision_id=revision_id,
            new_status=RevisionStatus.REVISION_REQUESTED,
            user_id=current_user.id,
            user_role=current_user.role
        )
        
        # 修正指示を作成
        await instruction_service.create_instruction(
            revision_id=revision_id,
            instruction_data=instruction_data,
            instructor_id=current_user.id
        )
        
        await db.commit()
        
        return SuccessResponse(message="修正指示を送信しました")
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except (NotFoundError, InvalidStateError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{revision_id}/instructions", response_model=List[ModificationInstructionResponse])
async def get_revision_instructions(
    revision_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案の修正指示一覧を取得"""
    instruction_service = RevisionInstructionService(db)
    
    try:
        instructions = await instruction_service.get_instructions_for_revision(revision_id)
        return instructions
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.patch("/{revision_id}/instructions/{instruction_id}/resolve", response_model=ModificationInstructionResponse)
async def resolve_instruction(
    revision_id: UUID,
    instruction_id: UUID,
    resolution_data: dict = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """修正指示を解決済みにマーク"""
    instruction_service = RevisionInstructionService(db)
    
    try:
        resolution_comment = resolution_data.get("comment") if resolution_data else None
        instruction = await instruction_service.resolve_instruction(
            instruction_id=instruction_id,
            resolution_comment=resolution_comment
        )
        await db.commit()
        
        return instruction
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/{revision_id}/resubmit", response_model=SuccessResponse)
async def resubmit_revision(
    revision_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案を再提出（RevisionRequested → UnderReview）"""
    workflow_service = WorkflowService(db)
    
    try:
        await workflow_service.transition_status(
            revision_id=revision_id,
            new_status=RevisionStatus.UNDER_REVIEW,
            user_id=current_user.id,
            user_role=current_user.role
        )
        await db.commit()
        
        return SuccessResponse(message="修正案を再提出しました")
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except (NotFoundError, InvalidStateError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{revision_id}/edit-history")
async def get_edit_history(
    revision_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案の編集履歴を取得"""
    edit_history_service = EditHistoryService(db)
    
    try:
        history = await edit_history_service.get_edit_history(revision_id)
        return {"edit_history": history}
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/{revision_id}/version-diff")
async def get_version_diff(
    revision_id: UUID,
    from_version: int = Query(..., description="From version"),
    to_version: int = Query(..., description="To version"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """指定バージョン間の差分を取得"""
    edit_history_service = EditHistoryService(db)
    
    try:
        diff = await edit_history_service.get_version_diff(
            revision_id=revision_id,
            from_version=from_version,
            to_version=to_version
        )
        return diff
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/{revision_id}/approval-history", response_model=List[ApprovalHistoryResponse])
async def get_approval_history(
    revision_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修正案の承認履歴を取得"""
    approval_service = ApprovalService(db)
    
    try:
        histories = await approval_service.get_approval_history(
            revision_id=revision_id,
            user_id=current_user.id,
            user_role=current_user.role
        )
        
        # Convert to response schema with actor information
        response_histories = []
        for history in histories:
            response_history = ApprovalHistoryResponse(
                id=history.id,
                revision_id=history.revision_id,
                actor_id=history.actor_id,
                action=history.action,
                comment=history.comment,
                created_at=history.created_at,
                updated_at=history.updated_at,
                actor_name=history.actor.full_name if history.actor else None,
                actor_username=history.actor.username if history.actor else None
            )
            response_histories.append(response_history)
        
        return response_histories
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/approval-status-counts", response_model=ApprovalStatusCounts)
async def get_approval_status_counts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """承認者向けの修正案ステータス集計を取得"""
    approval_service = ApprovalService(db)
    
    try:
        counts = await approval_service.get_revision_status_counts(current_user.role)
        return ApprovalStatusCounts(**counts)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status counts: {str(e)}"
        )