# SECURITY.md

## 1. セキュリティ基本方針

### 1.1 セキュリティ原則
- **最小権限の原則**: 必要最小限のアクセス権限のみを付与
- **多層防御**: 複数のセキュリティ対策を組み合わせる
- **入力検証**: 全ての外部入力を検証・サニタイズ
- **機密情報保護**: パスワード、APIキー等の適切な管理
- **ログ記録**: セキュリティイベントの適切な記録

### 1.2 社内ツール特有の考慮事項
- 内部ネットワークでも外部脅威を想定
- 従業員の権限管理とアクセス制御
- 機密データの適切な取り扱い
- 監査ログの保持

## 2. 認証・認可

### 2.1 認証実装
```python
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, status

# パスワードハッシュ化
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = 30
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """パスワード検証"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """パスワードハッシュ化"""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: dict) -> str:
        """JWTトークン作成"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> dict:
        """トークン検証"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username: str = payload.get("sub")
            if username is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials"
                )
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
```

### 2.2 認証ミドルウェア
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """現在のユーザーを取得"""
    token = credentials.credentials
    
    try:
        payload = auth_service.verify_token(token)
        username = payload.get("sub")
        user = get_user_by_username(username)
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        return user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

# 使用例
@app.get("/protected")
async def protected_endpoint(current_user: User = Depends(get_current_user)):
    return {"message": f"Hello {current_user.username}"}
```

### 2.3 ロールベースアクセス制御（RBAC）
```python
from enum import Enum
from functools import wraps

