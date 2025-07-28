#!/usr/bin/env python3
"""
Insert sample data for testing
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from app.db.session import get_db
from app.models.category import InfoCategory
from app.models.article import Article
from app.models.user import User
from app.services.user import UserService
from app.schemas.user import UserCreate


async def insert_sample_data():
    """Insert sample data for testing"""
    print("[START] Inserting sample data...")
    
    try:
        async for db in get_db():
            # Sample categories
            categories = [
                InfoCategory(
                    code="01",
                    display_name="システム操作",
                    display_order=1,
                    is_active=True
                ),
                InfoCategory(
                    code="02", 
                    display_name="業務プロセス",
                    display_order=2,
                    is_active=True
                ),
                InfoCategory(
                    code="03",
                    display_name="技術情報",
                    display_order=3,
                    is_active=True
                )
            ]
            
            # Add categories
            for category in categories:
                result = await db.execute(
                    select(InfoCategory).where(InfoCategory.code == category.code)
                )
                existing = result.scalar_one_or_none()
                if not existing:
                    db.add(category)
                    print(f"[OK] Added category: {category.display_name}")
                else:
                    print(f"[INFO] Category already exists: {category.display_name}")
            
            await db.commit()
            
            # Sample articles
            articles = [
                Article(
                    article_id="SYS001",
                    article_number="SYS-001",
                    title="システムログイン方法",
                    info_category_code="01",
                    keywords="ログイン,認証,パスワード",
                    importance=True,
                    target="全ユーザー",
                    question="システムにログインするにはどうすればよいですか？",
                    answer="ユーザー名とパスワードを入力してログインボタンをクリックしてください。",
                    additional_comment="初回ログイン時はパスワード変更が必要です。",
                    publish_start=datetime.now(),
                    publish_end=datetime.now() + timedelta(days=365),
                    approval_group="システム管理者",
                    is_active=True
                ),
                Article(
                    article_id="BIZ001",
                    article_number="BIZ-001", 
                    title="申請プロセスの流れ",
                    info_category_code="02",
                    keywords="申請,承認,プロセス",
                    importance=False,
                    target="申請者",
                    question="申請はどのような流れで進みますか？",
                    answer="申請→上長承認→部門承認→完了の順で進みます。",
                    additional_comment="緊急時は電話連絡も併用してください。",
                    publish_start=datetime.now(),
                    publish_end=datetime.now() + timedelta(days=365),
                    approval_group="業務責任者",
                    is_active=True
                ),
                Article(
                    article_id="TECH001",
                    article_number="TECH-001",
                    title="APIの使用方法",
                    info_category_code="03", 
                    keywords="API,REST,認証",
                    importance=True,
                    target="開発者",
                    question="APIを使用するにはどうすればよいですか？",
                    answer="認証トークンを取得してヘッダーに設定し、リクエストを送信してください。",
                    additional_comment="レート制限があるため注意してください。",
                    publish_start=datetime.now(),
                    publish_end=datetime.now() + timedelta(days=365),
                    approval_group="技術責任者",
                    is_active=True
                )
            ]
            
            # Add articles
            for article in articles:
                result = await db.execute(
                    select(Article).where(Article.article_id == article.article_id)
                )
                existing = result.scalar_one_or_none()
                if not existing:
                    db.add(article)
                    print(f"[OK] Added article: {article.title}")
                else:
                    print(f"[INFO] Article already exists: {article.title}")
            
            await db.commit()
            
            # Sample admin user
            user_service = UserService(db)
            try:
                admin_data = UserCreate(
                    username="admin",
                    email="admin@example.com",
                    password="Admin123!@#",
                    full_name="System Administrator"
                )
                
                existing_admin = await user_service.get_user_by_username("admin")
                if not existing_admin:
                    admin_user = await user_service.create_user(admin_data)
                    
                    # Update role to ADMIN
                    admin_user.role = "ADMIN"
                    admin_user.is_sv = True
                    await db.commit()
                    
                    print(f"[OK] Created admin user: {admin_user.username}")
                else:
                    print("[INFO] Admin user already exists")
                    
            except Exception as e:
                print(f"[WARN] Admin user creation failed: {e}")
            
            break
        
        print("[SUCCESS] Sample data inserted successfully!")
        
    except Exception as e:
        print(f"[ERROR] Failed to insert sample data: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(insert_sample_data())