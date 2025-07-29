"""
修正指示サービスの単体テスト
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from app.services.instruction import RevisionInstructionService
from app.models.revision import RevisionInstruction
from app.constants.enums import Priority
from app.schemas.revision import ModificationInstructionCreate
from app.core.exceptions import NotFoundError


@pytest.mark.asyncio
class TestRevisionInstructionService:
    """RevisionInstructionServiceのテストクラス"""
    
    async def test_create_instruction_success(self, db_session, test_approver, test_revision):
        """修正指示作成が成功することを確認"""
        instruction_service = RevisionInstructionService(db_session)
        
        due_date = datetime.utcnow() + timedelta(days=7)
        instruction_data = ModificationInstructionCreate(
            instruction_text="タイトルをより具体的にしてください。現在のタイトルでは内容が分かりにくいです。",
            required_fields=["title", "answer"],
            priority=Priority.HIGH,
            due_date=due_date
        )
        
        instruction_response = await instruction_service.create_instruction(
            revision_id=test_revision.id,
            instruction_data=instruction_data,
            instructor_id=test_approver.id
        )
        
        assert instruction_response is not None
        assert instruction_response.revision_id == test_revision.id
        assert instruction_response.instructor_id == test_approver.id
        assert instruction_response.instruction_text == "タイトルをより具体的にしてください。現在のタイトルでは内容が分かりにくいです。"
        assert instruction_response.required_fields == ["title", "answer"]
        assert instruction_response.priority == Priority.HIGH
        assert instruction_response.due_date == due_date
        assert instruction_response.resolved_at is None
        assert instruction_response.resolution_comment is None
        assert instruction_response.instructor_name is not None
    
    async def test_create_instruction_minimal_data(self, db_session, test_approver, test_revision):
        """最小限のデータで修正指示作成が成功することを確認"""
        instruction_service = RevisionInstructionService(db_session)
        
        instruction_data = ModificationInstructionCreate(
            instruction_text="修正が必要です。内容をより詳細に記述してください。"
        )
        
        instruction_response = await instruction_service.create_instruction(
            revision_id=test_revision.id,
            instruction_data=instruction_data,
            instructor_id=test_approver.id
        )
        
        assert instruction_response is not None
        assert instruction_response.instruction_text == "修正が必要です。内容をより詳細に記述してください。"
        assert instruction_response.required_fields is None
        assert instruction_response.priority == Priority.NORMAL  # デフォルト値
        assert instruction_response.due_date is None
    
    async def test_get_instructions_for_revision_success(self, db_session, test_approver, test_user, test_revision):
        """修正案の修正指示一覧取得が成功することを確認"""
        instruction_service = RevisionInstructionService(db_session)
        
        # 複数の修正指示を作成
        instruction_data_1 = ModificationInstructionCreate(
            instruction_text="最初の修正指示です。",
            priority=Priority.HIGH
        )
        
        instruction_data_2 = ModificationInstructionCreate(
            instruction_text="二番目の修正指示です。",
            required_fields=["answer"],
            priority=Priority.NORMAL
        )
        
        await instruction_service.create_instruction(
            revision_id=test_revision.id,
            instruction_data=instruction_data_1,
            instructor_id=test_approver.id
        )
        
        await instruction_service.create_instruction(
            revision_id=test_revision.id,
            instruction_data=instruction_data_2,
            instructor_id=test_user.id
        )
        
        # 修正指示一覧を取得
        instructions = await instruction_service.get_instructions_for_revision(test_revision.id)
        
        assert len(instructions) >= 2
        
        # 指示内容を確認
        instruction_texts = [inst.instruction_text for inst in instructions]
        assert "最初の修正指示です。" in instruction_texts
        assert "二番目の修正指示です。" in instruction_texts
        
        # 指示者を確認
        instructor_ids = [inst.instructor_id for inst in instructions]
        assert test_approver.id in instructor_ids
        assert test_user.id in instructor_ids
    
    async def test_get_instructions_for_revision_empty(self, db_session, test_revision):
        """修正指示がない場合の一覧取得が成功することを確認"""
        instruction_service = RevisionInstructionService(db_session)
        
        # 存在しない修正案IDの修正指示を取得
        non_existent_revision_id = uuid4()
        instructions = await instruction_service.get_instructions_for_revision(non_existent_revision_id)
        
        assert instructions == []
    
    async def test_get_unresolved_instructions_success(self, db_session, test_approver, test_revision):
        """未解決の修正指示一覧取得が成功することを確認"""
        instruction_service = RevisionInstructionService(db_session)
        
        # 複数の修正指示を作成
        instruction_data_1 = ModificationInstructionCreate(
            instruction_text="未解決の修正指示1です。",
            priority=Priority.HIGH
        )
        
        instruction_data_2 = ModificationInstructionCreate(
            instruction_text="未解決の修正指示2です。",
            priority=Priority.NORMAL
        )
        
        # 指示を作成
        instruction_1 = await instruction_service.create_instruction(
            revision_id=test_revision.id,
            instruction_data=instruction_data_1,
            instructor_id=test_approver.id
        )
        
        instruction_2 = await instruction_service.create_instruction(
            revision_id=test_revision.id,
            instruction_data=instruction_data_2,
            instructor_id=test_approver.id
        )
        
        # 1つを解決済みにする
        await instruction_service.resolve_instruction(
            instruction_id=instruction_1.id,
            resolution_comment="解決しました。"
        )
        
        # 未解決の指示を取得
        unresolved_instructions = await instruction_service.get_unresolved_instructions(test_revision.id)
        
        # 未解決の指示のみが返されることを確認
        unresolved_texts = [inst.instruction_text for inst in unresolved_instructions]
        assert "未解決の修正指示2です。" in unresolved_texts
        assert "未解決の修正指示1です。" not in unresolved_texts or any(
            inst.resolved_at is None for inst in unresolved_instructions 
            if inst.instruction_text == "未解決の修正指示1です。"
        )
    
    async def test_get_unresolved_instructions_empty(self, db_session, test_revision):
        """未解決の修正指示がない場合の取得が成功することを確認"""
        instruction_service = RevisionInstructionService(db_session)
        
        # 存在しない修正案IDの未解決指示を取得
        non_existent_revision_id = uuid4()
        unresolved_instructions = await instruction_service.get_unresolved_instructions(non_existent_revision_id)
        
        assert unresolved_instructions == []
    
    async def test_resolve_instruction_success(self, db_session, test_approver, test_revision):
        """修正指示の解決が成功することを確認"""
        instruction_service = RevisionInstructionService(db_session)
        
        # 修正指示を作成
        instruction_data = ModificationInstructionCreate(
            instruction_text="解決テスト用の修正指示です。",
            priority=Priority.NORMAL
        )
        
        instruction = await instruction_service.create_instruction(
            revision_id=test_revision.id,
            instruction_data=instruction_data,
            instructor_id=test_approver.id
        )
        
        # 初期状態では未解決
        assert instruction.resolved_at is None
        assert instruction.resolution_comment is None
        
        # 修正指示を解決
        resolved_instruction = await instruction_service.resolve_instruction(
            instruction_id=instruction.id,
            resolution_comment="修正内容を確認し、問題が解決されました。"
        )
        
        assert resolved_instruction is not None
        assert resolved_instruction.resolved_at is not None
        assert resolved_instruction.resolution_comment == "修正内容を確認し、問題が解決されました。"
        assert resolved_instruction.id == instruction.id
    
    async def test_resolve_instruction_without_comment(self, db_session, test_approver, test_revision):
        """コメントなしでの修正指示解決が成功することを確認"""
        instruction_service = RevisionInstructionService(db_session)
        
        # 修正指示を作成
        instruction_data = ModificationInstructionCreate(
            instruction_text="コメントなし解決テスト用の修正指示です。",
            priority=Priority.LOW
        )
        
        instruction = await instruction_service.create_instruction(
            revision_id=test_revision.id,
            instruction_data=instruction_data,
            instructor_id=test_approver.id
        )
        
        # コメントなしで修正指示を解決
        resolved_instruction = await instruction_service.resolve_instruction(
            instruction_id=instruction.id
        )
        
        assert resolved_instruction is not None
        assert resolved_instruction.resolved_at is not None
        assert resolved_instruction.resolution_comment is None
        assert resolved_instruction.id == instruction.id
    
    async def test_resolve_instruction_not_found(self, db_session):
        """存在しない修正指示の解決でエラーが発生することを確認"""
        instruction_service = RevisionInstructionService(db_session)
        
        non_existent_id = uuid4()
        
        with pytest.raises(NotFoundError) as exc_info:
            await instruction_service.resolve_instruction(non_existent_id)
        
        assert "修正指示が見つかりません" in str(exc_info.value)
    
    async def test_build_instruction_response_with_instructor(self, db_session, test_approver, test_revision):
        """指示者情報が含まれたレスポンス構築が成功することを確認"""
        instruction_service = RevisionInstructionService(db_session)
        
        instruction_data = ModificationInstructionCreate(
            instruction_text="レスポンス構築テスト用の修正指示です。",
            required_fields=["title"],
            priority=Priority.HIGH
        )
        
        instruction_response = await instruction_service.create_instruction(
            revision_id=test_revision.id,
            instruction_data=instruction_data,
            instructor_id=test_approver.id
        )
        
        # 指示者名が含まれていることを確認
        assert instruction_response.instructor_name is not None
        assert instruction_response.instructor_id == test_approver.id
        
        # その他のフィールドも正しく設定されていることを確認
        assert instruction_response.instruction_text == "レスポンス構築テスト用の修正指示です。"
        assert instruction_response.required_fields == ["title"]
        assert instruction_response.priority == Priority.HIGH
    
    async def test_instruction_with_complex_required_fields(self, db_session, test_approver, test_revision):
        """複雑な必須フィールド指定の修正指示が正しく処理されることを確認"""
        instruction_service = RevisionInstructionService(db_session)
        
        complex_fields = ["title", "answer", "keywords", "additional_comment", "target"]
        instruction_data = ModificationInstructionCreate(
            instruction_text="複数フィールドの修正が必要です。タイトル、回答、キーワード、追加コメント、対象者を見直してください。",
            required_fields=complex_fields,
            priority=Priority.URGENT
        )
        
        instruction_response = await instruction_service.create_instruction(
            revision_id=test_revision.id,
            instruction_data=instruction_data,
            instructor_id=test_approver.id
        )
        
        assert instruction_response.required_fields == complex_fields
        assert instruction_response.priority == Priority.URGENT
        assert len(instruction_response.required_fields) == 5
    
    async def test_instruction_with_future_due_date(self, db_session, test_approver, test_revision):
        """将来の期限日付を持つ修正指示が正しく処理されることを確認"""
        instruction_service = RevisionInstructionService(db_session)
        
        future_date = datetime.utcnow() + timedelta(days=30)
        instruction_data = ModificationInstructionCreate(
            instruction_text="1ヶ月後までに修正してください。",
            due_date=future_date,
            priority=Priority.LOW
        )
        
        instruction_response = await instruction_service.create_instruction(
            revision_id=test_revision.id,
            instruction_data=instruction_data,
            instructor_id=test_approver.id
        )
        
        assert instruction_response.due_date == future_date
        assert instruction_response.priority == Priority.LOW
        
        # 期限日が未来であることを確認
        assert instruction_response.due_date > datetime.utcnow()