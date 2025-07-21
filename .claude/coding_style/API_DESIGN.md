# API_DESIGN.md

## 1. API設計原則

### 1.1 基本原則
- **RESTful設計**: HTTPメソッドとステータスコードを適切に使用
- **一貫性**: 全APIエンドポイントで統一されたパターン
- **予測可能性**: URLとレスポンス形式が直感的
- **バージョニング**: 後方互換性を考慮したAPIバージョン管理
- **ドキュメント化**: 自動生成されたドキュメントの活用

### 1.2 設計指針
```python
# 良いAPI設計の例
GET    /api/v1/users              # ユーザー一覧取得
GET    /api/v1/users/{user_id}    # 特定ユーザー取得
POST   /api/v1/users              # ユーザー作成
PUT    /api/v1/users/{user_id}    # ユーザー更新（全項目）
PATCH  /api/v1/users/{user_id}    # ユーザー部分更新
DELETE /api/v1/users/{user_id}    # ユーザー削除

# 悪い例
GET    /api/getUsers               # 動詞を使用
POST   /api/user/create            # 冗長
GET    /api/users/{user_id}/delete # GETで削除操作
```

## 2. URLとエンドポイント設計

### 2.1 URL構造
```python
# 基本構造
/{api_prefix}/{version}/{resource}/{resource_id}/{sub_resource}

# 実例
/api/v1/users                     # リソースコレクション
/api/v1/users/123                 # 特定リソース
/api/v1/users/123/orders          # サブリソース
/api/v1/users/123/orders/456      # 特定サブリソース
```

### 2.2 FastAPIでのルーター設計
```python
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import List, Optional
from app.schemas.user import UserResponse, UserCreate, UserUpdate
from app.services.user_service import UserService

# ルーター定義
router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
    responses={404: {"description": "Not found"}}
)

@router.get("/", response_model=List[UserResponse])
async def get_users(
    skip: int = Query(0, ge=0, description="レコードをスキップする数"),
    limit: int = Query(100, ge=1, le=1000, description="取得するレコード数の上限"),
    search: Optional[str] = Query(None, description="ユーザー名・メールでの検索"),
    is_active: Optional[bool] = Query(None, description="アクティブユーザーのみ取得"),
    user_service: UserService = Depends(get_user_service)
):
    """
    ユーザー一覧を取得
    
    - **skip**: スキップするレコード数（ページネーション）
    - **limit**: 取得するレコード数（最大1000）
    - **search**: 名前またはメールでの検索
    - **is_active**: アクティブユーザーのみフィルタ
    """
    return await user_service.get_users(
        skip=skip, 
        limit=limit, 
        search=search, 
        is_active=is_active
    )

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int = Path(..., ge=1, description="ユーザーID"),
    user_service: UserService = Depends(get_user_service)
):
    """特定のユーザーを取得"""
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    user: UserCreate,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user)
):
    """新しいユーザーを作成"""
    return await user_service.create_user(user, created_by=current_user.id)

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int = Path(..., ge=1),
    user: UserUpdate,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user)
):
    """ユーザー情報を完全更新"""
    updated_user = await user_service.update_user(user_id, user, updated_by=current_user.id)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

@router.patch("/{user_id}", response_model=UserResponse)
async def partial_update_user(
    user_id: int = Path(..., ge=1),
    user: UserPartialUpdate,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user)
):
    """ユーザー情報を部分更新"""
    updated_user = await user_service.partial_update_user(user_id, user, updated_by=current_user.id)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int = Path(..., ge=1),
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user)
):
    """ユーザーを削除"""
    success = await user_service.delete_user(user_id, deleted_by=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
```

### 2.3 ネストされたリソース
```python
# ユーザーの注文履歴API
@router.get("/{user_id}/orders", response_model=List[OrderResponse])
async def get_user_orders(
    user_id: int = Path(..., ge=1),
    status: Optional[OrderStatus] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    order_service: OrderService = Depends(get_order_service)
):
    """特定ユーザーの注文履歴を取得"""
    return await order_service.get_orders_by_user(
        user_id=user_id,
        status=status,
        date_from=date_from,
        date_to=date_to
    )

# ユーザーの特定注文詳細
@router.get("/{user_id}/orders/{order_id}", response_model=OrderDetailResponse)
async def get_user_order_detail(
    user_id: int = Path(..., ge=1),
    order_id: int = Path(..., ge=1),
    order_service: OrderService = Depends(get_order_service)
):
    """特定ユーザーの特定注文詳細を取得"""
    order = await order_service.get_order_detail(user_id=user_id, order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
```

