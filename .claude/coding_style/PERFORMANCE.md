# PERFORMANCE.md

## 1. パフォーマンス基本方針

### 1.1 パフォーマンス目標
- **API レスポンス時間**: 95%のリクエストが500ms以内
- **データベースクエリ**: 単純クエリは50ms以内、複雑クエリは200ms以内
- **メモリ使用量**: 本番環境で1GB以下を維持
- **同時接続数**: 最低100同時ユーザーをサポート
- **可用性**: 99.9%のアップタイム

### 1.2 パフォーマンス原則
- **測定第一**: 推測ではなく測定に基づく最適化
- **ボトルネック特定**: 最も影響の大きい部分から改善
- **段階的最適化**: 小さな改善を積み重ねる
- **トレードオフ考慮**: メモリ vs CPU、複雑性 vs パフォーマンス
- **ユーザー体験重視**: 実際のユーザー影響を重視

## 2. データベースパフォーマンス

### 2.1 クエリ最適化
```python
# app/repositories/optimized_user_repository.py
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import text, func
from typing import List, Optional, Tuple

class OptimizedUserRepository:
    """パフォーマンス最適化されたユーザーリポジトリ"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_users_with_profile_efficient(self, limit: int = 100) -> List[User]:
        """効率的なユーザー・プロファイル取得（N+1問題解決）"""
        # 悪い例: N+1問題が発生
        # users = self.db.query(User).limit(limit).all()
        # for user in users:
        #     profile = user.profile  # 各ユーザーごとにクエリ実行
        
        # 良い例: JOINを使用してクエリを1回に削減
        return (
            self.db.query(User)
            .options(joinedload(User.profile))  # プロファイルを一緒に取得
            .limit(limit)
            .all()
        )
    
    def get_users_with_orders_efficient(self, user_ids: List[int]) -> List[User]:
        """効率的なユーザー・注文履歴取得"""
        return (
            self.db.query(User)
            .options(selectinload(User.orders))  # 別クエリで関連データ取得
            .filter(User.id.in_(user_ids))
            .all()
        )
    
    def get_user_statistics(self) -> dict:
        """集計クエリ最適化"""
        # 単一クエリで複数の統計を取得
        result = (
            self.db.query(
                func.count(User.id).label('total_users'),
                func.count(User.id).filter(User.is_active == True).label('active_users'),
                func.count(User.id).filter(User.created_at >= func.current_date()).label('new_today')
            )
            .first()
        )
        
        return {
            'total_users': result.total_users,
            'active_users': result.active_users,
            'new_today': result.new_today
        }
    
    def get_users_paginated_optimized(
        self, 
        page: int, 
        per_page: int, 
        filters: dict = None
    ) -> Tuple[List[User], int]:
        """最適化されたページネーション"""
        
        # ベースクエリ構築
        query = self.db.query(User)
        
        # フィルタ適用
        if filters:
            if filters.get('is_active') is not None:
                query = query.filter(User.is_active == filters['is_active'])
            
            if filters.get('search'):
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    User.username.ilike(search_term) |
                    User.email.ilike(search_term)
                )
        
        # 総数取得（サブクエリで最適化）
        total = query.count()
        
        # ページネーション適用
        users = (
            query
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        
        return users, total
    
    def bulk_create_users(self, user_data_list: List[dict]) -> List[User]:
        """バルクインサート最適化"""
        users = [User(**data) for data in user_data_list]
        
        # バルクインサート（個別INSERTより高速）
        self.db.bulk_save_objects(users)
        self.db.commit()
        
        return users
    
    def bulk_update_users(self, updates: List[dict]) -> None:
        """バルクアップデート最適化"""
        # 単一クエリで複数レコード更新
        self.db.bulk_update_mappings(User, updates)
        self.db.commit()
```

