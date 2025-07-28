#!/usr/bin/env python3
"""
ワークフロー機能の動作確認スクリプト
Task 2.10で実装したワークフロー機能をテストします
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, Any, Optional

BASE_URL = "http://localhost:8000"


class WorkflowTestClient:
    def __init__(self):
        self.client = httpx.AsyncClient()
        self.auth_token: Optional[str] = None
        self.revision_id: Optional[str] = None
    
    async def close(self):
        await self.client.aclose()
    
    async def register_user(self, username: str, email: str, password: str, role: str = "general") -> Dict[str, Any]:
        """ユーザー登録"""
        response = await self.client.post(
            f"{BASE_URL}/api/v1/users/register",
            json={
                "username": username,
                "email": email,
                "password": password,
                "full_name": f"{username} User",
                "role": role
            }
        )
        return response.status_code, response.json() if response.status_code < 400 else response.text
    
    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """ログイン"""
        response = await self.client.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={
                "username": username,
                "password": password
            }
        )
        if response.status_code == 200:
            data = response.json()
            self.auth_token = data.get("access_token")
            self.client.headers["Authorization"] = f"Bearer {self.auth_token}"
        return response.status_code, response.json() if response.status_code < 400 else response.text
    
    async def create_revision(self, article_id: str = "ARTICLE001") -> Dict[str, Any]:
        """修正案作成"""
        response = await self.client.post(
            f"{BASE_URL}/api/v1/revisions",
            json={
                "target_article_id": article_id,
                "reason": "テスト用の修正案です。タイトルとカテゴリを更新します。",
                "modifications": {
                    "title": "Updated Test Article",
                    "info_category": "02",
                    "answer": "This is an updated answer for testing"
                }
            }
        )
        if response.status_code == 201:
            data = response.json()
            self.revision_id = data.get("id")
        return response.status_code, response.json() if response.status_code < 400 else response.text
    
    async def get_revision(self, revision_id: str = None) -> Dict[str, Any]:
        """修正案詳細取得"""
        rid = revision_id or self.revision_id
        response = await self.client.get(f"{BASE_URL}/api/v1/revisions/{rid}")
        return response.status_code, response.json() if response.status_code < 400 else response.text
    
    async def get_available_actions(self, revision_id: str = None) -> Dict[str, Any]:
        """実行可能アクション取得"""
        rid = revision_id or self.revision_id
        response = await self.client.get(f"{BASE_URL}/api/v1/revisions/{rid}/available-actions")
        return response.status_code, response.json() if response.status_code < 400 else response.text
    
    async def submit_revision(self, revision_id: str = None) -> Dict[str, Any]:
        """修正案提出"""
        rid = revision_id or self.revision_id
        response = await self.client.post(f"{BASE_URL}/api/v1/revisions/{rid}/submit")
        return response.status_code, response.json() if response.status_code < 400 else response.text
    
    async def approve_revision(self, revision_id: str = None, comment: str = None) -> Dict[str, Any]:
        """修正案承認"""
        rid = revision_id or self.revision_id
        data = {"comment": comment} if comment else {}
        response = await self.client.post(f"{BASE_URL}/api/v1/revisions/{rid}/approve", json=data)
        return response.status_code, response.json() if response.status_code < 400 else response.text
    
    async def reject_revision(self, revision_id: str = None, comment: str = "テスト用の却下") -> Dict[str, Any]:
        """修正案却下"""
        rid = revision_id or self.revision_id
        response = await self.client.post(f"{BASE_URL}/api/v1/revisions/{rid}/reject", json={"comment": comment})
        return response.status_code, response.json() if response.status_code < 400 else response.text
    
    async def request_modification(self, revision_id: str = None) -> Dict[str, Any]:
        """修正指示送信"""
        rid = revision_id or self.revision_id
        response = await self.client.post(
            f"{BASE_URL}/api/v1/revisions/{rid}/request-modification",
            json={
                "instruction_text": "タイトルをもう少し具体的にしてください。また、回答内容に具体例を追加してください。",
                "required_fields": ["title", "answer"],
                "priority": "normal"
            }
        )
        return response.status_code, response.json() if response.status_code < 400 else response.text
    
    async def get_instructions(self, revision_id: str = None) -> Dict[str, Any]:
        """修正指示一覧取得"""
        rid = revision_id or self.revision_id
        response = await self.client.get(f"{BASE_URL}/api/v1/revisions/{rid}/instructions")
        return response.status_code, response.json() if response.status_code < 400 else response.text
    
    async def resubmit_revision(self, revision_id: str = None) -> Dict[str, Any]:
        """修正案再提出"""
        rid = revision_id or self.revision_id
        response = await self.client.post(f"{BASE_URL}/api/v1/revisions/{rid}/resubmit")
        return response.status_code, response.json() if response.status_code < 400 else response.text


async def run_workflow_test():
    """ワークフロー機能の動作確認"""
    print("Workflow Test Started")
    print("=" * 60)
    
    # テストクライアント初期化
    proposer = WorkflowTestClient()
    approver = WorkflowTestClient()
    
    try:
        # ===== 1. ユーザー登録とログイン =====
        print("\nStep 1: User Registration and Login")
        
        # 提案者ユーザー登録
        status, result = await proposer.register_user("test_proposer", "proposer@test.com", "TestPass123!", "general")
        print(f"Proposer registration: {status} - {'Success' if status == 201 else 'Failed'}")
        
        # 承認者ユーザー登録
        status, result = await approver.register_user("test_approver", "approver@test.com", "TestPass123!", "approver")
        print(f"Approver registration: {status} - {'Success' if status == 201 else 'Failed'}")
        
        # ログイン
        status, result = await proposer.login("test_proposer", "TestPass123!")
        print(f"Proposer login: {status} - {'Success' if status == 200 else 'Failed'}")
        
        status, result = await approver.login("test_approver", "TestPass123!")
        print(f"Approver login: {status} - {'Success' if status == 200 else 'Failed'}")
        
        # ===== 2. 修正案作成 =====
        print("\nStep 2: Create Revision (Draft status)")
        
        status, result = await proposer.create_revision()
        if status == 201:
            print(f"✅ 修正案作成成功: ID = {proposer.revision_id}")
        else:
            print(f"❌ 修正案作成失敗: {status} - {result}")
            return
        
        # 作成直後の状態確認
        status, revision_data = await proposer.get_revision()
        if status == 200:
            print(f"   現在の状態: {revision_data.get('status')}")
            print(f"   修正内容: {revision_data.get('modified_fields')}")
        
        # ===== 3. 実行可能アクション確認 =====
        print("\n🎯 Step 3: 実行可能アクション確認")
        
        status, actions = await proposer.get_available_actions()
        if status == 200:
            print(f"   提案者が実行可能なアクション: {actions.get('available_actions', [])}")
        
        status, actions = await approver.get_available_actions(proposer.revision_id)
        if status == 200:
            print(f"   承認者が実行可能なアクション: {actions.get('available_actions', [])}")
        
        # ===== 4. 修正案提出 (Draft → UnderReview) =====
        print("\n📤 Step 4: 修正案提出 (Draft → UnderReview)")
        
        status, result = await proposer.submit_revision()
        if status == 200:
            print("✅ 修正案提出成功")
            
            # 状態確認
            status, revision_data = await proposer.get_revision()
            if status == 200:
                print(f"   状態変更後: {revision_data.get('status')}")
        else:
            print(f"❌ 修正案提出失敗: {status} - {result}")
        
        # ===== 5. 修正指示送信 (UnderReview → RevisionRequested) =====
        print("\n📝 Step 5: 修正指示送信 (UnderReview → RevisionRequested)")
        
        status, result = await approver.request_modification(proposer.revision_id)
        if status == 200:
            print("✅ 修正指示送信成功")
            
            # 修正指示一覧確認
            status, instructions = await proposer.get_instructions()
            if status == 200:
                print(f"   修正指示数: {len(instructions)}")
                if instructions:
                    print(f"   指示内容: {instructions[0].get('instruction_text', '')[:50]}...")
        else:
            print(f"❌ 修正指示送信失敗: {status} - {result}")
        
        # ===== 6. 修正案再提出 (RevisionRequested → UnderReview) =====
        print("\n🔄 Step 6: 修正案再提出 (RevisionRequested → UnderReview)")
        
        status, result = await proposer.resubmit_revision()
        if status == 200:
            print("✅ 修正案再提出成功")
            
            # 状態確認
            status, revision_data = await proposer.get_revision()
            if status == 200:
                print(f"   状態変更後: {revision_data.get('status')}")
        else:
            print(f"❌ 修正案再提出失敗: {status} - {result}")
        
        # ===== 7. 修正案承認 (UnderReview → Approved) =====
        print("\n✅ Step 7: 修正案承認 (UnderReview → Approved)")
        
        status, result = await approver.approve_revision(proposer.revision_id, "内容を確認しました。承認します。")
        if status == 200:
            print("✅ 修正案承認成功")
            
            # 最終状態確認
            status, revision_data = await proposer.get_revision()
            if status == 200:
                print(f"   最終状態: {revision_data.get('status')}")
                print(f"   承認者: {revision_data.get('approver_name')}")
                print(f"   承認日時: {revision_data.get('approved_at')}")
        else:
            print(f"❌ 修正案承認失敗: {status} - {result}")
        
        print("\n🎉 ワークフロー機能動作確認テスト完了")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ テスト実行中にエラーが発生しました: {e}")
    
    finally:
        await proposer.close()
        await approver.close()


if __name__ == "__main__":
    asyncio.run(run_workflow_test())