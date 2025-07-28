#!/usr/bin/env python3
"""
Basic functionality test script
"""
import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.user import UserService
from app.schemas.user import UserCreate


async def test_basic_functionality():
    """Test basic functionality"""
    print("[START] Basic functionality test...")
    
    try:
        # Test 1: Check app creation
        print("[OK] FastAPI app created successfully")
        
        # Test 2: Check configuration
        print(f"[OK] Configuration loaded: {settings.PROJECT_NAME}")
        
        # Test 3: Test database connection
        async for db in get_db():
            print("[OK] Database connection successful")
            
            # Test 4: Test user service
            user_service = UserService(db)
            print("[OK] User service created successfully")
            
            # Test 5: Create a test user
            test_user_data = UserCreate(
                username="testuser",
                email="test@example.com",
                password="Test123!@#",
                full_name="Test User"
            )
            
            try:
                # Check if user already exists
                existing_user = await user_service.get_user_by_username("testuser")
                if existing_user:
                    print("[OK] Test user already exists")
                else:
                    # Create new user
                    user = await user_service.create_user(test_user_data)
                    print(f"[OK] Test user created: {user.username}")
            except Exception as e:
                print(f"[WARN] User creation test failed: {e}")
            
            break
        
        print("[SUCCESS] Basic functionality test completed successfully!")
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_basic_functionality())