### 2.2 インデックス戦略
```python
# app/models/user.py - インデックス定義
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 複合インデックス定義
    __table_args__ = (
        # よく一緒に検索される条件の複合インデックス
        Index('ix_user_active_created', 'is_active', 'created_at'),
        # 検索クエリ用の複合インデックス
        Index('ix_user_search', 'username', 'email'),
    )

# マイグレーションファイルでのインデックス作成例
"""
# alembic/versions/xxx_add_performance_indexes.py
def upgrade():
    # パフォーマンス向上のためのインデックス追加
    op.create_index('ix_orders_user_status', 'orders', ['user_id', 'status'])
    op.create_index('ix_orders_created_at', 'orders', ['created_at'])
    
    # 部分インデックス（条件付きインデックス）
    op.execute(
        "CREATE INDEX CONCURRENTLY ix_active_users ON users (id) WHERE is_active = true"
    )

def downgrade():
    op.drop_index('ix_orders_user_status')
    op.drop_index('ix_orders_created_at')
    op.execute("DROP INDEX IF EXISTS ix_active_users")
"""
```

### 2.3 データベース接続プール最適化
```python
# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os

class DatabaseManager:
    """データベース接続管理"""
    
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        self.engine = self._create_optimized_engine()
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    def _create_optimized_engine(self):
        """最適化されたデータベースエンジン作成"""
        return create_engine(
            self.database_url,
            # 接続プール設定
            poolclass=QueuePool,
            pool_size=20,          # 通常の接続プール数
            max_overflow=30,       # 最大追加接続数
            pool_pre_ping=True,    # 接続確認
            pool_recycle=3600,     # 接続リサイクル（1時間）
            
            # クエリ最適化設定
            echo=False,            # 本番環境ではFalse
            future=True,           # SQLAlchemy 2.0スタイル
            
            # PostgreSQL固有の設定
            connect_args={
                "options": "-c timezone=utc",
                "application_name": "internal_tool_api"
            } if "postgresql" in self.database_url else {}
        )
    
    async def health_check(self) -> bool:
        """データベース接続ヘルスチェック"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    
    def get_connection_stats(self) -> dict:
        """接続プール統計情報"""
        pool = self.engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }

database_manager = DatabaseManager()

def get_db_session():
    """データベースセッション取得"""
    db = database_manager.SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## 3. キャッシュ戦略

### 3.1 Redis キャッシュ実装
```python
# app/services/cache_service.py
import redis
import json
import pickle
from typing import Any, Optional, Union
from functools import wraps
import asyncio
import logging

logger = logging.getLogger(__name__)

class CacheService:
    """Redis キャッシュサービス"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
    
    def get(self, key: str) -> Optional[Any]:
        """キャッシュ取得"""
        try:
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Cache get error for key {key}: {e}")
        return None
    
    def set(self, key: str, value: Any, expire_seconds: int = 3600) -> bool:
        """キャッシュ設定"""
        try:
            serialized_value = json.dumps(value, default=str)
            return self.redis_client.setex(key, expire_seconds, serialized_value)
        except (redis.RedisError, TypeError) as e:
            logger.warning(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """キャッシュ削除"""
        try:
            return bool(self.redis_client.delete(key))
        except redis.RedisError as e:
            logger.warning(f"Cache delete error for key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """パターンマッチでキャッシュ削除"""
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
        except redis.RedisError as e:
            logger.warning(f"Cache delete pattern error for {pattern}: {e}")
        return 0
    
    def increment(self, key: str, amount: int = 1, expire_seconds: int = 3600) -> Optional[int]:
        """カウンター増加（レート制限等で使用）"""
        try:
            with self.redis_client.pipeline() as pipe:
                pipe.incr(key, amount)
                pipe.expire(key, expire_seconds)
                results = pipe.execute()
                return results[0]
        except redis.RedisError as e:
            logger.warning(f"Cache increment error for key {key}: {e}")
            return None

cache_service = CacheService()

def cached(expire_seconds: int = 3600, key_prefix: str = ""):
    """キャッシュデコレーター"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # キャッシュキー生成
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # キャッシュから取得
            cached_result = cache_service.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 関数実行
            result = await func(*args, **kwargs)
            
            # キャッシュに保存
            cache_service.set(cache_key, result, expire_seconds)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 同期版
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            cached_result = cache_service.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            result = func(*args, **kwargs)
            cache_service.set(cache_key, result, expire_seconds)
            
            return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator
