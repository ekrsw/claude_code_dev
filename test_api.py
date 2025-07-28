#!/usr/bin/env python3
"""
Test API endpoints without starting the server
"""
import asyncio
import json
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.core.config import settings
from app.db.session import get_db
from fastapi.testclient import TestClient
from httpx import AsyncClient


def test_sync_endpoints():
    """Test API endpoints synchronously"""
    print("[START] Testing API endpoints...")
    
    # Create test client
    client = TestClient(app)
    
    # Test health check
    response = client.get("/")
    print(f"[INFO] Health check: {response.status_code}")
    if response.status_code == 200:
        print(f"[OK] Response: {response.json()}")
    
    # Test docs endpoint
    response = client.get("/docs")
    print(f"[INFO] API docs: {response.status_code}")
    if response.status_code == 200:
        print("[OK] API documentation accessible")
    
    # Test OpenAPI schema
    response = client.get("/openapi.json")
    print(f"[INFO] OpenAPI schema: {response.status_code}")
    if response.status_code == 200:
        print("[OK] OpenAPI schema accessible")
    
    print("[SUCCESS] API endpoint test completed!")


async def test_async_endpoints():
    """Test API endpoints asynchronously"""
    print("[START] Testing async API endpoints...")
    
    # Test database connection through app startup
    try:
        await app.router.startup()
        print("[OK] App startup successful")
    except Exception as e:
        print(f"[WARN] App startup issue: {e}")
    
    # Use async client for more realistic testing
    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/")
        print(f"[INFO] Async health check: {response.status_code}")
        if response.status_code == 200:
            print(f"[OK] Async response: {response.json()}")
    
    print("[SUCCESS] Async API test completed!")


if __name__ == "__main__":
    # Run sync tests
    test_sync_endpoints()
    
    # Run async tests
    asyncio.run(test_async_endpoints())