class Role(Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"

class Permission(Enum):
    READ_USERS = "read_users"
    WRITE_USERS = "write_users"
    DELETE_USERS = "delete_users"
    READ_REPORTS = "read_reports"
    WRITE_REPORTS = "write_reports"

# ロール-権限マッピング
ROLE_PERMISSIONS = {
    Role.ADMIN: [Permission.READ_USERS, Permission.WRITE_USERS, Permission.DELETE_USERS, 
                Permission.READ_REPORTS, Permission.WRITE_REPORTS],
    Role.MANAGER: [Permission.READ_USERS, Permission.WRITE_USERS, Permission.READ_REPORTS, 
                  Permission.WRITE_REPORTS],
    Role.USER: [Permission.READ_REPORTS]
}

def require_permission(permission: Permission):
    """権限チェックデコレーター"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            user_permissions = ROLE_PERMISSIONS.get(current_user.role, [])
            if permission not in user_permissions:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# 使用例
@app.delete("/users/{user_id}")
@require_permission(Permission.DELETE_USERS)
async def delete_user(user_id: int, current_user: User = Depends(get_current_user)):
    # ユーザー削除処理
    pass
```

## 3. 入力検証・サニタイゼーション

### 3.1 Pydanticバリデーション
```python
from pydantic import BaseModel, validator, EmailStr
from typing import Optional
import re

class UserCreateSchema(BaseModel):
    username: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    
    @validator('username')
    def validate_username(cls, v):
        """ユーザー名バリデーション"""
        if len(v) < 3 or len(v) > 50:
            raise ValueError('Username must be between 3 and 50 characters')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, hyphens, and underscores')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        """パスワードバリデーション"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('phone')
    def validate_phone(cls, v):
        """電話番号バリデーション"""
        if v is not None:
            phone_pattern = r'^\+?[1-9]\d{1,14}$'
            if not re.match(phone_pattern, v):
                raise ValueError('Invalid phone number format')
        return v
```

### 3.2 SQLインジェクション対策
```python
from sqlalchemy import text
from sqlalchemy.orm import Session

class UserRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_users_by_criteria(self, name_filter: str, status: str) -> List[User]:
        """安全なクエリ実行（パラメータ化クエリ）"""
        # 悪い例: SQLインジェクション脆弱性あり
        # query = f"SELECT * FROM users WHERE name LIKE '%{name_filter}%' AND status = '{status}'"
        
        # 良い例: パラメータ化クエリ
        query = text("""
            SELECT * FROM users 
            WHERE name LIKE :name_pattern 
            AND status = :status
        """)
        
        result = self.db.execute(
            query, 
            {
                "name_pattern": f"%{name_filter}%",
                "status": status
            }
        )
        return result.fetchall()
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """ORMを使用した安全なクエリ"""
        return self.db.query(User).filter(User.id == user_id).first()
```

### 3.3 XSS対策
```python
import html
from markupsafe import escape

def sanitize_html_input(content: str) -> str:
    """HTML入力のサニタイズ"""
    # HTMLエスケープ
    sanitized = html.escape(content)
    return sanitized

def validate_and_sanitize_input(data: dict) -> dict:
    """入力データの検証とサニタイズ"""
    sanitized_data = {}
    
    for key, value in data.items():
        if isinstance(value, str):
            # HTMLタグの除去
            sanitized_value = escape(value)
            # 改行コードの正規化
            sanitized_value = sanitized_value.replace('\r\n', '\n').replace('\r', '\n')
            sanitized_data[key] = sanitized_value
        else:
            sanitized_data[key] = value
    
    return sanitized_data

# FastAPIでの使用例
@app.post("/comments")
async def create_comment(comment: CommentCreate):
    # 入力をサニタイズ
    sanitized_content = sanitize_html_input(comment.content)
    comment.content = sanitized_content
    
    # データベースに保存
    return create_comment_in_db(comment)
```

## 4. 機密情報管理

### 4.1 環境変数とシークレット管理
```python
from pydantic import BaseSettings, SecretStr
from typing import Optional

class Settings(BaseSettings):
    """セキュアな設定管理"""
    
    # データベース接続情報
    database_url: SecretStr
    
    # JWT設定
    secret_key: SecretStr
    algorithm: str = "HS256"
    
    # 外部API設定
    external_api_key: SecretStr
    
    # セキュリティ設定
    cors_origins: list = ["http://localhost:3000"]
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
    
    def get_database_url(self) -> str:
        """データベースURL取得（セキュア）"""
        return self.database_url.get_secret_value()
    
    def get_secret_key(self) -> str:
        """シークレットキー取得（セキュア）"""
        return self.secret_key.get_secret_value()

settings = Settings()

# .env ファイル例
"""
DATABASE_URL=postgresql://user:password@localhost/dbname
SECRET_KEY=your-super-secret-key-here
EXTERNAL_API_KEY=your-api-key-here
DEBUG=false
"""
```

### 4.2 ログ出力時の機密情報除去
```python
import logging
import re
from typing import Any, Dict

class SecureFormatter(logging.Formatter):
    """機密情報を除去するログフォーマッター"""
    
    SENSITIVE_PATTERNS = [
        (r'password["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', r'password="***"'),
        (r'token["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', r'token="***"'),
        (r'secret["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', r'secret="***"'),
        (r'key["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', r'key="***"'),
        (r'Authorization:\s*Bearer\s+([^\s]+)', r'Authorization: Bearer ***'),
    ]
    
    def format(self, record):
        # 元のメッセージを取得
        original_message = super().format(record)
        
        # 機密情報をマスク
        sanitized_message = original_message
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            sanitized_message = re.sub(pattern, replacement, sanitized_message, flags=re.IGNORECASE)
        
        return sanitized_message

# ロガー設定
def setup_secure_logging():
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(SecureFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def log_user_action(user_id: int, action: str, details: Dict[str, Any]):
    """ユーザーアクションの安全なログ出力"""
    # 機密情報を除去
    safe_details = {k: v for k, v in details.items() if k not in ['password', 'token', 'secret']}
    
    logger.info(f"User {user_id} performed {action}: {safe_details}")
```

## 5. セッション管理

### 5.1 セキュアなセッション設定
```python
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import secrets

app = FastAPI()

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 本番環境では適切なドメインを指定
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

class SessionManager:
    def __init__(self):
        self.sessions = {}  # 本番環境ではRedisなどを使用
        self.session_timeout = 1800  # 30分
    
    def create_session(self, user_id: int) -> str:
        """セッション作成"""
        session_id = secrets.token_urlsafe(32)
        session_data = {
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "last_accessed": datetime.utcnow()
        }
        self.sessions[session_id] = session_data
        return session_id
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """セッション取得"""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        # セッションタイムアウトチェック
        if (datetime.utcnow() - session["last_accessed"]).seconds > self.session_timeout:
            del self.sessions[session_id]
            return None
        
        # 最終アクセス時刻更新
        session["last_accessed"] = datetime.utcnow()
        return session
    
    def invalidate_session(self, session_id: str):
        """セッション無効化"""
        self.sessions.pop(session_id, None)

session_manager = SessionManager()

# クッキー設定でのセキュリティオプション
@app.post("/login")
async def login(response: Response, credentials: LoginCredentials):
    # 認証処理
    user = authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # セッション作成
    session_id = session_manager.create_session(user.id)
    
    # セキュアなクッキー設定
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,      # XSS対策
        secure=True,        # HTTPS必須
        samesite="strict",  # CSRF対策
        max_age=1800        # 30分
    )
    
    return {"message": "Login successful"}
```

## 6. レート制限・DDoS対策

### 6.1 レート制限実装
```python
from fastapi import HTTPException, Request
import time
from collections import defaultdict, deque

class RateLimiter:
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)
    
    def is_allowed(self, client_id: str) -> bool:
        """リクエスト許可判定"""
        now = time.time()
        client_requests = self.requests[client_id]
        
        # 古いリクエストを削除
        while client_requests and client_requests[0] <= now - self.window_seconds:
            client_requests.popleft()
        
        # リクエスト数チェック
        if len(client_requests) >= self.max_requests:
            return False
        
        # 新しいリクエストを記録
        client_requests.append(now)
        return True