## 3. リクエスト・レスポンス設計

### 3.1 統一されたレスポンス形式
```python
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime

class ApiResponse(BaseModel):
    """統一APIレスポンス形式"""
    success: bool = Field(description="処理成功フラグ")
    data: Optional[Any] = Field(None, description="レスポンスデータ")
    message: Optional[str] = Field(None, description="メッセージ")
    errors: Optional[List[str]] = Field(None, description="エラーメッセージリスト")
    meta: Optional[Dict[str, Any]] = Field(None, description="メタデータ")

class PaginatedResponse(BaseModel):
    """ページネーション付きレスポンス"""
    success: bool = True
    data: List[Any]
    meta: Dict[str, Any] = Field(description="ページネーション情報")
    
    @classmethod
    def create(cls, items: List[Any], total: int, page: int, per_page: int):
        """ページネーション付きレスポンスを作成"""
        total_pages = (total + per_page - 1) // per_page
        return cls(
            data=items,
            meta={
                "pagination": {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
        )

# 使用例
@router.get("/", response_model=PaginatedResponse)
async def get_users_paginated(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user_service: UserService = Depends(get_user_service)
):
    """ページネーション付きユーザー一覧取得"""
    users, total = await user_service.get_users_with_count(page, per_page)
    return PaginatedResponse.create(users, total, page, per_page)
```

### 3.2 Pydanticスキーマ設計
```python
from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"

class UserBase(BaseModel):
    """ユーザー基本情報"""
    username: str = Field(..., min_length=3, max_length=50, description="ユーザー名")
    email: EmailStr = Field(..., description="メールアドレス")
    full_name: Optional[str] = Field(None, max_length=100, description="フルネーム")
    is_active: bool = Field(True, description="アクティブフラグ")
    role: UserRole = Field(UserRole.USER, description="ユーザーロール")
    
    class Config:
        use_enum_values = True

class UserCreate(UserBase):
    """ユーザー作成用スキーマ"""
    password: str = Field(..., min_length=8, description="パスワード")
    
    @validator('password')
    def validate_password_strength(cls, v):
        """パスワード強度チェック"""
        import re
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        return v

class UserUpdate(UserBase):
    """ユーザー更新用スキーマ（全項目必須）"""
    pass

class UserPartialUpdate(BaseModel):
    """ユーザー部分更新用スキーマ（全項目任意）"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None

class UserResponse(UserBase):
    """ユーザー取得用レスポンス"""
    id: int = Field(description="ユーザーID")
    created_at: datetime = Field(description="作成日時")
    updated_at: Optional[datetime] = Field(None, description="更新日時")
    last_login_at: Optional[datetime] = Field(None, description="最終ログイン日時")
    
    class Config:
        from_attributes = True  # SQLAlchemyモデルから変換可能

class UserListResponse(BaseModel):
    """ユーザー一覧レスポンス"""
    id: int
    username: str
    email: str
    is_active: bool
    role: UserRole
    created_at: datetime
    
    class Config:
        from_attributes = True
```

### 3.3 バリデーションとエラーハンドリング
```python
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

class APIException(HTTPException):
    """カスタムAPI例外"""
    def __init__(self, status_code: int, detail: str, error_code: Optional[str] = None):
        super().__init__(status_code, detail)
        self.error_code = error_code

class BusinessLogicError(APIException):
    """ビジネスロジックエラー"""
    def __init__(self, detail: str, error_code: str = "BUSINESS_ERROR"):
        super().__init__(status_code=400, detail=detail, error_code=error_code)

class ResourceNotFoundError(APIException):
    """リソース未発見エラー"""
    def __init__(self, resource: str, identifier: str):
        detail = f"{resource} with identifier '{identifier}' not found"
        super().__init__(status_code=404, detail=detail, error_code="RESOURCE_NOT_FOUND")

# グローバル例外ハンドラー
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """バリデーションエラーハンドラー"""
    errors = []
    for error in exc.errors():
        field_name = " -> ".join(str(loc) for loc in error["loc"])
        errors.append(f"{field_name}: {error['msg']}")
    
    return JSONResponse(
        status_code=422,
        content=ApiResponse(
            success=False,
            message="Validation error",
            errors=errors
        ).dict()
    )

@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    """カスタムAPI例外ハンドラー"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse(
            success=False,
            message=exc.detail,
            errors=[exc.detail],
            meta={"error_code": getattr(exc, 'error_code', None)}
        ).dict()
    )

# 使用例
@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate, user_service: UserService = Depends()):
    # 重複チェック
    existing_user = await user_service.get_user_by_email(user.email)
    if existing_user:
        raise BusinessLogicError("Email already registered", "DUPLICATE_EMAIL")
    
    # ユーザー作成
    try:
        created_user = await user_service.create_user(user)
        return created_user
    except Exception as e:
        raise APIException(status_code=500, detail="Failed to create user", error_code="CREATE_FAILED")
```