```

### 3.2 アプリケーションレベルキャッシュ
```python
# app/services/optimized_user_service.py
from functools import lru_cache
from app.services.cache_service import cached, cache_service

class OptimizedUserService:
    """キャッシュ最適化されたユーザーサービス"""
    
    def __init__(self, db_session, cache_service):
        self.db = db_session
        self.cache = cache_service
    
    @cached(expire_seconds=300, key_prefix="user")
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """ユーザー取得（5分キャッシュ）"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    @cached(expire_seconds=600, key_prefix="user_stats")
    async def get_user_statistics(self) -> dict:
        """ユーザー統計（10分キャッシュ）"""
        total_users = self.db.query(User).count()
        active_users = self.db.query(User).filter(User.is_active == True).count()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users
        }
    
    async def create_user(self, user_data: UserCreate) -> User:
        """ユーザー作成（キャッシュ無効化）"""
        user = User(**user_data.dict())
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        # 関連キャッシュを無効化
        self.cache.delete_pattern("user_stats:*")
        
        return user
    
    async def update_user(self, user_id: int, update_data: dict) -> Optional[User]:
        """ユーザー更新（キャッシュ無効化）"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        for key, value in update_data.items():
            setattr(user, key, value)
        
        self.db.commit()
        self.db.refresh(user)
        
        # 該当ユーザーのキャッシュを削除
        self.cache.delete(f"user:get_user_by_id:{user_id}")
        self.cache.delete_pattern("user_stats:*")
        
        return user
    
    @lru_cache(maxsize=100)
    def get_user_permissions(self, user_role: str) -> set:
        """ユーザー権限取得（メモリキャッシュ）"""
        # 権限マッピング（変更頻度が低いためメモリキャッシュ使用）
        permission_mapping = {
            "admin": {"read", "write", "delete", "manage"},
            "manager": {"read", "write"},
            "user": {"read"}
        }
        return permission_mapping.get(user_role, set())
```

### 3.3 HTTPキャッシュヘッダー
```python
# app/middleware/cache_middleware.py
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
import hashlib

class HTTPCacheMiddleware(BaseHTTPMiddleware):
    """HTTP キャッシュミドルウェア"""
    
    async def dispatch(self, request: Request, call_next):
        # キャッシュ可能なリクエストかチェック
        if request.method != "GET":
            return await call_next(request)
        
        # ETag生成用のリクエスト識別子
        request_id = f"{request.url.path}:{request.url.query}"
        etag = hashlib.md5(request_id.encode()).hexdigest()
        
        # クライアントのIf-None-Matchヘッダーチェック
        if_none_match = request.headers.get("if-none-match")
        if if_none_match == etag:
            return Response(status_code=304)  # Not Modified
        
        response = await call_next(request)
        
        # キャッシュヘッダーを追加
        if response.status_code == 200:
            if "/api/v1/users" in request.url.path:
                # ユーザーAPIは5分キャッシュ
                response.headers["Cache-Control"] = "public, max-age=300"
                response.headers["ETag"] = etag
            elif "/api/v1/health" in request.url.path:
                # ヘルスチェックは30秒キャッシュ
                response.headers["Cache-Control"] = "public, max-age=30"
        
        return response

# FastAPIアプリケーションに追加
app.add_middleware(HTTPCacheMiddleware)
```

## 4. 非同期処理とバックグラウンドタスク

### 4.1 Celery バックグラウンドタスク
```python
# app/tasks/celery_app.py
from celery import Celery
import os

celery_app = Celery(
    "internal_tool_tasks",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
    include=["app.tasks.user_tasks", "app.tasks.email_tasks"]
)