# グローバルレート制限
global_rate_limiter = RateLimiter(max_requests=1000, window_seconds=60)

# APIエンドポイント別レート制限
api_rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """レート制限ミドルウェア"""
    client_ip = request.client.host
    
    # グローバルレート制限チェック
    if not global_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later."
        )
    
    # API別レート制限チェック
    if request.url.path.startswith("/api/"):
        if not api_rate_limiter.is_allowed(f"api_{client_ip}"):
            raise HTTPException(
                status_code=429,
                detail="API rate limit exceeded. Please try again later."
            )
    
    response = await call_next(request)
    return response
```

## 7. セキュリティヘッダー

### 7.1 セキュリティヘッダー設定
```python
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """セキュリティヘッダー追加ミドルウェア"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # セキュリティヘッダー設定
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

## 8. 監査ログ

### 8.1 監査ログシステム
```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import json

class AuditEventType(Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    CREATE_USER = "create_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    ACCESS_SENSITIVE_DATA = "access_sensitive_data"
    PERMISSION_CHANGE = "permission_change"

@dataclass
class AuditEvent:
    user_id: int
    event_type: AuditEventType
    resource_type: str
    resource_id: Optional[str]
    ip_address: str
    user_agent: str
    details: dict
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

class AuditLogger:
    def __init__(self, log_file: str = "audit.log"):
        self.log_file = log_file
        self.logger = logging.getLogger("audit")
        
        # 監査ログ専用ハンドラー
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_event(self, event: AuditEvent):
        """監査イベントをログ出力"""
        log_data = {
            "timestamp": event.timestamp.isoformat(),
            "user_id": event.user_id,
            "event_type": event.event_type.value,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "ip_address": event.ip_address,
            "user_agent": event.user_agent,
            "details": event.details
        }
        
        self.logger.info(json.dumps(log_data, ensure_ascii=False))

audit_logger = AuditLogger()

# 使用例
def audit_user_action(func):
    """監査ログデコレーター"""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        # リクエスト前の処理
        start_time = datetime.utcnow()
        
        try:
            result = await func(request, *args, **kwargs)
            
            # 成功時の監査ログ
            current_user = getattr(request.state, 'current_user', None)
            if current_user:
                event = AuditEvent(
                    user_id=current_user.id,
                    event_type=AuditEventType.ACCESS_SENSITIVE_DATA,
                    resource_type="api_endpoint",
                    resource_id=request.url.path,
                    ip_address=request.client.host,
                    user_agent=request.headers.get("user-agent", ""),
                    details={"method": request.method, "status": "success"}
                )
                audit_logger.log_event(event)
            
            return result
            
        except Exception as e:
            # エラー時の監査ログ
            current_user = getattr(request.state, 'current_user', None)
            if current_user:
                event = AuditEvent(
                    user_id=current_user.id,
                    event_type=AuditEventType.ACCESS_SENSITIVE_DATA,
                    resource_type="api_endpoint",
                    resource_id=request.url.path,
                    ip_address=request.client.host,
                    user_agent=request.headers.get("user-agent", ""),
                    details={"method": request.method, "status": "error", "error": str(e)}
                )
                audit_logger.log_event(event)
            raise
    
    return wrapper
```

## 9. 脆弱性対策チェックリスト

### 9.1 定期的なセキュリティチェック
```python
# セキュリティチェック用スクリプト例
import subprocess
import sys

def run_security_checks():
    """セキュリティチェック実行"""
    checks = [
        # 依存関係の脆弱性チェック
        ("safety check", "Dependencies vulnerability check"),
        
        # Banditによるセキュリティチェック
        ("bandit -r app/", "Python security issues check"),
        
        # 静的解析
        ("semgrep --config=auto app/", "Static analysis security check")
    ]
    
    for command, description in checks:
        print(f"Running {description}...")
        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✓ {description} passed")
        except subprocess.CalledProcessError as e:
            print(f"✗ {description} failed:")
            print(e.stdout)
            print(e.stderr)

if __name__ == "__main__":
    run_security_checks()
```

### 9.2 セキュリティ設定検証
```python
def validate_security_config():
    """セキュリティ設定の検証"""
    issues = []
    
    # 環境変数チェック
    required_env_vars = ['SECRET_KEY', 'DATABASE_URL']
    for var in required_env_vars:
        if not os.getenv(var):
            issues.append(f"Missing required environment variable: {var}")
    
    # シークレットキーの強度チェック
    secret_key = os.getenv('SECRET_KEY', '')
    if len(secret_key) < 32:
        issues.append("SECRET_KEY is too short (minimum 32 characters)")
    
    # デバッグモードチェック
    if settings.debug and os.getenv('ENVIRONMENT') == 'production':
        issues.append("Debug mode is enabled in production")
    
    # HTTPS設定チェック
    if not settings.use_https and os.getenv('ENVIRONMENT') == 'production':
        issues.append("HTTPS is not enabled in production")
    
    return issues

# アプリケーション起動時にセキュリティ設定を検証
@app.on_event("startup")
async def startup_event():
    issues = validate_security_config()
    if issues:
        for issue in issues:
            logger.warning(f"Security issue: {issue}")
        
        if os.getenv('ENVIRONMENT') == 'production':
            logger.error("Critical security issues found in production")
            sys.exit(1)
```

## 10. インシデント対応

### 10.1 セキュリティインシデント検知
```python
from dataclasses import dataclass
from typing import List
import smtplib
from email.mime.text import MIMEText

@dataclass
class SecurityIncident:
    incident_type: str
    severity: str  # "low", "medium", "high", "critical"
    description: str
    affected_user: Optional[str]
    source_ip: str
    timestamp: datetime
    additional_data: dict

class IncidentDetector:
    def __init__(self):
        self.failed_login_attempts = defaultdict(int)
        self.suspicious_ips = set()
    
    def detect_brute_force(self, ip_address: str, username: str) -> Optional[SecurityIncident]:
        """ブルートフォース攻撃検知"""
        key = f"{ip_address}:{username}"
        self.failed_login_attempts[key] += 1
        
        if self.failed_login_attempts[key] >= 5:
            return SecurityIncident(
                incident_type="brute_force_attack",
                severity="high",
                description=f"Multiple failed login attempts from {ip_address} for user {username}",
                affected_user=username,
                source_ip=ip_address,
                timestamp=datetime.utcnow(),
                additional_data={"attempts": self.failed_login_attempts[key]}
            )
        return None
    
    def detect_suspicious_activity(self, user_id: int, activity: str, metadata: dict) -> Optional[SecurityIncident]:
        """異常なアクティビティ検知"""
        # 例: 営業時間外のアクセス
        current_hour = datetime.now().hour
        if current_hour < 6 or current_hour > 22:
            return SecurityIncident(
                incident_type="after_hours_access",
                severity="medium",
                description=f"After-hours access detected: {activity}",
                affected_user=str(user_id),
                source_ip=metadata.get("ip_address", "unknown"),
                timestamp=datetime.utcnow(),
                additional_data=metadata
            )
        return None

class IncidentResponder:
    def __init__(self, admin_email: str):
        self.admin_email = admin_email
    
    def handle_incident(self, incident: SecurityIncident):
        """インシデント対応"""
        # ログ記録
        logger.error(f"Security incident detected: {incident}")
        
        # 重要度に応じた対応
        if incident.severity in ["high", "critical"]:
            self.send_alert_email(incident)
            self.block_ip_if_needed(incident)
        
        # 監査ログに記録
        audit_logger.log_event(AuditEvent(
            user_id=0,  # システムイベント
            event_type=AuditEventType.SECURITY_INCIDENT,
            resource_type="security",
            resource_id=incident.incident_type,
            ip_address=incident.source_ip,
            user_agent="system",
            details=incident.__dict__
        ))
    
    def send_alert_email(self, incident: SecurityIncident):
        """アラートメール送信"""
        subject = f"Security Alert: {incident.incident_type}"
        body = f"""