## 4. HTTPステータスコード

### 4.1 適切なステータスコード使用
```python
from fastapi import status

class HTTPStatus:
    """よく使用するHTTPステータスコード"""
    
    # 成功系
    OK = 200                    # GET: 正常取得
    CREATED = 201              # POST: 作成成功
    ACCEPTED = 202             # 非同期処理受付
    NO_CONTENT = 204           # DELETE: 削除成功（レスポンスボディなし）
    
    # リダイレクト系
    NOT_MODIFIED = 304         # キャッシュ有効
    
    # クライアントエラー系
    BAD_REQUEST = 400          # 不正なリクエスト
    UNAUTHORIZED = 401         # 認証が必要
    FORBIDDEN = 403            # アクセス権限なし
    NOT_FOUND = 404            # リソースが存在しない
    METHOD_NOT_ALLOWED = 405   # HTTPメソッドが許可されない
    CONFLICT = 409             # リソースの競合
    UNPROCESSABLE_ENTITY = 422 # バリデーションエラー
    TOO_MANY_REQUESTS = 429    # レート制限
    
    # サーバーエラー系
    INTERNAL_SERVER_ERROR = 500 # 内部サーバーエラー
    BAD_GATEWAY = 502           # 外部API接続エラー
    SERVICE_UNAVAILABLE = 503   # サービス利用不可

# 実装例
@router.get("/{user_id}", 
           response_model=UserResponse,
           responses={
               404: {"description": "User not found"},
               403: {"description": "Access denied"}
           })
async def get_user(user_id: int, current_user: User = Depends(get_current_user)):
    user = await user_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="User not found")
    
    # アクセス権限チェック
    if not can_access_user(current_user, user):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Access denied")
    
    return user

@router.post("/", 
            response_model=UserResponse, 
            status_code=HTTPStatus.CREATED,
            responses={
                409: {"description": "User already exists"},
                422: {"description": "Validation error"}
            })
async def create_user(user: UserCreate):
    # 重複チェック
    if await user_service.exists_by_email(user.email):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT, 
            detail="User with this email already exists"
        )
    
    return await user_service.create_user(user)

@router.delete("/{user_id}", status_code=HTTPStatus.NO_CONTENT)
async def delete_user(user_id: int):
    success = await user_service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="User not found")
    # 204 No Contentはレスポンスボディを返さない
```

## 5. フィルタリング・ソート・検索

### 5.1 クエリパラメータ設計
```python
from enum import Enum
from typing import Optional, List
from fastapi import Query

class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"

class UserSortField(str, Enum):
    ID = "id"
    USERNAME = "username"
    EMAIL = "email"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

@router.get("/", response_model=PaginatedResponse)
async def get_users(
    # ページネーション
    page: int = Query(1, ge=1, description="ページ番号"),
    per_page: int = Query(20, ge=1, le=100, description="1ページあたりの件数"),
    
    # フィルタリング
    search: Optional[str] = Query(None, description="ユーザー名・メール・フルネームでの検索"),
    role: Optional[List[UserRole]] = Query(None, description="ロールでフィルタ"),
    is_active: Optional[bool] = Query(None, description="アクティブ状態でフィルタ"),
    created_from: Optional[datetime] = Query(None, description="作成日FROM"),
    created_to: Optional[datetime] = Query(None, description="作成日TO"),
    
    # ソート
    sort_by: UserSortField = Query(UserSortField.ID, description="ソートフィールド"),
    sort_order: SortOrder = Query(SortOrder.ASC, description="ソート順"),
    
    user_service: UserService = Depends(get_user_service)
):
    """
    高度なフィルタリング・ソート機能付きユーザー一覧取得
    
    ## フィルタ条件
    - search: 部分一致検索（名前、メール、フルネーム）
    - role: 複数ロール指定可能（例: ?role=admin&role=manager）
    - is_active: アクティブ状態
    - created_from/created_to: 作成日範囲
    
    ## ソート
    - sort_by: ソートフィールド
    - sort_order: asc（昇順）またはdesc（降順）
    """
    
    # フィルタ条件構築
    filters = {
        "search": search,
        "roles": role,
        "is_active": is_active,
        "created_from": created_from,
        "created_to": created_to
    }
    
    # ソート条件構築
    sort_config = {
        "field": sort_by,
        "order": sort_order
    }
    
    users, total = await user_service.get_users_filtered(
        page=page,
        per_page=per_page,
        filters=filters,
        sort=sort_config
    )
    
    return PaginatedResponse.create(users, total, page, per_page)
```