# Celery設定
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # パフォーマンス設定
    worker_prefetch_multiplier=4,  # ワーカーあたりのタスク予約数
    task_acks_late=True,          # タスク完了後にACK
    worker_disable_rate_limits=False,
    
    # タスクルーティング
    task_routes={
        "app.tasks.email_tasks.*": {"queue": "email"},
        "app.tasks.user_tasks.*": {"queue": "user_processing"},
    }
)

# app/tasks/user_tasks.py
from celery import current_task
from app.tasks.celery_app import celery_app
from app.database import DatabaseManager
from app.services.user_service import UserService
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_bulk_user_import(self, user_data_list: list):
    """大量ユーザー一括インポート"""
    try:
        db_manager = DatabaseManager()
        db_session = db_manager.SessionLocal()
        user_service = UserService(db_session)
        
        total_users = len(user_data_list)
        processed = 0
        
        for i, user_data in enumerate(user_data_list):
            try:
                user_service.create_user(user_data)
                processed += 1
                
                # 進捗更新（10件ごと）
                if i % 10 == 0:
                    current_task.update_state(
                        state='PROGRESS',
                        meta={'processed': processed, 'total': total_users}
                    )
                    
            except Exception as e:
                logger.warning(f"Failed to create user {user_data.get('username')}: {e}")
        
        db_session.close()
        
        return {
            'status': 'completed',
            'processed': processed,
            'total': total_users,
            'failed': total_users - processed
        }
        
    except Exception as e:
        logger.error(f"Bulk user import failed: {e}")
        # リトライ実行
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))

@celery_app.task
def cleanup_inactive_users():
    """非アクティブユーザーのクリーンアップ"""
    db_manager = DatabaseManager()
    db_session = db_manager.SessionLocal()
    
    try:
        # 1年以上非アクティブなユーザーを削除
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=365)
        
        deleted_count = (
            db_session.query(User)
            .filter(User.is_active == False)
            .filter(User.updated_at < cutoff_date)
            .delete()
        )
        
        db_session.commit()
        logger.info(f"Cleaned up {deleted_count} inactive users")
        
        return {"deleted_users": deleted_count}
        
    except Exception as e:
        logger.error(f"User cleanup failed: {e}")
        db_session.rollback()
        raise
    finally:
        db_session.close()
```

### 4.2 FastAPI バックグラウンドタスク
```python
# app/api/endpoints/users.py
from fastapi import BackgroundTasks
from app.tasks.user_tasks import process_bulk_user_import

@router.post("/bulk-import")
async def bulk_import_users(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_admin_user)
):
    """ユーザー一括インポート（バックグラウンド処理）"""
    
    # ファイル読み込み
    content = await file.read()
    user_data_list = parse_csv_content(content)
    
    # バックグラウンドタスクとして実行
    if len(user_data_list) > 100:
        # 大量データはCeleryで処理
        task = process_bulk_user_import.delay(user_data_list)
        return {
            "message": "Bulk import started",
            "task_id": task.id,
            "status_url": f"/api/v1/tasks/{task.id}/status"
        }
    else:
        # 少量データはFastAPIバックグラウンドタスクで処理
        background_tasks.add_task(process_small_batch_import, user_data_list)
        return {"message": "Small batch import started"}

async def process_small_batch_import(user_data_list: list):
    """小量データの一括インポート"""
    # 実装省略
    pass

@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """タスクステータス確認"""
    from app.tasks.celery_app import celery_app
    
    task = celery_app.AsyncResult(task_id)
    
    if task.state == 'PENDING':
        response = {'state': task.state, 'status': 'Task is waiting...'}
    elif task.state == 'PROGRESS':
        response = {
            'state': task.state,
            'processed': task.info.get('processed', 0),
            'total': task.info.get('total', 0)
        }
    elif task.state == 'SUCCESS':
        response = {'state': task.state, 'result': task.result}
    else:
        response = {'state': task.state, 'error': str(task.info)}
    
    return response
```

## 5. リクエスト最適化

### 5.1 ページネーションとフィルタリング最適化
```python
# app/services/pagination_service.py
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Query
from pydantic import BaseModel

