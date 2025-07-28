#!/usr/bin/env python3
"""
Manual testing script for the Knowledge Revision Management API
"""
import asyncio
import json
import sys
import os
from typing import Dict, Any

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from httpx import AsyncClient, ASGITransport
from app.main import app


class APITester:
    def __init__(self):
        self.transport = ASGITransport(app=app)
        self.base_url = "http://test"
        self.access_token = None
        self.refresh_token = None
        
    async def make_request(self, method: str, endpoint: str, data: Dict[Any, Any] = None, headers: Dict[str, str] = None):
        """Make HTTP request to API"""
        async with AsyncClient(transport=self.transport, base_url=self.base_url) as client:
            if headers is None:
                headers = {}
            
            if self.access_token and 'Authorization' not in headers:
                headers['Authorization'] = f"Bearer {self.access_token}"
            
            if method.upper() == "GET":
                response = await client.get(endpoint, headers=headers)
            elif method.upper() == "POST":
                response = await client.post(endpoint, json=data, headers=headers)
            elif method.upper() == "PUT":
                response = await client.put(endpoint, json=data, headers=headers)
            elif method.upper() == "DELETE":
                response = await client.delete(endpoint, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            return response
    
    def print_response(self, title: str, response, show_body: bool = True):
        """Print formatted response"""
        print(f"\n{'='*20} {title} {'='*20}")
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if show_body:
            try:
                body = response.json()
                print(f"Body: {json.dumps(body, indent=2, ensure_ascii=False)}")
            except:
                print(f"Body: {response.text}")
        print("="*60)
    
    async def test_health_endpoints(self):
        """Test health and root endpoints"""
        print("\n[TEST] Health and Root Endpoints")
        
        # Root endpoint
        response = await self.make_request("GET", "/")
        self.print_response("Root Endpoint", response)
        
        # Health endpoint
        response = await self.make_request("GET", "/health")
        self.print_response("Health Check", response)
    
    async def test_user_registration(self):
        """Test user registration"""
        print("\n[TEST] User Registration")
        
        user_data = {
            "username": "testuser_manual",
            "email": "manual@test.com",
            "password": "Test123!@#",
            "full_name": "Manual Test User"
        }
        
        response = await self.make_request("POST", "/api/v1/users/register", user_data)
        self.print_response("User Registration", response)
        
        return response.status_code == 201
    
    async def test_user_login(self):
        """Test user login"""
        print("\n[TEST] User Login")
        
        login_data = {
            "username": "testuser_manual",
            "password": "Test123!@#"
        }
        
        response = await self.make_request("POST", "/api/v1/auth/login", login_data)
        self.print_response("User Login", response)
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            print(f"[INFO] Access token stored: {self.access_token[:20]}...")
            return True
        
        return False
    
    async def test_protected_endpoints(self):
        """Test protected endpoints with authentication"""
        print("\n[TEST] Protected Endpoints")
        
        if not self.access_token:
            print("[ERROR] No access token available. Please login first.")
            return
        
        # Test current user info
        response = await self.make_request("GET", "/api/v1/users/me")
        self.print_response("Current User Info", response)
        
        # Test users list (if admin)
        response = await self.make_request("GET", "/api/v1/users/")
        self.print_response("Users List", response)
    
    async def test_article_endpoints(self):
        """Test article-related endpoints"""
        print("\n[TEST] Article Endpoints")
        
        # Test articles list
        response = await self.make_request("GET", "/api/v1/articles/")
        self.print_response("Articles List", response)
        
        # Test categories list
        response = await self.make_request("GET", "/api/v1/categories/")
        self.print_response("Categories List", response)
    
    async def test_token_refresh(self):
        """Test token refresh"""
        print("\n[TEST] Token Refresh")
        
        if not self.refresh_token:
            print("[ERROR] No refresh token available.")
            return
        
        refresh_data = {
            "refresh_token": self.refresh_token
        }
        
        response = await self.make_request("POST", "/api/v1/auth/refresh", refresh_data)
        self.print_response("Token Refresh", response)
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            print(f"[INFO] New access token stored: {self.access_token[:20]}...")
    
    async def run_all_tests(self):
        """Run all tests in sequence"""
        print("=" * 80)
        print("KNOWLEDGE REVISION MANAGEMENT API - MANUAL TEST")
        print("=" * 80)
        
        try:
            # Basic endpoints
            await self.test_health_endpoints()
            
            # User registration and authentication
            registration_success = await self.test_user_registration()
            if registration_success:
                login_success = await self.test_user_login()
                if login_success:
                    await self.test_protected_endpoints()
                    await self.test_token_refresh()
            
            # Article endpoints
            await self.test_article_endpoints()
            
            print("\n" + "="*80)
            print("MANUAL TEST COMPLETED")
            print("="*80)
            
        except Exception as e:
            print(f"\n[ERROR] Test failed: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Main function"""
    tester = APITester()
    await tester.run_all_tests()


if __name__ == "__main__":
    # Run the manual test
    asyncio.run(main())