### 5.2 高度な検索機能
```python
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

class SearchFilter(BaseModel):
    """検索フィルタ"""
    field: str
    operator: str  # eq, ne, gt, gte, lt, lte, in, like, between
    value: Any

class SearchRequest(BaseModel):
    """複合検索リクエスト"""
    filters: List[SearchFilter] = []
    sort: Optional[Dict[str, str]] = None
    page: int = 1
    per_page: int = 20

@router.post("/search", response_model=PaginatedResponse)
async def search_users(
    search_request: SearchRequest,
    user_service: UserService = Depends(get_user_service)
):
    """
    複合条件による高度なユーザー検索
    
    ## リクエスト例
    ```json
    {
        "filters": [
            {"field": "role", "operator": "in", "value": ["admin", "manager"]},
            {"field": "created_at", "operator": "gte", "value": "2024-01-01T00:00:00"},
            {"field": "username", "operator": "like", "value": "john%"}
        ],
        "sort": {"field": "created_at", "order": "desc"},
        "page": 1,
        "per_page": 20
    }
    ```
    """
    
    # フィルタ条件の検証
    allowed_fields = {"id", "username", "email", "role", "is_active", "created_at"}
    allowed_operators = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "like", "between"}
    
    for filter_item in search_request.filters:
        if filter_item.field not in allowed_fields:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid filter field: {filter_item.field}"
            )
        if filter_item.operator not in allowed_operators:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid operator: {filter_item.operator}"
            )
    
    users, total = await user_service.search_users(search_request)
    return PaginatedResponse.create(users, total, search_request.page, search_request.per_page)
```

## 6. バージョニング

### 6.1 URLパスバージョニング
```python
from fastapi import APIRouter

# v1 API
v1_router = APIRouter(prefix="/api/v1")

@v1_router.get("/users", tags=["users-v1"])
async def get_users_v1():
    """バージョン1のユーザー一覧取得"""
    pass

# v2 API（新機能追加）
v2_router = APIRouter(prefix="/api/v2")

@v2_router.get("/users", tags=["users-v2"])
async def get_users_v2():
    """バージョン2のユーザー一覧取得（拡張機能付き）"""
    pass

# メインアプリケーションに登録
app.include_router(v1_router)
app.include_router(v2_router)
```

### 6.2 ヘッダーベースバージョニング
```python
from fastapi import Header, HTTPException

@router.get("/users")
async def get_users(api_version: str = Header("1.0", alias="API-Version")):
    """ヘッダーベースバージョニング"""
    
    if api_version == "1.0":
        return await get_users_v1()
    elif api_version == "2.0":
        return await get_users_v2()
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported API version: {api_version}"
        )
```

### 6.3 非推奨API管理
```python
from fastapi import APIRouter
import warnings

@router.get("/old-endpoint", deprecated=True)
async def old_endpoint():
    """
    非推奨のエンドポイント
    
    ⚠️ このエンドポイントは非推奨です。新しいエンドポイントを使用してください。
    """
    warnings.warn("This endpoint is deprecated", DeprecationWarning)
    return {"message": "This endpoint will be removed in v3.0"}

# レスポンスヘッダーで非推奨を通知
from fastapi import Response

@router.get("/legacy-users")
async def get_legacy_users(response: Response):
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</api/v2/users>; rel="successor-version"'
    return await get_users_legacy()
```

## 7. ドキュメント化

