#!/usr/bin/env python3
"""
Simple Workflow Test Script
Task 2.10で実装したワークフロー機能をテストします
"""

import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000"

async def test_basic_workflow():
    """基本的なワークフローテスト"""
    print("Starting basic workflow test...")
    
    async with httpx.AsyncClient() as client:
        # Test 1: Health Check
        print("\n1. Health Check")
        try:
            response = await client.get(f"{BASE_URL}/")
            print(f"   Health check: {response.status_code}")
        except Exception as e:
            print(f"   Server not running or error: {e}")
            return False
        
        # Test 2: User Registration (Proposer)
        print("\n2. User Registration")
        proposer_data = {
            "username": "test_proposer",
            "email": "proposer@test.com", 
            "password": "TestPass123!",
            "full_name": "Test Proposer",
            "role": "general"
        }
        
        response = await client.post(f"{BASE_URL}/api/v1/users/register", json=proposer_data)
        print(f"   Proposer registration: {response.status_code}")
        if response.status_code != 201:
            print(f"   Error: {response.text}")
            
        # Test 3: User Registration (Approver)
        approver_data = {
            "username": "test_approver",
            "email": "approver@test.com",
            "password": "TestPass123!",
            "full_name": "Test Approver", 
            "role": "approver"
        }
        
        response = await client.post(f"{BASE_URL}/api/v1/users/register", json=approver_data)
        print(f"   Approver registration: {response.status_code}")
        if response.status_code != 201:
            print(f"   Error: {response.text}")
        
        # Test 4: Login (Proposer)
        print("\n3. Login")
        login_data = {
            "username": "test_proposer",
            "password": "TestPass123!"
        }
        
        response = await client.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)
        print(f"   Proposer login: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            proposer_token = token_data.get("access_token")
            proposer_headers = {"Authorization": f"Bearer {proposer_token}"}
            print(f"   Got proposer token: {proposer_token[:20]}...")
        else:
            print(f"   Login failed: {response.text}")
            return False
        
        # Test 5: Login (Approver)
        login_data = {
            "username": "test_approver",
            "password": "TestPass123!"
        }
        
        response = await client.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)
        print(f"   Approver login: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            approver_token = token_data.get("access_token")
            approver_headers = {"Authorization": f"Bearer {approver_token}"}
            print(f"   Got approver token: {approver_token[:20]}...")
        else:
            print(f"   Login failed: {response.text}")
            return False
        
        # Test 6: Create Revision
        print("\n4. Create Revision")
        revision_data = {
            "target_article_id": "ARTICLE001",
            "reason": "Test revision for workflow functionality",
            "modifications": {
                "title": "Updated Test Article Title",
                "info_category": "02",
                "answer": "This is an updated answer for testing workflow"
            }
        }
        
        response = await client.post(
            f"{BASE_URL}/api/v1/revisions",
            json=revision_data,
            headers=proposer_headers
        )
        print(f"   Create revision: {response.status_code}")
        
        if response.status_code == 201:
            revision = response.json()
            revision_id = revision.get("id")
            print(f"   Created revision ID: {revision_id}")
            print(f"   Status: {revision.get('status')}")
        else:
            print(f"   Error: {response.text}")
            return False
        
        # Test 7: Get Available Actions (Proposer)
        print("\n5. Get Available Actions")
        response = await client.get(
            f"{BASE_URL}/api/v1/revisions/{revision_id}/available-actions",
            headers=proposer_headers
        )
        print(f"   Get actions (proposer): {response.status_code}")
        if response.status_code == 200:
            actions = response.json()
            print(f"   Proposer actions: {actions.get('available_actions', [])}")
        
        # Test 8: Submit Revision (Draft -> UnderReview)
        print("\n6. Submit Revision")
        response = await client.post(
            f"{BASE_URL}/api/v1/revisions/{revision_id}/submit",
            headers=proposer_headers
        )
        print(f"   Submit revision: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   Message: {result.get('message')}")
        else:
            print(f"   Error: {response.text}")
        
        # Test 9: Get Revision Status After Submit
        response = await client.get(
            f"{BASE_URL}/api/v1/revisions/{revision_id}",
            headers=proposer_headers
        )
        if response.status_code == 200:
            revision = response.json()
            print(f"   New status: {revision.get('status')}")
        
        # Test 10: Approve Revision (UnderReview -> Approved)
        print("\n7. Approve Revision")
        approval_data = {
            "comment": "Test approval comment"
        }
        
        response = await client.post(
            f"{BASE_URL}/api/v1/revisions/{revision_id}/approve",
            json=approval_data,
            headers=approver_headers
        )
        print(f"   Approve revision: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   Message: {result.get('message')}")
        else:
            print(f"   Error: {response.text}")
        
        # Test 11: Final Status Check
        print("\n8. Final Status Check")
        response = await client.get(
            f"{BASE_URL}/api/v1/revisions/{revision_id}",
            headers=proposer_headers
        )
        if response.status_code == 200:
            revision = response.json()
            print(f"   Final status: {revision.get('status')}")
            print(f"   Approved at: {revision.get('approved_at')}")
            print(f"   Approver: {revision.get('approver_name')}")
        
        print("\nWorkflow test completed successfully!")
        return True


if __name__ == "__main__":
    asyncio.run(test_basic_workflow())