Security incident detected:

Type: {incident.incident_type}
Severity: {incident.severity}
Description: {incident.description}
Source IP: {incident.source_ip}
Timestamp: {incident.timestamp}
Additional Data: {incident.additional_data}
"""
        
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = "security@company.com"
        msg['To'] = self.admin_email
        
        # メール送信実装（実際の設定に合わせて調整）
        # smtp_server.send_message(msg)
        logger.info(f"Alert email sent for incident: {incident.incident_type}")

detector = IncidentDetector()
responder = IncidentResponder("admin@company.com")
```

## 11. セキュリティテスト

### 11.1 セキュリティテスト例
```python
import pytest
from fastapi.testclient import TestClient

def test_sql_injection_protection():
    """SQLインジェクション対策テスト"""
    client = TestClient(app)
    
    # SQLインジェクション試行
    malicious_input = "'; DROP TABLE users; --"
    response = client.get(f"/users?search={malicious_input}")
    
    # 正常に処理され、エラーが発生しないことを確認
    assert response.status_code != 500
    
    # データベースが正常であることを確認
    response = client.get("/users")
    assert response.status_code == 200

def test_xss_protection():
    """XSS対策テスト"""
    client = TestClient(app)
    
    # XSSペイロード
    xss_payload = "<script>alert('XSS')</script>"
    
    response = client.post("/comments", json={
        "content": xss_payload
    })
    
    # レスポンスでスクリプトがエスケープされていることを確認
    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text

def test_authentication_required():
    """認証必須エンドポイントのテスト"""
    client = TestClient(app)
    
    # 認証なしでアクセス
    response = client.get("/protected-endpoint")
    assert response.status_code == 401
    
    # 不正なトークンでアクセス
    headers = {"Authorization": "Bearer invalid-token"}
    response = client.get("/protected-endpoint", headers=headers)
    assert response.status_code == 401

def test_rate_limiting():
    """レート制限テスト"""
    client = TestClient(app)
    
    # 大量のリクエストを送信
    for i in range(150):  # 制限を超える数
        response = client.get("/api/test")
        if response.status_code == 429:
            break
    else:
        pytest.fail("Rate limiting not working")
```