### 7.1 OpenAPI設定
```python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="社内ツール API",
        version="1.0.0",
        description="""
        ## 概要
        社内業務用のRESTful API
        
        ## 認証
        Bearer Token認証を使用
        ```
        Authorization: Bearer <your-token>
        ```
        
        ## レート制限
        - 通常API: 100req/min
        - 認証API: 20req/min
        
        ## エラーレスポンス
        全てのエラーは以下の形式で返されます：
        ```json
        {
            "success": false,
            "message": "エラーメッセージ",
            "errors": ["詳細エラー1", "詳細エラー2"],
            "meta": {"error_code": "ERROR_CODE"}
        }
        ```
        """,
        routes=app.routes,
        tags=[
            {
                "name": "users",
                "description": "ユーザー管理API"
            },
            {
                "name": "auth",
                "description": "認証関連API"
            }
        ]
    )
    
    # セキュリティスキーム追加
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

### 7.2 詳細なドキュメント記述
```python
@router.post("/",
    response_model=UserResponse,
    status_code=201,
    summary="ユーザー作成",
    description="新しいユーザーアカウントを作成します。管理者権限が必要です。",
    response_description="作成されたユーザー情報",
    responses={
        201: {
            "description": "ユーザー作成成功",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "id": 123,
                            "username": "john_doe",
                            "email": "john@example.com",
                            "full_name": "John Doe",
                            "is_active": True,
                            "role": "user",
                            "created_at": "2024-01-15T10:30:00Z"
                        }
                    }
                }
            }
        },
        400: {
            "description": "バリデーションエラー",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "message": "Validation error",
                        "errors": ["Email already exists"]
                    }
                }
            }
        },
        403: {
            "description": "権限不足",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "message": "Insufficient permissions"
                    }
                }
            }
        }
    },
    tags=["users"],
    dependencies=[Depends(require_admin_role)]
)
async def create_user(user: UserCreate):
    """
    ## ユーザー作成API
    
    新しいユーザーアカウントを作成します。
    
    ### 必要な権限
    - 管理者ロール (admin)
    
    ### 入力検証
    - username: 3-50文字、英数字・ハイフン・アンダースコアのみ
    - email: 有効なメールアドレス形式
    - password: 8文字以上、大文字・小文字・数字・記号を含む
    
    ### 処理フロー
    1. 入力データのバリデーション
    2. メールアドレス重複チェック
    3. パスワードハッシュ化
    4. データベースへの保存
    5. ウェルカムメール送信（非同期）
    
    ### 注意事項
    - 作成されたユーザーはデフォルトでアクティブ状態
    - 初回ログイン時にパスワード変更を促すメールが送信される
    """
    return await user_service.create_user(user)
```

## 8. テスト用エンドポイント

### 8.1 ヘルスチェック
```python
from fastapi import status
from datetime import datetime
import psutil

@app.get("/health", 
         tags=["system"],
         summary="ヘルスチェック",
         response_model=Dict[str, Any])
async def health_check():
    """
    システムのヘルスチェック
    
    - アプリケーションの稼働状態
    - データベース接続状態
    - 外部サービス接続状態
    """
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "uptime_seconds": time.time() - app_start_time,
        "checks": {}
    }
    
    # データベース接続チェック
    try:
        await database_service.ping()
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = "unhealthy"
        health_status["status"] = "degraded"
    
    # 外部API接続チェック
    try:
        await external_api_service.ping()
        health_status["checks"]["external_api"] = "healthy"
    except Exception as e:
        health_status["checks"]["external_api"] = "unhealthy"
        health_status["status"] = "degraded"
    
    # システムリソース情報
    health_status["system"] = {
        "cpu_usage": psutil.cpu_percent(),
        "memory_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent
    }
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)

@app.get("/ready", tags=["system"])
async def readiness_check():
    """
    Readinessプローブ用エンドポイント
    アプリケーションがリクエストを受け付ける準備ができているかチェック
    """
    # 必要なサービスの初期化確認
    if not database_service.is_initialized():
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    return {"status": "ready"}

@app.get("/live", tags=["system"])
async def liveness_check():
    """
    Livenessプローブ用エンドポイント
    アプリケーションが生きているかの基本チェック
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}
```

### 8.2 開発・デバッグ用エンドポイント
```python
from fastapi import Depends
from app.core.config import settings

# デバッグモードでのみ有効
if settings.debug:
    
    @app.get("/debug/config", tags=["debug"])
    async def debug_config(current_user: User = Depends(get_admin_user)):
        """設定情報の確認（管理者のみ、デバッグモードのみ）"""
        return {
            "debug": settings.debug,
            "database_url": settings.database_url[:20] + "...",  # 一部のみ表示
            "cors_origins": settings.cors_origins,
            "log_level": settings.log_level
        }
    
    @app.get("/debug/users/{user_id}/raw", tags=["debug"])
    async def debug_user_raw(
        user_id: int, 
        current_user: User = Depends(get_admin_user)
    ):
        """ユーザーの生データ確認（管理者のみ、デバッグモードのみ）"""
        user = await user_service.get_user_raw(user_id)
        return user
```