class PaginationParams(BaseModel):
    page: int = 1
    per_page: int = 20
    sort_by: str = "id"
    sort_order: str = "asc"

class FilterParams(BaseModel):
    search: Optional[str] = None
    filters: Dict[str, Any] = {}

class OptimizedPaginationService:
    """最適化されたページネーションサービス"""
    
    @staticmethod
    def paginate_query(
        query: Query,
        pagination: PaginationParams,
        filters: FilterParams = None
    ) -> Tuple[List[Any], dict]:
        """効率的なページネーション実行"""
        
        # フィルター適用
        if filters:
            query = OptimizedPaginationService._apply_filters(query, filters)
        
        # ソート適用
        query = OptimizedPaginationService._apply_sorting(query, pagination)
        
        # 総数取得（効率的なCOUNT）
        total = query.count()
        
        # ページネーション
        offset = (pagination.page - 1) * pagination.per_page
        items = query.offset(offset).limit(pagination.per_page).all()
        
        # メタデータ生成
        total_pages = (total + pagination.per_page - 1) // pagination.per_page
        meta = {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": pagination.page < total_pages,
            "has_prev": pagination.page > 1
        }
        
        return items, meta
    
    @staticmethod
    def _apply_filters(query: Query, filters: FilterParams) -> Query:
        """効率的なフィルター適用"""
        if filters.search:
            # 全文検索の最適化
            search_term = f"%{filters.search}%"
            query = query.filter(
                User.username.ilike(search_term) |
                User.email.ilike(search_term) |
                User.full_name.ilike(search_term)
            )
        
        # 個別フィルター適用
        for field, value in filters.filters.items():
            if hasattr(User, field) and value is not None:
                if isinstance(value, list):
                    query = query.filter(getattr(User, field).in_(value))
                else:
                    query = query.filter(getattr(User, field) == value)
        
        return query
    
    @staticmethod
    def _apply_sorting(query: Query, pagination: PaginationParams) -> Query:
        """効率的なソート適用"""
        if hasattr(User, pagination.sort_by):
            sort_column = getattr(User, pagination.sort_by)
            if pagination.sort_order.lower() == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
        
        return query

# 使用例
@router.get("/users", response_model=PaginatedResponse)
async def get_users_optimized(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: Session = Depends(get_db_session)
):
    """最適化されたユーザー一覧取得"""
    
    base_query = db.query(User)
    users, meta = OptimizedPaginationService.paginate_query(
        base_query, pagination, filters
    )
    
    return PaginatedResponse(data=users, meta=meta)
```

### 5.2 レスポンス圧縮
```python
# app/middleware/compression_middleware.py
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
import gzip
import json

class CompressionMiddleware(BaseHTTPMiddleware):
    """レスポンス圧縮ミドルウェア"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # 圧縮条件チェック
        accept_encoding = request.headers.get("accept-encoding", "")
        content_type = response.headers.get("content-type", "")
        
        # JSON レスポンスでgzip対応クライアントの場合のみ圧縮
        if (
            "gzip" in accept_encoding and
            "application/json" in content_type and
            hasattr(response, 'body') and
            len(response.body) > 1000  # 1KB以上のみ圧縮
        ):
            # レスポンスボディを圧縮
            compressed_body = gzip.compress(response.body)
            
            # 圧縮効果がある場合のみ適用（20%以上削減）
            if len(compressed_body) < len(response.body) * 0.8:
                response.body = compressed_body
                response.headers["content-encoding"] = "gzip"
                response.headers["content-length"] = str(len(compressed_body))
        
        return response

# app/main.py
app.add_middleware(CompressionMiddleware)
```

## 6. モニタリングとプロファイリング

### 6.1 パフォーマンス監視
```python
# app/middleware/performance_middleware.py
import time
import psutil
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """パフォーマンス監視ミドルウェア"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # システムリソース測定開始
        process = psutil.Process()
        cpu_start = process.cpu_percent()
        memory_start = process.memory_info().rss
        
        # リクエスト処理
        response = await call_next(request)
        
        # 処理時間計算
        process_time = time.time() - start_time
        
        # システムリソース測定終了
        cpu_end = process.cpu_percent()
        memory_end = process.memory_info().rss
        memory_diff = memory_end - memory_start
        
        # パフォーマンス情報をヘッダーに追加
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Memory-Usage"] = str(memory_end // 1024 // 1024)  # MB
        
        # 遅いリクエストをログ出力
        if process_time > 1.0:  # 1秒以上
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {process_time:.3f}s, memory: {memory_diff//1024}KB"
            )
        
        # メトリクス収集（実際の実装では監視システムに送信）
        await self._collect_metrics(request, response, process_time, memory_diff)
        
        return response
    
    async def _collect_metrics(self, request, response, process_time, memory_diff):
        """メトリクス収集"""
        metrics = {
            "endpoint": f"{request.method} {request.url.path}",
            "status_code": response.status_code,
            "response_time": process_time,
            "memory_usage": memory_diff,
            "timestamp": time.time()
        }
        
        # 実際の実装ではPrometheus、DataDog等に送信
        # await send_to_monitoring_system(metrics)

