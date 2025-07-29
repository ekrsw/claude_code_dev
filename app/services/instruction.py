from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.constants.enums import RevisionStatus, Priority
from app.models.revision import RevisionInstruction
from app.repositories.revision import RevisionInstructionRepository
from app.repositories.user import UserRepository
from app.schemas.revision import (
    ModificationInstructionCreate,
    ModificationInstructionResponse
)
from app.core.exceptions import NotFoundError, AuthorizationError

logger = structlog.get_logger()


class RevisionInstructionService:
    """修正指示管理サービス"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.instruction_repo = RevisionInstructionRepository(db)
        self.user_repo = UserRepository(db)
    
    async def create_instruction(
        self,
        revision_id: UUID,
        instruction_data: ModificationInstructionCreate,
        instructor_id: UUID
    ) -> ModificationInstructionResponse:
        """修正指示を作成"""
        # データベースに保存
        created_instruction = await self.instruction_repo.create(
            revision_id=revision_id,
            instructor_id=instructor_id,
            instruction_text=instruction_data.instruction_text,
            required_fields=instruction_data.required_fields,
            priority=instruction_data.priority,
            due_date=instruction_data.due_date
        )
        await self.db.flush()
        
        logger.info(
            "Modification instruction created",
            instruction_id=str(created_instruction.id),
            revision_id=str(revision_id),
            instructor_id=str(instructor_id)
        )
        
        return await self._build_instruction_response(created_instruction)
    
    async def get_instructions_for_revision(
        self,
        revision_id: UUID
    ) -> List[ModificationInstructionResponse]:
        """修正案の修正指示一覧を取得"""
        instructions = await self.instruction_repo.get_by_revision(revision_id)
        
        return [
            await self._build_instruction_response(instruction)
            for instruction in instructions
        ]
    
    async def get_unresolved_instructions(
        self,
        revision_id: UUID
    ) -> List[ModificationInstructionResponse]:
        """未解決の修正指示一覧を取得"""
        instructions = await self.instruction_repo.get_unresolved(revision_id)
        
        return [
            await self._build_instruction_response(instruction)
            for instruction in instructions
        ]
    
    async def resolve_instruction(
        self,
        instruction_id: UUID,
        resolution_comment: Optional[str] = None
    ) -> ModificationInstructionResponse:
        """修正指示を解決済みにマーク"""
        instruction = await self.instruction_repo.get(instruction_id)
        if not instruction:
            raise NotFoundError("修正指示が見つかりません")
        
        instruction.resolved_at = datetime.utcnow()
        instruction.resolution_comment = resolution_comment
        
        await self.db.flush()
        
        logger.info(
            "Modification instruction resolved",
            instruction_id=str(instruction_id),
            resolution_comment=resolution_comment
        )
        
        return await self._build_instruction_response(instruction)
    
    async def _build_instruction_response(
        self,
        instruction: RevisionInstruction
    ) -> ModificationInstructionResponse:
        """修正指示レスポンスを構築"""
        # 指示者の情報を取得
        instructor = instruction.instructor if hasattr(instruction, 'instructor') else await self.user_repo.get(instruction.instructor_id)
        
        response_data = {
            **instruction.__dict__,
            'instructor_name': instructor.full_name if instructor else None
        }
        
        return ModificationInstructionResponse(**response_data)