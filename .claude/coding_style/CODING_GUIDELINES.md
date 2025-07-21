# CODING_GUIDELINES.md

## 1. 基本方針

### 1.1 開発思想
- **可読性第一**: 6ヶ月後の自分が理解できるコードを書く
- **シンプルさ**: 複雑さを避け、明確で簡潔な実装を心がける
- **保守性**: 機能追加・修正が容易な構造にする
- **一貫性**: プロジェクト全体で統一されたスタイルを保つ

### 1.2 準拠基準
- **PEP 8**: Pythonコーディングスタイルガイド
- **PEP 257**: Docstringガイド
- **PEP 484**: 型ヒントの活用
- **Black**: コードフォーマッター（88文字制限）

## 2. コードフォーマット

### 2.1 基本的なフォーマット
```python
# インデント: スペース4つ
def example_function():
    if condition:
        return value

# 行の長さ: 88文字以内（Blackのデフォルト）
# 長い行は適切に分割
result = some_long_function_name(
    argument_one="value1",
    argument_two="value2",
    argument_three="value3"
)

# 空行の使い方
class MyClass:  # クラス定義の前後に2行
    
    def __init__(self):  # メソッド間に1行
        pass
    
    def method_one(self):
        pass


def standalone_function():  # 関数定義の前後に2行
    pass
```

### 2.2 文字列とクォート
```python
# シングルクォートを基本とする
message = 'Hello, World!'
sql_query = 'SELECT * FROM users WHERE id = ?'

# 文字列内にシングルクォートが含まれる場合はダブルクォート
message = "It's a beautiful day"

# 複数行文字列はトリプルクォート
docstring = """
これは複数行の
文字列です
"""

# f-string を積極的に使用
user_id = 123
message = f'User {user_id} has been created'

# 長い文字列の分割
long_message = (
    'This is a very long message that needs to be split '
    'across multiple lines for better readability'
)
```

## 3. 命名規則

### 3.1 基本ルール
```python
# 変数・関数: snake_case
user_name = "john_doe"
total_count = 100

def get_user_data():
    pass

def calculate_total_price():
    pass

# 定数: UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
API_BASE_URL = "https://api.example.com"
DEFAULT_TIMEOUT = 30

# クラス: PascalCase
class UserService:
    pass

class DatabaseManager:
    pass

# プライベート属性・メソッド: 先頭にアンダースコア
class ApiClient:
    def __init__(self):
        self._session = None
        self._retry_count = 0
    
    def _build_headers(self):
        pass
```

### 3.2 意味のある名前をつける
```python
# 悪い例
def calc(x, y):
    return x * y * 0.1

# 良い例
def calculate_tax_amount(price: float, tax_rate: float) -> float:
    return price * tax_rate

# 悪い例
users = get_data()
for u in users:
    print(u.name)

# 良い例
active_users = get_active_users()
for user in active_users:
    print(user.name)
```

### 3.3 ブール値の命名
```python
# is_, has_, can_, should_ などの接頭辞を使用
is_active = True
has_permission = False
can_edit = True
should_retry = False

# 関数名でも同様
def is_valid_email(email: str) -> bool:
    pass

def has_admin_role(user: User) -> bool:
    pass
```

## 4. インポート

### 4.1 インポートの順序
```python
# 1. 標準ライブラリ
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# 2. サードパーティライブラリ
import requests
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine

# 3. ローカルモジュール
from app.models import User
from app.services.user_service import UserService
from app.utils.database import get_db_session
```

### 4.2 インポートのベストプラクティス
```python
# 絶対インポートを優先
from app.services.user_service import UserService

# 相対インポートは近接モジュールのみ
from .models import User
from ..utils import validate_email

# * インポートは避ける（例外: __all__ が適切に定義されている場合）
# 悪い例
from app.utils import *

# 良い例
from app.utils import validate_email, format_date

# 長いインポートは適切に分割
from app.services import (
    UserService,
    EmailService,
    NotificationService
)
```

## 5. 関数設計