# app/api/endpoints/monitoring.py
import psutil
from datetime import datetime

@router.get("/metrics", tags=["monitoring"])
async def get_performance_metrics():
    """パフォーマンスメトリクス取得"""
    
    # システムメトリクス
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # アプリケーションメトリクス
    process = psutil.Process()
    app_memory = process.memory_info()
    
    # データベース接続プール情報
    from app.database import database_manager
    db_stats = database_manager.get_connection_stats()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": memory.available / 1024**3,
            "disk_usage_percent": disk.percent,
        },
        "application": {
            "memory_rss_mb": app_memory.rss / 1024**2,
            "memory_vms_mb": app_memory.vms / 1024**2,
        },
        "database": db_stats,
        "cache": {
            # Redis統計情報
            "redis_connected": cache_service.redis_client.ping() if cache_service else False
        }
    }
```

### 6.2 プロファイリング
```python
# app/utils/profiler.py
import cProfile
import pstats
from functools import wraps
from typing import Callable
import io

def profile_function(func: Callable) -> Callable:
    """関数プロファイリングデコレーター"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        
        try:
            result = func(*args, **kwargs)
        finally:
            profiler.disable()
            
            # プロファイル結果出力
            stats_stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stats_stream)
            stats.sort_stats('cumulative')
            stats.print_stats(20)  # 上位20件
            
            print(f"\n=== Profile for {func.__name__} ===")
            print(stats_stream.getvalue())
        
        return result
    
    return wrapper

# 使用例
@profile_function
def heavy_computation_function():
    """重い処理の関数"""
    # 実装省略
    pass

# SQL クエリプロファイリング
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(Engine, "after_cursor_execute")  
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total_time = time.time() - context._query_start_time
    
    # 遅いクエリをログ出力（100ms以上）
    if total_time > 0.1:
        logger.warning(f"Slow query ({total_time:.3f}s): {statement[:200]}...")
```

## 7. フロントエンド最適化

### 7.1 API レスポンス最適化
```python
# app/schemas/optimized_responses.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserListItem(BaseModel):
    """ユーザー一覧用の軽量スキーマ"""
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserDetail(UserListItem):
    """ユーザー詳細用のスキーマ（必要な時のみ追加情報）"""
    full_name: Optional[str] = None
    role: str
    last_login_at: Optional[datetime] = None
    profile: Optional["UserProfile"] = None

# レスポンスサイズ最適化
@router.get("/users", response_model=List[UserListItem])
async def get_users_lightweight(db: Session = Depends(get_db_session)):
    """軽量ユーザー一覧（必要最小限の情報のみ）"""
    users = db.query(User).options(
        # 関連テーブルは読み込まない
        defer(User.full_name),
        defer(User.updated_at),
        defer(User.last_login_at)
    ).all()
    
    return users

@router.get("/users/{user_id}", response_model=UserDetail)
async def get_user_detail(user_id: int, db: Session = Depends(get_db_session)):
    """詳細ユーザー情報（必要な時のみ全情報取得）"""
    user = db.query(User).options(
        joinedload(User.profile)
    ).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user
```

### 7.2 GraphQL風API（選択的フィールド取得）
```python
# app/api/endpoints/flexible_users.py
from typing import Set, Optional

class FieldSelector:
    """フィールド選択クラス"""
    
    @staticmethod
    def parse_fields(fields_param: Optional[str]) -> Set[str]:
        """フィールドパラメータをパース"""
        if not fields_param:
            return {"id", "username", "email"}  # デフォルトフィールド
        
        return set(field.strip() for field in fields_param.split(","))
    
    @staticmethod
    def build_response(user: User, selected_fields: Set[str]) -> dict:
        """選択されたフィールドのみのレスポンス構築"""
        response = {}
        
        field_mapping = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }
        
        for field in selected_fields:
            if field in field_mapping:
                response[field] = field_mapping[field]
        
        return response

@router.get("/users/flexible")
async def get_users_flexible(
    fields: Optional[str] = Query(None, description="カンマ区切りのフィールド名"),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db_session)
):
    """
    フレキシブルフィールド選択API
    
    例: /users/flexible?fields=id,username,email&limit=10
    """
    
    selected_fields = FieldSelector.parse_fields(fields)
    
    # 必要なフィールドのみクエリ（SQLレベル最適化）
    query_fields = []
    for field in selected_fields:
        if hasattr(User, field):
            query_fields.append(getattr(User, field))
    
    if not query_fields:
        query_fields = [User.id, User.username, User.email]
    
    users = db.query(*query_fields).limit(limit).all()
    
    # レスポンス構築
    response = []
    for user_tuple in users:
        user_dict = {}
        for i, field_name in enumerate(selected_fields):
            if i < len(user_tuple):
                user_dict[field_name] = user_tuple[i]
        response.append(user_dict)
    
    return {"data": response, "fields": list(selected_fields)}
```

## 8. 本番環境最適化

### 8.1 Dockerコンテナ最適化
```dockerfile
# Dockerfile.optimized
FROM python:3.9-slim as builder

# システム依存関係インストール
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係インストール
COPY requirements/prod.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r prod.txt

# 本番イメージ
FROM python:3.9-slim

# 非rootユーザー作成
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 最適化されたPython設定
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ランタイム依存関係のみインストール
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# ビルド済みwheelをコピー
COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/*

# アプリケーションコード
COPY --chown=appuser:appuser . /app
WORKDIR /app

USER appuser

# Gunicorn設定で最適化
CMD ["gunicorn", "app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--worker-tmp-dir", "/dev/shm", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--preload"]
```

### 8.2 Nginx リバースプロキシ設定
```nginx
# nginx.conf
upstream fastapi_backend {
    least_conn;
    server app1:8000 max_fails=3 fail_timeout=30s;
    server app2:8000 max_fails=3 fail_timeout=30s;
    server app3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    client_max_body_size 10M;
    
    # gzip圧縮
    gzip on;
    gzip_vary on;
    gzip_min_length 1000;
    gzip_types
        text/plain
        text/css
        text/xml
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml;
    
    # 静的ファイルキャッシュ
    location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # API プロキシ
    location /api/ {
        proxy_pass http://fastapi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # コネクション最適化
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        
        # タイムアウト設定
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # バッファリング設定
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
    
    # ヘルスチェック
    location /health {
        access_log off;
        proxy_pass http://fastapi_backend;
        proxy_connect_timeout 1s;
        proxy_send_timeout 1s;
        proxy_read_timeout 1s;
    }
    
    # レート制限
    location /api/auth/login {
        limit_req zone=login_limit burst=10 nodelay;
        proxy_pass http://fastapi_backend;
    }
}

# レート制限設定
http {
    limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/m;
}
```