### 5.1 関数の基本原則
```python
def fetch_user_by_id(user_id: int) -> Optional[User]:
    """
    ユーザーIDでユーザー情報を取得
    
    Args:
        user_id: 取得するユーザーのID
        
    Returns:
        ユーザー情報。見つからない場合はNone
        
    Raises:
        ValueError: user_idが不正な場合
    """
    if user_id <= 0:
        raise ValueError("user_id must be positive")
    
    # 実装
    pass

# 単一責任の原則
def validate_email(email: str) -> bool:
    """メールアドレスの形式をチェック"""
    pass

def send_welcome_email(user: User) -> None:
    """ウェルカムメールを送信"""
    pass

# 関数は短く（20行以内を目安）
def process_user_registration(user_data: dict) -> User:
    """ユーザー登録処理"""
    validated_data = validate_user_data(user_data)
    user = create_user(validated_data)
    send_welcome_email(user)
    return user
```

### 5.2 引数とデフォルト値
```python
# デフォルト値は不変オブジェクトを使用
def create_user(name: str, tags: Optional[List[str]] = None) -> User:
    if tags is None:
        tags = []
    return User(name=name, tags=tags)

# キーワード引数を活用
def send_notification(
    user: User,
    message: str,
    *,  # 以下はキーワード専用引数
    urgent: bool = False,
    email: bool = True,
    sms: bool = False
) -> None:
    pass

# 複数の戻り値はNamedTupleまたはdataclassを使用
from typing import NamedTuple

class ValidationResult(NamedTuple):
    is_valid: bool
    errors: List[str]

def validate_user_data(data: dict) -> ValidationResult:
    errors = []
    # バリデーション処理
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)
```

## 6. クラス設計

### 6.1 クラスの基本構造
```python
from abc import ABC, abstractmethod
from typing import Protocol

# 抽象基底クラス
class BaseService(ABC):
    """サービス層の基底クラス"""
    
    def __init__(self, db_session):
        self.db_session = db_session
    
    @abstractmethod
    def get_by_id(self, id: int):
        """IDで取得（サブクラスで実装必須）"""
        pass

# 具象クラス
class UserService(BaseService):
    """ユーザー関連のビジネスロジック"""
    
    def __init__(self, db_session, email_service):
        super().__init__(db_session)
        self._email_service = email_service
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """ユーザーIDでユーザーを取得"""
        return self.db_session.query(User).filter(User.id == user_id).first()
    
    def create_user(self, user_data: UserCreate) -> User:
        """新規ユーザーを作成"""
        user = User(**user_data.dict())
        self.db_session.add(user)
        self.db_session.commit()
        
        self._email_service.send_welcome_email(user)
        return user

# Protocolを使った型定義（Duck Typing）
class Serializable(Protocol):
    def to_dict(self) -> dict:
        ...
```

### 6.2 dataclassの活用
```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class User:
    """ユーザー情報"""
    id: int
    name: str
    email: str
    is_active: bool = True
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """バリデーションやデータ変換"""
        self.email = self.email.lower()
    
    @property
    def display_name(self) -> str:
        """表示用の名前"""
        return f"{self.name} ({self.email})"

@dataclass(frozen=True)  # イミュータブル
class ApiConfig:
    """API設定（変更不可）"""
    base_url: str
    timeout: int = 30
    retry_count: int = 3
```

## 7. 型ヒント

### 7.1 基本的な型ヒント
```python
from typing import Dict, List, Optional, Union, Any, Callable

# 基本型
def process_data(data: str) -> int:
    return len(data)

# コレクション型
def get_user_names(users: List[User]) -> List[str]:
    return [user.name for user in users]

def get_user_mapping(users: List[User]) -> Dict[int, str]:
    return {user.id: user.name for user in users}

# Optional（None許可）
def find_user(user_id: int) -> Optional[User]:
    pass

# Union（複数型許可）
def process_id(user_id: Union[int, str]) -> str:
    return str(user_id)

# Callable（関数型）
def apply_transform(data: List[str], transform: Callable[[str], str]) -> List[str]:
    return [transform(item) for item in data]
```

### 7.2 高度な型ヒント
```python
from typing import TypeVar, Generic, Literal

# TypeVar（ジェネリクス）
T = TypeVar('T')

class Repository(Generic[T]):
    def get_by_id(self, id: int) -> Optional[T]:
        pass

# Literal（リテラル値）
def set_log_level(level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR']) -> None:
    pass

# NewType（型エイリアス）
from typing import NewType

UserId = NewType('UserId', int)
Email = NewType('Email', str)

def get_user(user_id: UserId) -> Optional[User]:
    pass
```

## 8. コメントとドキュメント

### 8.1 Docstring
```python
def calculate_discount(
    price: float, 
    discount_rate: float, 
    max_discount: Optional[float] = None
) -> float:
    """
    割引価格を計算する
    
    Args:
        price: 元の価格
        discount_rate: 割引率（0.0-1.0）
        max_discount: 最大割引額（制限なしの場合はNone）
    
    Returns:
        割引後の価格
    
    Raises:
        ValueError: 価格や割引率が不正な場合
        
    Examples:
        >>> calculate_discount(1000.0, 0.1)
        900.0
        >>> calculate_discount(1000.0, 0.3, max_discount=200.0)
        800.0
    """
    if price < 0:
        raise ValueError("Price must be non-negative")
    if not 0 <= discount_rate <= 1:
        raise ValueError("Discount rate must be between 0 and 1")
    
    discount = price * discount_rate
    if max_discount is not None:
        discount = min(discount, max_discount)
    
    return price - discount
```

### 8.2 コメント
```python
# TODOコメントの書き方
# TODO: キャッシュ機能を追加する
# FIXME: エラーハンドリングを改善する
# NOTE: この処理は外部APIの制限により必要

def process_users():
    # ユーザーデータを取得（大量データのため分割処理）
    batch_size = 100
    for offset in range(0, total_count, batch_size):
        users = get_users(offset, batch_size)
        
        # 各ユーザーの処理
        for user in users:
            # アクティブユーザーのみ処理対象
            if user.is_active:
                process_user(user)
```

## 9. プロジェクト構造

### 9.1 推奨ディレクトリ構造
```
project/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPIアプリケーション
│   ├── config.py            # 設定管理
│   ├── dependencies.py      # 依存性注入
│   │
│   ├── models/              # データモデル（SQLAlchemy）
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user.py
│   │   └── product.py
│   │
│   ├── schemas/             # Pydanticスキーマ
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── product.py
│   │
│   ├── services/            # ビジネスロジック
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   └── email_service.py
│   │
│   ├── routers/             # APIエンドポイント
│   │   ├── __init__.py
│   │   ├── users.py
│   │   └── products.py
│   │
│   ├── utils/               # ユーティリティ
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── validators.py
│   │   └── helpers.py
│   │
│   └── exceptions/          # カスタム例外
│       ├── __init__.py
│       └── custom_exceptions.py
│
├── tests/                   # テストコード
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_services/
│   └── test_routers/
│
├── docs/                    # ドキュメント
│   ├── CODING_GUIDELINES.md
│   ├── API_DESIGN.md
│   ├── SECURITY.md
│   ├── PERFORMANCE.md
│   └── TESTING.md
│
├── scripts/                 # スクリプト
├── requirements/            # 依存関係
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

### 9.2 __init__.py の活用
```python
# app/services/__init__.py
from .user_service import UserService
from .email_service import EmailService

__all__ = ['UserService', 'EmailService']

# app/models/__init__.py
from .user import User
from .product import Product

__all__ = ['User', 'Product']
```

## 10. 開発ツール設定

### 10.1 pyproject.toml
```toml
[tool.black]
line-length = 88
target-version = ['py39']
include = '\.pyi?$'
extend-exclude = '''
/(
  migrations
| venv
)/
'''

[tool.isort]
profile = "black"
multi_line_output = 3
line_length = 88
known_first_party = ["app"]

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
no_implicit_optional = true
check_untyped_defs = true

[[tool.mypy.overrides]]
module = ["sqlalchemy.*", "alembic.*"]
ignore_missing_imports = true

[tool.flake8]
max-line-length = 88
extend-ignore = ["E203", "W503"]
exclude = [
    ".git",
    "__pycache__",
    "venv",
    "migrations"
]
```

### 10.2 pre-commit設定
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
```

## 11. バージョン管理

### 11.1 コミットメッセージ
```
# 形式: <type>: <description>

feat: ユーザー作成APIを追加
fix: ユーザー検索時のSQLエラーを修正
docs: APIドキュメントを更新
style: コードフォーマットを統一
refactor: UserServiceのメソッド名を変更
test: ユーザー削除のテストケースを追加
chore: 依存関係を更新
```

### 11.2 .gitignore
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Project specific
.env
*.log
uploads/
```